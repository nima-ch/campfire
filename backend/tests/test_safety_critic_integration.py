"""
Safety Critic integration tests for blocking inappropriate responses.

Tests the complete safety critic system integration with various scenarios.
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient

from campfire.api.main import create_app, app_state
from campfire.critic import SafetyCritic
from campfire.critic.types import CriticStatus, CriticDecision, ChecklistResponse, ChecklistStep


@pytest.fixture
def safety_test_client():
    """Create test client with safety critic integration."""
    with patch.multiple(
        'campfire.api.main',
        initialize_components=AsyncMock(),
        cleanup_components=AsyncMock()
    ):
        # Mock components
        mock_llm = Mock()
        mock_llm.supports_tokens.return_value = True
        app_state["llm_provider"] = mock_llm
        
        mock_browser = Mock()
        app_state["browser_tool"] = mock_browser
        
        mock_harmony = Mock()
        app_state["harmony_engine"] = mock_harmony
        
        # Use real safety critic for integration testing
        real_critic = SafetyCritic()
        app_state["safety_critic"] = real_critic
        
        mock_audit = Mock()
        mock_audit.log_interaction = Mock()
        app_state["audit_logger"] = mock_audit
        
        mock_corpus = Mock()
        app_state["corpus_db"] = mock_corpus
        
        app = create_app()
        client = TestClient(app)
        
        yield {
            "client": client,
            "critic": real_critic,
            "mocks": {
                "llm": mock_llm,
                "browser": mock_browser,
                "harmony": mock_harmony,
                "audit": mock_audit,
                "corpus": mock_corpus
            }
        }


class TestSafetyCriticIntegration:
    """Test Safety Critic integration with the complete system."""
    
    def test_inappropriate_medical_diagnosis_blocked(self, safety_test_client):
        """Test that inappropriate medical diagnoses are blocked."""
        client = safety_test_client["client"]
        mocks = safety_test_client["mocks"]
        
        # Mock response with inappropriate medical diagnosis
        mocks["harmony"].process_query = AsyncMock(return_value=ChecklistResponse(
            checklist=[
                ChecklistStep(
                    title="Medical Diagnosis",
                    action="Based on your symptoms, I diagnose you with pneumonia and prescribe antibiotics",
                    source={"doc_id": "fake_medical", "loc": [0, 50]}
                ),
                ChecklistStep(
                    title="Treatment Plan",
                    action="Take amoxicillin 500mg three times daily for 10 days",
                    source={"doc_id": "fake_medical", "loc": [51, 100]}
                )
            ],
            meta={
                "disclaimer": "This is medical advice from a qualified physician"
            }
        ))
        
        response = client.post("/chat", json={
            "query": "I have a cough and fever, what's wrong with me?",
            "conversation_id": "diagnosis-test"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Should be blocked by safety critic
        assert data["blocked"] is True
        assert "block_reason" in data
        assert len(data["checklist"]) == 0
        
        # Check that blocking reasons include medical diagnosis issues
        block_reason = data["block_reason"]
        assert "diagnose" in block_reason.lower() or "medical" in block_reason.lower()
        
        # Verify audit logging
        mocks["audit"].log_interaction.assert_called_once()
        call_args = mocks["audit"].log_interaction.call_args[1]
        assert call_args["query"] == "I have a cough and fever, what's wrong with me?"
        assert call_args["critic_decision"].status.value == "BLOCK"
    
    def test_emergency_keywords_trigger_banner(self, safety_test_client):
        """Test that emergency keywords trigger appropriate banners."""
        client = safety_test_client["client"]
        mocks = safety_test_client["mocks"]
        
        # Mock appropriate emergency response
        mocks["harmony"].process_query = AsyncMock(return_value=ChecklistResponse(
            checklist=[
                ChecklistStep(
                    title="Check Responsiveness",
                    action="Tap shoulders and shout to check if person is unconscious",
                    source={"doc_id": "ifrc_cpr", "loc": [0, 50]}
                ),
                ChecklistStep(
                    title="Call Emergency Services",
                    action="Call 911 immediately for unconscious person",
                    source={"doc_id": "ifrc_emergency", "loc": [0, 50]}
                )
            ],
            meta={
                "disclaimer": "Not medical advice. Call emergency services immediately.",
                "when_to_call_emergency": "Call 911 for unconscious person"
            }
        ))
        
        response = client.post("/chat", json={
            "query": "Found someone unconscious, what should I do?",
            "conversation_id": "emergency-test"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Should be allowed but with emergency banner
        assert data["blocked"] is False
        assert data["emergency_banner"] is not None
        assert "EMERGENCY" in data["emergency_banner"]
        assert "Call local emergency services" in data["emergency_banner"]
        
        # Verify audit logging captures emergency detection
        mocks["audit"].log_interaction.assert_called_once()
        call_args = mocks["audit"].log_interaction.call_args[1]
        assert call_args["critic_decision"].emergency_detected is True
    
    def test_missing_citations_blocked(self, safety_test_client):
        """Test that responses without proper citations are blocked."""
        client = safety_test_client["client"]
        mocks = safety_test_client["mocks"]
        
        # Mock response without proper citations
        mocks["harmony"].process_query = AsyncMock(return_value=ChecklistResponse(
            checklist=[
                ChecklistStep(
                    title="Treat Burn",
                    action="Cool the burn with running water",
                    # Missing source citation
                ),
                ChecklistStep(
                    title="Cover Burn",
                    action="Cover with bandage",
                    source="invalid_format"  # Invalid citation format
                )
            ],
            meta={
                "disclaimer": "Not medical advice"
            }
        ))
        
        response = client.post("/chat", json={
            "query": "How do I treat a burn?",
            "conversation_id": "citation-test"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Should be blocked due to missing/invalid citations
        assert data["blocked"] is True
        assert "citation" in data["block_reason"].lower() or "source" in data["block_reason"].lower()
    
    def test_out_of_scope_content_blocked(self, safety_test_client):
        """Test that out-of-scope content is blocked."""
        client = safety_test_client["client"]
        mocks = safety_test_client["mocks"]
        
        # Mock response with blocked medical content
        mocks["harmony"].process_query = AsyncMock(return_value=ChecklistResponse(
            checklist=[
                ChecklistStep(
                    title="Medical Diagnosis",
                    action="I diagnose this condition as a serious illness that requires surgery",
                    source={"doc_id": "medical_guide", "loc": [0, 50]}
                ),
                ChecklistStep(
                    title="Prescription",
                    action="Take this medication to cure the disease",
                    source={"doc_id": "medical_guide", "loc": [51, 100]}
                )
            ],
            meta={
                "disclaimer": "Not medical advice"
            }
        ))
        
        response = client.post("/chat", json={
            "query": "What should I do after a car accident?",
            "conversation_id": "scope-test"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Should be blocked due to inappropriate medical content
        assert data["blocked"] is True
        block_reason = data["block_reason"].lower()
        assert "diagnose" in block_reason or "medical" in block_reason or "inappropriate" in block_reason
    
    def test_multiple_safety_violations(self, safety_test_client):
        """Test response with multiple safety violations."""
        client = safety_test_client["client"]
        mocks = safety_test_client["mocks"]
        
        # Mock response with multiple violations
        mocks["harmony"].process_query = AsyncMock(return_value=ChecklistResponse(
            checklist=[
                ChecklistStep(
                    title="",  # Empty title
                    action="I diagnose you with a heart attack and prescribe medication",  # Diagnosis + prescription
                    # Missing source
                ),
                ChecklistStep(
                    title="Investment Advice",  # Out of scope
                    action="",  # Empty action
                    source="invalid"  # Invalid source format
                )
            ],
            meta={
                # Missing disclaimer
            }
        ))
        
        response = client.post("/chat", json={
            "query": "Having chest pain, what should I do?",
            "conversation_id": "multiple-violations-test"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Should be blocked with multiple reasons
        assert data["blocked"] is True
        
        # Block reason should mention multiple issues
        block_reason = data["block_reason"].lower()
        # Should detect various issues like missing citations, inappropriate content, etc.
        violation_indicators = ["citation", "source", "diagnose", "title", "action", "disclaimer"]
        violations_found = sum(1 for indicator in violation_indicators if indicator in block_reason)
        assert violations_found >= 2  # Should find multiple violations
    
    def test_borderline_content_handling(self, safety_test_client):
        """Test handling of borderline content that might be acceptable."""
        client = safety_test_client["client"]
        mocks = safety_test_client["mocks"]
        
        # Mock borderline response that should be allowed
        mocks["harmony"].process_query = AsyncMock(return_value=ChecklistResponse(
            checklist=[
                ChecklistStep(
                    title="Assess Situation",
                    action="Look for signs of serious injury and determine if emergency services are needed",
                    source={"doc_id": "ifrc_assessment", "loc": [0, 50]}
                ),
                ChecklistStep(
                    title="Provide Basic Care",
                    action="If minor injury, clean wound gently and apply bandage",
                    source={"doc_id": "ifrc_basic_care", "loc": [0, 50]},
                    caution="Seek medical attention if wound is deep or shows signs of infection"
                )
            ],
            meta={
                "disclaimer": "Not medical advice. Seek professional medical care for serious injuries.",
                "when_to_call_emergency": "Call 911 for severe injuries or if unsure"
            }
        ))
        
        response = client.post("/chat", json={
            "query": "Someone fell and has a cut, what should I do?",
            "conversation_id": "borderline-test"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Should be allowed as it's appropriate first aid guidance
        assert data["blocked"] is False
        assert len(data["checklist"]) == 2
        
        # Should have proper disclaimers
        assert "not medical advice" in data["meta"]["disclaimer"].lower()
    
    def test_custom_policy_enforcement(self, safety_test_client):
        """Test enforcement of custom policy rules."""
        # Create custom policy for testing
        custom_policy = """
