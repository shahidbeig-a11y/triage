"""
Simulate the /classify-ai endpoint response.

This shows what the API would return when classifying unprocessed emails with AI.
"""

import json
import time


def simulate_ai_classification():
    """Simulate the AI classification endpoint behavior."""

    print("=" * 80)
    print("SIMULATE POST /api/emails/classify-ai")
    print("=" * 80)
    print()

    # Simulate unprocessed emails
    unprocessed_emails = [
        {
            "id": 1,
            "from_address": "colleague@company.com",
            "subject": "Can you review this PR?",
            "body": "Hey, I've finished the feature. Can you take a look?",
            "expected_category": 2,  # Action Required
        },
        {
            "id": 2,
            "from_address": "manager@company.com",
            "subject": "What's your opinion on Q4 priorities?",
            "body": "Need your input on whether to prioritize mobile vs web.",
            "expected_category": 2,  # Action Required
        },
        {
            "id": 3,
            "from_address": "devops@company.com",
            "subject": "URGENT: Production API down",
            "body": "Production is down. Need immediate approval to deploy fix.",
            "expected_category": 1,  # Blocking
        },
        {
            "id": 4,
            "from_address": "vendor@company.com",
            "subject": "Re: Support ticket #12345",
            "body": "Thanks for reporting. Our team is investigating and will get back to you.",
            "expected_category": 3,  # Waiting On
        },
        {
            "id": 5,
            "from_address": "hr@company.com",
            "subject": "Reminder: Benefits enrollment ends Friday",
            "body": "Please complete your benefits selections by EOD Friday.",
            "expected_category": 4,  # Time-Sensitive
        },
        {
            "id": 6,
            "from_address": "teammate@company.com",
            "subject": "FYI: Deployed new feature",
            "body": "Just letting you know I deployed the new dashboard feature to prod.",
            "expected_category": 5,  # FYI
        },
        {
            "id": 7,
            "from_address": "client@client.com",
            "subject": "Quick question about the API",
            "body": "How do I authenticate with the API? Need to integrate by next week.",
            "expected_category": 2,  # Action Required
        },
        {
            "id": 8,
            "from_address": "boss@company.com",
            "subject": "Need your approval on budget",
            "body": "Can you approve the Q4 budget? CFO needs it by tomorrow.",
            "expected_category": 4,  # Time-Sensitive
        },
        {
            "id": 9,
            "from_address": "engineer@company.com",
            "subject": "Re: Database migration plan",
            "body": "I'll handle the migration this weekend. Will keep you posted.",
            "expected_category": 3,  # Waiting On
        },
        {
            "id": 10,
            "from_address": "security@company.com",
            "subject": "CRITICAL: Security vulnerability detected",
            "body": "Critical vulnerability in production. Need immediate action.",
            "expected_category": 1,  # Blocking
        },
    ]

    print(f"Processing {len(unprocessed_emails)} unprocessed emails...")
    print()

    # Simulate processing
    classified_count = 0
    failed_count = 0
    breakdown = {
        "1_blocking": 0,
        "2_action_required": 0,
        "3_waiting_on": 0,
        "4_time_sensitive": 0,
        "5_fyi": 0,
    }

    DELAY = 0.5
    start_time = time.time()

    for i, email in enumerate(unprocessed_emails, 1):
        print(f"[{i}/{len(unprocessed_emails)}] Classifying: {email['subject']}")
        print(f"  From: {email['from_address']}")

        # Simulate API call delay
        time.sleep(DELAY)

        # Simulate successful classification
        category_id = email["expected_category"]
        category_names = {
            1: "Blocking",
            2: "Action Required",
            3: "Waiting On",
            4: "Time-Sensitive",
            5: "FYI"
        }

        print(f"  ✓ Classified as: {category_id} - {category_names[category_id]}")

        classified_count += 1
        category_key = {
            1: "1_blocking",
            2: "2_action_required",
            3: "3_waiting_on",
            4: "4_time_sensitive",
            5: "5_fyi"
        }.get(category_id)

        if category_key:
            breakdown[category_key] += 1

        print()

    elapsed_time = time.time() - start_time

    # Calculate cost
    COST_PER_EMAIL = 0.004
    estimated_cost = classified_count * COST_PER_EMAIL

    # Print response
    print("=" * 80)
    print("RESPONSE:")
    print("=" * 80)

    response = {
        "total_processed": len(unprocessed_emails),
        "classified": classified_count,
        "failed": failed_count,
        "breakdown": breakdown,
        "api_cost_estimate": f"${estimated_cost:.2f}",
        "message": f"Classified {classified_count} out of {len(unprocessed_emails)} emails using AI. {failed_count} failed. Estimated cost: ${estimated_cost:.2f}"
    }

    print(json.dumps(response, indent=2))
    print()

    print("=" * 80)
    print("STATISTICS:")
    print("=" * 80)
    print(f"Processing time: {elapsed_time:.1f} seconds")
    print(f"Average time per email: {elapsed_time / len(unprocessed_emails):.1f} seconds")
    print(f"Emails per minute: {len(unprocessed_emails) / (elapsed_time / 60):.0f}")
    print(f"Cost per email: ${COST_PER_EMAIL:.4f}")
    print(f"Total cost: ${estimated_cost:.2f}")
    print()

    print("=" * 80)
    print("CATEGORY BREAKDOWN:")
    print("=" * 80)
    for key, count in breakdown.items():
        category_name = key.split("_", 1)[1].replace("_", " ").title()
        percentage = (count / classified_count * 100) if classified_count > 0 else 0
        print(f"{category_name:20} {count:3} emails ({percentage:5.1f}%)")
    print()

    print("=" * 80)
    print("DATABASE UPDATES:")
    print("=" * 80)
    print(f"✓ {classified_count} emails updated:")
    print(f"  - status changed from 'unprocessed' to 'classified'")
    print(f"  - category_id assigned (1-5)")
    print(f"  - confidence score added")
    print()
    print(f"✓ {classified_count} classification_log entries created:")
    print(f"  - classifier_type: 'ai'")
    print(f"  - reasoning included")
    print()

    print("=" * 80)
    print("NEXT STEPS:")
    print("=" * 80)
    print("1. All emails are now classified (deterministic + AI)")
    print("2. User can review inbox sorted by priority")
    print("3. Low-confidence emails may need manual review")
    print("4. System learns from user corrections over time")
    print()


if __name__ == "__main__":
    simulate_ai_classification()
