from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import time
from ..database import get_db
from ..models import Email, User, ClassificationLog, OverrideLog
from ..services.graph import GraphClient
from ..services.classifier_deterministic import classify_deterministic
from ..services.classifier_override import check_override
from ..services.classifier_ai import classify_with_ai
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


@router.post("/check-overrides")
async def check_overrides_batch(db: Session = Depends(get_db)):
    """
    Check for overrides on already-classified emails in categories 6-11.

    This endpoint is useful for:
    - Testing override logic on existing classifications
    - Re-running override checks after updating VIP lists
    - Auditing which emails should be reconsidered for Work pipeline

    Fetches all emails with status='classified' and category_id in [6,7,8,9,11],
    runs override detection, and resets any that trigger an override.

    Args:
        db: Database session

    Returns:
        dict: Summary with total checked, overridden count, and breakdown by trigger type
    """
    # Get the authenticated user
    user = db.query(User).first()
    user_email = user.email if user else None
    # TODO: Get user's first name from user.display_name or settings
    user_first_name = "User"  # Hardcoded for now

    # Fetch all classified emails in categories 6-11 (Other categories)
    classified_emails = db.query(Email).filter(
        Email.status == "classified",
        Email.category_id.in_([6, 7, 8, 9, 11])
    ).all()

    total_checked = len(classified_emails)
    overridden_count = 0
    trigger_breakdown = {}

    # Process each email
    for email in classified_emails:
        # Convert SQLAlchemy model to dict for override checker
        email_dict = {
            "message_id": email.message_id,
            "from_address": email.from_address,
            "from_name": email.from_name,
            "subject": email.subject,
            "body": email.body,
            "body_preview": email.body_preview,
            "to_recipients": email.to_recipients,
            "cc_recipients": email.cc_recipients,
            "conversation_id": email.conversation_id,
            "importance": email.importance,
            "has_attachments": email.has_attachments,
        }

        # Check for override
        override_result = check_override(
            email_dict,
            email.category_id,
            user_email=user_email,
            first_name=user_first_name,
            db=db
        )

        if override_result.get("override"):
            original_category = email.category_id

            # Reset to unprocessed for AI classification
            email.category_id = None
            email.confidence = None
            email.status = "unprocessed"

            # Log the override
            override_log = OverrideLog(
                email_id=email.id,
                original_category=original_category,
                trigger_type=override_result["trigger"],
                reason=override_result["reason"],
                timestamp=datetime.utcnow()
            )
            db.add(override_log)

            # Update breakdown
            overridden_count += 1
            trigger_type = override_result["trigger"]
            trigger_breakdown[trigger_type] = trigger_breakdown.get(trigger_type, 0) + 1

    # Commit all changes
    db.commit()

    return {
        "total_checked": total_checked,
        "overridden": overridden_count,
        "remaining_classified": total_checked - overridden_count,
        "trigger_breakdown": trigger_breakdown,
        "message": f"Checked {total_checked} classified emails. {overridden_count} overridden to Work pipeline."
    }


@router.post("/classify-deterministic")
async def classify_deterministic_batch(db: Session = Depends(get_db)):
    """
    Run deterministic classification on all unprocessed emails with override checking.

    Fetches all emails with status='unprocessed' and attempts to classify them
    using header-based and sender-based rules. After classification, checks if
    emails in "Other" categories (6-11) should be overridden back to Work pipeline
    based on urgency, VIP sender, or personal direction.

    Successfully classified emails are updated with category_id, confidence,
    and status='classified'. Overridden emails are reset to 'unprocessed' for
    AI classification.

    Args:
        db: Database session

    Returns:
        dict: Summary with total processed, classified count, remaining count,
              overridden count, and breakdown by category
    """
    # Get the authenticated user (for recipient checking and override detection)
    user = db.query(User).first()
    user_email = user.email if user else None
    # TODO: Get user's first name from user.display_name or settings
    user_first_name = "User"  # Hardcoded for now

    # Fetch all unprocessed emails
    unprocessed_emails = db.query(Email).filter(
        Email.status == "unprocessed"
    ).all()

    total_processed = len(unprocessed_emails)
    classified_count = 0
    overridden_count = 0
    breakdown = {
        "6_marketing": 0,
        "7_notification": 0,
        "8_calendar": 0,
        "9_fyi": 0,
        "11_travel": 0,
    }

    # Process each email
    for email in unprocessed_emails:
        # Convert SQLAlchemy model to dict for classifier
        email_dict = {
            "message_id": email.message_id,
            "from_address": email.from_address,
            "from_name": email.from_name,
            "subject": email.subject,
            "body": email.body,
            "body_preview": email.body_preview,
            "to_recipients": email.to_recipients,
            "cc_recipients": email.cc_recipients,
            "conversation_id": email.conversation_id,
            "importance": email.importance,
            "has_attachments": email.has_attachments,
        }

        # Try deterministic classification
        result = classify_deterministic(email_dict, user_email)

        if result:
            # Classification successful - check for override
            category_id = result["category_id"]
            confidence = result["confidence"]
            rule = result["rule"]

            # Check if this should be overridden to Work pipeline
            override_result = check_override(
                email_dict,
                category_id,
                user_email=user_email,
                first_name=user_first_name,
                db=db
            )

            if override_result.get("override"):
                # Override triggered - reset to unprocessed for AI
                email.category_id = None
                email.status = "unprocessed"

                # Log the override
                override_log = OverrideLog(
                    email_id=email.id,
                    original_category=category_id,
                    trigger_type=override_result["trigger"],
                    reason=override_result["reason"],
                    timestamp=datetime.utcnow()
                )
                db.add(override_log)

                overridden_count += 1
            else:
                # Keep deterministic classification
                email.category_id = category_id
                email.confidence = confidence
                email.status = "classified"

                # Create classification log entry
                log_entry = ClassificationLog(
                    email_id=email.id,
                    category_id=category_id,
                    rule=rule,
                    classifier_type="deterministic",
                    confidence=confidence,
                    created_at=datetime.utcnow()
                )
                db.add(log_entry)

                # Update breakdown
                classified_count += 1
                category_key = {
                    6: "6_marketing",
                    7: "7_notification",
                    8: "8_calendar",
                    9: "9_fyi",
                    11: "11_travel"
                }.get(category_id)

                if category_key:
                    breakdown[category_key] += 1

    # Commit all changes
    db.commit()

    remaining = total_processed - classified_count

    return {
        "total_processed": total_processed,
        "classified": classified_count,
        "overridden": overridden_count,
        "remaining": remaining,
        "breakdown": breakdown,
        "message": f"Classified {classified_count} out of {total_processed} emails. {overridden_count} overridden to Work. {remaining} emails need AI classification."
    }


