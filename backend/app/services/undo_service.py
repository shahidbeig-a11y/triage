"""
Undo Service - Reverses user actions

Tracks and reverses actions including:
- Email approvals
- Email executions (categories, flags, To-Do tasks, folder moves)
- Reclassifications
- Batch operations
"""

import json
import requests
from typing import Dict, List
from datetime import datetime
from sqlalchemy.orm import Session
from ..models import ActionHistory, Email, User

GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"


def record_action(
    db: Session,
    action_type: str,
    description: str,
    action_data: Dict,
    user_id: int = None
) -> int:
    """
    Record an action in history for potential undo.

    Args:
        db: Database session
        action_type: Type of action (approve, execute, reclassify, etc.)
        description: Human-readable description
        action_data: Dict with all data needed to undo the action
        user_id: User who performed the action

    Returns:
        Action ID
    """
    action = ActionHistory(
        action_type=action_type,
        description=description,
        action_data=json.dumps(action_data),
        user_id=user_id
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    return action.id


def get_recent_actions(db: Session, limit: int = 5) -> List[Dict]:
    """
    Get recent actions that can be undone.

    Args:
        db: Database session
        limit: Number of recent actions to return

    Returns:
        List of action dicts with id, type, description, created_at
    """
    actions = db.query(ActionHistory).order_by(
        ActionHistory.created_at.desc()
    ).limit(limit).all()

    return [
        {
            "id": action.id,
            "action_type": action.action_type,
            "description": action.description,
            "created_at": action.created_at.isoformat(),
        }
        for action in actions
    ]


async def undo_action(db: Session, action_id: int, access_token: str) -> Dict:
    """
    Undo a recorded action.

    Reverses all changes made by the action:
    - Email status changes
    - Category changes
    - Outlook categories
    - Email flags
    - To-Do tasks
    - Folder moves

    Args:
        db: Database session
        action_id: ID of action to undo
        access_token: Microsoft Graph access token

    Returns:
        Dict with undo results
    """
    action = db.query(ActionHistory).filter(ActionHistory.id == action_id).first()
    if not action:
        return {"success": False, "error": "Action not found"}

    action_data = json.loads(action.action_data)
    results = {
        "success": True,
        "action_type": action.action_type,
        "description": action.description,
        "emails_reverted": 0,
        "errors": []
    }

    try:
        if action.action_type == "execute":
            results = await _undo_execute(db, action_data, access_token)
        elif action.action_type == "approve":
            results = _undo_approve(db, action_data)
        elif action.action_type == "reclassify":
            results = _undo_reclassify(db, action_data)
        elif action.action_type == "batch_move":
            results = await _undo_batch_move(db, action_data, access_token)
        elif action.action_type == "batch_delete":
            results = await _undo_batch_delete(db, action_data, access_token)
        else:
            results["success"] = False
            results["error"] = f"Unknown action type: {action.action_type}"

        # Delete the action from history after successful undo
        if results["success"]:
            db.delete(action)
            db.commit()

    except Exception as e:
        results["success"] = False
        results["error"] = str(e)

    return results


async def _undo_execute(db: Session, action_data: Dict, access_token: str) -> Dict:
    """
    Undo an execute action.

    Reverses:
    - Status change from 'actioned' back to 'approved'
    - Outlook category removal
    - Email unflagging
    - To-Do task deletion
    - Folder moves
    """
    results = {
        "success": True,
        "emails_reverted": 0,
        "outlook_categories_removed": 0,
        "emails_unflagged": 0,
        "todos_deleted": 0,
        "emails_moved_back": 0,
        "errors": []
    }

    email_ids = action_data.get("email_ids", [])

    for email_data in email_ids:
        email_id = email_data["email_id"]
        email = db.query(Email).filter(Email.id == email_id).first()

        if not email:
            results["errors"].append(f"Email {email_id} not found")
            continue

        try:
            # Revert status
            email.status = "approved"

            # Remove Outlook category if it was applied
            if email_data.get("category_applied"):
                await _remove_outlook_category(
                    access_token,
                    email.message_id,
                    email_data["category_name"]
                )
                results["outlook_categories_removed"] += 1

            # Unflag email in Outlook if it was flagged
            if email_data.get("email_flagged"):
                await _unflag_email(access_token, email.message_id)
                results["emails_unflagged"] += 1

            # Delete To-Do task if it was created
            if email.todo_task_id and email_data.get("todo_created"):
                await _delete_todo_task(
                    access_token,
                    email_data["todo_list_id"],
                    email.todo_task_id
                )
                email.todo_task_id = None
                results["todos_deleted"] += 1

            # Move email back from folder if it was moved
            if email_data.get("folder_moved"):
                await _move_email_back(
                    access_token,
                    email.message_id,
                    email_data["original_folder"]
                )
                email.folder = email_data["original_folder"]
                results["emails_moved_back"] += 1

            results["emails_reverted"] += 1

        except Exception as e:
            results["errors"].append(f"Email {email_id}: {str(e)}")

    db.commit()
    return results


def _undo_approve(db: Session, action_data: Dict) -> Dict:
    """
    Undo an approve action.

    Reverses:
    - Status change from 'approved' back to 'classified'
    - Category changes
    - Due date changes
    - Folder changes
    """
    results = {
        "success": True,
        "emails_reverted": 0,
        "errors": []
    }

    email_ids = action_data.get("email_ids", [])

    for email_data in email_ids:
        email_id = email_data["email_id"]
        email = db.query(Email).filter(Email.id == email_id).first()

        if not email:
            results["errors"].append(f"Email {email_id} not found")
            continue

        try:
            # Revert to previous values
            email.status = email_data["previous_status"]
            email.category_id = email_data.get("previous_category_id")
            email.due_date = email_data.get("previous_due_date")
            email.folder = email_data.get("previous_folder")
            email.assigned_to = email_data.get("previous_assigned_to")

            results["emails_reverted"] += 1

        except Exception as e:
            results["errors"].append(f"Email {email_id}: {str(e)}")

    db.commit()
    return results


def _undo_reclassify(db: Session, action_data: Dict) -> Dict:
    """
    Undo a reclassify action.

    Reverses:
    - Category change back to original
    """
    results = {
        "success": True,
        "emails_reverted": 0,
        "errors": []
    }

    email_id = action_data["email_id"]
    email = db.query(Email).filter(Email.id == email_id).first()

    if not email:
        results["success"] = False
        results["error"] = f"Email {email_id} not found"
        return results

    try:
        email.category_id = action_data["previous_category_id"]
        email.confidence = action_data.get("previous_confidence", email.confidence)
        results["emails_reverted"] = 1
        db.commit()

    except Exception as e:
        results["success"] = False
        results["error"] = str(e)

    return results


async def _remove_outlook_category(access_token: str, message_id: str, category_name: str):
    """Remove a category from an email in Outlook."""
    import httpx

    async with httpx.AsyncClient() as client:
        # Get current categories
        get_response = await client.get(
            f"{GRAPH_API_BASE}/me/messages/{message_id}",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"$select": "categories"}
        )

        if get_response.status_code == 200:
            current_categories = get_response.json().get("categories", [])
            # Remove the category
            updated_categories = [cat for cat in current_categories if cat != category_name]

            # Update email
            await client.patch(
                f"{GRAPH_API_BASE}/me/messages/{message_id}",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                },
                json={"categories": updated_categories}
            )


