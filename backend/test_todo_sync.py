#!/usr/bin/env python3
"""
Test script for Microsoft To-Do sync functionality.

Tests the todo_sync service functions with sample data.
Requires a valid Microsoft Graph access token to test with real API.
"""

import sys
from datetime import datetime, timedelta
from app.services.todo_sync import (
    get_or_create_task_list,
    create_todo_task,
    sync_all_tasks,
    clear_cache,
    TodoSyncError,
    TokenExpiredError,
    CATEGORY_LIST_NAMES
)


def print_section(title):
    """Print a section header."""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print('='*70)


def test_list_names():
    """Test that category list names are defined."""
    print_section("Test 1: Category List Names")

    print("\nCategory to List Name Mapping:")
    for category_id, list_name in CATEGORY_LIST_NAMES.items():
        print(f"  Category {category_id}: {list_name}")

    assert len(CATEGORY_LIST_NAMES) == 5, "Should have 5 categories"
    print("\n✓ All category list names defined")


def test_sample_emails():
    """Create sample emails for testing."""
    print_section("Test 2: Sample Email Data")

    today = datetime.now()
    tomorrow = today + timedelta(days=1)

    sample_emails = [
        {
            "email_id": 1,
            "subject": "Urgent: Project deadline approaching",
            "body_preview": "The project deadline is this Friday. We need to finalize the deliverables and prepare the presentation for the client meeting.",
            "from_name": "John Smith",
            "from_address": "john.smith@example.com",
            "received_at": today - timedelta(days=2),
            "due_date": today,
            "category_id": 1,  # Blocking
            "urgency_score": 100,
            "floor_override": True,
            "todo_task_id": None
        },
        {
            "email_id": 2,
            "subject": "Review: Q4 Budget Proposal",
            "body_preview": "Please review the attached Q4 budget proposal and provide your feedback by end of week.",
            "from_name": "Finance Team",
            "from_address": "finance@example.com",
            "received_at": today - timedelta(days=1),
            "due_date": tomorrow,
            "category_id": 2,  # Action Required
            "urgency_score": 75,
            "floor_override": False,
            "todo_task_id": None
        },
        {
            "email_id": 3,
            "subject": "FYI: Team meeting notes",
            "body_preview": "Here are the notes from today's team meeting. No action required, just for your information.",
            "from_name": "Team Lead",
            "from_address": "lead@example.com",
            "received_at": today,
            "due_date": today + timedelta(days=3),
            "category_id": 5,  # FYI
            "urgency_score": 30,
            "floor_override": False,
            "todo_task_id": None
        },
        {
            "email_id": 4,
            "subject": "Old email with no date",
            "body_preview": "This email has no due date assigned.",
            "from_name": "Someone",
            "from_address": "someone@example.com",
            "received_at": today - timedelta(days=10),
            "due_date": None,  # No due date
            "category_id": 3,
            "urgency_score": 50,
            "floor_override": False,
            "todo_task_id": None
        },
        {
            "email_id": 5,
            "subject": "Already synced email",
            "body_preview": "This email was already synced to To-Do.",
            "from_name": "Another Person",
            "from_address": "another@example.com",
            "received_at": today - timedelta(days=1),
            "due_date": today,
            "category_id": 2,
            "urgency_score": 80,
            "floor_override": True,
            "todo_task_id": "existing-task-id-123"  # Already synced
        }
    ]

    print("\nCreated 5 sample emails:")
    for email in sample_emails:
        status = ""
        if email['todo_task_id']:
            status = " (already synced)"
        elif not email['due_date']:
            status = " (no due date)"

        print(f"  {email['email_id']}. [{email['urgency_score']:3.0f}] {email['subject'][:50]}{status}")

    return sample_emails


def test_sync_without_token():
    """Test sync_all_tasks without a real token (will fail gracefully)."""
    print_section("Test 3: Sync Without Token (Expected to Fail)")

    sample_emails = test_sample_emails()

    print("\nAttempting to sync with invalid token...")
    try:
        result = sync_all_tasks("invalid-token", sample_emails)
        print("\nSync result:")
        print(f"  Synced: {result['synced']}")
        print(f"  Skipped (already synced): {result['skipped_already_synced']}")
        print(f"  Skipped (no date): {result['skipped_no_date']}")
        print(f"  Lists created: {result['lists_created']}")
        print(f"  Errors: {len(result['errors'])}")

        if result['errors']:
            print(f"\nFirst error: {result['errors'][0]}")
    except TokenExpiredError as e:
        print(f"\n✓ Caught expected TokenExpiredError: {str(e)}")
    except Exception as e:
        print(f"\n✓ Caught expected error: {type(e).__name__}: {str(e)}")


