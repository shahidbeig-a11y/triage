"""
Batch To-Do Sync - Optimized flagging method

Flags all emails first, waits once (10s), then updates all tasks.
Much faster than processing one email at a time.
"""

import requests
import time
from typing import Dict, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"

CATEGORY_LIST_NAMES = {
    1: "1. Blocking",
    2: "2. Action Required",
    3: "3. Waiting On",
    4: "4. Time-Sensitive",
    5: "5. FYI"
}


class TodoSyncError(Exception):
    pass


class TokenExpiredError(TodoSyncError):
    pass


def sync_all_tasks_batch(access_token: str, assigned_emails: List[Dict], db=None) -> Dict:
    """
    Sync assigned emails to Microsoft To-Do using BATCH method.

    Process:
    1. Flag ALL emails (fast)
    2. Wait 10 seconds ONCE
    3. Find and update all tasks

    Args:
        access_token: Microsoft Graph access token
        assigned_emails: List of email dicts with message_id, subject, due_date, etc.
        db: Optional database session for updating todo_task_id

    Returns:
        Dict with sync summary
    """
    synced = 0
    skipped_already_synced = 0
    skipped_no_date = 0
    errors = []

    # Filter emails to sync
    emails_to_sync = []
    for email in assigned_emails:
        if email.get('todo_task_id'):
            skipped_already_synced += 1
            continue
        if not email.get('due_date'):
            skipped_no_date += 1
            continue
        if email.get('category_id') not in CATEGORY_LIST_NAMES:
            skipped_no_date += 1
            continue
        emails_to_sync.append(email)

    if not emails_to_sync:
        return {
            "synced": 0,
            "skipped_already_synced": skipped_already_synced,
            "skipped_no_date": skipped_no_date,
            "lists_created": [],
            "errors": []
        }

    logger.info(f"Batch sync: Flagging {len(emails_to_sync)} emails...")

    # PHASE 1: Flag all emails
    flagged_emails = []
    for email in emails_to_sync:
        message_id = email.get('message_id')
        if not message_id:
            errors.append(f"Email {email.get('email_id')} missing message_id")
            continue

        try:
            flag_url = f"{GRAPH_API_BASE}/me/messages/{message_id}"
            flag_data = {"flag": {"flagStatus": "flagged"}}
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            response = requests.patch(flag_url, headers=headers, json=flag_data, timeout=30)

            if response.status_code == 401:
                raise TokenExpiredError("Access token expired")
            if response.status_code == 404:
                errors.append(f"Email {message_id} not found")
                continue

            response.raise_for_status()
            flagged_emails.append(email)

        except Exception as e:
            errors.append(f"Failed to flag email {email.get('email_id')}: {str(e)}")
            continue

    if not flagged_emails:
        return {
            "synced": 0,
            "skipped_already_synced": skipped_already_synced,
            "skipped_no_date": skipped_no_date,
            "lists_created": [],
            "errors": errors
        }

    # PHASE 2: Wait once for all tasks to be created
    logger.info(f"Waiting 15 seconds for Microsoft to create {len(flagged_emails)} tasks...")
    time.sleep(15)  # Increased from 10 to 15 seconds

    # PHASE 3: Get all tasks and update them
    logger.info("Finding and updating tasks...")

    try:
        # Get default Tasks list
        lists_url = f"{GRAPH_API_BASE}/me/todo/lists"
        lists_response = requests.get(lists_url, headers={
            "Authorization": f"Bearer {access_token}"
        }, timeout=30)
        lists_response.raise_for_status()

        # Look for "Flagged Emails" list first (where flagged emails go)
        # Fall back to default "Tasks" list if not found
        tasks_list_id = None
        tasks_list_name = None

        for task_list in lists_response.json().get('value', []):
            display_name = task_list.get('displayName', '')
            if display_name == 'Flagged Emails':
                tasks_list_id = task_list['id']
                tasks_list_name = display_name
                logger.info("Found 'Flagged Emails' list")
                break

        # Fall back to default list if Flagged Emails not found
        if not tasks_list_id:
            for task_list in lists_response.json().get('value', []):
                if task_list.get('wellknownListName') == 'defaultList':
                    tasks_list_id = task_list['id']
                    tasks_list_name = task_list.get('displayName', 'Tasks')
                    logger.info("Using default 'Tasks' list")
                    break

        if not tasks_list_id:
            raise TodoSyncError("Could not find Flagged Emails or default Tasks list")

        # Get all tasks
        tasks_url = f"{GRAPH_API_BASE}/me/todo/lists/{tasks_list_id}/tasks"
        tasks_response = requests.get(tasks_url, headers={
            "Authorization": f"Bearer {access_token}"
        }, timeout=30)
        tasks_response.raise_for_status()
        all_tasks = tasks_response.json().get('value', [])

        logger.info(f"Found {len(all_tasks)} tasks in '{tasks_list_name}' list")

        # Log all task titles for debugging
        if all_tasks:
            logger.info("Sample task titles found:")
            for i, task in enumerate(all_tasks[:5]):
                logger.info(f"  Task {i+1}: '{task.get('title', '')}'")

        # Build subject index for faster matching
        tasks_by_subject = {}
        for task in all_tasks:
            task_title = task.get('title', '').strip().lower()
            tasks_by_subject[task_title] = task

        logger.info(f"Built index with {len(tasks_by_subject)} unique task titles")

        # Update each flagged email's task
        for email in flagged_emails:
            try:
                original_subject = email.get('subject', '').strip()
                category_id = email.get('category_id')
                email_id = email.get('email_id')

                logger.info(f"Trying to match email {email_id} with subject: '{original_subject}'")

                # Try multiple matching strategies
                task_id = None
                task_title_lower = original_subject.lower()

                # Strategy 1: Exact match
                if task_title_lower in tasks_by_subject:
                    task_id = tasks_by_subject[task_title_lower]['id']
                    logger.info(f"✓ Found task by exact match for email {email_id}")

                # Strategy 2: Prefix match (first 50 chars)
                if not task_id and len(original_subject) > 50:
                    prefix = original_subject[:50].lower()
                    for title, task in tasks_by_subject.items():
                        if title.startswith(prefix):
                            task_id = task['id']
                            logger.debug(f"Found task by prefix match: {original_subject[:50]}")
                            break

                # Strategy 3: Contains match (for tasks with "FW:" or "RE:" prefixes)
                if not task_id:
                    clean_subject = original_subject.replace('RE:', '').replace('FW:', '').replace('Fwd:', '').strip().lower()
                    for title, task in tasks_by_subject.items():
                        clean_title = title.replace('re:', '').replace('fw:', '').replace('fwd:', '').strip()
                        if clean_subject == clean_title or clean_subject in clean_title or clean_title in clean_subject:
                            task_id = task['id']
                            logger.debug(f"Found task by clean match: {original_subject[:50]}")
                            break

                if not task_id:
                    logger.warning(f"Task not found for email {email.get('email_id')} with subject: '{original_subject[:60]}'")
                    logger.debug(f"Available task titles: {list(tasks_by_subject.keys())[:5]}")
                    errors.append(f"Task not found for email {email.get('email_id')}: {original_subject[:60]}")
                    continue

                # Format new title
                category_prefix = {
                    1: "[BLOCKING]",
                    2: "[ACTION]",
                    3: "[WAITING]",
                    4: "[TIME-SENSITIVE]",
                    5: "[FYI]"
                }.get(category_id, "[WORK]")

                priority_marker = "⚠️ " if email.get('floor_override') else ""
                new_title = f"{priority_marker}{category_prefix} {original_subject}"
                if len(new_title) > 255:
                    new_title = new_title[:252] + "..."

                # Prepare update
                update_data = {
                    "title": new_title,
                    "importance": "high" if email.get('urgency_score', 0) >= 70 else "normal"
                }

                # Add due date
                due_date = email.get('due_date')
                if due_date:
                    if isinstance(due_date, datetime):
                        due_date_str = due_date.isoformat()
                    else:
                        due_date_str = due_date
                    if 'T' not in due_date_str:
                        due_date_str = f"{due_date_str}T00:00:00"
                    update_data["dueDateTime"] = {
                        "dateTime": due_date_str,
                        "timeZone": "UTC"
                    }

                # Update task
                update_url = f"{GRAPH_API_BASE}/me/todo/lists/{tasks_list_id}/tasks/{task_id}"
                update_response = requests.patch(update_url, headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                }, json=update_data, timeout=30)

                if update_response.status_code == 401:
                    raise TokenExpiredError("Access token expired")
                update_response.raise_for_status()

                # Update database
                if db:
                    from ..models import Email
                    email_record = db.query(Email).filter(Email.id == email['email_id']).first()
                    if email_record:
                        email_record.todo_task_id = task_id

                synced += 1
                logger.info(f"Updated task for email {email.get('email_id')}")

            except Exception as e:
                errors.append(f"Failed to update task for email {email.get('email_id')}: {str(e)}")
                continue

    except TokenExpiredError:
        raise
    except Exception as e:
        errors.append(f"Failed to process tasks: {str(e)}")

    return {
        "synced": synced,
        "skipped_already_synced": skipped_already_synced,
        "skipped_no_date": skipped_no_date,
        "lists_created": [],
        "errors": errors
    }


def delete_all_todo_lists(access_token: str) -> Dict:
    """
    Delete all flagged tasks (for cleanup/testing).
    Note: This just removes the flag, tasks remain in To-Do.
    """
    return {
        "deleted": 0,
        "list_names": [],
        "errors": []
    }


def clear_cache():
    """Clear cache (no-op for batch method)."""
    pass
