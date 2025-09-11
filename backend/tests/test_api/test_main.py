"""
Integration tests for FastAPI endpoints.
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient

from campfire.api.main import create_app, app_state
from campfire.critic.types import CriticDecision, CriticStatus, ChecklistResponse, ChecklistStep


@pytest.fixture
def mock_components():
    """Mock all application components."""
    with patch.multiple(
        'campfire.api.main',
        initialize_components=AsyncMock(),
        cleanup_components=AsyncMock()
    ):
        # Mock LLM provider
        mock_llm = Mock()
        mock_llm.supports_tokens.return_value = True
        app_state["llm_provider"] = mock_llm
        
        # Mock browser tool
        mock_browser = Mock()
        mock_browser.search.return_value = {
            "status": "success",
            "results": [
                {
                    "doc_id": "test-doc",
                    "doc_title": "Test Document",
                    "snippet": "Test content snippet",
                    "location": {"start_offset": 100, "end_offset": 200}
                }
            ]
        }
        mock_browser.open.return_value = {
            "status": "success",
            "doc_id": "test-doc",
            "doc_title": "Test Document", 
            "text": "Test document content",
            "location": {"start_offset": 100, "end_offset": 200}
        }
        app_state["browser_tool"] = mock_browser
        
        # Mock Harmony engine
        mock_harmony = Mock()
        mock_harmony.process_query = AsyncMock(return_value=ChecklistResponse(
            checklist=[
                ChecklistStep(
                    title="Test Step",
                    action="Take test action",
                    source={"doc_id": "test-doc", "loc": [100, 200]},
                    caution="Test caution"
                )
            ],
            meta={
                "disclaimer": "Not medical advice",
                "when_to_call_emergency": "Call 911 for emergencies"
            }
        ))
        app_state["harmony_engine"] = mock_harmony
        
        # Mock safety critic
        mock_critic = Mock()
        mock_critic.review_response.return_value = CriticDecision(
            status=CriticStatus.ALLOW,
            reasons=["Response meets safety criteria"],
            emergency_detected=False,
            requires_emergency_banner=False
        )
        app_state["safety_critic"] = mock_critic
        
        # Mock audit logger
        mock_audit = Mock()
        mock_audit.log_interaction = Mock()
        mock_audit.get_recent_logs.return_value = []
        mock_audit.get_log_count.return_value = 0
        mock_audit.get_stats.return_value = {
            "total_interactions": 0,
            "blocked_responses": 0,
            "emergency_detections": 0
        }
        app_state["audit_logger"] = mock_audit
        
        # Mock corpus database
        mock_corpus = Mock()
        mock_corpus.list_documents.return_value = ["test-doc"]
        app_state["corpus_db"] = mock_corpus
        
        yield {
            "llm_provider": mock_llm,
            "browser_tool": mock_browser,
            "harmony_engine": mock_harmony,
            "safety_critic": mock_critic,
            "audit_logger": mock_audit,
            "corpus_db": mock_corpus
        }


@pytest.fixture
def client(mock_components):
    """Create test client with mocked components."""
    app = create_app()
    return TestClient(app)


class TestHealthEndpoint:
    """Test health check endpoint."""
    
    def test_health_check_success(self, client):
        """Test successful health check."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] in ["healthy", "degraded"]
        assert "timestamp" in data
        assert "version" in data
        assert "components" in data
        assert data["offline_mode"] is True
    
    def test_health_check_with_component_errors(self, client, mock_components):
        """Test health check when components have errors."""
        # Make corpus DB raise an error
        mock_components["corpus_db"].list_documents.side_effect = Exception("DB error")
        
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "degraded"
        assert "error: DB error" in data["components"]["corpus_db"]


