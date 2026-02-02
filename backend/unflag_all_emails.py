"""
Unflag all emails and check if To-Do tasks are removed
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
        print(f"Error getting lists: {response.status_code}")
        return None

    lists = response.json().get('value', [])
    flagged_list_id = None

    for task_list in lists:
        if task_list.get('displayName') == 'Flagged Emails':
            flagged_list_id = task_list['id']
            break

    if not flagged_list_id:
        print("No 'Flagged Emails' list found")
        return 0

    tasks_url = f"{GRAPH_API_BASE}/me/todo/lists/{flagged_list_id}/tasks"
    response = requests.get(tasks_url, headers={
        "Authorization": f"Bearer {access_token}"
    })

    if response.status_code != 200:
        print(f"Error getting tasks: {response.status_code}")
        return None

    tasks = response.json().get('value', [])
    return len(tasks)


def unflag_email(access_token, message_id):
    """Remove flag from an email"""
    url = f"{GRAPH_API_BASE}/me/messages/{message_id}"
    data = {
        "flag": {
            "flagStatus": "notFlagged"
        }
    }

    response = requests.patch(url, headers={
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }, json=data, timeout=30)

    return response.status_code == 200


async def main():
    db = SessionLocal()
    user = db.query(User).first()

    if not user:
        print("No user found. Please authenticate first.")
        return

    # Get access token
    graph = GraphClient()
    access_token = await graph.get_token(user.email, db)

    # Get count of To-Do tasks before unflagging
    print("Checking To-Do tasks BEFORE unflagging...")
    tasks_before = get_todo_task_count(access_token)
    print(f"✓ Found {tasks_before} tasks in 'Flagged Emails' list\n")

    # Get all emails with message_id
    emails = db.query(Email).filter(
        Email.message_id.isnot(None)
    ).all()

    print(f"Found {len(emails)} emails in database")
    print("Unflagging all emails...\n")

    unflagged_count = 0
    failed_count = 0

    for email in emails:
        try:
            if unflag_email(access_token, email.message_id):
                unflagged_count += 1
                if unflagged_count % 10 == 0:
                    print(f"  Unflagged {unflagged_count} emails...")
            else:
                failed_count += 1
        except Exception as e:
            failed_count += 1
            continue

    print(f"\n✓ Unflagged {unflagged_count} emails")
    if failed_count > 0:
        print(f"✗ Failed to unflag {failed_count} emails")

    # Wait a moment for Microsoft to process
    print("\nWaiting 10 seconds for Microsoft to sync...")
    time.sleep(10)

    # Check To-Do tasks after unflagging
    print("\nChecking To-Do tasks AFTER unflagging...")
    tasks_after = get_todo_task_count(access_token)
    print(f"✓ Found {tasks_after} tasks in 'Flagged Emails' list")

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"To-Do tasks before: {tasks_before}")
    print(f"To-Do tasks after:  {tasks_after}")
    print(f"Difference:         {tasks_before - tasks_after}")
    print()

    if tasks_after == 0:
        print("✅ SUCCESS: All To-Do tasks were removed!")
    elif tasks_after < tasks_before:
        print(f"⚠️  PARTIAL: {tasks_before - tasks_after} tasks removed, {tasks_after} remain")
    else:
        print("✗ ISSUE: Tasks were not removed")

    print("="*60)

    # Clear todo_task_id in database
    print("\nClearing todo_task_id in database...")
    db.query(Email).update({Email.todo_task_id: None})
    db.commit()
    print("✓ Database cleared")

    db.close()


if __name__ == "__main__":
    asyncio.run(main())
