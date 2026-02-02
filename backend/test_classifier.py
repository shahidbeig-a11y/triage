"""
Test script for deterministic email classifier.

Run with: python test_classifier.py
"""

import json
import sys
import os

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app', 'services'))
from classifier_deterministic import classify_deterministic


# Test emails
test_emails = [
    {
        "name": "Marketing Newsletter",
        "email": {
            "message_id": "1",
            "from_address": "newsletter@example.com",
            "from_name": "Example Store",
            "subject": "50% off sale - Limited time only!",
            "body": "Shop now and save...",
            "to_recipients": json.dumps([{"name": "User", "address": "user@example.com"}]),
            "cc_recipients": json.dumps([]),
        }
    },
    {
        "name": "Calendar Invite",
        "email": {
            "message_id": "2",
            "from_address": "calendar-notification@google.com",
            "from_name": "Google Calendar",
            "subject": "Invitation: Team Meeting @ Mon Jan 15, 2024",
            "body": "You have been invited to a meeting...",
            "to_recipients": json.dumps([{"name": "User", "address": "user@example.com"}]),
            "cc_recipients": json.dumps([]),
        }
    },
    {
        "name": "Travel Confirmation",
        "email": {
            "message_id": "3",
            "from_address": "noreply@delta.com",
            "from_name": "Delta Airlines",
            "subject": "Flight confirmation - ATL to NYC",
            "body": "Your itinerary for...",
            "to_recipients": json.dumps([{"name": "User", "address": "user@example.com"}]),
            "cc_recipients": json.dumps([]),
        }
    },
    {
        "name": "Notification from GitHub",
        "email": {
            "message_id": "4",
            "from_address": "notifications@github.com",
            "from_name": "GitHub",
            "subject": "New sign-in from Chrome on Windows",
            "body": "We detected a new sign-in...",
            "to_recipients": json.dumps([{"name": "User", "address": "user@example.com"}]),
            "cc_recipients": json.dumps([]),
        }
    },
    {
        "name": "FYI Group Email",
        "email": {
            "message_id": "5",
            "from_address": "boss@company.com",
            "from_name": "Boss Name",
            "subject": "Update on Q4 results",
            "body": "Everyone, just wanted to share...",
            "to_recipients": json.dumps([
                {"name": "Alice", "address": "alice@company.com"},
                {"name": "Bob", "address": "bob@company.com"},
                {"name": "Carol", "address": "carol@company.com"},
            ]),
            "cc_recipients": json.dumps([{"name": "User", "address": "user@company.com"}]),
        }
    },
    {
        "name": "Direct Work Email",
        "email": {
            "message_id": "6",
            "from_address": "colleague@company.com",
            "from_name": "Colleague Name",
            "subject": "Can you review this PR?",
            "body": "Hey, I need your input on...",
            "to_recipients": json.dumps([{"name": "User", "address": "user@company.com"}]),
            "cc_recipients": json.dumps([]),
        }
    },
]


def main():
    print("=" * 80)
    print("DETERMINISTIC EMAIL CLASSIFIER TEST")
    print("=" * 80)
    print()

    user_email = "user@company.com"

    for test in test_emails:
        print(f"Test: {test['name']}")
        print(f"From: {test['email']['from_address']}")
        print(f"Subject: {test['email']['subject']}")

        result = classify_deterministic(test['email'], user_email)

        if result:
            category_names = {
                6: "Marketing",
                7: "Notification",
                8: "Calendar",
                9: "FYI",
                11: "Travel"
            }
            category_name = category_names.get(result['category_id'], "Unknown")
            print(f"✓ Classification: Category {result['category_id']} ({category_name})")
            print(f"  Rule: {result['rule']}")
            print(f"  Confidence: {result['confidence']}")
        else:
            print("✗ No deterministic classification (needs AI)")

        print("-" * 80)
        print()


if __name__ == "__main__":
    main()
