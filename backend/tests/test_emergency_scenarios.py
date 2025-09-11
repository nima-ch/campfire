"""
Emergency scenario test cases for Campfire emergency helper.

Tests specific emergency scenarios like gas leaks, bleeding, burns, etc.
"""

import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient

from campfire.api.main import create_app, app_state
from campfire.critic.types import CriticDecision, CriticStatus, ChecklistResponse, ChecklistStep


@pytest.fixture
def emergency_test_client():
    """Create test client with emergency scenario mocks."""
    with patch.multiple(
        'campfire.api.main',
        initialize_components=AsyncMock(),
        cleanup_components=AsyncMock()
    ):
        # Mock components for emergency scenarios
        mock_llm = Mock()
        mock_llm.supports_tokens.return_value = True
        app_state["llm_provider"] = mock_llm
        
        mock_browser = Mock()
        app_state["browser_tool"] = mock_browser
        
        mock_harmony = Mock()
        app_state["harmony_engine"] = mock_harmony
        
        mock_critic = Mock()
        app_state["safety_critic"] = mock_critic
        
        mock_audit = Mock()
        mock_audit.log_interaction = Mock()
        app_state["audit_logger"] = mock_audit
        
        mock_corpus = Mock()
        mock_corpus.list_documents.return_value = ["ifrc_2020", "who_pfa_2011"]
        app_state["corpus_db"] = mock_corpus
        
        app = create_app()
        client = TestClient(app)
        
        yield {
            "client": client,
            "mocks": {
                "llm": mock_llm,
                "browser": mock_browser,
                "harmony": mock_harmony,
                "critic": mock_critic,
                "audit": mock_audit,
                "corpus": mock_corpus
            }
        }


