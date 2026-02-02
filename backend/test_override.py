"""
Test script for override classifier.

Run with: python3 test_override.py
"""

import json
import sys
import os

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app', 'services'))
from classifier_override import check_override, USER_EMAIL, USER_FIRST_NAME


# Test emails with various override triggers
test_cases = [
    {
        "name": "Marketing with Urgency Language",
        "email": {
            "message_id": "1",
            "from_address": "newsletter@example.com",
            "subject": "URGENT: Action required on your account",
            "body": "Your immediate attention is needed...",
            "to_recipients": json.dumps([{"name": "User", "address": "user@company.com"}]),
            "cc_recipients": json.dumps([]),
            "conversation_id": "conv-1",
        },
        "current_category": 6,  # Marketing
        "expected_override": True,
        "expected_trigger": "urgency_language"
    },
    {
        "name": "Notification - No Override Needed",
        "email": {
            "message_id": "2",
            "from_address": "notifications@github.com",
            "subject": "New commit in repository",
            "body": "A new commit was pushed...",
            "to_recipients": json.dumps([{"name": "User", "address": "user@company.com"}]),
            "cc_recipients": json.dumps([]),
            "conversation_id": "conv-2",
        },
        "current_category": 7,  # Notification
        "expected_override": False,
        "expected_trigger": None
    },
    {
        "name": "FYI with Sole Recipient (should override)",
        "email": {
            "message_id": "3",
            "from_address": "colleague@company.com",
            "subject": "Update on project",
            "body": "Here's the latest update...",
            "to_recipients": json.dumps([{"name": "User", "address": "user@company.com"}]),
            "cc_recipients": json.dumps([]),
            "conversation_id": "conv-3",
        },
        "current_category": 9,  # FYI
        "expected_override": True,
        "expected_trigger": "sole_recipient_mismatch"
    },
    {
        "name": "FYI with Multiple Recipients (no override)",
        "email": {
            "message_id": "4",
            "from_address": "boss@company.com",
            "subject": "Team update",
            "body": "Everyone, here's the update...",
            "to_recipients": json.dumps([
                {"name": "Alice", "address": "alice@company.com"},
                {"name": "Bob", "address": "bob@company.com"},
                {"name": "User", "address": "user@company.com"},
            ]),
            "cc_recipients": json.dumps([]),
            "conversation_id": "conv-4",
        },
        "current_category": 9,  # FYI
        "expected_override": False,
        "expected_trigger": None
    },
    {
        "name": "Travel with Direct Address",
        "email": {
            "message_id": "5",
            "from_address": "noreply@delta.com",
            "subject": "Flight confirmation",
            "body": "Hi User, can you confirm your seat selection?",
            "to_recipients": json.dumps([{"name": "User", "address": "user@company.com"}]),
            "cc_recipients": json.dumps([]),
            "conversation_id": "conv-5",
        },
        "current_category": 11,  # Travel
        "expected_override": True,
        "expected_trigger": "direct_address"
    },
    {
        "name": "Marketing with ASAP",
        "email": {
            "message_id": "6",
            "from_address": "deals@store.com",
            "subject": "Limited time offer",
            "body": "Reply ASAP to claim your discount!",
            "to_recipients": json.dumps([{"name": "User", "address": "user@company.com"}]),
            "cc_recipients": json.dumps([]),
            "conversation_id": "conv-6",
        },
        "current_category": 6,  # Marketing
        "expected_override": True,
        "expected_trigger": "urgency_language"
    },
    {
        "name": "Calendar with Deadline Language",
        "email": {
            "message_id": "7",
            "from_address": "calendar@google.com",
            "subject": "Meeting invitation",
            "body": "Deadline today to RSVP for the meeting...",
            "to_recipients": json.dumps([{"name": "User", "address": "user@company.com"}]),
            "cc_recipients": json.dumps([]),
            "conversation_id": "conv-7",
        },
        "current_category": 8,  # Calendar
        "expected_override": True,
        "expected_trigger": "urgency_language"
    },
    {
        "name": "Regular Marketing - No Override",
        "email": {
            "message_id": "8",
            "from_address": "newsletter@store.com",
            "subject": "New products available",
            "body": "Check out our latest collection...",
            "to_recipients": json.dumps([{"name": "User", "address": "user@company.com"}]),
            "cc_recipients": json.dumps([]),
            "conversation_id": "conv-8",
        },
        "current_category": 6,  # Marketing
        "expected_override": False,
        "expected_trigger": None
    },
]


def main():
    print("=" * 80)
    print("OVERRIDE CLASSIFIER TEST")
    print("=" * 80)
    print()
    print(f"User Email: {USER_EMAIL}")
    print(f"User First Name: {USER_FIRST_NAME}")
    print()

    passed = 0
    failed = 0

    for test in test_cases:
        print(f"Test: {test['name']}")
        print(f"From: {test['email']['from_address']}")
        print(f"Subject: {test['email']['subject']}")
        print(f"Current Category: {test['current_category']}")

        result = check_override(
            test['email'],
            test['current_category'],
            user_email=USER_EMAIL,
            first_name=USER_FIRST_NAME,
            db=None  # No DB session for basic tests
        )

        override = result.get("override", False)
        trigger = result.get("trigger")
        reason = result.get("reason")

        if override:
            print(f"✓ Override: YES")
            print(f"  Trigger: {trigger}")
            print(f"  Reason: {reason}")
        else:
            print(f"✗ Override: NO")

        # Check expectations
        expected_override = test["expected_override"]
        expected_trigger = test["expected_trigger"]

        if override == expected_override:
            if not override or trigger == expected_trigger:
                print("✅ PASS - Result matches expectation")
                passed += 1
            else:
                print(f"❌ FAIL - Expected trigger '{expected_trigger}', got '{trigger}'")
                failed += 1
        else:
            print(f"❌ FAIL - Expected override={expected_override}, got override={override}")
            failed += 1

        print("-" * 80)
        print()

    print("=" * 80)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 80)

    # Test VIP sender (when configured)
    print()
    print("=" * 80)
    print("VIP SENDER TEST (requires manual configuration)")
    print("=" * 80)
    print()
    print("To test VIP sender override:")
    print("1. Edit app/services/classifier_override.py")
    print("2. Add email addresses to VIP_SENDERS list")
    print("3. Add domains to VIP_DOMAINS list")
    print("4. Run this test again")
    print()
    print("Example:")
    print("  VIP_SENDERS = ['boss@company.com', 'ceo@company.com']")
    print("  VIP_DOMAINS = ['executive.company.com']")


if __name__ == "__main__":
    main()