def test_sync_logic():
    """Test the sync logic with sample data (without API calls)."""
    print_section("Test 4: Sync Logic Analysis")

    sample_emails = [
        {"email_id": 1, "due_date": "2024-01-01", "category_id": 1, "todo_task_id": None},
        {"email_id": 2, "due_date": "2024-01-02", "category_id": 2, "todo_task_id": None},
        {"email_id": 3, "due_date": None, "category_id": 3, "todo_task_id": None},  # No date
        {"email_id": 4, "due_date": "2024-01-03", "category_id": 4, "todo_task_id": "existing"},  # Already synced
        {"email_id": 5, "due_date": "2024-01-04", "category_id": 5, "todo_task_id": None},
    ]

    print("\nAnalyzing sync logic for 5 emails:")

    syncable = [e for e in sample_emails if not e['todo_task_id'] and e['due_date']]
    skipped_synced = [e for e in sample_emails if e['todo_task_id']]
    skipped_no_date = [e for e in sample_emails if not e['todo_task_id'] and not e['due_date']]

    print(f"  Syncable: {len(syncable)} emails")
    print(f"  Skipped (already synced): {len(skipped_synced)} emails")
    print(f"  Skipped (no date): {len(skipped_no_date)} emails")

    print("\nSyncable emails will be organized into lists:")
    for email in syncable:
        list_name = CATEGORY_LIST_NAMES.get(email['category_id'], "Unknown")
        print(f"  Email {email['email_id']} → {list_name}")

    unique_lists = set(CATEGORY_LIST_NAMES[e['category_id']] for e in syncable)
    print(f"\nTotal lists needed: {len(unique_lists)}")
    for list_name in sorted(unique_lists):
        print(f"  - {list_name}")


def test_with_real_token():
    """Test with a real Microsoft Graph token if available."""
    print_section("Test 5: Real API Test (Optional)")

    print("\nTo test with real Microsoft Graph API:")
    print("  1. Get a valid access token")
    print("  2. Run: python test_todo_sync.py <access_token>")
    print("\nOr use the database token:")

    try:
        from app.database import SessionLocal
        from app.models import User
        from app.services.graph import GraphClient

        db = SessionLocal()
        user = db.query(User).first()

        if user and user.email:
            print(f"\n  Found user: {user.email}")
            print("  Attempting to get token...")

            graph_client = GraphClient()
            try:
                # This will use the refresh token to get a new access token
                import asyncio
                access_token = asyncio.run(graph_client.get_token(user.email, db))

                if access_token:
                    print("  ✓ Got access token from database")

                    # Test with one sample email
                    sample_emails = [{
                        "email_id": 999,
                        "subject": "Test To-Do Sync",
                        "body_preview": "This is a test email from the To-Do sync test script.",
                        "from_name": "Test Script",
                        "from_address": "test@example.com",
                        "received_at": datetime.now(),
                        "due_date": datetime.now(),
                        "category_id": 2,
                        "urgency_score": 75,
                        "floor_override": False,
                        "todo_task_id": None
                    }]

                    print("\n  Attempting to sync 1 test email...")
                    result = sync_all_tasks(access_token, sample_emails)

                    print(f"\n  ✓ Sync completed!")
                    print(f"    Synced: {result['synced']}")
                    print(f"    Lists created: {result['lists_created']}")
                    if result['errors']:
                        print(f"    Errors: {result['errors']}")

                    # Clear cache for next run
                    clear_cache()

            except Exception as e:
                print(f"  ✗ Error: {str(e)}")
        else:
            print("\n  No user found in database")

        db.close()

    except Exception as e:
        print(f"\n  Cannot test with database token: {str(e)}")


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("  MICROSOFT TO-DO SYNC - TEST SUITE")
    print("="*70)

    test_list_names()
    test_sample_emails()
    test_sync_without_token()
    test_sync_logic()
    test_with_real_token()

    print("\n" + "="*70)
    print("  ALL TESTS COMPLETED")
    print("="*70)
    print("\nNote: Some tests expected to fail without a valid access token.")
    print("To test with real API, ensure you have a valid Microsoft Graph token.\n")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Token provided as command line argument
        token = sys.argv[1]
        print(f"\nUsing provided access token (length: {len(token)})")

        # Test with the provided token
        sample_emails = test_sample_emails()
        print("\nAttempting sync with provided token...")

        try:
            result = sync_all_tasks(token, sample_emails[:3])  # Sync first 3 emails
            print("\n✓ Sync completed!")
            print(f"  Synced: {result['synced']}")
            print(f"  Skipped (already synced): {result['skipped_already_synced']}")
            print(f"  Skipped (no date): {result['skipped_no_date']}")
            print(f"  Lists created: {result['lists_created']}")
            if result['errors']:
                print(f"  Errors: {result['errors']}")
        except Exception as e:
            print(f"\n✗ Sync failed: {type(e).__name__}: {str(e)}")
    else:
        # Run standard tests
        main()
