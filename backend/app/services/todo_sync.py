"""
Microsoft To-Do Sync Service

Syncs assigned emails to Microsoft To-Do tasks via the Graph API.
Creates task lists for each work category and individual tasks for each email.
"""

import requests
import time
from typing import Dict, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Module-level cache for task list IDs
_task_list_cache: Dict[str, str] = {}

# Category to list name mapping
CATEGORY_LIST_NAMES = {
    1: "1. Blocking",
    2: "2. Action Required",
    3: "3. Waiting On",
    4: "4. Time-Sensitive",
    5: "5. FYI"
}

# Graph API base URL
GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"


class TodoSyncError(Exception):
    """Base exception for To-Do sync errors."""
    pass


class TokenExpiredError(TodoSyncError):
    """Raised when the access token has expired."""
    pass


class RateLimitError(TodoSyncError):
    """Raised when the API rate limit is exceeded."""
    pass


def _retry_with_backoff(func, max_retries=3, initial_delay=1.0):
    """
    Retry a function with exponential backoff.

    Args:
        func: Function to retry
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds

    Returns:
        Result from successful function call

    Raises:
        Exception from last failed attempt
    """
    delay = initial_delay

    for attempt in range(max_retries):
        try:
            return func()
        except RateLimitError as e:
            if attempt == max_retries - 1:
                raise

            # Extract Retry-After header if available
            retry_after = getattr(e, 'retry_after', None)
            if retry_after:
                delay = float(retry_after)
            else:
                delay = initial_delay * (2 ** attempt)

            logger.warning(f"Rate limit hit, retrying in {delay}s (attempt {attempt + 1}/{max_retries})")
            time.sleep(delay)
        except TokenExpiredError:
            # Don't retry token errors
            raise
        except Exception as e:
            if attempt == max_retries - 1:
                raise

            logger.warning(f"Request failed, retrying in {delay}s (attempt {attempt + 1}/{max_retries}): {str(e)}")
            time.sleep(delay)
            delay *= 2

    raise TodoSyncError("Max retries exceeded")