async def _unflag_email(access_token: str, message_id: str):
    """Remove flag from an email in Outlook."""
    import httpx

    async with httpx.AsyncClient() as client:
        await client.patch(
            f"{GRAPH_API_BASE}/me/messages/{message_id}",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            },
            json={"flag": {"flagStatus": "notFlagged"}}
        )


async def _delete_todo_task(access_token: str, list_id: str, task_id: str):
    """Delete a To-Do task."""
    import httpx

    async with httpx.AsyncClient() as client:
        await client.delete(
            f"{GRAPH_API_BASE}/me/todo/lists/{list_id}/tasks/{task_id}",
            headers={"Authorization": f"Bearer {access_token}"}
        )


async def _move_email_back(access_token: str, immutable_id: str, folder_name: str):
    """Move email back to original folder (inbox) using immutableId."""
    import httpx
    import logging
    from urllib.parse import quote

    logger = logging.getLogger(__name__)
    print(f"\n[MOVE EMAIL BACK] Called for immutable_id: {immutable_id}")

    async with httpx.AsyncClient() as client:
        # Get folders to find inbox
        folders_response = await client.get(
            f"{GRAPH_API_BASE}/me/mailFolders",
            headers={"Authorization": f"Bearer {access_token}"}
        )

        if folders_response.status_code != 200:
            error_msg = f"Failed to fetch folders: {folders_response.status_code}"
            logger.error(error_msg)
            raise Exception(error_msg)

        folders = folders_response.json().get("value", [])
        inbox_id = None

        for folder in folders:
            if folder["displayName"].lower() == "inbox":
                inbox_id = folder["id"]
                break

        if not inbox_id:
            error_msg = "Could not find Inbox folder"
            logger.error(error_msg)
            print(f"[MOVE EMAIL BACK] ERROR: {error_msg}")
            raise Exception(error_msg)

        # URL-encode the immutableId for use in the API endpoint
        encoded_id = quote(immutable_id, safe='')

        # Move email back to inbox using immutableId
        logger.info(f"Moving email (immutable_id) back to Inbox")
        print(f"[MOVE EMAIL BACK] Found Inbox ID: {inbox_id}")
        print(f"[MOVE EMAIL BACK] Moving message (immutable_id: {immutable_id[:50]}...) to Inbox...")

        # Use the immutableId in the endpoint
        move_response = await client.post(
            f"{GRAPH_API_BASE}/me/messages/{encoded_id}/move",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "Prefer": 'IdType="ImmutableId"'  # Tell Graph API we're using immutableId
            },
            json={"destinationId": inbox_id}
        )

        print(f"[MOVE EMAIL BACK] Move response status: {move_response.status_code}")

        if move_response.status_code in [200, 201]:
            logger.info(f"Successfully moved email back to Inbox")
            print(f"[MOVE EMAIL BACK] ✓ SUCCESS - Email moved to Inbox")
        elif move_response.status_code == 404:
            error_msg = f"Email (immutable_id: {immutable_id[:50]}...) not found in Outlook"
            logger.warning(error_msg)
            print(f"[MOVE EMAIL BACK] ✗ ERROR 404: {error_msg}")
            raise Exception(error_msg)
        else:
            error_msg = f"Failed to move email: {move_response.status_code} - {move_response.text}"
            logger.error(error_msg)
            print(f"[MOVE EMAIL BACK] ✗ ERROR {move_response.status_code}: {error_msg}")
            raise Exception(error_msg)


