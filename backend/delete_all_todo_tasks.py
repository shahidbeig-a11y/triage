"""
Directly delete all tasks from Flagged Emails list
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


async def delete_all_todo_tasks():
    db = SessionLocal()
    user = db.query(User).first()

    if not user:
        print("No user found. Please authenticate first.")
        return

    # Get access token
    graph = GraphClient()
    access_token = await graph.get_token(user.email, db)

    # Get Flagged Emails list
    print("Finding 'Flagged Emails' list...")
    lists_url = f"{GRAPH_API_BASE}/me/todo/lists"
    response = requests.get(lists_url, headers={
        "Authorization": f"Bearer {access_token}"
    })

    if response.status_code != 200:
        print(f"Error getting lists: {response.status_code}")
        return

    lists = response.json().get('value', [])
    flagged_list_id = None

    for task_list in lists:
        display_name = task_list.get('displayName', '')
        print(f"  Found list: {display_name}")
        if display_name == 'Flagged Emails':
            flagged_list_id = task_list['id']

    if not flagged_list_id:
        print("\n✗ No 'Flagged Emails' list found")
        return

    print(f"\n✓ Found 'Flagged Emails' list")

    # Get all tasks
    print("\nFetching all tasks...")
    tasks_url = f"{GRAPH_API_BASE}/me/todo/lists/{flagged_list_id}/tasks"
    response = requests.get(tasks_url, headers={
        "Authorization": f"Bearer {access_token}"
    })

    if response.status_code != 200:
        print(f"Error getting tasks: {response.status_code}")
        return

    tasks = response.json().get('value', [])
    print(f"✓ Found {len(tasks)} tasks\n")

    if len(tasks) == 0:
        print("No tasks to delete!")
        return

    # Delete each task
    print("Deleting tasks...")
    deleted = 0
    failed = 0

    for i, task in enumerate(tasks, 1):
        task_id = task['id']
        task_title = task.get('title', 'No title')

        try:
            delete_url = f"{GRAPH_API_BASE}/me/todo/lists/{flagged_list_id}/tasks/{task_id}"
            response = requests.delete(delete_url, headers={
                "Authorization": f"Bearer {access_token}"
            }, timeout=30)

            if response.status_code in [204, 200]:
                deleted += 1
                if deleted % 10 == 0:
                    print(f"  Deleted {deleted}/{len(tasks)} tasks...")
            else:
                failed += 1
                print(f"  Failed to delete: {task_title[:50]} (status: {response.status_code})")

        except Exception as e:
            failed += 1
            print(f"  Error deleting task: {str(e)}")

    print(f"\n✓ Deleted {deleted} tasks")
    if failed > 0:
        print(f"✗ Failed to delete {failed} tasks")

    # Clear database
    print("\nClearing todo_task_id in database...")
    db.query(Email).update({Email.todo_task_id: None})
    db.commit()
    print("✓ Database cleared")

    # Verify
    print("\nVerifying...")
    response = requests.get(tasks_url, headers={
        "Authorization": f"Bearer {access_token}"
    })
    remaining = len(response.json().get('value', []))

    print(f"✓ {remaining} tasks remaining in 'Flagged Emails' list")

    if remaining == 0:
        print("\n✅ SUCCESS: All tasks deleted!")
    else:
        print(f"\n⚠️  {remaining} tasks still remain")

    db.close()


if __name__ == "__main__":
    asyncio.run(delete_all_todo_tasks())