# Custom Test Policy

## Emergency Keywords
- `test emergency`, `custom alert`

## Blocked Phrases  
- `custom blocked phrase`, `test forbidden`

## Scope Requirements
Content must be related to:
- First aid and emergency response
- Basic safety procedures
- Psychological support
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(custom_policy)
            temp_policy_path = f.name
        
        try:
            # Create critic with custom policy
            custom_critic = SafetyCritic(policy_path=temp_policy_path)
            app_state["safety_critic"] = custom_critic
            
            client = safety_test_client["client"]
            mocks = safety_test_client["mocks"]
            
            # Test custom blocked phrase
            mocks["harmony"].process_query = AsyncMock(return_value=ChecklistResponse(
                checklist=[
                    ChecklistStep(
                        title="Blocked Content",
                        action="This contains a custom blocked phrase that should be caught",
                        source={"doc_id": "test_doc", "loc": [0, 50]}
                    )
                ],
                meta={"disclaimer": "Not medical advice"}
            ))
            
            response = client.post("/chat", json={
                "query": "Test query with custom policy",
                "conversation_id": "custom-policy-test"
            })
            
            assert response.status_code == 200
            data = response.json()
            
            # Should be blocked due to custom blocked phrase
            assert data["blocked"] is True
            
        finally:
            Path(temp_policy_path).unlink(missing_ok=True)
    
    def test_audit_trail_integration(self, safety_test_client):
        """Test that safety critic decisions are properly logged."""
        client = safety_test_client["client"]
        mocks = safety_test_client["mocks"]
        critic = safety_test_client["critic"]
        
        # Test allowed response
        mocks["harmony"].process_query = AsyncMock(return_value=ChecklistResponse(
            checklist=[
                ChecklistStep(
                    title="Cool Burn",
                    action="Cool burn with running water for 10-20 minutes",
                    source={"doc_id": "ifrc_burns", "loc": [0, 50]}
                )
            ],
            meta={"disclaimer": "Not medical advice"}
        ))
        
        response = client.post("/chat", json={
            "query": "How do I treat a minor burn?",
            "conversation_id": "audit-test-1"
        })
        
        assert response.status_code == 200
        
        # Check audit log
        audit_entries = critic.get_audit_log()
        assert len(audit_entries) > 0
        
        latest_entry = audit_entries[-1]
        assert latest_entry["status"] == "ALLOW"
        # "burn" is an emergency keyword, so emergency_detected should be True
        assert latest_entry["emergency_detected"] is True
        
        # Test blocked response
        mocks["harmony"].process_query = AsyncMock(return_value=ChecklistResponse(
            checklist=[
                ChecklistStep(
                    title="Diagnosis",
                    action="I diagnose this condition and prescribe treatment",
                    # Missing source
                )
            ],
            meta={}  # Missing disclaimer
        ))
        
        response = client.post("/chat", json={
            "query": "What's wrong with me?",
            "conversation_id": "audit-test-2"
        })
        
        assert response.status_code == 200
        
        # Check updated audit log
        audit_entries = critic.get_audit_log()
        latest_entry = audit_entries[-1]
        assert latest_entry["status"] == "BLOCK"
        assert len(latest_entry["reasons"]) > 0
    
    def test_performance_under_load(self, safety_test_client):
        """Test safety critic performance under load."""
        import time
        
        client = safety_test_client["client"]
        mocks = safety_test_client["mocks"]
        
        # Mock standard valid response
        mocks["harmony"].process_query = AsyncMock(return_value=ChecklistResponse(
            checklist=[
                ChecklistStep(
                    title="First Aid Step",
                    action="Provide appropriate first aid care",
                    source={"doc_id": "ifrc_guide", "loc": [0, 50]}
                )
            ],
            meta={"disclaimer": "Not medical advice"}
        ))
        
        # Test multiple rapid requests
        start_time = time.time()
        responses = []
        
        for i in range(10):
            response = client.post("/chat", json={
                "query": f"Emergency question {i}",
                "conversation_id": f"load-test-{i}"
            })
            responses.append(response)
        
        total_time = time.time() - start_time
        
        # All responses should be successful
        for response in responses:
            assert response.status_code == 200
            data = response.json()
            assert "blocked" in data
        
        # Should complete within reasonable time (5 seconds for 10 requests)
        assert total_time < 5.0
        
        # Average response time should be reasonable
        avg_time = total_time / len(responses)
        assert avg_time < 1.0  # Less than 1 second per request on average
    
    def test_error_recovery(self, safety_test_client):
        """Test safety critic error recovery and fallback behavior."""
        client = safety_test_client["client"]
        mocks = safety_test_client["mocks"]
        
        # Mock response that might cause critic to fail
        mocks["harmony"].process_query = AsyncMock(return_value=ChecklistResponse(
            checklist=[
                ChecklistStep(
                    title=None,  # None value that might cause issues
                    action=None,
                    source=None
                )
            ],
            meta=None
        ))
        
        response = client.post("/chat", json={
            "query": "Test error recovery",
            "conversation_id": "error-recovery-test"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Should handle gracefully - either block or provide safe fallback
        assert "blocked" in data
        if data["blocked"]:
            assert "block_reason" in data
        else:
            # If allowed, should have safe content
            assert "meta" in data
    
    def test_concurrent_safety_reviews(self, safety_test_client):
        """Test multiple safety critic reviews work correctly."""
        client = safety_test_client["client"]
        mocks = safety_test_client["mocks"]
        
        # Test valid response
        mocks["harmony"].process_query = AsyncMock(return_value=ChecklistResponse(
            checklist=[
                ChecklistStep(
                    title="Valid Step",
                    action="Valid first aid action",
                    source={"doc_id": "valid_doc", "loc": [0, 50]}
                )
            ],
            meta={"disclaimer": "Not medical advice"}
        ))
        
        valid_response = client.post("/chat", json={
            "query": "valid query test",
            "conversation_id": "multi-test-1"
        })
        
        assert valid_response.status_code == 200
        valid_data = valid_response.json()
        assert valid_data["blocked"] is False
        
        # Test invalid response
        mocks["harmony"].process_query = AsyncMock(return_value=ChecklistResponse(
            checklist=[
                ChecklistStep(
                    title="Invalid Step",
                    action="I diagnose and prescribe medication",
                    # Missing source
                )
            ],
            meta={}  # Missing disclaimer
        ))
        
        invalid_response = client.post("/chat", json={
            "query": "invalid query test",
            "conversation_id": "multi-test-2"
        })
        
        assert invalid_response.status_code == 200
        invalid_data = invalid_response.json()
        assert invalid_data["blocked"] is True
        
        # Test another valid response to ensure state doesn't interfere
        mocks["harmony"].process_query = AsyncMock(return_value=ChecklistResponse(
            checklist=[
                ChecklistStep(
                    title="Another Valid Step",
                    action="Another valid first aid action",
                    source={"doc_id": "valid_doc2", "loc": [0, 50]}
                )
            ],
            meta={"disclaimer": "Not medical advice"}
        ))
        
        another_valid_response = client.post("/chat", json={
            "query": "another valid query test",
            "conversation_id": "multi-test-3"
        })
        
        assert another_valid_response.status_code == 200
        another_valid_data = another_valid_response.json()
        assert another_valid_data["blocked"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])