async def _undo_batch_move(db: Session, action_data: Dict, access_token: str) -> Dict:
    """
    Undo a batch move action.

    Moves all emails back to Inbox and reverts status to 'classified'.
    """
    import logging
    logger = logging.getLogger(__name__)

    results = {
        "success": True,
        "emails_reverted": 0,
        "emails_moved_back": 0,
        "errors": []
    }

    email_ids = action_data.get("email_ids", [])
    logger.info(f"[UNDO BATCH MOVE] Starting undo for {len(email_ids)} emails")
    print(f"\n[UNDO BATCH MOVE] Starting undo for {len(email_ids)} emails")
    print(f"[UNDO BATCH MOVE] Email IDs: {email_ids}")

    for email_id in email_ids:
        email = db.query(Email).filter(Email.id == email_id).first()

        if not email:
            error_msg = f"Email {email_id} not found in database"
            logger.warning(f"[UNDO BATCH MOVE] {error_msg}")
            results["errors"].append(error_msg)
            continue

        try:
            logger.info(f"[UNDO BATCH MOVE] Processing email {email_id} (immutable_id: {email.immutable_id})")

            # Check if we have immutable_id
            if not email.immutable_id:
                error_msg = f"Email {email_id} has no immutable_id (old email, cannot undo folder move)"
                logger.warning(f"[UNDO BATCH MOVE] {error_msg}")
                results["errors"].append(error_msg)
                # Still revert database status
                email.status = "classified"
                email.folder = "inbox"
                results["emails_reverted"] += 1
                continue

            # Move email back to Inbox in Outlook FIRST using immutableId
            await _move_email_back(access_token, email.immutable_id, "inbox")
            results["emails_moved_back"] += 1
            logger.info(f"[UNDO BATCH MOVE] ✓ Moved email {email_id} back to Inbox in Outlook")

            # Then revert database status
            email.status = "classified"
            email.folder = "inbox"
            results["emails_reverted"] += 1
            logger.info(f"[UNDO BATCH MOVE] ✓ Reverted email {email_id} status in database")

        except Exception as e:
            error_msg = f"Email {email_id}: {str(e)}"
            logger.error(f"[UNDO BATCH MOVE] ✗ Failed: {error_msg}")
            results["errors"].append(error_msg)

    db.commit()
    logger.info(f"[UNDO BATCH MOVE] Completed: {results['emails_reverted']} reverted, {results['emails_moved_back']} moved back, {len(results['errors'])} errors")
    return results


