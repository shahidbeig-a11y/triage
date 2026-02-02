from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import UserSettings

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/")
async def get_settings(db: Session = Depends(get_db)):
    """
    Placeholder: Get user settings.

    Args:
        db: Database session

    Returns:
        dict: User settings object
    """
    # Get or create default settings
    settings = db.query(UserSettings).first()
    if not settings:
        settings = UserSettings()
        db.add(settings)
        db.commit()
        db.refresh(settings)

    return {
        "task_limit": settings.task_limit,
        "urgency_floor": settings.urgency_floor,
        "ai_threshold": settings.ai_threshold,
        "tone_exclusions": settings.tone_exclusions
    }


@router.put("/")
async def update_settings(
    task_limit: int = None,
    urgency_floor: float = None,
    ai_threshold: float = None,
    tone_exclusions: str = None,
    db: Session = Depends(get_db)
):
    """
    Placeholder: Update user settings.

    Args:
        task_limit: Maximum number of tasks to show
        urgency_floor: Minimum urgency score threshold
        ai_threshold: Confidence threshold for auto-classification
        tone_exclusions: JSON string of excluded tone keywords
        db: Database session

    Returns:
        dict: Updated settings object
    """
    settings = db.query(UserSettings).first()
    if not settings:
        settings = UserSettings()
        db.add(settings)

    if task_limit is not None:
        settings.task_limit = task_limit
    if urgency_floor is not None:
        settings.urgency_floor = urgency_floor
    if ai_threshold is not None:
        settings.ai_threshold = ai_threshold
    if tone_exclusions is not None:
        settings.tone_exclusions = tone_exclusions

    db.commit()
    db.refresh(settings)

    return {
        "message": "Settings updated successfully",
        "task_limit": settings.task_limit,
        "urgency_floor": settings.urgency_floor,
        "ai_threshold": settings.ai_threshold,
        "tone_exclusions": settings.tone_exclusions
    }
