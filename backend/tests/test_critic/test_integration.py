"""Integration tests for Safety Critic system."""

import pytest
import tempfile
import os
from pathlib import Path

from campfire.critic import SafetyCritic, CriticStatus


class TestSafetyCriticIntegration:
    """Integration tests for the complete Safety Critic system."""
    
    def test_complete_emergency_scenario(self):
        """Test complete emergency scenario with all safety features."""
        critic = SafetyCritic()
        
        # Emergency response with proper citations
        response = {
            'checklist': [
                {
                    'title': 'Check Responsiveness',
                    'action': 'Tap shoulders and shout "Are you okay?" to check if person is unconscious',
                    'source': {
                        'doc_id': 'ifrc_2020_cpr',
                        'loc': [45, 120]
                    },
                    'caution': 'Do not move person if spinal injury is suspected'
                },
                {
                    'title': 'Call for Help',
                    'action': 'Call emergency services immediately if person is not breathing',
                    'source': {
                        'doc_id': 'ifrc_2020_emergency',
                        'loc': [200, 250]
                    }
                }
            ],
            'meta': {
                'disclaimer': 'Not medical advice. Call local emergency services for life-threatening situations.',
                'when_to_call_emergency': 'Call immediately for unconsciousness, no breathing, or severe bleeding'
            }
        }
        
        decision = critic.review_response(response)
        
        # Should be allowed despite emergency keywords because it has proper citations and disclaimers
        assert decision.status == CriticStatus.ALLOW
        assert decision.emergency_detected is True
        assert decision.requires_emergency_banner is True
        
        # Check audit log
        audit_entries = critic.get_audit_log()
        assert len(audit_entries) == 1
        assert audit_entries[0]['emergency_detected'] is True
    
    def test_inappropriate_medical_advice_blocked(self):
        """Test that inappropriate medical advice is properly blocked."""
        critic = SafetyCritic()
        
        response = {
            'checklist': [
                {
                    'title': 'Medical Diagnosis',
                    'action': 'Based on your symptoms, I diagnose you with a heart condition and prescribe medication',
                    'source': {
                        'doc_id': 'fake_medical_source',
                        'loc': [0, 50]
                    }
                }
            ],
            'meta': {
                'disclaimer': 'This is medical advice from a qualified doctor.'
            }
        }
        
        decision = critic.review_response(response)
        
        assert decision.status == CriticStatus.BLOCK
        
        # Should detect multiple issues
        reasons = ' '.join(decision.reasons)
        assert "inappropriate medical terms" in reasons
        assert "must include 'Not medical advice'" in reasons
        
        # Get safe fallback
        fallback = critic.get_safe_fallback_message()
        assert fallback['meta']['blocked_by_safety_critic'] is True
    
    def test_custom_policy_file_integration(self):
        """Test integration with custom policy file."""
        # Create custom policy file
        custom_policy = """
# Custom Policy

## Emergency Keywords

- `custom emergency`, `special alert`

## Blocked Phrases

- `custom blocked phrase`, `forbidden term`
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(custom_policy)
            temp_path = f.name
        
        try:
            critic = SafetyCritic(policy_path=temp_path)
            
            # Test custom emergency keyword
            response1 = {
                'checklist': [
                    {
                        'title': 'Custom Emergency',
                        'action': 'This is a custom emergency situation',
                        'source': {'doc_id': 'test', 'loc': [0, 10]}
                    }
                ],
                'meta': {'disclaimer': 'Not medical advice.'}
            }
            
            decision1 = critic.review_response(response1)
            assert decision1.emergency_detected is True
            
            # Test custom blocked phrase
            response2 = {
                'checklist': [
                    {
                        'title': 'Blocked Content',
                        'action': 'This contains a custom blocked phrase',
                        'source': {'doc_id': 'test', 'loc': [0, 10]}
                    }
                ],
                'meta': {'disclaimer': 'Not medical advice.'}
            }
            
            decision2 = critic.review_response(response2)
            assert decision2.status == CriticStatus.BLOCK
            
        finally:
            os.unlink(temp_path)
    
    def test_multiple_validation_failures(self):
        """Test response with multiple validation failures."""
        critic = SafetyCritic()
        
        response = {
            'checklist': [
                {
                    'title': '',  # Empty title
                    'action': 'Patient is unconscious, I will diagnose the condition',  # Emergency + blocked phrase
                    # Missing source
                },
                {
                    'title': 'Another Step',
                    'action': '',  # Empty action
                    'source': 'invalid_format'  # Invalid source format
                }
            ],
            'meta': {
                # Missing disclaimer
            }
        }
        
        decision = critic.review_response(response)
        
        assert decision.status == CriticStatus.BLOCK
        assert decision.emergency_detected is True
        
        # Should have multiple reasons
        assert len(decision.reasons) > 3
        
        reasons_text = ' '.join(decision.reasons)
        assert "lacks source citation" in reasons_text
        assert "inappropriate medical terms" in reasons_text
        assert "Missing medical disclaimer" in reasons_text
        assert "has no title specified" in reasons_text
        assert "has no action specified" in reasons_text
        assert "invalid source format" in reasons_text
        # Emergency keywords are detected but don't appear in blocking reasons
    
    def test_edge_case_handling(self):
        """Test handling of edge cases and boundary conditions."""
        critic = SafetyCritic()
        
        # Test with None values
        response1 = {
            'checklist': [
                {
                    'title': None,
                    'action': None,
                    'source': None
                }
            ],
            'meta': None
        }
        
        decision1 = critic.review_response(response1)
        assert decision1.status == CriticStatus.BLOCK
        
        # Test with very long content
        long_text = "a" * 10000
        response2 = {
            'checklist': [
                {
                    'title': long_text,
                    'action': long_text,
                    'source': {'doc_id': 'test', 'loc': [0, 10]}
                }
            ],
            'meta': {'disclaimer': 'Not medical advice.'}
        }
        
        decision2 = critic.review_response(response2)
        # Should handle long content without crashing
        assert decision2.status in [CriticStatus.ALLOW, CriticStatus.BLOCK]
        
        # Test with special characters
        response3 = {
            'checklist': [
                {
                    'title': 'Special chars: !@#$%^&*()',
                    'action': 'Unicode: 你好 🚑 ñoño',
                    'source': {'doc_id': 'test', 'loc': [0, 10]}
                }
            ],
            'meta': {'disclaimer': 'Not medical advice.'}
        }
        
        decision3 = critic.review_response(response3)
        # Should handle special characters without crashing
        assert decision3.status in [CriticStatus.ALLOW, CriticStatus.BLOCK]
    
    def test_concurrent_reviews(self):
        """Test that concurrent reviews don't interfere with each other."""
        critic = SafetyCritic()
        
        # Create multiple responses
        responses = []
        for i in range(10):
            responses.append({
                'checklist': [
                    {
                        'title': f'Step {i}',
                        'action': f'Action {i}',
                        'source': {'doc_id': f'doc_{i}', 'loc': [i*10, (i+1)*10]}
                    }
                ],
                'meta': {'disclaimer': 'Not medical advice.'}
            })
        
        # Review all responses
        decisions = []
        for response in responses:
            decisions.append(critic.review_response(response))
        
        # All should be allowed (valid responses)
        for decision in decisions:
            assert decision.status == CriticStatus.ALLOW
        
        # Check audit log has all entries
        audit_log = critic.get_audit_log()
        assert len(audit_log) == 10
    
    def test_policy_engine_integration(self):
        """Test integration between SafetyCritic and PolicyEngine."""
        critic = SafetyCritic()
        
        # Test that policy engine methods are accessible
        emergency_keywords = critic.policy_engine.detect_emergency_keywords("unconscious patient")
        assert "unconscious" in emergency_keywords
        
        blocked_phrases = critic.policy_engine.detect_blocked_phrases("I will diagnose")
        assert "diagnose" in blocked_phrases
        
        # Test scope validation
        assert critic.policy_engine.is_within_scope("first aid emergency help") is True
        assert critic.policy_engine.is_within_scope("diagnose disease") is False
        
        # Test banner and disclaimer generation
        banner = critic.policy_engine.get_emergency_banner_text()
        assert "EMERGENCY" in banner
        
        disclaimer = critic.policy_engine.get_medical_disclaimer()
        assert "not medical advice" in disclaimer.lower()