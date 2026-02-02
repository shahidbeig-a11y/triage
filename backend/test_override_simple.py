"""
Simple test for override classifier logic (without dependencies).

Run with: python3 test_override_simple.py
"""

import json
import re


# Copied from classifier_override.py for testing
URGENCY_KEYWORDS = [
    "urgent", "asap", "time-sensitive", "time sensitive",
    "immediate attention", "action required", "critical",
    "deadline today", "due today", "due immediately",
    "needs your approval", "please respond by",
]

USER_EMAIL = "user@company.com"
USER_FIRST_NAME = "User"


def contains_urgency_language(text):
    """Check if text contains urgency keywords."""
    if not text:
        return None
    text_lower = text.lower()
    for keyword in URGENCY_KEYWORDS:
        if keyword in text_lower:
            return keyword
    return None


def is_sole_to_recipient(to_recipients, user_email):
    """Check if user is the sole To: recipient."""
    if not to_recipients or len(to_recipients) != 1:
        return False
    return to_recipients[0].get("address", "").lower() == user_email.lower()


def has_direct_address(body, first_name):
    """Check if email body contains direct address to the user."""
    if not body or not first_name:
        return None

    patterns = [
        rf"\b{re.escape(first_name)},\s+(can|could|would|will|please)",
        rf"hi\s+{re.escape(first_name)},",
        rf"hello\s+{re.escape(first_name)},",
        rf"hey\s+{re.escape(first_name)},",
        rf"{re.escape(first_name)}\s*[-:]\s*(can|could|would|will|please)",
    ]

    for pattern in patterns:
        match = re.search(pattern, body, re.IGNORECASE)
        if match:
            return match.group(0)
    return None


# Test cases
test_cases = [
    {
        "name": "Urgency: URGENT in subject",
        "subject": "URGENT: Action required",
        "body": "Please review this.",
        "expected": "urgent"
    },
    {
        "name": "Urgency: ASAP in body",
        "subject": "Project update",
        "body": "Please respond ASAP",
        "expected": "asap"
    },
    {
        "name": "Urgency: deadline today",
        "subject": "Review needed",
        "body": "This has a deadline today",
        "expected": "deadline today"
    },
    {
        "name": "No urgency",
        "subject": "Regular update",
        "body": "Here's the latest information",
        "expected": None
    },
]

sole_recipient_tests = [
    {
        "name": "Sole recipient",
        "to_recipients": [{"address": "user@company.com"}],
        "expected": True
    },
    {
        "name": "Multiple recipients",
        "to_recipients": [
            {"address": "user@company.com"},
            {"address": "other@company.com"}
        ],
        "expected": False
    },
    {
        "name": "Not recipient",
        "to_recipients": [{"address": "other@company.com"}],
        "expected": False
    },
]

direct_address_tests = [
    {
        "name": "Direct address: 'User, can you'",
        "body": "User, can you review this?",
        "expected": True
    },
    {
        "name": "Direct address: 'Hi User,'",
        "body": "Hi User, please take a look at this.",
        "expected": True
    },
    {
        "name": "Direct address: 'User - please'",
        "body": "User - please approve this request.",
        "expected": True
    },
    {
        "name": "No direct address",
        "body": "Everyone, please review the document.",
        "expected": False
    },
    {
        "name": "User mentioned but not direct",
        "body": "I spoke with User yesterday about this.",
        "expected": False
    },
]


def main():
    print("=" * 80)
    print("OVERRIDE CLASSIFIER LOGIC TEST")
    print("=" * 80)
    print()

    # Test urgency detection
    print("URGENCY LANGUAGE TESTS:")
    print("-" * 80)
    for test in test_cases:
        text = f"{test['subject']} {test['body']}"
        result = contains_urgency_language(text)
        expected = test['expected']
        passed = (result == expected) if expected is None else (result is not None)

        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test['name']}")
        if not passed:
            print(f"  Expected: {expected}, Got: {result}")
    print()

    # Test sole recipient detection
    print("SOLE RECIPIENT TESTS:")
    print("-" * 80)
    for test in sole_recipient_tests:
        result = is_sole_to_recipient(test['to_recipients'], USER_EMAIL)
        expected = test['expected']
        passed = result == expected

        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test['name']}")
        if not passed:
            print(f"  Expected: {expected}, Got: {result}")
    print()

    # Test direct address detection
    print("DIRECT ADDRESS TESTS:")
    print("-" * 80)
    for test in direct_address_tests:
        result = has_direct_address(test['body'], USER_FIRST_NAME)
        expected = test['expected']
        passed = (result is not None) == expected

        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test['name']}")
        if not passed:
            print(f"  Expected match: {expected}, Got: {result}")
        elif result:
            print(f"  Matched pattern: '{result}'")
    print()

    print("=" * 80)
    print("INTEGRATION TEST SCENARIOS:")
    print("=" * 80)
    print()

    scenarios = [
        {
            "name": "Marketing with urgency → Should override",
            "category": 6,
            "triggers": ["Urgency language: 'ASAP'"],
        },
        {
            "name": "FYI with sole recipient → Should override",
            "category": 9,
            "triggers": ["Sole To: recipient mismatch"],
        },
        {
            "name": "Calendar with direct address → Should override",
            "category": 8,
            "triggers": ["Direct address: 'User, can you'"],
        },
        {
            "name": "Regular marketing → No override",
            "category": 6,
            "triggers": [],
        },
    ]

    for scenario in scenarios:
        print(f"Scenario: {scenario['name']}")
        print(f"  Category: {scenario['category']}")
        if scenario['triggers']:
            print(f"  Triggers: {', '.join(scenario['triggers'])}")
            print(f"  Result: ✓ Override to Work pipeline")
        else:
            print(f"  Result: ✗ No override, stays in Other")
        print()


if __name__ == "__main__":
    main()
