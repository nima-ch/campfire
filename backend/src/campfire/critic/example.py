"""Example usage of the Safety Critic system."""

from campfire.critic import SafetyCritic, CriticStatus


def main():
    """Demonstrate Safety Critic functionality."""
    print("=== Campfire Safety Critic Demo ===\n")
    
    # Initialize the Safety Critic
    critic = SafetyCritic()
    
    # Example 1: Valid first-aid response
    print("1. Testing valid first-aid response:")
    valid_response = {
        'checklist': [
            {
                'title': 'Apply Direct Pressure',
                'action': 'Apply direct pressure to the wound using a clean cloth or bandage',
                'source': {
                    'doc_id': 'ifrc_2020_bleeding',
                    'loc': [45, 120]
                },
                'caution': 'Do not remove embedded objects from wounds'
            }
        ],
        'meta': {
            'disclaimer': 'Not medical advice. Contact emergency services for severe injuries.',
            'when_to_call_emergency': 'Call immediately for severe bleeding or shock'
        }
    }
    
    decision1 = critic.review_response(valid_response)
    print(f"Status: {decision1.status.value}")
    print(f"Reasons: {decision1.reasons}")
    print(f"Emergency detected: {decision1.emergency_detected}")
    print()
    
    # Example 2: Emergency scenario (should be allowed but flagged)
    print("2. Testing emergency scenario:")
    emergency_response = {
        'checklist': [
            {
                'title': 'Check Responsiveness',
                'action': 'Tap shoulders and shout to check if person is unconscious',
                'source': {
                    'doc_id': 'ifrc_2020_cpr',
                    'loc': [10, 50]
                }
            }
        ],
        'meta': {
            'disclaimer': 'Not medical advice. Call emergency services immediately.'
        }
    }
    
    decision2 = critic.review_response(emergency_response)
    print(f"Status: {decision2.status.value}")
    print(f"Emergency detected: {decision2.emergency_detected}")
    print(f"Requires emergency banner: {decision2.requires_emergency_banner}")
    print()
    
    # Example 3: Inappropriate medical advice (should be blocked)
    print("3. Testing inappropriate medical advice:")
    blocked_response = {
        'checklist': [
            {
                'title': 'Medical Diagnosis',
                'action': 'Based on your symptoms, I diagnose you with a heart condition',
                'source': {
                    'doc_id': 'fake_source',
                    'loc': [0, 50]
                }
            }
        ],
        'meta': {
            'disclaimer': 'This is medical advice from a doctor.'
        }
    }
    
    decision3 = critic.review_response(blocked_response)
    print(f"Status: {decision3.status.value}")
    print(f"Reasons: {decision3.reasons}")
    print(f"Suggested fixes: {decision3.fixes}")
    print()
    
    # Example 4: Missing citations (should be blocked)
    print("4. Testing missing citations:")
    no_citation_response = {
        'checklist': [
            {
                'title': 'Apply Bandage',
                'action': 'Apply a clean bandage to the wound'
                # Missing source
            }
        ],
        'meta': {
            'disclaimer': 'Not medical advice.'
        }
    }
    
    decision4 = critic.review_response(no_citation_response)
    print(f"Status: {decision4.status.value}")
    print(f"Reasons: {decision4.reasons}")
    print()
    
    # Show safe fallback message
    print("5. Safe fallback message for blocked responses:")
    fallback = critic.get_safe_fallback_message()
    print(f"Fallback title: {fallback['checklist'][0]['title']}")
    print(f"Fallback action: {fallback['checklist'][0]['action']}")
    print(f"Disclaimer: {fallback['meta']['disclaimer']}")
    print()
    
    # Show audit log
    print("6. Audit log summary:")
    audit_log = critic.get_audit_log()
    print(f"Total decisions logged: {len(audit_log)}")
    for i, entry in enumerate(audit_log, 1):
        print(f"  Decision {i}: {entry['status']} - Emergency: {entry['emergency_detected']}")
    
    print("\n=== Demo Complete ===")


if __name__ == "__main__":
    main()