async def _undo_batch_delete(db: Session, action_data: Dict, access_token: str) -> Dict:
    """
    Undo a batch delete action.

    Moves all emails back from trash to Inbox and reverts status to 'classified'.
    """
    import logging
    logger = logging.getLogger(__name__)

    results = {
        "success": True,
        "emails_reverted": 0,
        "emails_moved_back": 0,
        "errors": []
    }

    email_ids = action_data.get("email_ids", [])
    logger.info(f"[UNDO BATCH DELETE] Starting undo for {len(email_ids)} emails")

    for email_id in email_ids:
        email = db.query(Email).filter(Email.id == email_id).first()

        if not email:
            error_msg = f"Email {email_id} not found in database"
            logger.warning(f"[UNDO BATCH DELETE] {error_msg}")
            results["errors"].append(error_msg)
            continue

        try:
            logger.info(f"[UNDO BATCH DELETE] Processing email {email_id} (immutable_id: {email.immutable_id})")

            # Check if we have immutable_id
            if not email.immutable_id:
                error_msg = f"Email {email_id} has no immutable_id (old email, cannot undo folder move)"
                logger.warning(f"[UNDO BATCH DELETE] {error_msg}")
                results["errors"].append(error_msg)
                # Still revert database status
                email.status = "classified"
                email.folder = "inbox"
                results["emails_reverted"] += 1
                continue

            # Move email back to Inbox from trash in Outlook FIRST using immutableId
            await _move_email_back(access_token, email.immutable_id, "inbox")
            results["emails_moved_back"] += 1
            logger.info(f"[UNDO BATCH DELETE] ✓ Moved email {email_id} back to Inbox in Outlook")

            # Then revert database status
            email.status = "classified"
            email.folder = "inbox"
            results["emails_reverted"] += 1
            logger.info(f"[UNDO BATCH DELETE] ✓ Reverted email {email_id} status in database")

        except Exception as e:
            error_msg = f"Email {email_id}: {str(e)}"
            logger.error(f"[UNDO BATCH DELETE] ✗ Failed: {error_msg}")
            results["errors"].append(error_msg)

    db.commit()
    logger.info(f"[UNDO BATCH DELETE] Completed: {results['emails_reverted']} reverted, {results['emails_moved_back']} moved back, {len(results['errors'])} errors")
    return results
