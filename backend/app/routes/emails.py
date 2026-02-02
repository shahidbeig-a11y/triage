from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from ..database import get_db
from ..models import Email, User
from ..services.graph import GraphClient
import json

router = APIRouter(prefix="/api/emails", tags=["emails"])


@router.post("/fetch")
async def fetch_emails(
    count: int = Query(default=50, ge=1, le=200, description="Number of emails to fetch"),
    db: Session = Depends(get_db)
):
    """
    Fetch emails from Microsoft Graph API and store them in the database.

    Args:
        count: Number of emails to fetch (1-200)
        db: Database session

    Returns:
        dict: Number of emails fetched and number of new emails stored
    """
    # Get the authenticated user (in production, use session/JWT)
    user = db.query(User).first()
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated. Please log in first.")

    try:
        # Get valid access token
        graph_client = GraphClient()
        access_token = await graph_client.get_token(user.email, db)

        # Fetch emails from Graph API
        emails = await graph_client.fetch_inbox_emails(access_token, count)

        # Store emails in database
        new_count = graph_client.store_emails(emails, db)

        return {
            "fetched": len(emails),
            "new": new_count,
            "message": f"Fetched {len(emails)} emails, {new_count} new emails added to database"
        }

    except Exception as e:
        error_message = str(e)
        if "Token expired" in error_message or "re-authenticate" in error_message:
            raise HTTPException(status_code=401, detail=error_message)
        raise HTTPException(status_code=500, detail=f"Failed to fetch emails: {error_message}")


@router.get("/")
async def list_emails(
    limit: int = Query(default=20, ge=1, le=100, description="Number of emails to return"),
    offset: int = Query(default=0, ge=0, description="Number of emails to skip"),
    folder: Optional[str] = Query(default=None, description="Filter by folder (inbox, archive, deleted)"),
    status: Optional[str] = Query(default=None, description="Filter by status (unprocessed, processed, archived)"),
    db: Session = Depends(get_db)
):
    """
    Get stored emails from the database with pagination.

    Args:
        limit: Maximum number of emails to return (1-100)
        offset: Number of emails to skip for pagination
        folder: Optional folder filter
        status: Optional status filter
        db: Database session

    Returns:
        dict: List of emails and pagination info
    """
    # Build query
    query = db.query(Email)

    if folder:
        query = query.filter(Email.folder == folder)

    if status:
        query = query.filter(Email.status == status)

    # Order by received date (most recent first)
    query = query.order_by(Email.received_at.desc())

    # Get total count
    total = query.count()

    # Apply pagination
    emails = query.offset(offset).limit(limit).all()

    # Convert emails to dicts and parse JSON fields
    email_list = []
    for email in emails:
        email_dict = {
            "id": email.id,
            "message_id": email.message_id,
            "from_address": email.from_address,
            "from_name": email.from_name,
            "subject": email.subject,
            "body_preview": email.body_preview,
            "body": email.body,
            "received_at": email.received_at.isoformat() if email.received_at else None,
            "importance": email.importance,
            "conversation_id": email.conversation_id,
            "has_attachments": email.has_attachments,
            "is_read": email.is_read,
            "to_recipients": json.loads(email.to_recipients) if email.to_recipients else [],
            "cc_recipients": json.loads(email.cc_recipients) if email.cc_recipients else [],
            "folder": email.folder,
            "status": email.status,
            "category_id": email.category_id,
            "confidence": email.confidence,
            "urgency_score": email.urgency_score,
        }
        email_list.append(email_dict)

    return {
        "emails": email_list,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + limit < total
    }


@router.post("/{email_id}/classify")
async def classify_email(email_id: int, db: Session = Depends(get_db)):
    """
    Placeholder: Classify a single email using Claude AI.

    Args:
        email_id: ID of the email to classify
        db: Database session

    Returns:
        dict: Classification result with category and confidence
    """
    # TODO: Implement Claude API integration for email classification
    email = db.query(Email).filter(Email.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")

    return {
        "message": "Classification endpoint - to be implemented",
        "email_id": email_id,
        "category": None,
        "confidence": 0.0
    }


@router.post("/{email_id}/score")
async def score_urgency(email_id: int, db: Session = Depends(get_db)):
    """
    Placeholder: Calculate urgency score for an email.

    Args:
        email_id: ID of the email to score
        db: Database session

    Returns:
        dict: Urgency score and factors
    """
    # TODO: Implement urgency scoring engine
    email = db.query(Email).filter(Email.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")

    return {
        "message": "Urgency scoring endpoint - to be implemented",
        "email_id": email_id,
        "urgency_score": 0.0,
        "factors": []
    }