@router.post("/classify-ai")
async def classify_ai_batch(db: Session = Depends(get_db)):
    """
    Classify unprocessed emails using Claude AI.

    Processes all emails with status='unprocessed' (emails that weren't caught
    by deterministic classifier or were overridden) using Claude 3.5 Sonnet.

    Processes in batches of 10 with 0.5s delay between API calls to respect
    rate limits. Classifies into Work categories (1-5):
    - 1: Blocking
    - 2: Action Required
    - 3: Waiting On
    - 4: Time-Sensitive
    - 5: FYI

    Args:
        db: Database session

    Returns:
        dict: Summary with total processed, classified count, failed count,
              breakdown by category, and estimated API cost
    """
    # Fetch all unprocessed emails
    unprocessed_emails = db.query(Email).filter(
        Email.status == "unprocessed"
    ).all()

    total_processed = len(unprocessed_emails)
    classified_count = 0
    failed_count = 0

    breakdown = {
        "1_blocking": 0,
        "2_action_required": 0,
        "3_waiting_on": 0,
        "4_time_sensitive": 0,
        "5_fyi": 0,
    }

    # Process in batches of 10 to avoid overwhelming the API
    BATCH_SIZE = 10
    DELAY_BETWEEN_CALLS = 0.5  # seconds

    for i, email in enumerate(unprocessed_emails):
        try:
            # Convert SQLAlchemy model to dict for AI classifier
            email_dict = {
                "message_id": email.message_id,
                "from_address": email.from_address,
                "from_name": email.from_name,
                "subject": email.subject,
                "body": email.body,
                "body_preview": email.body_preview,
                "to_recipients": email.to_recipients,
                "cc_recipients": email.cc_recipients,
                "conversation_id": email.conversation_id,
                "received_at": email.received_at,
                "importance": email.importance,
                "has_attachments": email.has_attachments,
            }

            # Call AI classifier
            result = classify_with_ai(email_dict)

            # Update email record
            email.category_id = result["category_id"]
            email.confidence = result["confidence"]
            email.status = "classified"

            # Create classification log entry
            log_entry = ClassificationLog(
                email_id=email.id,
                category_id=result["category_id"],
                rule=result["reasoning"],
                classifier_type="ai",
                confidence=result["confidence"],
                created_at=datetime.utcnow()
            )
            db.add(log_entry)

            # Update breakdown
            classified_count += 1
            category_key = {
                1: "1_blocking",
                2: "2_action_required",
                3: "3_waiting_on",
                4: "4_time_sensitive",
                5: "5_fyi"
            }.get(result["category_id"])

            if category_key:
                breakdown[category_key] += 1

            # Commit after each successful classification to avoid losing progress
            db.commit()

            # Add delay between API calls (except after the last email)
            if i < len(unprocessed_emails) - 1:
                time.sleep(DELAY_BETWEEN_CALLS)

        except Exception as e:
            # Log error but continue processing other emails
            failed_count += 1
            print(f"Error classifying email {email.id}: {str(e)}")

            # Rollback this email's changes
            db.rollback()

            # Add delay even on error to respect rate limits
            if i < len(unprocessed_emails) - 1:
                time.sleep(DELAY_BETWEEN_CALLS)

    # Calculate estimated API cost
    # Rough estimate: $0.004 per email (based on ~800 input + 100 output tokens)
    COST_PER_EMAIL = 0.004
    estimated_cost = classified_count * COST_PER_EMAIL

    return {
        "total_processed": total_processed,
        "classified": classified_count,
        "failed": failed_count,
        "breakdown": breakdown,
        "api_cost_estimate": f"${estimated_cost:.2f}",
        "message": f"Classified {classified_count} out of {total_processed} emails using AI. {failed_count} failed. Estimated cost: ${estimated_cost:.2f}"
    }
