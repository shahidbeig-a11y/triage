#!/usr/bin/env python3
"""
Test script for the urgency scoring engine.

Tests all 8 signal extractors with various email scenarios.
"""

from datetime import datetime, timedelta
from app.services.scoring import score_email

# Test cases covering different urgency scenarios
TEST_EMAILS = [
    {
        "name": "Urgent deadline today",
        "email": {
            "subject": "URGENT: Report due by EOD",
            "body": "Please submit the quarterly report by end of day today.",
            "body_preview": "Please submit the quarterly report by end of day today.",
            "from_address": "boss@company.com",
            "importance": "high",
            "received_at": datetime.utcnow() - timedelta(hours=3),
            "conversation_id": "conv_urgent_1",
            "category_id": 2,
        }
    },
    {
        "name": "External client request",
        "email": {
            "subject": "Re: Project timeline discussion",
            "body": "Following up on our meeting. When can we expect the deliverables?",
            "body_preview": "Following up on our meeting.",
            "from_address": "client@external.com",
            "importance": "normal",
            "received_at": datetime.utcnow() - timedelta(hours=1),
            "conversation_id": "conv_client_1",
            "category_id": 2,
        }
    },
    {
        "name": "Old email waiting for response",
        "email": {
            "subject": "Question about budget approval",
            "body": "Can you approve the budget request I sent last week?",
            "body_preview": "Can you approve the budget request",
            "from_address": "teammate@live.com",
            "importance": "normal",
            "received_at": datetime.utcnow() - timedelta(days=4),
            "conversation_id": "conv_old_1",
            "category_id": 2,
        }
    },
    {
        "name": "Low priority FYI",
        "email": {
            "subject": "FYI: Team update - no action needed",
            "body": "Just keeping you in the loop. Read when you have a chance.",
            "body_preview": "Just keeping you in the loop",
            "from_address": "hr@live.com",
            "importance": "low",
            "received_at": datetime.utcnow() - timedelta(minutes=30),
            "conversation_id": "conv_fyi_1",
            "category_id": 5,
        }
    },
    {
        "name": "Time-sensitive with specific date",
        "email": {
            "subject": "Action required: Sign documents by Friday",
            "body": "Please review and sign the attached documents by this Friday.",
            "body_preview": "Please review and sign the attached documents",
            "from_address": "legal@company.com",
            "importance": "normal",
            "received_at": datetime.utcnow() - timedelta(hours=12),
            "conversation_id": "conv_legal_1",
            "category_id": 4,
        }
    },
    {
        "name": "Hot thread - multiple replies",
        "email": {
            "subject": "Re: Critical bug in production",
            "body": "We need to address this immediately. The system is down.",
            "body_preview": "We need to address this immediately",
            "from_address": "engineer@company.com",
            "importance": "high",
            "received_at": datetime.utcnow() - timedelta(minutes=15),
            "conversation_id": "conv_hot_1",
            "category_id": 1,
        }
    },
    {
        "name": "Overdue followup",
        "email": {
            "subject": "Following up - deadline was yesterday",
            "body": "Just checking in. The deadline for this was February 1st.",
            "body_preview": "Just checking in",
            "from_address": "manager@company.com",
            "importance": "normal",
            "received_at": datetime.utcnow() - timedelta(days=2),
            "conversation_id": "conv_overdue_1",
            "category_id": 4,
        }
    },
    {
        "name": "Normal internal email",
        "email": {
            "subject": "Question about meeting schedule",
            "body": "What time works best for you next week?",
            "body_preview": "What time works best for you",
            "from_address": "colleague@live.com",
            "importance": "normal",
            "received_at": datetime.utcnow() - timedelta(hours=6),
            "conversation_id": "conv_normal_1",
            "category_id": 2,
        }
    },
]


def print_separator():
    print("\n" + "=" * 80 + "\n")


def print_score_result(name, result):
    """Print formatted scoring result."""
    print(f"📧 {name}")
    print(f"   Urgency Score: {result['urgency_score']}/100")
    print(f"\n   Signal Breakdown:")

    for signal, score in result['signals'].items():
        weight = result['weights'][signal]
        weighted = result['breakdown'][f"{signal}_weighted"]
        print(f"   • {signal:20s}: {score:4d} × {weight:.2f} = {weighted:5.2f}")

    print_separator()


def main():
    """Run scoring tests on all test emails."""
    print_separator()
    print("🎯 URGENCY SCORING ENGINE TEST")
    print_separator()

    print("Testing 8 signal extractors:")
    print("1. Explicit Deadline - Finds dates in text")
    print("2. Sender Seniority - Checks VIP status")
    print("3. Importance Flag - Uses Graph API flag")
    print("4. Urgency Language - Detects keywords")
    print("5. Thread Velocity - Measures reply rate (requires DB)")
    print("6. Client External - Prioritizes external senders")
    print("7. Age of Email - Older = more urgent")
    print("8. Followup Overdue - Checks overdue Category 4 emails")
    print_separator()

    # Score all test emails (without DB for thread velocity)
    results = []
    for test_case in TEST_EMAILS:
        name = test_case["name"]
        email = test_case["email"]

        result = score_email(email, db=None, user_domain="live.com")
        results.append((name, result))
        print_score_result(name, result)

    # Summary
    print("\n📊 SUMMARY - Ranked by Urgency")
    print_separator()

    # Sort by urgency score
    sorted_results = sorted(results, key=lambda x: x[1]['urgency_score'], reverse=True)

    for rank, (name, result) in enumerate(sorted_results, 1):
        score = result['urgency_score']
        top_signals = sorted(
            result['signals'].items(),
            key=lambda x: x[1],
            reverse=True
        )[:3]

        top_signal_names = [s[0] for s in top_signals if s[1] > 0]

        print(f"{rank}. {name:40s} Score: {score:3d}/100")
        if top_signal_names:
            print(f"   Top signals: {', '.join(top_signal_names)}")
        print()

    print_separator()
    print("✅ All tests completed!")
    print("\nNote: Thread velocity signal requires database connection.")
    print("To test with DB: Run from an endpoint with db session.")


if __name__ == "__main__":
    main()
