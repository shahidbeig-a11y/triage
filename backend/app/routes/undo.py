"""
Undo API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict
from ..database import get_db
from ..models import User
from ..services.graph import GraphClient
from ..services.undo_service import get_recent_actions, undo_action

router = APIRouter(prefix="/api/undo", tags=["undo"])


@router.get("/actions")
async def list_recent_actions(
    limit: int = 5,
    db: Session = Depends(get_db)
) -> Dict:
    """
    Get list of recent actions that can be undone.

    Args:
        limit: Number of recent actions (max 5)
        db: Database session

    Returns:
        List of recent actions with id, type, description, timestamp
    """
    if limit > 5:
        limit = 5

    actions = get_recent_actions(db, limit)

    return {
        "actions": actions,
        "total": len(actions)
    }


@router.post("/actions/{action_id}")
async def undo_specific_action(
    action_id: int,
    db: Session = Depends(get_db)
) -> Dict:
    """
    Undo a specific action by ID.

    Reverses all changes made by the action:
    - Email status
    - Categories
    - Outlook categories
    - Flags
    - To-Do tasks
    - Folder moves

    Args:
        action_id: ID of action to undo
        db: Database session

    Returns:
        Undo results
    """
    # Get user and access token
    user = db.query(User).first()
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        print(f"\n{'='*60}")
        print(f"[UNDO ENDPOINT] Starting undo for action_id: {action_id}")
        print(f"{'='*60}\n")

        graph_client = GraphClient()
        access_token = await graph_client.get_token(user.email, db)

        result = await undo_action(db, action_id, access_token)

        print(f"\n{'='*60}")
        print(f"[UNDO ENDPOINT] Undo result for action_id {action_id}:")
        print(f"  Success: {result.get('success')}")
        print(f"  Emails reverted: {result.get('emails_reverted', 0)}")
        print(f"  Emails moved back: {result.get('emails_moved_back', 0)}")
        print(f"  Errors: {result.get('errors', [])}")
        print(f"{'='*60}\n")

        if not result["success"]:
            raise HTTPException(status_code=400, detail=result.get("error", "Undo failed"))

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to undo action: {str(e)}")
