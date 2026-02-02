"""
Debug script to check what tasks exist in Microsoft To-Do
"""

import requests
import sys

def check_todo_tasks(access_token):
    """Check what tasks exist in the default Tasks list"""

    GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"

    # Get task lists
    lists_url = f"{GRAPH_API_BASE}/me/todo/lists"
    response = requests.get(lists_url, headers={
        "Authorization": f"Bearer {access_token}"
    })

    if response.status_code != 200:
        print(f"Error getting lists: {response.status_code}")
        print(response.text)
        return

    lists = response.json().get('value', [])
    print(f"Found {len(lists)} task lists")

    # Find default list
    default_list = None
    for task_list in lists:
        list_name = task_list.get('displayName')
        is_default = task_list.get('wellknownListName') == 'defaultList'
        print(f"  - {list_name} (default={is_default})")
        if is_default:
            default_list = task_list

    if not default_list:
        print("No default list found!")
        return

    # Get tasks from default list
    list_id = default_list['id']
    tasks_url = f"{GRAPH_API_BASE}/me/todo/lists/{list_id}/tasks"
    response = requests.get(tasks_url, headers={
        "Authorization": f"Bearer {access_token}"
    })

    if response.status_code != 200:
        print(f"Error getting tasks: {response.status_code}")
        print(response.text)
        return

    tasks = response.json().get('value', [])
    print(f"\nFound {len(tasks)} tasks in default list:")

    for i, task in enumerate(tasks[:10], 1):
        title = task.get('title', '')
        status = task.get('status', '')
        print(f"{i}. '{title}' (status: {status})")

    if len(tasks) > 10:
        print(f"... and {len(tasks) - 10} more tasks")

if __name__ == "__main__":
    # Get access token from database
    import sys
    sys.path.insert(0, '/Users/shahid/Projects/triage/backend')

    from app.database import SessionLocal
    from app.models import User
    from app.services.graph import GraphClient
    import asyncio

    db = SessionLocal()
    user = db.query(User).first()

    if not user:
        print("No user found. Please authenticate first.")
        sys.exit(1)

    async def get_token():
        graph = GraphClient()
        return await graph.get_token(user.email, db)

    token = asyncio.run(get_token())
    check_todo_tasks(token)

    db.close()
