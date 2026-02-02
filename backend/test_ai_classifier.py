"""
Test script for AI classifier (simulated responses).

This demonstrates what the AI classifier would return for different email types.
Since we can't call the actual API without a key, this shows expected behavior.
"""

import json


# Simulated responses from Claude API for different email types
test_cases = [
    {
        "name": "Blocking - Production Down",
        "email": {
            "from_name": "DevOps Team",
            "from_address": "devops@company.com",
            "subject": "URGENT: Production API down - need immediate approval",
            "body": "Our production API is down affecting all customers. We have a fix ready but need your approval to deploy. Please respond ASAP.",
            "to_recipients": json.dumps([{"name": "User", "address": "user@company.com"}]),
            "cc_recipients": json.dumps([]),
            "importance": "high",
        },
        "expected_response": {
            "category_id": 1,
            "category_name": "Blocking",
            "confidence": 0.95,
            "reasoning": "Production outage with team blocked waiting for approval. Clear blocking situation requiring immediate action."
        }
    },
    {
        "name": "Action Required - Review Request",
        "email": {
            "from_name": "Colleague",
            "from_address": "colleague@company.com",
            "subject": "Can you review this pull request?",
            "body": "Hey, I've finished implementing the new feature. Can you review the PR when you get a chance? No rush, but would be great to get your feedback.",
            "to_recipients": json.dumps([{"name": "User", "address": "user@company.com"}]),
            "cc_recipients": json.dumps([]),
            "importance": "normal",
        },
        "expected_response": {
            "category_id": 2,
            "category_name": "Action Required",
            "confidence": 0.85,
            "reasoning": "Direct request for code review. This is a to-do action that requires effort beyond just replying."
        }
    },
    {
        "name": "Action Required - Question Needs Reply",
        "email": {
            "from_name": "Manager",
            "from_address": "manager@company.com",
            "subject": "Quick question about Q4 priorities",
            "body": "What's your opinion on prioritizing the mobile app vs web dashboard for Q4? Need to finalize our roadmap this week.",
            "to_recipients": json.dumps([{"name": "User", "address": "user@company.com"}]),
            "cc_recipients": json.dumps([]),
            "importance": "normal",
        },
        "expected_response": {
            "category_id": 2,
            "category_name": "Action Required",
            "confidence": 0.80,
            "reasoning": "Direct question requiring thoughtful response. This is a reply action with some time sensitivity."
        }
    },
    {
        "name": "Waiting On - Status Update",
        "email": {
            "from_name": "Vendor",
            "from_address": "support@vendor.com",
            "subject": "Re: Support ticket #12345",
            "body": "Thanks for reporting this issue. Our engineering team is investigating and we'll get back to you within 24 hours with an update.",
            "to_recipients": json.dumps([{"name": "User", "address": "user@company.com"}]),
            "cc_recipients": json.dumps([]),
            "importance": "normal",
        },
        "expected_response": {
            "category_id": 3,
            "category_name": "Waiting On",
            "confidence": 0.90,
            "reasoning": "Confirmation that they're working on the issue and will follow up. Clear waiting state."
        }
    },
    {
        "name": "Time-Sensitive - Deadline Reminder",
        "email": {
            "from_name": "HR Department",
            "from_address": "hr@company.com",
            "subject": "Reminder: Benefits enrollment ends Friday",
            "body": "This is a reminder that open enrollment for benefits ends this Friday, October 15th. Please complete your selections by EOD.",
            "to_recipients": json.dumps([{"name": "User", "address": "user@company.com"}]),
            "cc_recipients": json.dumps([]),
            "importance": "normal",
        },
        "expected_response": {
            "category_id": 4,
            "category_name": "Time-Sensitive",
            "confidence": 0.85,
            "reasoning": "Specific deadline mentioned (Friday) but not blocking anyone. Needs attention soon."
        }
    },
    {
        "name": "FYI - Newsletter",
        "email": {
            "from_name": "Team Lead",
            "from_address": "lead@company.com",
            "subject": "FYI: Team accomplishments this month",
            "body": "Hi team, just wanted to share some great accomplishments from this month: [list of achievements]. Keep up the great work!",
            "to_recipients": json.dumps([
                {"name": "Team", "address": "team@company.com"}
            ]),
            "cc_recipients": json.dumps([{"name": "User", "address": "user@company.com"}]),
            "importance": "normal",
        },
        "expected_response": {
            "category_id": 5,
            "category_name": "FYI",
            "confidence": 0.90,
            "reasoning": "Informational update with 'FYI' in subject. User is CC'd and no action is required."
        }
    },
    {
        "name": "Ambiguous - Could be Action or FYI",
        "email": {
            "from_name": "Colleague",
            "from_address": "colleague@company.com",
            "subject": "Heads up about the new policy",
            "body": "Hey, just wanted to let you know about the new expense policy. It might affect how you submit your travel expenses. Take a look at the attached document when you have time.",
            "to_recipients": json.dumps([{"name": "User", "address": "user@company.com"}]),
            "cc_recipients": json.dumps([]),
            "importance": "normal",
        },
        "expected_response": {
            "category_id": 2,
            "category_name": "Action Required",
            "confidence": 0.60,
            "reasoning": "Suggests reviewing attached document which requires action, though not urgent. Moderate confidence due to soft language ('when you have time')."
        }
    },
]


def main():
    print("=" * 80)
    print("AI CLASSIFIER TEST (SIMULATED RESPONSES)")
    print("=" * 80)
    print()
    print("NOTE: These are simulated responses showing expected behavior.")
    print("To test with real API, set ANTHROPIC_API_KEY in .env and run with actual client.")
    print()

    for i, test in enumerate(test_cases, 1):
        print(f"Test {i}: {test['name']}")
        print("-" * 80)
        print(f"From: {test['email']['from_address']}")
        print(f"Subject: {test['email']['subject']}")
        print(f"Body: {test['email']['body'][:100]}...")
        print()

        response = test['expected_response']
        print(f"Expected Classification:")
        print(f"  Category: {response['category_id']} - {response['category_name']}")
        print(f"  Confidence: {response['confidence']}")
        print(f"  Reasoning: {response['reasoning']}")
        print()

    print("=" * 80)
    print("CATEGORY SUMMARY")
    print("=" * 80)
    print()
    print("1. BLOCKING      - Critical blockers, immediate action needed")
    print("2. ACTION REQ    - Tasks to complete or questions to answer")
    print("3. WAITING ON    - Waiting for others, no action needed now")
    print("4. TIME-SENSITIVE - Has deadline but not blocking")
    print("5. FYI           - Informational only, no action needed")
    print()

    print("=" * 80)
    print("CONFIDENCE LEVELS")
    print("=" * 80)
    print()
    print("0.9-1.0  - Very clear (obvious category)")
    print("0.7-0.89 - Clear (strong indicators)")
    print("0.5-0.69 - Moderate (some ambiguity)")
    print("0.3-0.49 - Low (uncertain)")
    print()

    print("=" * 80)
    print("TO RUN WITH REAL API:")
    print("=" * 80)
    print()
    print("1. Add ANTHROPIC_API_KEY to .env file")
    print("2. Install anthropic SDK: pip install anthropic")
    print("3. Use classify_with_ai() function:")
    print()
    print("   from app.services import classify_with_ai")
    print("   result = classify_with_ai(email_dict)")
    print("   print(result)  # {'category_id': 2, 'confidence': 0.85, ...}")


if __name__ == "__main__":
    main()