def _make_graph_request(method: str, url: str, access_token: str, json_data: Optional[Dict] = None) -> Optional[Dict]:
    """
    Make a request to the Microsoft Graph API with error handling.

    Args:
        method: HTTP method (GET, POST, etc.)
        url: Full URL to request
        access_token: Microsoft Graph access token
        json_data: Optional JSON data for POST/PATCH requests

    Returns:
        Response JSON data or None for 404

    Raises:
        TokenExpiredError: If access token is expired
        RateLimitError: If rate limit is exceeded
        TodoSyncError: For other API errors
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    try:
        if method == "GET":
            response = requests.get(url, headers=headers, timeout=30)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=json_data, timeout=30)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        # Handle specific status codes
        if response.status_code == 401:
            raise TokenExpiredError("Access token expired. Please re-authenticate.")

        if response.status_code == 429:
            retry_after = response.headers.get('Retry-After', '60')
            error = RateLimitError(f"Rate limit exceeded. Retry after {retry_after} seconds.")
            error.retry_after = retry_after
            raise error

        if response.status_code == 404:
            # Return None for 404 to allow handling (e.g., list not found)
            logger.warning(f"Resource not found (404): {url}")
            return None

        # Raise for other error status codes
        response.raise_for_status()

        # Return JSON response
        return response.json()

    except requests.exceptions.Timeout:
        raise TodoSyncError("Request timed out")
    except requests.exceptions.RequestException as e:
        if hasattr(e, 'response') and e.response is not None:
            raise TodoSyncError(f"Request failed (status {e.response.status_code}): {str(e)}")
        raise TodoSyncError(f"Request failed: {str(e)}")


def get_or_create_task_list(access_token: str, list_name: str) -> str:
    """
    Get or create a Microsoft To-Do task list.

    Checks if a list with the given name exists. If not, creates it.
    Results are cached to avoid repeated API calls.

    Args:
        access_token: Microsoft Graph access token
        list_name: Display name for the task list

    Returns:
        Task list ID

    Raises:
        TokenExpiredError: If access token is expired
        TodoSyncError: For other API errors
    """
    # Check cache first
    if list_name in _task_list_cache:
        logger.debug(f"Using cached list ID for '{list_name}'")
        return _task_list_cache[list_name]

    # Get all task lists
    url = f"{GRAPH_API_BASE}/me/todo/lists"

    def get_lists():
        return _make_graph_request("GET", url, access_token)

    lists_response = _retry_with_backoff(get_lists)

    # Search for existing list
    if lists_response and 'value' in lists_response:
        for task_list in lists_response['value']:
            if task_list.get('displayName') == list_name:
                list_id = task_list['id']
                _task_list_cache[list_name] = list_id
                logger.info(f"Found existing task list: '{list_name}' (ID: {list_id})")
                return list_id

    # List not found, create it
    logger.info(f"Creating new task list: '{list_name}'")

    create_data = {
        "displayName": list_name
    }

    def create_list():
        return _make_graph_request("POST", url, access_token, create_data)

    create_response = _retry_with_backoff(create_list)

    list_id = create_response['id']
    _task_list_cache[list_name] = list_id
    logger.info(f"Created task list: '{list_name}' (ID: {list_id})")

    return list_id


def create_todo_task(
    access_token: str,
    list_id: str,
    email: Dict,
    urgency_score: float,
    floor_override: bool,
    category_id: int
) -> str:
    """
    Create a Microsoft To-Do task from an email by flagging the email.

    NEW METHOD: Instead of creating tasks directly, this flags the email which
    causes Microsoft to automatically create a To-Do task after ~10 seconds.
    Then we find and update that task with the proper title and due date.

    Args:
        access_token: Microsoft Graph access token
        list_id: Task list ID (not used in new method, kept for compatibility)
        email: Email dict with message_id, subject, due_date, etc.
        urgency_score: Urgency score (0-100)
        floor_override: True if this is a floor/critical item
        category_id: Work category ID (1-5)

    Returns:
        Task ID of the created task

    Raises:
        TokenExpiredError: If access token is expired
        TodoSyncError: For other API errors
    """
    message_id = email.get('message_id')
    if not message_id:
        raise TodoSyncError("Email missing message_id, cannot flag")

    # Format task title with category prefix and priority marker
    category_prefix = {
        1: "[BLOCKING]",
        2: "[ACTION]",
        3: "[WAITING]",
        4: "[TIME-SENSITIVE]",
        5: "[FYI]"
    }.get(category_id, "[WORK]")

    priority_marker = "⚠️ " if floor_override else ""
    subject = email.get('subject', '[No Subject]')
    title = f"{priority_marker}{category_prefix} {subject}"

    # Truncate title if too long (To-Do has a 255 character limit)
    if len(title) > 255:
        title = title[:252] + "..."

    # Step 1: Flag the email
    logger.info(f"Flagging email {message_id}...")
    flag_url = f"{GRAPH_API_BASE}/me/messages/{message_id}"
    flag_data = {
        "flag": {
            "flagStatus": "flagged"
        }
    }

    def flag_email():
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        response = requests.patch(flag_url, headers=headers, json=flag_data, timeout=30)

        if response.status_code == 401:
            raise TokenExpiredError("Access token expired. Please re-authenticate.")

        if response.status_code == 404:
            raise TodoSyncError(f"Email {message_id} not found")

        response.raise_for_status()
        return True

    _retry_with_backoff(flag_email)
    logger.info(f"Email {message_id} flagged successfully")

    # Step 2: Wait for Microsoft to create the To-Do task (~10 seconds)
    logger.info("Waiting 10 seconds for Microsoft to create To-Do task...")
    time.sleep(10)

    # Step 3: Find the auto-created task
    # The task should be in the "Tasks" list (default list) with linkedResources pointing to the email
    logger.info(f"Searching for auto-created task for email {message_id}...")

    # Get the default "Tasks" list
    lists_url = f"{GRAPH_API_BASE}/me/todo/lists"

    def get_lists():
        return _make_graph_request("GET", lists_url, access_token)

    lists_response = _retry_with_backoff(get_lists)

    # Find the default "Tasks" list
    tasks_list_id = None
    for task_list in lists_response.get('value', []):
        if task_list.get('wellknownListName') == 'defaultList':
            tasks_list_id = task_list['id']
            break

    if not tasks_list_id:
        raise TodoSyncError("Could not find default Tasks list")

    # Get all tasks from the Tasks list
    tasks_url = f"{GRAPH_API_BASE}/me/todo/lists/{tasks_list_id}/tasks"

    def get_tasks():
        return _make_graph_request("GET", tasks_url, access_token)

    tasks_response = _retry_with_backoff(get_tasks)

    # Find the task created from our email by matching the subject
    original_subject = email.get('subject', '')
    task_id = None

    for task in tasks_response.get('value', []):
        task_title = task.get('title', '')
        # The auto-created task title should match the original email subject
        if task_title == original_subject or task_title.startswith(original_subject[:50]):
            task_id = task['id']
            logger.info(f"Found auto-created task: {task_id}")
            break

    if not task_id:
        raise TodoSyncError(f"Could not find auto-created task for email {message_id}")

    # Step 4: Update the task with proper title and due date
    logger.info(f"Updating task {task_id} with title and due date...")

    update_url = f"{GRAPH_API_BASE}/me/todo/lists/{tasks_list_id}/tasks/{task_id}"

    update_data = {
        "title": title,
        "importance": "high" if urgency_score >= 70 else "normal"
    }

    # Add due date if present
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

    def update_task():
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        response = requests.patch(update_url, headers=headers, json=update_data, timeout=30)

        if response.status_code == 401:
            raise TokenExpiredError("Access token expired. Please re-authenticate.")

        response.raise_for_status()
        return response.json()

    _retry_with_backoff(update_task)

    logger.info(f"Task {task_id} updated successfully with title: {title[:50]}...")

    return task_id


def sync_all_tasks(access_token: str, assigned_emails: List[Dict], db=None) -> Dict:
    """
    Sync all assigned emails to Microsoft To-Do tasks using BATCH processing.

    BATCH METHOD:
    1. Flag ALL emails first (fast)
    2. Wait 10 seconds ONCE for Microsoft to create tasks
    3. Find and update all tasks in batch

    Args:
        access_token: Microsoft Graph access token
        assigned_emails: List of email dicts with:
                        - email_id
                        - message_id (required for flagging)
                        - subject
                        - body_preview
                        - from_name
                        - from_address
                        - received_at
                        - due_date
                        - category_id
                        - urgency_score
                        - floor_override
                        - todo_task_id (if already synced)
        db: Optional database session for updating todo_task_id

    Returns:
        Dict with sync summary:
        - synced: Number of tasks created
        - skipped_already_synced: Number already synced
        - skipped_no_date: Number without due dates
        - lists_created: List of task list names created
        - errors: List of error messages
    """
    synced = 0
    skipped_already_synced = 0
    skipped_no_date = 0
    lists_created = []
    errors = []

    # Track which lists we've created/accessed in this sync
    lists_accessed = set()
    lists_before_sync = set(_task_list_cache.keys())

    # ========================================================================
    # PHASE 1: FLAG ALL EMAILS (FAST)
    # ========================================================================
    emails_to_sync = []

    for email in assigned_emails:
        # Skip if already synced
        if email.get('todo_task_id'):
            skipped_already_synced += 1
            logger.debug(f"Skipping email {email.get('email_id')} - already synced")
            continue

        # Skip if no due date
        if not email.get('due_date'):
            skipped_no_date += 1
            logger.debug(f"Skipping email {email.get('email_id')} - no due date")
            continue

        # Check category
        category_id = email.get('category_id')
        if category_id not in CATEGORY_LIST_NAMES:
            logger.warning(f"Unknown category_id {category_id} for email {email.get('email_id')}")
            skipped_no_date += 1
            continue

        emails_to_sync.append(email)

    if not emails_to_sync:
        logger.info("No emails to sync")
        return {
            "synced": 0,
            "skipped_already_synced": skipped_already_synced,
            "skipped_no_date": skipped_no_date,
            "lists_created": [],
            "errors": []
        }

    logger.info(f"Flagging {len(emails_to_sync)} emails...")

    # Flag all emails
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
                raise TokenExpiredError("Access token expired. Please re-authenticate.")

            if response.status_code == 404:
                errors.append(f"Email {message_id} not found")
                continue

            response.raise_for_status()
            flagged_emails.append(email)
            logger.debug(f"Flagged email {message_id}")

        except Exception as e:
            error_msg = f"Failed to flag email {email.get('email_id')}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
            continue

    if not flagged_emails:
        logger.warning("No emails were successfully flagged")
        return {
            "synced": 0,
            "skipped_already_synced": skipped_already_synced,
            "skipped_no_date": skipped_no_date,
            "lists_created": [],
            "errors": errors
        }

    # ========================================================================
    # PHASE 2: WAIT FOR MICROSOFT TO CREATE TASKS (10 SECONDS ONCE)
    # ========================================================================
    logger.info(f"Waiting 10 seconds for Microsoft to create {len(flagged_emails)} tasks...")
    time.sleep(10)

    # ========================================================================
    # PHASE 3: FIND AND UPDATE ALL TASKS
    # ========================================================================
    logger.info("Finding and updating auto-created tasks...")

    # Get the default "Tasks" list
    lists_url = f"{GRAPH_API_BASE}/me/todo/lists"

    try:
        lists_response = _make_graph_request("GET", lists_url, access_token)
        tasks_list_id = None

        for task_list in lists_response.get('value', []):
            if task_list.get('wellknownListName') == 'defaultList':
                tasks_list_id = task_list['id']
                break

        if not tasks_list_id:
            raise TodoSyncError("Could not find default Tasks list")

        # Get all tasks from the Tasks list
        tasks_url = f"{GRAPH_API_BASE}/me/todo/lists/{tasks_list_id}/tasks"
        tasks_response = _make_graph_request("GET", tasks_url, access_token)
        all_tasks = tasks_response.get('value', [])

        # Match and update tasks for each flagged email
        for email in flagged_emails:
        try:
            # Skip if already synced
            if email.get('todo_task_id'):
                skipped_already_synced += 1
                logger.debug(f"Skipping email {email.get('email_id')} - already synced")
                continue

            # Skip if no due date
            if not email.get('due_date'):
                skipped_no_date += 1
                logger.debug(f"Skipping email {email.get('email_id')} - no due date")
                continue

            # Get category and list name
            category_id = email.get('category_id')
            if category_id not in CATEGORY_LIST_NAMES:
                logger.warning(f"Unknown category_id {category_id} for email {email.get('email_id')}")
                skipped_no_date += 1
                continue

            list_name = CATEGORY_LIST_NAMES[category_id]

            # Get or create task list
            try:
                list_id = get_or_create_task_list(access_token, list_name)

                # Track if this is a newly created list
                if list_name not in lists_accessed and list_name not in lists_before_sync:
                    lists_created.append(list_name)
                lists_accessed.add(list_name)

            except TokenExpiredError:
                raise  # Re-raise token errors immediately
            except Exception as e:
                error_msg = f"Failed to get/create list '{list_name}': {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
                continue

            # Create the task
            try:
                task_id = create_todo_task(
                    access_token,
                    list_id,
                    email,
                    email.get('urgency_score', 0),
                    email.get('floor_override', False),
                    category_id
                )

                # Update database with task_id if db session provided
                if db:
                    from ..models import Email
                    email_record = db.query(Email).filter(Email.id == email['email_id']).first()
                    if email_record:
                        email_record.todo_task_id = task_id
                        # Note: Caller should commit the session

                synced += 1

            except TokenExpiredError:
                raise  # Re-raise token errors immediately
            except Exception as e:
                error_msg = f"Failed to create task for email {email.get('email_id')}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
                continue

        except Exception as e:
            error_msg = f"Unexpected error processing email {email.get('email_id')}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
            continue

    return {
        "synced": synced,
        "skipped_already_synced": skipped_already_synced,
        "skipped_no_date": skipped_no_date,
        "lists_created": lists_created,
        "errors": errors
    }


def delete_task_list(access_token: str, list_id: str) -> bool:
    """
    Delete a Microsoft To-Do task list.

    Args:
        access_token: Microsoft Graph access token
        list_id: Task list ID to delete

    Returns:
        True if deleted successfully, False otherwise

    Raises:
        TokenExpiredError: If access token is expired
        TodoSyncError: For other API errors
    """
    url = f"{GRAPH_API_BASE}/me/todo/lists/{list_id}"

    try:
        response = requests.delete(url, headers={
            "Authorization": f"Bearer {access_token}"
        }, timeout=30)

        if response.status_code == 401:
            raise TokenExpiredError("Access token expired. Please re-authenticate.")

        if response.status_code == 404:
            logger.warning(f"List {list_id} not found (already deleted?)")
            return True

        if response.status_code == 204:
            logger.info(f"Deleted task list: {list_id}")
            return True

        response.raise_for_status()
        return True

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to delete list {list_id}: {str(e)}")
        return False


def delete_all_todo_lists(access_token: str) -> Dict:
    """
    Delete all Microsoft To-Do task lists that match our category names.

    This is useful for cleaning up duplicates or resetting the To-Do state.
    Only deletes lists with names matching our category patterns.

    Args:
        access_token: Microsoft Graph access token

    Returns:
        Dict with deletion summary:
        - deleted: Number of lists deleted
        - list_names: Names of deleted lists
        - errors: List of error messages
    """
    deleted = 0
    deleted_names = []
    errors = []

    try:
        # Get all task lists
        url = f"{GRAPH_API_BASE}/me/todo/lists"
        response = _make_graph_request("GET", url, access_token)

        if not response or 'value' not in response:
            return {"deleted": 0, "list_names": [], "errors": ["No lists found"]}

        # Find and delete lists matching our category names
        for task_list in response['value']:
            list_name = task_list.get('displayName', '')
            list_id = task_list['id']

            # Only delete lists that match our category naming pattern
            if list_name in CATEGORY_LIST_NAMES.values():
                try:
                    if delete_task_list(access_token, list_id):
                        deleted += 1
                        deleted_names.append(list_name)
                        logger.info(f"Deleted list: {list_name}")

                        # Remove from cache if present
                        if list_name in _task_list_cache:
                            del _task_list_cache[list_name]
                except Exception as e:
                    error_msg = f"Failed to delete list '{list_name}': {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)

    except TokenExpiredError:
        raise
    except Exception as e:
        error_msg = f"Failed to list task lists: {str(e)}"
        logger.error(error_msg)
        errors.append(error_msg)

    return {
        "deleted": deleted,
        "list_names": deleted_names,
        "errors": errors
    }


def clear_cache():
    """Clear the task list cache. Useful for testing or after errors."""
    global _task_list_cache
    _task_list_cache.clear()
    logger.info("Task list cache cleared")
