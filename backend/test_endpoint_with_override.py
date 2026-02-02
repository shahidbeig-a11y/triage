"""
Test script to demonstrate the integrated classification endpoint with override checking.

This simulates the POST /api/emails/classify-deterministic endpoint behavior
with both deterministic classification and override detection.
"""

import json
import sys
import os
from datetime import datetime

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app', 'services'))
from classifier_deterministic import classify_deterministic
from classifier_override import check_override, USER_EMAIL, USER_FIRST_NAME


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
        "conversation_id": "conv-1",
        "importance": "normal",
        "has_attachments": False,
        "status": "unprocessed",
    },
    {
        "id": 2,
        "message_id": "msg-2",
        "from_address": "marketing@service.com",
        "from_name": "Service Alert",
        "subject": "URGENT: Action required on your account",
        "body": "Your immediate attention is needed to update your payment method.",
        "body_preview": "Your immediate attention...",
        "to_recipients": json.dumps([{"name": "User", "address": "user@company.com"}]),
        "cc_recipients": json.dumps([]),
        "conversation_id": "conv-2",
        "importance": "high",
        "has_attachments": False,
        "status": "unprocessed",
    },
    {
        "id": 3,
        "message_id": "msg-3",
        "from_address": "calendar-notification@google.com",
        "from_name": "Google Calendar",
        "subject": "Invitation: Team Meeting",
        "body": "You have been invited to a meeting...",
        "body_preview": "You have been invited...",
        "to_recipients": json.dumps([{"name": "User", "address": "user@company.com"}]),
        "cc_recipients": json.dumps([]),
        "conversation_id": "conv-3",
        "importance": "normal",
        "has_attachments": False,
        "status": "unprocessed",
    },
    {
        "id": 4,
        "message_id": "msg-4",
        "from_address": "boss@company.com",
        "from_name": "Boss",
        "subject": "Team update",
        "body": "Everyone, here's the update...",
        "body_preview": "Everyone, here's...",
        "to_recipients": json.dumps([
            {"name": "Alice", "address": "alice@company.com"},
            {"name": "Bob", "address": "bob@company.com"},
            {"name": "User", "address": "user@company.com"},
        ]),
        "cc_recipients": json.dumps([{"name": "User", "address": "user@company.com"}]),
        "conversation_id": "conv-4",
        "importance": "normal",
        "has_attachments": False,
        "status": "unprocessed",
    },
    {
        "id": 5,
        "message_id": "msg-5",
        "from_address": "colleague@company.com",
        "from_name": "Colleague",
        "subject": "Project discussion",
        "body": "Just wanted to get your thoughts on this...",
        "body_preview": "Just wanted to...",
        "to_recipients": json.dumps([{"name": "User", "address": "user@company.com"}]),
        "cc_recipients": json.dumps([]),
        "conversation_id": "conv-5",
        "importance": "normal",
        "has_attachments": False,
        "status": "unprocessed",
    },
    {
        "id": 6,
        "message_id": "msg-6",
        "from_address": "notifications@github.com",
        "from_name": "GitHub",
        "subject": "New issue assigned to you",
        "body": "User, can you review this issue? It's blocking the release.",
        "body_preview": "User, can you review...",
        "to_recipients": json.dumps([{"name": "User", "address": "user@company.com"}]),
        "cc_recipients": json.dumps([]),
        "conversation_id": "conv-6",
        "importance": "normal",
        "has_attachments": False,
        "status": "unprocessed",
    },
]


def simulate_endpoint():
    """Simulate the classify-deterministic endpoint with override checking."""
    user_email = USER_EMAIL
    user_first_name = USER_FIRST_NAME

    total_processed = len(mock_emails)
    classified_count = 0
    overridden_count = 0
    breakdown = {
        "6_marketing": 0,
        "7_notification": 0,
        "8_calendar": 0,
        "9_fyi": 0,
        "11_travel": 0,
    }

    classification_logs = []
    override_logs = []

    print("=" * 80)
    print("SIMULATE POST /api/emails/classify-deterministic (WITH OVERRIDE)")
    print("=" * 80)
    print()

    for email in mock_emails:
        print(f"Processing Email ID {email['id']}: {email['from_address']}")
        print(f"  Subject: {email['subject']}")
        print(f"  Status: {email['status']}")

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
            "conversation_id": email["conversation_id"],
            "importance": email["importance"],
            "has_attachments": email["has_attachments"],
        }

        # Try deterministic classification
        result = classify_deterministic(email_dict, user_email)

        if result:
            category_id = result["category_id"]
            confidence = result["confidence"]
            rule = result["rule"]

            print(f"  ✓ Deterministic: Category {category_id}")
            print(f"    Rule: {rule}")
            print(f"    Confidence: {confidence}")

            # Check for override
            override_result = check_override(
                email_dict,
                category_id,
                user_email=user_email,
                first_name=user_first_name,
                db=None  # No DB session for this test
            )

            if override_result.get("override"):
                print(f"  ⚠️  OVERRIDE TRIGGERED!")
                print(f"    Trigger: {override_result['trigger']}")
                print(f"    Reason: {override_result['reason']}")
                print(f"    Action: Reset to unprocessed for AI classification")

                # Update email status (simulated)
                email["category_id"] = None
                email["status"] = "unprocessed"

                # Log override
                override_log = {
                    "email_id": email["id"],
                    "original_category": category_id,
                    "trigger_type": override_result["trigger"],
                    "reason": override_result["reason"],
                    "timestamp": datetime.utcnow().isoformat()
                }
                override_logs.append(override_log)

                overridden_count += 1
            else:
                print(f"  ✅ KEPT: Category {category_id} (no override)")

                # Update email record (simulated)
                email["category_id"] = category_id
                email["confidence"] = confidence
                email["status"] = "classified"

                # Log classification
                log_entry = {
                    "email_id": email["id"],
                    "category_id": category_id,
                    "rule": rule,
                    "classifier_type": "deterministic",
                    "confidence": confidence,
                    "created_at": datetime.utcnow().isoformat()
                }
                classification_logs.append(log_entry)

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
        else:
            print(f"  ✗ No deterministic classification (needs AI)")

        print()

    remaining = total_processed - classified_count

    # Print response
    print("=" * 80)
    print("RESPONSE:")
    print("=" * 80)
    response = {
        "total_processed": total_processed,
        "classified": classified_count,
        "overridden": overridden_count,
        "remaining": remaining,
        "breakdown": breakdown,
        "message": f"Classified {classified_count} out of {total_processed} emails. {overridden_count} overridden to Work. {remaining} emails need AI classification."
    }
    print(json.dumps(response, indent=2))
    print()

    # Print classification logs
    if classification_logs:
        print("=" * 80)
        print(f"CLASSIFICATION LOGS ({len(classification_logs)} entries):")
        print("=" * 80)
        for log in classification_logs:
            print(json.dumps(log, indent=2))
            print()

    # Print override logs
    if override_logs:
        print("=" * 80)
        print(f"OVERRIDE LOGS ({len(override_logs)} entries):")
        print("=" * 80)
        for log in override_logs:
            print(json.dumps(log, indent=2))
            print()


if __name__ == "__main__":
    simulate_endpoint()
