"""
Unflag all emails (improved version with detailed error reporting)
"""

import requests
import sys
import time

sys.path.insert(0, '/Users/shahid/Projects/triage/backend')

from app.database import SessionLocal
from app.models import User, Email
from app.services.graph import GraphClient
import asyncio

GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"


def get_todo_task_count(access_token):
    """Get count of tasks in Flagged Emails list"""
    lists_url = f"{GRAPH_API_BASE}/me/todo/lists"
    response = requests.get(lists_url, headers={
        "Authorization": f"Bearer {access_token}"
    })

    if response.status_code != 200:
        return None

    lists = response.json().get('value', [])
    for task_list in lists:
        if task_list.get('displayName') == 'Flagged Emails':
            tasks_url = f"{GRAPH_API_BASE}/me/todo/lists/{task_list['id']}/tasks"
            response = requests.get(tasks_url, headers={
                "Authorization": f"Bearer {access_token}"
            })
            if response.status_code == 200:
                return len(response.json().get('value', []))
    return 0


def unflag_email(access_token, message_id, subject):
    """Remove flag from an email"""
    url = f"{GRAPH_API_BASE}/me/messages/{message_id}"
    data = {
        "flag": {
            "flagStatus": "notFlagged"
        }
    }

    try:
        response = requests.patch(url, headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }, json=data, timeout=30)

        if response.status_code == 200:
            return True, None
        elif response.status_code == 404:
            return False, "Email not found"
        else:
            return False, f"HTTP {response.status_code}: {response.text[:100]}"

    except Exception as e:
        return False, str(e)


async def main():
    db = SessionLocal()
    user = db.query(User).first()

    if not user:
        print("✗ No user found. Please authenticate first.")
        return

    print("="*70)
    print("UNFLAG ALL EMAILS")
    print("="*70)

    # Get access token
    graph = GraphClient()
    access_token = await graph.get_token(user.email, db)

    # Count tasks before
    print("\n1. Checking To-Do tasks BEFORE unflagging...")
    tasks_before = get_todo_task_count(access_token)
    print(f"   ✓ Found {tasks_before} tasks in 'Flagged Emails' list")

    # Get all emails with message_id
    emails = db.query(Email).filter(
        Email.message_id.isnot(None)
    ).all()

    print(f"\n2. Found {len(emails)} emails in database")
    print("   Starting unflag process...\n")

    unflagged_count = 0
    failed_count = 0
    errors = {}

    for i, email in enumerate(emails, 1):
        subject = (email.subject[:50] if email.subject else "No subject")

        success, error = unflag_email(access_token, email.message_id, subject)

        if success:
            unflagged_count += 1
            if unflagged_count % 10 == 0:
                print(f"   Progress: {unflagged_count}/{len(emails)} unflagged...")
        else:
            failed_count += 1
            # Track error types
            error_type = error.split(':')[0] if error else "Unknown"
            errors[error_type] = errors.get(error_type, 0) + 1

            # Show first few failures
            if failed_count <= 3:
                print(f"   ✗ Failed: {subject}")
                print(f"      Error: {error}")

    print(f"\n   ✓ Unflagged: {unflagged_count}")
    if failed_count > 0:
        print(f"   ✗ Failed: {failed_count}")
        print(f"      Error breakdown: {errors}")

    # Wait for sync
    print(f"\n3. Waiting 15 seconds for Microsoft to sync...")
    for i in range(15, 0, -1):
        print(f"   {i}...", end='\r')
        time.sleep(1)
    print("   ✓ Done       ")

    # Count tasks after
    print("\n4. Checking To-Do tasks AFTER unflagging...")
    tasks_after = get_todo_task_count(access_token)
    print(f"   ✓ Found {tasks_after} tasks in 'Flagged Emails' list")

    # Summary
    print("\n" + "="*70)
    print("RESULTS")
    print("="*70)
    print(f"Emails unflagged:     {unflagged_count}/{len(emails)}")
    print(f"To-Do tasks before:   {tasks_before}")
    print(f"To-Do tasks after:    {tasks_after}")
    print(f"Tasks removed:        {tasks_before - tasks_after}")
    print()

    if tasks_after == 0:
        print("✅ SUCCESS: All To-Do tasks removed!")
    elif tasks_after < tasks_before:
        print(f"⚠️  PARTIAL: {tasks_before - tasks_after} removed, {tasks_after} remain")
        print("   Note: Some tasks may take longer to sync")
    else:
        print("✗ ISSUE: Tasks were not removed")
        print("  Possible reasons:")
        print("  - Microsoft may not auto-delete tasks when unflagged")
        print("  - Tasks need to be manually deleted from To-Do")

    print("="*70)

    # Clear database
    print("\n5. Clearing todo_task_id in database...")
    db.query(Email).update({Email.todo_task_id: None})
    db.commit()
    print("   ✓ Database cleared")

    db.close()


if __name__ == "__main__":
    asyncio.run(main())
