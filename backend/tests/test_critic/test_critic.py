"""Tests for the Safety Critic."""

import pytest
from unittest.mock import Mock, patch

from campfire.critic import SafetyCritic, CriticDecision, CriticStatus


class TestSafetyCritic:
    """Test cases for SafetyCritic."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.critic = SafetyCritic()
    
    def test_valid_response_allowed(self):
        """Test that valid responses are allowed."""
        response = {
            'checklist': [
                {
                    'title': 'Apply Pressure',
                    'action': 'Apply direct pressure to the wound with a clean cloth',
                    'source': {
                        'doc_id': 'ifrc_2020',
                        'loc': [100, 200]
                    }
                }
            ],
            'meta': {
                'disclaimer': 'Not medical advice. Contact emergency services for serious injuries.'
            }
        }
        
        decision = self.critic.review_response(response)
        
        assert decision.status == CriticStatus.ALLOW
        assert "meets all safety criteria" in decision.reasons[0]
        assert decision.emergency_detected is False
    
    def test_missing_citations_blocked(self):
        """Test that responses without citations are blocked."""
        response = {
            'checklist': [
                {
                    'title': 'Apply Pressure',
                    'action': 'Apply direct pressure to the wound',
                    # Missing source
                }
            ],
            'meta': {
                'disclaimer': 'Not medical advice.'
            }
        }
        
        decision = self.critic.review_response(response)
        
        assert decision.status == CriticStatus.BLOCK
        assert any("lacks source citation" in reason for reason in decision.reasons)
        assert "Ensure every step includes a valid source citation" in decision.fixes
    
    def test_emergency_keywords_detected(self):
        """Test detection of emergency keywords."""
        response = {
            'checklist': [
                {
                    'title': 'Check Consciousness',
                    'action': 'Check if the person is unconscious and not breathing',
                    'source': {
                        'doc_id': 'ifrc_2020',
                        'loc': [100, 200]
                    }
                }
            ],
            'meta': {
                'disclaimer': 'Not medical advice.'
            }
        }
        
        decision = self.critic.review_response(response)
        
        assert decision.emergency_detected is True
        assert decision.requires_emergency_banner is True
        # Emergency keywords don't block responses, they just trigger banners
        assert decision.status == CriticStatus.ALLOW
    
    def test_blocked_medical_phrases(self):
        """Test blocking of inappropriate medical phrases."""
        response = {
            'checklist': [
                {
                    'title': 'Medical Assessment',
                    'action': 'I will diagnose your condition and prescribe medication',
                    'source': {
                        'doc_id': 'ifrc_2020',
                        'loc': [100, 200]
                    }
                }
            ],
            'meta': {
                'disclaimer': 'Not medical advice.'
            }
        }
        
        decision = self.critic.review_response(response)
        
        assert decision.status == CriticStatus.BLOCK
        assert any("inappropriate medical terms" in reason for reason in decision.reasons)
    
    def test_missing_disclaimer_blocked(self):
        """Test that responses without proper disclaimers are blocked."""
        response = {
            'checklist': [
                {
                    'title': 'Apply Bandage',
                    'action': 'Apply a clean bandage',
                    'source': {
                        'doc_id': 'ifrc_2020',
                        'loc': [100, 200]
                    }
                }
            ],
            'meta': {
                # Missing disclaimer
            }
        }
        
        decision = self.critic.review_response(response)
        
        assert decision.status == CriticStatus.BLOCK
        assert any("Missing medical disclaimer" in reason for reason in decision.reasons)
    
    def test_invalid_disclaimer_blocked(self):
        """Test that responses with invalid disclaimers are blocked."""
        response = {
            'checklist': [
                {
                    'title': 'Apply Bandage',
                    'action': 'Apply a clean bandage',
                    'source': {
                        'doc_id': 'ifrc_2020',
                        'loc': [100, 200]
                    }
                }
            ],
            'meta': {
                'disclaimer': 'This is medical advice from a doctor.'  # Invalid
            }
        }
        
        decision = self.critic.review_response(response)
        
        assert decision.status == CriticStatus.BLOCK
        assert any("must include 'Not medical advice'" in reason for reason in decision.reasons)
    
    def test_empty_response_blocked(self):
        """Test that empty responses are blocked."""
        response = {
            'checklist': [],
            'meta': {
                'disclaimer': 'Not medical advice.'
            }
        }
        
        decision = self.critic.review_response(response)
        
        assert decision.status == CriticStatus.BLOCK
        assert any("contains no actionable steps" in reason for reason in decision.reasons)
    
    def test_invalid_source_format_blocked(self):
        """Test that invalid source formats are blocked."""
        response = {
            'checklist': [
                {
                    'title': 'Apply Pressure',
                    'action': 'Apply direct pressure',
                    'source': "invalid_source_format"  # Should be dict
                }
            ],
            'meta': {
                'disclaimer': 'Not medical advice.'
            }
        }
        
        decision = self.critic.review_response(response)
        
        assert decision.status == CriticStatus.BLOCK
        assert any("invalid source format" in reason for reason in decision.reasons)
    
    def test_missing_source_fields_blocked(self):
        """Test that missing source fields are blocked."""
        response = {
            'checklist': [
                {
                    'title': 'Apply Pressure',
                    'action': 'Apply direct pressure',
                    'source': {
                        'doc_id': 'ifrc_2020'
                        # Missing 'loc' field
                    }
                }
            ],
            'meta': {
                'disclaimer': 'Not medical advice.'
            }
        }
        
        decision = self.critic.review_response(response)
        
        assert decision.status == CriticStatus.BLOCK
        assert any("missing location in source" in reason for reason in decision.reasons)
    
    def test_empty_step_content_blocked(self):
        """Test that steps with empty content are blocked."""
        response = {
            'checklist': [
                {
                    'title': '',  # Empty title
                    'action': '',  # Empty action
                    'source': {
                        'doc_id': 'ifrc_2020',
                        'loc': [100, 200]
                    }
                }
            ],
            'meta': {
                'disclaimer': 'Not medical advice.'
            }
        }
        
        decision = self.critic.review_response(response)
        
        assert decision.status == CriticStatus.BLOCK
        assert any("has no action specified" in reason for reason in decision.reasons)
        assert any("has no title specified" in reason for reason in decision.reasons)
    
    def test_malformed_response_blocked(self):
        """Test that malformed responses are blocked."""
        # Test non-dict response
        decision1 = self.critic.review_response("invalid_response")
        assert decision1.status == CriticStatus.BLOCK
        assert any("must be a dictionary" in reason for reason in decision1.reasons)
        
        # Test invalid checklist format
        response2 = {
            'checklist': "not_a_list",
            'meta': {}
        }
        decision2 = self.critic.review_response(response2)
        assert decision2.status == CriticStatus.BLOCK
        assert any("must be a list" in reason for reason in decision2.reasons)
    
    def test_audit_log_functionality(self):
        """Test audit logging functionality."""
        response = {
            'checklist': [
                {
                    'title': 'Test Step',
                    'action': 'Test action',
                    'source': {
                        'doc_id': 'test_doc',
                        'loc': [0, 100]
                    }
                }
            ],
            'meta': {
                'disclaimer': 'Not medical advice.'
            }
        }
        
        # Clear any existing log entries
        self.critic.audit_log.clear()
        
        decision = self.critic.review_response(response)
        
        # Check that decision was logged
        assert len(self.critic.audit_log) == 1
        log_entry = self.critic.audit_log[0]
        
        assert log_entry['status'] == decision.status.value
        assert log_entry['reasons'] == decision.reasons
        assert 'timestamp' in log_entry
        assert 'response_summary' in log_entry
    
    def test_get_audit_log(self):
        """Test audit log retrieval."""
        # Add some test entries
        self.critic.audit_log = [
            {'timestamp': '2023-01-01T00:00:00', 'status': 'ALLOW'},
            {'timestamp': '2023-01-01T01:00:00', 'status': 'BLOCK'},
            {'timestamp': '2023-01-01T02:00:00', 'status': 'ALLOW'},
        ]
        
        # Test getting all entries
        all_entries = self.critic.get_audit_log()
        assert len(all_entries) == 3
        
        # Test getting limited entries
        limited_entries = self.critic.get_audit_log(limit=2)
        assert len(limited_entries) == 2
        assert limited_entries[0]['timestamp'] == '2023-01-01T01:00:00'  # Last 2
    
    def test_safe_fallback_message(self):
        """Test safe fallback message generation."""
        fallback = self.critic.get_safe_fallback_message()
        
        assert 'checklist' in fallback
        assert len(fallback['checklist']) == 1
        assert 'Seek Professional Help' in fallback['checklist'][0]['title']
        assert 'meta' in fallback
        assert 'blocked_by_safety_critic' in fallback['meta']
        assert fallback['meta']['blocked_by_safety_critic'] is True
    
    def test_error_handling(self):
        """Test error handling in critic review."""
        # Mock policy engine to raise an exception
        with patch.object(self.critic, '_parse_response', side_effect=Exception("Test error")):
            decision = self.critic.review_response({'test': 'data'})
            
            assert decision.status == CriticStatus.BLOCK
            assert any("Internal error during review" in reason for reason in decision.reasons)
            assert "Contact system administrator" in decision.fixes
    
    def test_audit_log_size_limit(self):
        """Test that audit log maintains size limit."""
        # Fill audit log beyond limit
        for i in range(1100):
            self.critic.audit_log.append({'entry': i})
        
        # Add one more entry to trigger cleanup
        response = {
            'checklist': [
                {
                    'title': 'Test',
                    'action': 'Test',
                    'source': {'doc_id': 'test', 'loc': [0, 1]}
                }
            ],
            'meta': {'disclaimer': 'Not medical advice.'}
        }
        
        self.critic.review_response(response)
        
        # Should be limited to 1000 entries
        assert len(self.critic.audit_log) == 1000