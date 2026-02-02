"""
Simulate the /check-overrides endpoint response.

This shows what the API would return when checking already-classified emails.
"""

import json

# Simulate checking 10 classified emails
mock_response = {
    "total_checked": 10,
    "overridden": 3,
    "remaining_classified": 7,
    "trigger_breakdown": {
        "urgency_language": 2,
        "direct_address": 1
    },
    "message": "Checked 10 classified emails. 3 overridden to Work pipeline."
}

print("Simulated Response from: POST /api/emails/check-overrides")
print("=" * 80)
print(json.dumps(mock_response, indent=2))
print()

print("What this means:")
print("-" * 80)
print(f"• {mock_response['total_checked']} emails were already classified in categories 6-11")
print(f"• {mock_response['overridden']} emails triggered override rules:")
for trigger, count in mock_response['trigger_breakdown'].items():
    print(f"  - {count} triggered by: {trigger}")
print(f"• {mock_response['remaining_classified']} emails correctly stayed in their categories")
print()
print("Next steps:")
print("-" * 80)
print("• Overridden emails are now status='unprocessed'")
print("• They will be picked up by the AI classifier")
print("• Check override_log table to see which emails and why")
