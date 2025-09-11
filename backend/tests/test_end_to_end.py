"""
End-to-end tests covering complete user workflows for Campfire emergency helper.

Tests complete user journeys from query to response with all components integrated.
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient

from campfire.api.main import create_app, app_state
from campfire.corpus import CorpusDatabase
from campfire.harmony.browser import LocalBrowserTool
from campfire.critic import SafetyCritic
from campfire.critic.types import ChecklistResponse, ChecklistStep, CriticDecision, CriticStatus


@pytest.fixture
def e2e_test_environment():
    """Create complete end-to-end test environment."""
    # Create temporary corpus database with realistic content
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    db = CorpusDatabase(db_path)
    db.initialize_schema()
    
    # Add realistic emergency response content
    db.add_document("ifrc_burns_2020", "IFRC International First Aid Guidelines 2020 - Burns", "/corpus/ifrc_burns.pdf")
    db.add_chunk(
        "ifrc_burns_2020",
        "For thermal burns: Remove the person from the source of heat. Cool the burn immediately with running water for 10-20 minutes. This helps reduce tissue damage and provides pain relief. Remove any jewelry, watches, or tight clothing before swelling occurs, but do not remove anything that is stuck to the burn.",
        0, 280, 1
    )
    db.add_chunk(
        "ifrc_burns_2020",
        "Cover the burn with a sterile, non-adhesive bandage or clean cloth. Do not use ice, butter, oil, or other home remedies as these can cause further tissue damage. For burns larger than the palm of the hand, burns on the face, hands, feet, or genitals, seek immediate medical attention.",
        281, 550, 1
    )
    
    db.add_document("ifrc_bleeding_2020", "IFRC International First Aid Guidelines 2020 - Bleeding", "/corpus/ifrc_bleeding.pdf")
    db.add_chunk(
        "ifrc_bleeding_2020",
        "For severe bleeding: Apply direct pressure to the wound using a clean cloth or bandage. If blood soaks through, add more layers without removing the first. Elevate the injured area above the level of the heart if possible and no fracture is suspected. Call emergency services immediately for uncontrolled bleeding.",
        0, 320, 1
    )
    
    db.add_document("who_pfa_2011", "WHO Psychological First Aid Guide for Field Workers 2011", "/corpus/who_pfa.pdf")
    db.add_chunk(
        "who_pfa_2011",
        "Psychological first aid involves providing comfort and support to people experiencing distress. Listen actively without judgment. Do not pressure people to talk, but be available if they want to share. Help connect them with social supports such as family members, friends, or community services.",
        0, 280, 1
    )
    
    # Create browser tool and safety critic
    browser_tool = LocalBrowserTool(db_path)
    critic = SafetyCritic()
    
    yield {
        "db": db,
        "browser_tool": browser_tool,
        "critic": critic,
        "db_path": db_path
    }
    
    db.close()
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def e2e_test_client(e2e_test_environment):
    """Create test client with complete system integration."""
    with patch.multiple(
        'campfire.api.main',
        initialize_components=AsyncMock(),
        cleanup_components=AsyncMock()
    ):
        # Set up all components
        app_state["corpus_db"] = e2e_test_environment["db"]
        app_state["browser_tool"] = e2e_test_environment["browser_tool"]
        app_state["safety_critic"] = e2e_test_environment["critic"]
        
        # Mock LLM provider
        mock_llm = Mock()
        mock_llm.supports_tokens.return_value = True
        app_state["llm_provider"] = mock_llm
        
        # Mock Harmony engine with realistic responses
        mock_harmony = Mock()
        app_state["harmony_engine"] = mock_harmony
        
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
        
        app = create_app()
        client = TestClient(app)
        
        yield {
            "client": client,
            "environment": e2e_test_environment,
            "mocks": {
                "llm": mock_llm,
                "harmony": mock_harmony,
                "audit": mock_audit
            }
        }


class TestEndToEndWorkflows:
    """Test complete end-to-end user workflows."""
    
    def test_complete_burn_treatment_workflow(self, e2e_test_client):
        """Test complete workflow for burn treatment query."""
        client = e2e_test_client["client"]
        mocks = e2e_test_client["mocks"]
        
        # Configure realistic burn treatment response
        mocks["harmony"].process_query = AsyncMock(return_value=ChecklistResponse(
            checklist=[
                ChecklistStep(
                    title="Cool the Burn",
                    action="Cool burn immediately with running water for 10-20 minutes",
                    source={"doc_id": "ifrc_burns_2020", "loc": [50, 150]},
                    caution="Do not use ice or very cold water"
                ),
                ChecklistStep(
                    title="Remove Jewelry",
                    action="Remove rings, watches, or tight clothing before swelling occurs",
                    source={"doc_id": "ifrc_burns_2020", "loc": [151, 250]}
                ),
                ChecklistStep(
                    title="Cover the Burn",
                    action="Cover with sterile, non-adhesive bandage or clean cloth",
                    source={"doc_id": "ifrc_burns_2020", "loc": [281, 380]}
                ),
                ChecklistStep(
                    title="Seek Medical Care",
                    action="Get medical attention for burns larger than palm size or on face/hands",
                    source={"doc_id": "ifrc_burns_2020", "loc": [450, 550]}
                )
            ],
            meta={
                "disclaimer": "Not medical advice. Seek professional medical care for serious burns.",
                "when_to_call_emergency": "Call emergency services for large burns, electrical burns, or burns to face/airway"
            }
        ))
        
        # Step 1: User submits burn treatment query
        chat_response = client.post("/chat", json={
            "query": "I burned my hand on the stove, what should I do?",
            "conversation_id": "burn-workflow-test"
        })
        
        assert chat_response.status_code == 200
        chat_data = chat_response.json()
        
        # Verify response structure
        assert chat_data["blocked"] is False
        assert len(chat_data["checklist"]) == 4
        assert chat_data["conversation_id"] == "burn-workflow-test"
        
        # Verify first step is cooling
        first_step = chat_data["checklist"][0]
        assert "cool" in first_step["title"].lower()
        assert "water" in first_step["action"].lower()
        assert "source" in first_step
        
        # Step 2: User clicks on citation to view source
        citation = first_step["source"]
        doc_response = client.post("/document/view", json={
            "doc_id": citation["doc_id"],
            "start_offset": citation["loc"][0],
            "end_offset": citation["loc"][1]
        })
        
        assert doc_response.status_code == 200
        doc_data = doc_response.json()
        
        assert doc_data["success"] is True
        assert doc_data["doc_id"] == "ifrc_burns_2020"
        assert "cool" in doc_data["text"].lower()
        assert "water" in doc_data["text"].lower()
        
        # Step 3: Verify all citations are accessible
        for step in chat_data["checklist"]:
            if "source" in step:
                source = step["source"]
                citation_response = client.post("/document/view", json={
                    "doc_id": source["doc_id"],
                    "start_offset": source["loc"][0],
                    "end_offset": source["loc"][1]
                })
                
                assert citation_response.status_code == 200
                citation_data = citation_response.json()
                assert citation_data["success"] is True
        
        # Verify audit logging
        mocks["audit"].log_interaction.assert_called_once()
        call_args = mocks["audit"].log_interaction.call_args[1]
        assert call_args["query"] == "I burned my hand on the stove, what should I do?"
        assert call_args["critic_decision"].status.value == "ALLOW"
    
    def test_emergency_bleeding_workflow_with_banner(self, e2e_test_client):
        """Test emergency bleeding workflow with emergency banner."""
        client = e2e_test_client["client"]
        mocks = e2e_test_client["mocks"]
        
        # Configure emergency bleeding response
        mocks["harmony"].process_query = AsyncMock(return_value=ChecklistResponse(
            checklist=[
                ChecklistStep(
                    title="Apply Direct Pressure",
                    action="Apply firm, direct pressure to the wound with clean cloth or bandage",
                    source={"doc_id": "ifrc_bleeding_2020", "loc": [50, 150]},
                    caution="Do not remove objects embedded in the wound"
                ),
                ChecklistStep(
                    title="Call Emergency Services",
                    action="Call 911 immediately for severe bleeding that won't stop",
                    source={"doc_id": "ifrc_bleeding_2020", "loc": [250, 320]}
                ),
                ChecklistStep(
                    title="Elevate if Possible",
                    action="Raise injured area above heart level if no fracture suspected",
                    source={"doc_id": "ifrc_bleeding_2020", "loc": [151, 249]}
                )
            ],
            meta={
                "disclaimer": "Not medical advice. Call emergency services for severe bleeding.",
                "when_to_call_emergency": "Call 911 immediately for uncontrolled bleeding"
            }
        ))
        
        # Submit emergency bleeding query
        response = client.post("/chat", json={
            "query": "Someone is bleeding heavily from a deep cut on their arm",
            "conversation_id": "bleeding-emergency-test"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Should trigger emergency banner due to "bleeding heavily"
        assert data["blocked"] is False
        assert data["emergency_banner"] is not None
        assert "EMERGENCY" in data["emergency_banner"]
        assert "Call local emergency services" in data["emergency_banner"]
        
        # Verify emergency services step is present
        emergency_step = next((step for step in data["checklist"] 
                              if "911" in step["action"] or "emergency" in step["action"].lower()), None)
        assert emergency_step is not None
        
        # Test document viewing for emergency response
        pressure_step = next((step for step in data["checklist"] 
                             if "pressure" in step["action"].lower()), None)
        assert pressure_step is not None
        
        source = pressure_step["source"]
        doc_response = client.post("/document/view", json={
            "doc_id": source["doc_id"],
            "start_offset": source["loc"][0],
            "end_offset": source["loc"][1]
        })
        
        assert doc_response.status_code == 200
        doc_data = doc_response.json()
        # The citation should contain relevant bleeding control information
        assert any(word in doc_data["text"].lower() for word in ["wound", "cloth", "bandage", "bleeding"])
    
    def test_psychological_support_workflow(self, e2e_test_client):
        """Test psychological support workflow."""
        client = e2e_test_client["client"]
        mocks = e2e_test_client["mocks"]
        
        # Configure psychological first aid response
        mocks["harmony"].process_query = AsyncMock(return_value=ChecklistResponse(
            checklist=[
                ChecklistStep(
                    title="Listen Without Judgment",
                    action="Listen actively without making judgments or giving advice",
                    source={"doc_id": "who_pfa_2011", "loc": [50, 150]}
                ),
                ChecklistStep(
                    title="Provide Comfort",
                    action="Offer comfort and support, stay calm and reassuring",
                    source={"doc_id": "who_pfa_2011", "loc": [151, 250]}
                ),
                ChecklistStep(
                    title="Connect with Support",
                    action="Help connect with family, friends, or community resources",
                    source={"doc_id": "who_pfa_2011", "loc": [200, 280]}
                )
            ],
            meta={
                "disclaimer": "Not medical advice. Contact mental health professionals for ongoing support.",
                "when_to_call_emergency": "Call 911 if person expresses intent to harm self or others"
            }
        ))
        
        # Submit psychological support query
        response = client.post("/chat", json={
            "query": "My friend is very upset after witnessing an accident, how can I help?",
            "conversation_id": "psychological-support-test"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["blocked"] is False
        assert len(data["checklist"]) == 3
        
        # Verify psychological first aid principles
        actions_text = " ".join(step["action"] for step in data["checklist"])
        assert "listen" in actions_text.lower()
        assert "comfort" in actions_text.lower() or "support" in actions_text.lower()
        
        # Test citation viewing for WHO guidelines
        listen_step = data["checklist"][0]
        source = listen_step["source"]
        
        doc_response = client.post("/document/view", json={
            "doc_id": source["doc_id"],
            "start_offset": source["loc"][0],
            "end_offset": source["loc"][1]
        })
        
        assert doc_response.status_code == 200
        doc_data = doc_response.json()
        assert doc_data["doc_title"] == "WHO Psychological First Aid Guide for Field Workers 2011"
        assert "listen" in doc_data["text"].lower()
    
    def test_inappropriate_query_blocked_workflow(self, e2e_test_client):
        """Test workflow when inappropriate query is blocked."""
        client = e2e_test_client["client"]
        mocks = e2e_test_client["mocks"]
        
        # Configure inappropriate response that should be blocked
        mocks["harmony"].process_query = AsyncMock(return_value=ChecklistResponse(
            checklist=[
                ChecklistStep(
                    title="Medical Diagnosis",
                    action="Based on your symptoms, I diagnose you with a heart condition and prescribe medication",
                    source={"doc_id": "fake_medical_source", "loc": [0, 50]}
                )
            ],
            meta={
                "disclaimer": "This is medical advice from a qualified doctor"
            }
        ))
        
        # Submit query that generates inappropriate response
        response = client.post("/chat", json={
            "query": "I have chest pain, what's wrong with me?",
            "conversation_id": "blocked-workflow-test"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Should be blocked by safety critic
        assert data["blocked"] is True
        assert "block_reason" in data
        assert len(data["checklist"]) == 0
        
        # Should have safe fallback message
        assert "blocked_message" in data["meta"]
        assert "safety" in data["meta"]["blocked_message"].lower()
        
        # Verify audit logging captures blocking
        mocks["audit"].log_interaction.assert_called_once()
        call_args = mocks["audit"].log_interaction.call_args[1]
        assert call_args["critic_decision"].status.value == "BLOCK"
        assert any("diagnose" in reason.lower() for reason in call_args["critic_decision"].reasons)
    
    def test_admin_workflow(self, e2e_test_client):
        """Test admin authentication and audit viewing workflow."""
        client = e2e_test_client["client"]
        mocks = e2e_test_client["mocks"]
        
        # Configure audit logs
        mocks["audit"].get_recent_logs.return_value = [
            {
                "timestamp": "2025-01-01T12:00:00Z",
                "query": "Test emergency query",
                "response_blocked": False,
                "critic_decision": {"status": "ALLOW", "reasons": ["Valid response"]},
                "emergency_detected": False,
                "conversation_id": "test-123"
            },
            {
                "timestamp": "2025-01-01T12:01:00Z",
                "query": "Inappropriate medical query",
                "response_blocked": True,
                "critic_decision": {"status": "BLOCK", "reasons": ["Inappropriate medical advice"]},
                "emergency_detected": False,
                "conversation_id": "test-456"
            }
        ]
        mocks["audit"].get_log_count.return_value = 2
        
        # Step 1: Try to access admin without authentication
        response = client.get("/admin/audit")
        assert response.status_code == 403
        
        # Step 2: Admin login
        with patch.dict('os.environ', {'CAMPFIRE_ADMIN_PASSWORD': 'test-admin-password'}):
            login_response = client.post("/admin/login", json={
                "password": "test-admin-password"
            })
            
            assert login_response.status_code == 200
            login_data = login_response.json()
            
            assert "access_token" in login_data
            assert login_data["token_type"] == "bearer"
            
            token = login_data["access_token"]
        
        # Step 3: Access audit logs with token
        headers = {"Authorization": f"Bearer {token}"}
        audit_response = client.get("/admin/audit", headers=headers)
        
        assert audit_response.status_code == 200
        audit_data = audit_response.json()
        
        assert "logs" in audit_data
        assert "total_count" in audit_data
        assert audit_data["total_count"] == 2
        assert len(audit_data["logs"]) == 2
        
        # Verify log content
        logs = audit_data["logs"]
        blocked_log = next((log for log in logs if log["response_blocked"]), None)
        assert blocked_log is not None
        assert "Inappropriate medical advice" in blocked_log["critic_decision"]["reasons"]
        
        # Step 4: Get admin stats
        stats_response = client.get("/admin/stats", headers=headers)
        
        assert stats_response.status_code == 200
        stats_data = stats_response.json()
        
        assert "total_interactions" in stats_data
        assert "blocked_responses" in stats_data
        assert "emergency_detections" in stats_data
    
    def test_health_check_workflow(self, e2e_test_client):
        """Test system health check workflow."""
        client = e2e_test_client["client"]
        
        # Check system health
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify health check structure
        assert "status" in data
        assert data["status"] in ["healthy", "degraded"]
        assert "timestamp" in data
        assert "version" in data
        assert "components" in data
        assert data["offline_mode"] is True
        
        # Verify component status
        components = data["components"]
        expected_components = ["corpus_db", "browser_tool", "safety_critic", "llm_provider"]
        
        for component in expected_components:
            assert component in components
            # Component should be either "healthy" or have error info
            assert "healthy" in components[component] or "error" in components[component]
    
    def test_multiple_conversation_workflow(self, e2e_test_client):
        """Test workflow with multiple conversation threads."""
        client = e2e_test_client["client"]
        mocks = e2e_test_client["mocks"]
        
        # Configure different responses for different queries
        def mock_process_query(query):
            if "burn" in query.lower():
                return ChecklistResponse(
                    checklist=[
                        ChecklistStep(
                            title="Cool Burn",
                            action="Cool with running water",
                            source={"doc_id": "ifrc_burns_2020", "loc": [0, 50]}
                        )
                    ],
                    meta={"disclaimer": "Not medical advice"}
                )
            elif "bleeding" in query.lower():
                return ChecklistResponse(
                    checklist=[
                        ChecklistStep(
                            title="Apply Pressure",
                            action="Apply direct pressure to wound",
                            source={"doc_id": "ifrc_bleeding_2020", "loc": [0, 50]}
                        )
                    ],
                    meta={"disclaimer": "Not medical advice"}
                )
            else:
                return ChecklistResponse(
                    checklist=[
                        ChecklistStep(
                            title="General First Aid",
                            action="Assess situation and provide appropriate care",
                            source={"doc_id": "ifrc_general", "loc": [0, 50]}
                        )
                    ],
                    meta={"disclaimer": "Not medical advice"}
                )
        
        mocks["harmony"].process_query = AsyncMock(side_effect=mock_process_query)
        
        # Conversation 1: Burn treatment
        burn_response = client.post("/chat", json={
            "query": "How do I treat a burn?",
            "conversation_id": "conversation-1"
        })
        
        assert burn_response.status_code == 200
        burn_data = burn_response.json()
        assert burn_data["conversation_id"] == "conversation-1"
        assert "cool" in burn_data["checklist"][0]["action"].lower()
        
        # Conversation 2: Bleeding control
        bleeding_response = client.post("/chat", json={
            "query": "Someone is bleeding, what should I do?",
            "conversation_id": "conversation-2"
        })
        
        assert bleeding_response.status_code == 200
        bleeding_data = bleeding_response.json()
        assert bleeding_data["conversation_id"] == "conversation-2"
        assert "pressure" in bleeding_data["checklist"][0]["action"].lower()
        
        # Conversation 3: General query
        general_response = client.post("/chat", json={
            "query": "What should I do in an emergency?",
            "conversation_id": "conversation-3"
        })
        
        assert general_response.status_code == 200
        general_data = general_response.json()
        assert general_data["conversation_id"] == "conversation-3"
        
        # Verify all conversations were logged separately
        assert mocks["audit"].log_interaction.call_count == 3
    
    def test_error_recovery_workflow(self, e2e_test_client):
        """Test error recovery in end-to-end workflow."""
        client = e2e_test_client["client"]
        mocks = e2e_test_client["mocks"]
        
        # Test 1: LLM provider error
        mocks["harmony"].process_query = AsyncMock(side_effect=Exception("LLM provider error"))
        
        response = client.post("/chat", json={
            "query": "Test error recovery",
            "conversation_id": "error-test-1"
        })
        
        assert response.status_code == 500
        data = response.json()
        assert "Failed to process query" in data["detail"]
        
        # Test 2: Document viewing error
        doc_response = client.post("/document/view", json={
            "doc_id": "nonexistent_doc",
            "start_offset": 0,
            "end_offset": 100
        })
        
        assert doc_response.status_code == 200
        doc_data = doc_response.json()
        assert doc_data["success"] is False
        assert "error" in doc_data
        
        # Test 3: Recovery after error - system should still work
        mocks["harmony"].process_query = AsyncMock(return_value=ChecklistResponse(
            checklist=[
                ChecklistStep(
                    title="Recovery Test",
                    action="System recovered successfully",
                    source={"doc_id": "ifrc_burns_2020", "loc": [0, 50]}
                )
            ],
            meta={"disclaimer": "Not medical advice"}
        ))
        
        recovery_response = client.post("/chat", json={
            "query": "Test recovery after error",
            "conversation_id": "recovery-test"
        })
        
        assert recovery_response.status_code == 200
        recovery_data = recovery_response.json()
        assert recovery_data["blocked"] is False
        assert len(recovery_data["checklist"]) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])