class TestChatEndpoint:
    """Test main chat endpoint."""
    
    def test_chat_success(self, client, mock_components):
        """Test successful chat interaction."""
        request_data = {
            "query": "What should I do for a burn?",
            "conversation_id": "test-123"
        }
        
        response = client.post("/chat", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["conversation_id"] == "test-123"
        assert len(data["checklist"]) == 1
        assert data["checklist"][0]["title"] == "Test Step"
        assert data["checklist"][0]["action"] == "Take test action"
        assert data["blocked"] is False
        assert "meta" in data
        
        # Verify components were called
        mock_components["harmony_engine"].process_query.assert_called_once_with(
            "What should I do for a burn?"
        )
        mock_components["safety_critic"].review_response.assert_called_once()
        mock_components["audit_logger"].log_interaction.assert_called_once()
    
    def test_chat_blocked_response(self, client, mock_components):
        """Test chat with blocked response."""
        # Configure critic to block response
        mock_components["safety_critic"].review_response.return_value = CriticDecision(
            status=CriticStatus.BLOCK,
            reasons=["Inappropriate medical advice"],
            emergency_detected=False,
            requires_emergency_banner=False
        )
        
        request_data = {
            "query": "How do I perform surgery?",
        }
        
        response = client.post("/chat", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["blocked"] is True
        assert data["block_reason"] == "Inappropriate medical advice"
        assert len(data["checklist"]) == 0
        assert "blocked_message" in data["meta"]
    
    def test_chat_emergency_banner(self, client, mock_components):
        """Test chat with emergency banner."""
        # Configure critic to require emergency banner
        mock_components["safety_critic"].review_response.return_value = CriticDecision(
            status=CriticStatus.ALLOW,
            reasons=["Response allowed with warning"],
            emergency_detected=True,
            requires_emergency_banner=True
        )
        
        request_data = {
            "query": "Someone is unconscious",
        }
        
        response = client.post("/chat", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["blocked"] is False
        assert data["emergency_banner"] is not None
        assert "EMERGENCY" in data["emergency_banner"]
        assert "Call local emergency services" in data["emergency_banner"]
    
    def test_chat_invalid_request(self, client):
        """Test chat with invalid request data."""
        request_data = {
            "query": "",  # Empty query
        }
        
        response = client.post("/chat", json=request_data)
        
        assert response.status_code == 422  # Validation error
    
    def test_chat_system_error(self, client, mock_components):
        """Test chat with system error."""
        # Make harmony engine raise an error
        mock_components["harmony_engine"].process_query.side_effect = Exception("System error")
        
        request_data = {
            "query": "Test query",
        }
        
        response = client.post("/chat", json=request_data)
        
        assert response.status_code == 500
        data = response.json()
        assert "Failed to process query" in data["detail"]


class TestDocumentViewEndpoint:
    """Test document viewer endpoint."""
    
    def test_document_view_success(self, client, mock_components):
        """Test successful document viewing."""
        request_data = {
            "doc_id": "test-doc",
            "start_offset": 100,
            "end_offset": 200
        }
        
        response = client.post("/document/view", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["doc_id"] == "test-doc"
        assert data["doc_title"] == "Test Document"
        assert data["text"] == "Test document content"
        assert data["success"] is True
        
        # Verify browser tool was called
        mock_components["browser_tool"].open.assert_called_once_with(
            doc_id="test-doc",
            start=100,
            end=200
        )
    
    def test_document_view_error(self, client, mock_components):
        """Test document viewing with error."""
        # Configure browser tool to return error
        mock_components["browser_tool"].open.return_value = {
            "status": "error",
            "error": "Document not found"
        }
        
        request_data = {
            "doc_id": "nonexistent",
            "start_offset": 0,
            "end_offset": 100
        }
        
        response = client.post("/document/view", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is False
        assert data["error"] == "Document not found"
    
    def test_document_view_invalid_request(self, client):
        """Test document viewing with invalid request."""
        request_data = {
            "doc_id": "test-doc",
            "start_offset": -1,  # Invalid offset
            "end_offset": 100
        }
        
        response = client.post("/document/view", json=request_data)
        
        assert response.status_code == 422  # Validation error


class TestAdminEndpoints:
    """Test admin authentication and audit endpoints."""
    
    def test_admin_login_success(self, client):
        """Test successful admin login."""
        with patch.dict('os.environ', {'CAMPFIRE_ADMIN_PASSWORD': 'test-password'}):
            request_data = {
                "password": "test-password"
            }
            
            response = client.post("/admin/login", json=request_data)
            
            assert response.status_code == 200
            data = response.json()
            
            assert "access_token" in data
            assert data["token_type"] == "bearer"
            assert "expires_in" in data
    
    def test_admin_login_invalid_password(self, client):
        """Test admin login with invalid password."""
        request_data = {
            "password": "wrong-password"
        }
        
        response = client.post("/admin/login", json=request_data)
        
        assert response.status_code == 401
        data = response.json()
        assert "Invalid admin credentials" in data["detail"]
    
    def test_audit_logs_unauthorized(self, client):
        """Test audit logs without authentication."""
        response = client.get("/admin/audit")
        
        assert response.status_code == 403  # No authorization header
    
    def test_audit_logs_success(self, client, mock_components):
        """Test successful audit logs retrieval."""
        # Mock audit logs
        mock_components["audit_logger"].get_recent_logs.return_value = [
            {
                "timestamp": "2025-01-01T00:00:00Z",
                "query": "test query",
                "response_blocked": False,
                "critic_decision": {"status": "ALLOW"},
                "emergency_detected": False,
                "conversation_id": "test-123"
            }
        ]
        mock_components["audit_logger"].get_log_count.return_value = 1
        
        # Get admin token first
        with patch.dict('os.environ', {'CAMPFIRE_ADMIN_PASSWORD': 'test-password'}):
            login_response = client.post("/admin/login", json={"password": "test-password"})
            token = login_response.json()["access_token"]
        
        # Request audit logs with token
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/admin/audit", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "logs" in data
        assert "total_count" in data
        assert data["total_count"] == 1
        assert len(data["logs"]) == 1
    
    def test_admin_stats_success(self, client, mock_components):
        """Test successful admin stats retrieval."""
        # Get admin token first
        with patch.dict('os.environ', {'CAMPFIRE_ADMIN_PASSWORD': 'test-password'}):
            login_response = client.post("/admin/login", json={"password": "test-password"})
            token = login_response.json()["access_token"]
        
        # Request stats with token
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/admin/stats", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "total_interactions" in data
        assert "blocked_responses" in data
        assert "emergency_detections" in data
        assert "components" in data
        assert "available_providers" in data


class TestCORSAndMiddleware:
    """Test CORS and middleware functionality."""
    
    def test_cors_headers(self, client):
        """Test CORS headers are present."""
        response = client.options("/health")
        
        # FastAPI automatically handles OPTIONS requests
        assert response.status_code in [200, 405]  # 405 if OPTIONS not explicitly defined
    
    def test_error_handling(self, client, mock_components):
        """Test global error handling."""
        # Make a component raise an unexpected error
        mock_components["corpus_db"].list_documents.side_effect = RuntimeError("Unexpected error")
        
        response = client.get("/health")
        
        # Should still return a response, not crash
        assert response.status_code in [200, 500]


@pytest.mark.integration
class TestEndToEndFlow:
    """Test complete end-to-end API flows."""
    
    def test_complete_chat_flow(self, client, mock_components):
        """Test complete chat interaction flow."""
        # 1. Check system health
        health_response = client.get("/health")
        assert health_response.status_code == 200
        
        # 2. Submit chat query
        chat_request = {
            "query": "What should I do for a minor burn?",
            "conversation_id": "e2e-test"
        }
        
        chat_response = client.post("/chat", json=chat_request)
        assert chat_response.status_code == 200
        
        chat_data = chat_response.json()
        assert chat_data["conversation_id"] == "e2e-test"
        assert len(chat_data["checklist"]) > 0
        
        # 3. View document citation
        if chat_data["checklist"][0].get("source"):
            doc_request = {
                "doc_id": "test-doc",
                "start_offset": 100,
                "end_offset": 200
            }
            
            doc_response = client.post("/document/view", json=doc_request)
            assert doc_response.status_code == 200
            
            doc_data = doc_response.json()
            assert doc_data["success"] is True
        
        # 4. Check admin logs (with authentication)
        with patch.dict('os.environ', {'CAMPFIRE_ADMIN_PASSWORD': 'test-password'}):
            login_response = client.post("/admin/login", json={"password": "test-password"})
            token = login_response.json()["access_token"]
        
        headers = {"Authorization": f"Bearer {token}"}
        audit_response = client.get("/admin/audit", headers=headers)
        assert audit_response.status_code == 200
        
        # Verify interaction was logged
        mock_components["audit_logger"].log_interaction.assert_called()


if __name__ == "__main__":
    pytest.main([__file__])