class TestEmergencyScenarios:
    """Test specific emergency scenarios with proper responses."""
    
    def test_gas_leak_scenario(self, emergency_test_client):
        """Test gas leak emergency scenario."""
        client = emergency_test_client["client"]
        mocks = emergency_test_client["mocks"]
        
        # Configure mocks for gas leak scenario
        mocks["harmony"].process_query = AsyncMock(return_value=ChecklistResponse(
            checklist=[
                ChecklistStep(
                    title="Evacuate Immediately",
                    action="Leave the area immediately and get to fresh air",
                    source={"doc_id": "ifrc_2020_gas", "loc": [150, 200]},
                    caution="Do not use electrical switches or create sparks"
                ),
                ChecklistStep(
                    title="Call Emergency Services",
                    action="Call gas company emergency line and fire department",
                    source={"doc_id": "ifrc_2020_gas", "loc": [201, 250]}
                ),
                ChecklistStep(
                    title="Ventilate Area",
                    action="Open windows and doors from outside if safe to do so",
                    source={"doc_id": "ifrc_2020_gas", "loc": [251, 300]}
                )
            ],
            meta={
                "disclaimer": "Not medical advice. Call local emergency services immediately.",
                "when_to_call_emergency": "Call gas company and fire department immediately"
            }
        ))
        
        mocks["critic"].review_response.return_value = CriticDecision(
            status=CriticStatus.ALLOW,
            reasons=["Response provides appropriate emergency guidance"],
            emergency_detected=True,
            requires_emergency_banner=True
        )
        
        # Test gas leak query
        response = client.post("/chat", json={
            "query": "I smell gas in my house, what should I do?",
            "conversation_id": "gas-leak-test"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify emergency response
        assert data["blocked"] is False
        assert data["emergency_banner"] is not None
        assert "EMERGENCY" in data["emergency_banner"]
        assert len(data["checklist"]) == 3
        
        # Verify evacuation is first step
        first_step = data["checklist"][0]
        assert "evacuate" in first_step["title"].lower()
        assert "immediately" in first_step["action"].lower()
        
        # Verify proper citations
        for step in data["checklist"]:
            assert "source" in step
            assert "doc_id" in step["source"]
            assert "loc" in step["source"]
        
        # Verify emergency services mentioned
        actions_text = " ".join(step["action"] for step in data["checklist"])
        assert "emergency" in actions_text.lower()
    
    def test_severe_bleeding_scenario(self, emergency_test_client):
        """Test severe bleeding emergency scenario."""
        client = emergency_test_client["client"]
        mocks = emergency_test_client["mocks"]
        
        mocks["harmony"].process_query = AsyncMock(return_value=ChecklistResponse(
            checklist=[
                ChecklistStep(
                    title="Apply Direct Pressure",
                    action="Apply firm, direct pressure to the wound with clean cloth or bandage",
                    source={"doc_id": "ifrc_2020_bleeding", "loc": [100, 180]},
                    caution="Do not remove objects embedded in the wound"
                ),
                ChecklistStep(
                    title="Elevate if Possible",
                    action="Raise the injured area above heart level if no fracture suspected",
                    source={"doc_id": "ifrc_2020_bleeding", "loc": [181, 240]}
                ),
                ChecklistStep(
                    title="Call Emergency Services",
                    action="Call 911 immediately for severe bleeding that won't stop",
                    source={"doc_id": "ifrc_2020_emergency", "loc": [50, 100]}
                )
            ],
            meta={
                "disclaimer": "Not medical advice. Call emergency services for severe bleeding.",
                "when_to_call_emergency": "Call 911 immediately for uncontrolled bleeding"
            }
        ))
        
        mocks["critic"].review_response.return_value = CriticDecision(
            status=CriticStatus.ALLOW,
            reasons=["Appropriate first aid guidance with emergency escalation"],
            emergency_detected=True,
            requires_emergency_banner=True
        )
        
        response = client.post("/chat", json={
            "query": "Someone is bleeding heavily from a deep cut",
            "conversation_id": "bleeding-test"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify emergency handling
        assert data["blocked"] is False
        assert data["emergency_banner"] is not None
        assert len(data["checklist"]) == 3
        
        # Verify direct pressure is first step
        first_step = data["checklist"][0]
        assert "pressure" in first_step["action"].lower()
        
        # Verify emergency services step
        emergency_step = next((step for step in data["checklist"] 
                              if "emergency" in step["action"].lower() or "911" in step["action"]), None)
        assert emergency_step is not None
    
    def test_burn_injury_scenario(self, emergency_test_client):
        """Test burn injury scenario."""
        client = emergency_test_client["client"]
        mocks = emergency_test_client["mocks"]
        
        mocks["harmony"].process_query = AsyncMock(return_value=ChecklistResponse(
            checklist=[
                ChecklistStep(
                    title="Cool the Burn",
                    action="Cool burn with running water for 10-20 minutes",
                    source={"doc_id": "ifrc_2020_burns", "loc": [75, 125]},
                    caution="Do not use ice or very cold water"
                ),
                ChecklistStep(
                    title="Remove Jewelry",
                    action="Remove rings, watches, or tight clothing near the burn before swelling",
                    source={"doc_id": "ifrc_2020_burns", "loc": [126, 180]}
                ),
                ChecklistStep(
                    title="Cover the Burn",
                    action="Cover with sterile, non-adhesive bandage or clean cloth",
                    source={"doc_id": "ifrc_2020_burns", "loc": [181, 230]}
                ),
                ChecklistStep(
                    title="Seek Medical Care",
                    action="Get medical attention for burns larger than palm size or on face/hands",
                    source={"doc_id": "ifrc_2020_burns", "loc": [231, 280]}
                )
            ],
            meta={
                "disclaimer": "Not medical advice. Seek medical care for serious burns.",
                "when_to_call_emergency": "Call 911 for large burns, electrical burns, or burns to face/airway"
            }
        ))
        
        mocks["critic"].review_response.return_value = CriticDecision(
            status=CriticStatus.ALLOW,
            reasons=["Appropriate burn first aid guidance"],
            emergency_detected=False,
            requires_emergency_banner=False
        )
        
        response = client.post("/chat", json={
            "query": "I burned my hand on the stove, what should I do?",
            "conversation_id": "burn-test"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["blocked"] is False
        assert len(data["checklist"]) == 4
        
        # Verify cooling is first step
        first_step = data["checklist"][0]
        assert "cool" in first_step["action"].lower()
        assert "water" in first_step["action"].lower()
        
        # Verify proper sequence
        step_titles = [step["title"].lower() for step in data["checklist"]]
        assert any("cool" in title for title in step_titles)
        assert any("jewelry" in title or "remove" in title for title in step_titles)
        assert any("cover" in title for title in step_titles)
    
    def test_unconscious_person_scenario(self, emergency_test_client):
        """Test unconscious person emergency scenario."""
        client = emergency_test_client["client"]
        mocks = emergency_test_client["mocks"]
        
        mocks["harmony"].process_query = AsyncMock(return_value=ChecklistResponse(
            checklist=[
                ChecklistStep(
                    title="Check Responsiveness",
                    action="Tap shoulders firmly and shout 'Are you okay?' to check consciousness",
                    source={"doc_id": "ifrc_2020_cpr", "loc": [50, 120]},
                    caution="Do not move if spinal injury suspected"
                ),
                ChecklistStep(
                    title="Call Emergency Services",
                    action="Call 911 immediately if person is unresponsive",
                    source={"doc_id": "ifrc_2020_emergency", "loc": [25, 75]}
                ),
                ChecklistStep(
                    title="Check Breathing",
                    action="Look, listen, and feel for normal breathing for no more than 10 seconds",
                    source={"doc_id": "ifrc_2020_cpr", "loc": [121, 180]}
                ),
                ChecklistStep(
                    title="Recovery Position",
                    action="If breathing normally, place in recovery position if no spinal injury",
                    source={"doc_id": "ifrc_2020_recovery", "loc": [100, 160]}
                )
            ],
            meta={
                "disclaimer": "Not medical advice. Call emergency services immediately.",
                "when_to_call_emergency": "Call 911 immediately for unconscious person"
            }
        ))
        
        mocks["critic"].review_response.return_value = CriticDecision(
            status=CriticStatus.ALLOW,
            reasons=["Critical emergency response with proper escalation"],
            emergency_detected=True,
            requires_emergency_banner=True
        )
        
        response = client.post("/chat", json={
            "query": "Found someone unconscious on the ground",
            "conversation_id": "unconscious-test"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # This should trigger emergency banner
        assert data["blocked"] is False
        assert data["emergency_banner"] is not None
        assert "EMERGENCY" in data["emergency_banner"]
        
        # Verify emergency services is called early
        emergency_step = next((i for i, step in enumerate(data["checklist"]) 
                              if "911" in step["action"] or "emergency" in step["action"].lower()), None)
        assert emergency_step is not None
        assert emergency_step <= 1  # Should be first or second step
    
    def test_chest_pain_scenario(self, emergency_test_client):
        """Test chest pain emergency scenario."""
        client = emergency_test_client["client"]
        mocks = emergency_test_client["mocks"]
        
        mocks["harmony"].process_query = AsyncMock(return_value=ChecklistResponse(
            checklist=[
                ChecklistStep(
                    title="Call Emergency Services",
                    action="Call 911 immediately for chest pain - do not delay",
                    source={"doc_id": "ifrc_2020_cardiac", "loc": [25, 80]}
                ),
                ChecklistStep(
                    title="Keep Person Calm",
                    action="Help person sit in comfortable position and stay calm",
                    source={"doc_id": "ifrc_2020_cardiac", "loc": [81, 130]},
                    caution="Do not give food, water, or medication unless prescribed"
                ),
                ChecklistStep(
                    title="Loosen Clothing",
                    action="Loosen any tight clothing around neck and chest",
                    source={"doc_id": "ifrc_2020_cardiac", "loc": [131, 170]}
                ),
                ChecklistStep(
                    title="Monitor Condition",
                    action="Stay with person and monitor breathing and consciousness",
                    source={"doc_id": "ifrc_2020_cardiac", "loc": [171, 220]}
                )
            ],
            meta={
                "disclaimer": "Not medical advice. Call emergency services immediately for chest pain.",
                "when_to_call_emergency": "Call 911 immediately - chest pain can be life-threatening"
            }
        ))
        
        mocks["critic"].review_response.return_value = CriticDecision(
            status=CriticStatus.ALLOW,
            reasons=["Critical emergency with immediate 911 call"],
            emergency_detected=True,
            requires_emergency_banner=True
        )
        
        response = client.post("/chat", json={
            "query": "Having severe chest pain and shortness of breath",
            "conversation_id": "chest-pain-test"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have emergency banner
        assert data["emergency_banner"] is not None
        assert "EMERGENCY" in data["emergency_banner"]
        
        # First step should be calling 911
        first_step = data["checklist"][0]
        assert "911" in first_step["action"] or "emergency" in first_step["action"].lower()
        assert "immediately" in first_step["action"].lower()
    
    def test_choking_scenario(self, emergency_test_client):
        """Test choking emergency scenario."""
        client = emergency_test_client["client"]
        mocks = emergency_test_client["mocks"]
        
        mocks["harmony"].process_query = AsyncMock(return_value=ChecklistResponse(
            checklist=[
                ChecklistStep(
                    title="Assess Severity",
                    action="Ask 'Are you choking?' If person can speak or cough forcefully, encourage coughing",
                    source={"doc_id": "ifrc_2020_choking", "loc": [50, 120]}
                ),
                ChecklistStep(
                    title="Back Blows",
                    action="If severe choking, give 5 sharp back blows between shoulder blades",
                    source={"doc_id": "ifrc_2020_choking", "loc": [121, 180]},
                    caution="Use heel of hand, lean person forward"
                ),
                ChecklistStep(
                    title="Abdominal Thrusts",
                    action="If back blows fail, give 5 abdominal thrusts (Heimlich maneuver)",
                    source={"doc_id": "ifrc_2020_choking", "loc": [181, 240]}
                ),
                ChecklistStep(
                    title="Call for Help",
                    action="Call 911 if choking persists or person becomes unconscious",
                    source={"doc_id": "ifrc_2020_emergency", "loc": [75, 125]}
                )
            ],
            meta={
                "disclaimer": "Not medical advice. Call 911 if choking cannot be cleared.",
                "when_to_call_emergency": "Call 911 if choking persists or person loses consciousness"
            }
        ))
        
        mocks["critic"].review_response.return_value = CriticDecision(
            status=CriticStatus.ALLOW,
            reasons=["Appropriate choking response protocol"],
            emergency_detected=True,
            requires_emergency_banner=True
        )
        
        response = client.post("/chat", json={
            "query": "Someone is choking and can't breathe",
            "conversation_id": "choking-test"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["blocked"] is False
        assert len(data["checklist"]) == 4
        
        # Verify proper choking protocol
        actions_text = " ".join(step["action"] for step in data["checklist"])
        assert "back blows" in actions_text.lower() or "back" in actions_text.lower()
        assert "abdominal" in actions_text.lower() or "heimlich" in actions_text.lower()
    
    def test_psychological_emergency_scenario(self, emergency_test_client):
        """Test psychological emergency scenario."""
        client = emergency_test_client["client"]
        mocks = emergency_test_client["mocks"]
        
        mocks["harmony"].process_query = AsyncMock(return_value=ChecklistResponse(
            checklist=[
                ChecklistStep(
                    title="Listen Without Judgment",
                    action="Listen actively and avoid giving advice or making judgments",
                    source={"doc_id": "who_pfa_2011", "loc": [200, 260]}
                ),
                ChecklistStep(
                    title="Provide Comfort",
                    action="Offer comfort and support, stay calm and reassuring",
                    source={"doc_id": "who_pfa_2011", "loc": [261, 320]}
                ),
                ChecklistStep(
                    title="Ensure Safety",
                    action="Help person get to a safe, quiet place away from stressors",
                    source={"doc_id": "who_pfa_2011", "loc": [321, 380]}
                ),
                ChecklistStep(
                    title="Connect with Support",
                    action="Help connect with family, friends, or professional mental health services",
                    source={"doc_id": "who_pfa_2011", "loc": [381, 440]}
                )
            ],
            meta={
                "disclaimer": "Not medical advice. Contact mental health professionals for ongoing support.",
                "when_to_call_emergency": "Call 911 if person expresses intent to harm self or others"
            }
        ))
        
        mocks["critic"].review_response.return_value = CriticDecision(
            status=CriticStatus.ALLOW,
            reasons=["Appropriate psychological first aid guidance"],
            emergency_detected=False,
            requires_emergency_banner=False
        )
        
        response = client.post("/chat", json={
            "query": "Friend is having panic attack and very distressed",
            "conversation_id": "psychological-test"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["blocked"] is False
        assert len(data["checklist"]) == 4
        
        # Verify psychological first aid principles
        actions_text = " ".join(step["action"] for step in data["checklist"])
        assert "listen" in actions_text.lower()
        assert "comfort" in actions_text.lower() or "support" in actions_text.lower()
    
    def test_scenario_with_inappropriate_response_blocked(self, emergency_test_client):
        """Test that inappropriate responses to emergencies are blocked."""
        client = emergency_test_client["client"]
        mocks = emergency_test_client["mocks"]
        
        # Mock inappropriate response that should be blocked
        mocks["harmony"].process_query = AsyncMock(return_value=ChecklistResponse(
            checklist=[
                ChecklistStep(
                    title="Diagnose Condition",
                    action="Based on symptoms, I diagnose this as a heart attack and prescribe aspirin",
                    source={"doc_id": "fake_source", "loc": [0, 50]}
                )
            ],
            meta={
                "disclaimer": "This is medical advice from a qualified doctor"
            }
        ))
        
        mocks["critic"].review_response.return_value = CriticDecision(
            status=CriticStatus.BLOCK,
            reasons=["Contains inappropriate medical diagnosis", "Claims to provide medical advice"],
            emergency_detected=True,
            requires_emergency_banner=False
        )
        
        response = client.post("/chat", json={
            "query": "Having chest pain, what's wrong with me?",
            "conversation_id": "blocked-test"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Should be blocked
        assert data["blocked"] is True
        assert "block_reason" in data
        assert len(data["checklist"]) == 0
        
        # Should have safe fallback message
        assert "blocked_message" in data["meta"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])