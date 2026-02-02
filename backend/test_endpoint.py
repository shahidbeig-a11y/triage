"""
Test script to verify the classify-deterministic endpoint logic.

This simulates the endpoint behavior without requiring FastAPI to run.
"""

import json
import sys
import os
from datetime import datetime

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app', 'services'))
from classifier_deterministic import classify_deterministic


# Mock email data (simulating what comes from the database)
mock_emails = [
    {
        "id": 1,
        "message_id": "msg-1",
        "from_address": "newsletter@example.com",
        "from_name": "Example Store",
        "subject": "50% off sale - Limited time only!",
        "body": "Shop now and save...",
        "body_preview": "Shop now...",
        "to_recipients": json.dumps([{"name": "User", "address": "user@company.com"}]),
        "cc_recipients": json.dumps([]),
        "importance": "normal",
        "has_attachments": False,
    },
    {
        "id": 2,
        "message_id": "msg-2",
        "from_address": "calendar-notification@google.com",
        "from_name": "Google Calendar",
        "subject": "Invitation: Team Meeting",
        "body": "You have been invited...",
        "body_preview": "You have been invited...",
        "to_recipients": json.dumps([{"name": "User", "address": "user@company.com"}]),
        "cc_recipients": json.dumps([]),
        "importance": "normal",
        "has_attachments": False,
    },
    {
        "id": 3,
        "message_id": "msg-3",
        "from_address": "colleague@company.com",
        "from_name": "Colleague",
        "subject": "Can you review this PR?",
        "body": "Hey, I need your input...",
        "body_preview": "Hey, I need...",
        "to_recipients": json.dumps([{"name": "User", "address": "user@company.com"}]),
        "cc_recipients": json.dumps([]),
        "importance": "normal",
        "has_attachments": False,
    },
]


def simulate_endpoint():
    """Simulate the classify-deterministic endpoint behavior."""
    user_email = "user@company.com"

    total_processed = len(mock_emails)
    classified_count = 0
    breakdown = {
        "6_marketing": 0,
        "7_notification": 0,
        "8_calendar": 0,
        "9_fyi": 0,
        "11_travel": 0,
    }

    classification_logs = []

    print("=" * 80)
    print("SIMULATE POST /api/emails/classify-deterministic")
    print("=" * 80)
    print()

    for email in mock_emails:
        print(f"Processing Email ID {email['id']}: {email['from_address']}")
        print(f"  Subject: {email['subject']}")

        # Convert to format expected by classifier
        email_dict = {
            "message_id": email["message_id"],
            "from_address": email["from_address"],
            "from_name": email["from_name"],
            "subject": email["subject"],
            "body": email["body"],
            "body_preview": email["body_preview"],
            "to_recipients": email["to_recipients"],
            "cc_recipients": email["cc_recipients"],
            "importance": email["importance"],
            "has_attachments": email["has_attachments"],
        }

        # Try deterministic classification
        result = classify_deterministic(email_dict, user_email)

        if result:
            category_id = result["category_id"]
            confidence = result["confidence"]
            rule = result["rule"]

            print(f"  ✓ Classified: Category {category_id}")
            print(f"    Rule: {rule}")
            print(f"    Confidence: {confidence}")

            # Update breakdown
            classified_count += 1
            category_key = {
                6: "6_marketing",
                7: "7_notification",
                8: "8_calendar",
                9: "9_fyi",
                11: "11_travel"
            }.get(category_id)

            if category_key:
                breakdown[category_key] += 1

            # Log entry (would be saved to DB)
            log_entry = {
                "email_id": email["id"],
                "category_id": category_id,
                "rule": rule,
                "classifier_type": "deterministic",
                "confidence": confidence,
                "created_at": datetime.utcnow().isoformat()
            }
            classification_logs.append(log_entry)
        else:
            print(f"  ✗ No classification (needs AI)")

        print()

    remaining = total_processed - classified_count

    # Print response
    print("=" * 80)
    print("RESPONSE:")
    print("=" * 80)
    response = {
        "total_processed": total_processed,
        "classified": classified_count,
        "remaining": remaining,
        "breakdown": breakdown,
        "message": f"Classified {classified_count} out of {total_processed} emails. {remaining} emails need AI classification."
    }
    print(json.dumps(response, indent=2))
    print()

    # Print classification logs
    print("=" * 80)
    print("CLASSIFICATION LOGS (would be saved to database):")
    print("=" * 80)
    for log in classification_logs:
        print(json.dumps(log, indent=2))
        print()


if __name__ == "__main__":
    simulate_endpoint()
