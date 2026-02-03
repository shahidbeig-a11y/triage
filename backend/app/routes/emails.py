from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
import time
import asyncio
import httpx
from ..database import get_db
from ..models import Email, User, ClassificationLog, OverrideLog, Category, UrgencyScore
from ..services.graph import GraphClient
from ..services.classifier_deterministic import classify_deterministic
from ..services.classifier_override import check_override
from ..services.classifier_ai import classify_with_ai
from ..services.pipeline import run_full_pipeline
from ..services.scoring import score_email
from ..services.undo_service import record_action
from ..services.outlook_categories import replace_category_on_email, remove_all_app_categories
from pydantic import BaseModel
import json

router = APIRouter(prefix="/api/emails", tags=["emails"])


def get_work_category_ids(db: Session) -> list:
    """Get list of Work category IDs from database."""
    work_categories = db.query(Category).filter(Category.master_category == "Work").all()
    return [cat.id for cat in work_categories]


class ReclassifyRequest(BaseModel):
    category_id: int


class ApproveRequest(BaseModel):
    due_date: Optional[str] = None
    category_id: Optional[int] = None
    folder: Optional[str] = None
    assigned_to: Optional[str] = None


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
    limit: int = Query(default=1000, ge=1, le=10000, description="Number of emails to return"),
    offset: int = Query(default=0, ge=0, description="Number of emails to skip"),
    folder: Optional[str] = Query(default="inbox", description="Filter by folder (inbox, archive, deleted). Defaults to inbox."),
    status: Optional[str] = Query(default=None, description="Filter by status (unprocessed, processed, archived)"),
    db: Session = Depends(get_db)
):
    """
    Get stored emails from the database with pagination.

    Args:
        limit: Maximum number of emails to return (1-10000, default 1000)
        offset: Number of emails to skip for pagination
        folder: Folder filter (defaults to "inbox" to show only inbox emails)
        status: Optional status filter
        db: Database session

    Returns:
        dict: List of emails and pagination info
    """
    # Build query
    query = db.query(Email)

    # Filter by folder (default to inbox, or None/null for inbox emails)
    if folder and folder.lower() != "all":
        # Match emails where folder is explicitly set to the requested folder,
        # OR folder is None/inbox (for inbox emails)
        if folder.lower() == "inbox":
            query = query.filter((Email.folder == None) | (Email.folder == "inbox") | (Email.folder == ""))
        else:
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
            "due_date": email.due_date.isoformat() if email.due_date else None,
            "todo_task_id": email.todo_task_id,
            "assigned_to": email.assigned_to,
            "recommended_folder": email.recommended_folder,
            "folder_is_new": email.folder_is_new if hasattr(email, 'folder_is_new') else False,
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

    Filters out:
    - Emails older than 45 days
    - Emails processed in the last 3 days

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

    # Apply filters: not older than 45 days, not processed in last 3 days
    cutoff_date = datetime.utcnow() - timedelta(days=45)
    recent_processing_cutoff = datetime.utcnow() - timedelta(days=3)

    # Get email IDs that were classified in the last 3 days
    recently_processed_ids = db.query(ClassificationLog.email_id).filter(
        ClassificationLog.created_at >= recent_processing_cutoff
    ).distinct().all()
    recently_processed_ids = [id_tuple[0] for id_tuple in recently_processed_ids]

    # Fetch all unprocessed emails with filters
    unprocessed_emails = db.query(Email).filter(
        Email.status == "unprocessed",
        Email.received_at >= cutoff_date,  # Not older than 45 days
        ~Email.id.in_(recently_processed_ids) if recently_processed_ids else True  # Not processed recently
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

    Filters out:
    - Emails older than 45 days
    - Emails processed in the last 3 days

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
    # Apply filters: not older than 45 days, not processed in last 3 days
    cutoff_date = datetime.utcnow() - timedelta(days=45)
    recent_processing_cutoff = datetime.utcnow() - timedelta(days=3)

    # Get email IDs that were classified in the last 3 days
    recently_processed_ids = db.query(ClassificationLog.email_id).filter(
        ClassificationLog.created_at >= recent_processing_cutoff
    ).distinct().all()
    recently_processed_ids = [id_tuple[0] for id_tuple in recently_processed_ids]

    # Fetch all unprocessed emails with filters
    unprocessed_emails = db.query(Email).filter(
        Email.status == "unprocessed",
        Email.received_at >= cutoff_date,  # Not older than 45 days
        ~Email.id.in_(recently_processed_ids) if recently_processed_ids else True  # Not processed recently
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

            # Call AI classifier with database session
            result = classify_with_ai(email_dict, db_session=db)

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


# ============================================================================
# NEW ENDPOINTS
# ============================================================================


@router.get("/summary")
async def get_email_summary(db: Session = Depends(get_db)):
    """
    Get summary statistics of all emails in the database.

    Returns:
        dict: Summary with total count, breakdown by category, and breakdown by status
    """
    # Get total count
    total = db.query(Email).count()

    # Get all categories for proper labeling
    categories = db.query(Category).all()
    category_map = {cat.id: cat.label for cat in categories}

    # Count emails by category
    by_category = {}
    for category_id, label in category_map.items():
        count = db.query(Email).filter(Email.category_id == category_id).count()
        # Use format: "{id}_{label_snake_case}"
        label_snake = label.lower().replace(" ", "_").replace("/", "_")
        key = f"{category_id}_{label_snake}"
        by_category[key] = count

    # Count uncategorized emails
    uncategorized = db.query(Email).filter(Email.category_id.is_(None)).count()
    by_category["uncategorized"] = uncategorized

    # Count by status
    by_status = {
        "unprocessed": db.query(Email).filter(Email.status == "unprocessed").count(),
        "classified": db.query(Email).filter(Email.status == "classified").count(),
    }

    # Add other statuses if they exist
    for status in ["processed", "archived"]:
        count = db.query(Email).filter(Email.status == status).count()
        if count > 0:
            by_status[status] = count

    return {
        "total": total,
        "by_category": by_category,
        "by_status": by_status
    }


class ReclassifyRequest(BaseModel):
    category_id: int


@router.post("/{email_id}/reclassify")
async def reclassify_email(
    email_id: int,
    request: ReclassifyRequest,
    db: Session = Depends(get_db)
):
    """
    Manually reclassify an email.

    Updates the email's category and logs the manual classification.

    Args:
        email_id: ID of the email to reclassify
        request: Request body with new category_id
        db: Database session

    Returns:
        dict: Updated email information
    """
    # Get the email
    email = db.query(Email).filter(Email.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")

    # Verify category exists
    category = db.query(Category).filter(Category.id == request.category_id).first()
    if not category:
        raise HTTPException(status_code=400, detail="Invalid category_id")

    # Update email
    old_category_id = email.category_id
    email.category_id = request.category_id
    email.confidence = 1.0  # Manual classification has 100% confidence
    email.status = "classified"

    # Create classification log entry
    log_entry = ClassificationLog(
        email_id=email.id,
        category_id=request.category_id,
        rule=f"Manual reclassification from category {old_category_id} to {request.category_id}",
        classifier_type="manual",
        confidence=1.0,
        created_at=datetime.utcnow()
    )
    db.add(log_entry)
    db.commit()

    return {
        "email_id": email.id,
        "old_category_id": old_category_id,
        "new_category_id": email.category_id,
        "category_label": category.label,
        "status": email.status,
        "message": f"Email reclassified to {category.label}"
    }


@router.post("/pipeline/run")
async def run_pipeline(
    fetch_count: int = Query(default=50, ge=1, le=200, description="Number of emails to fetch"),
    db: Session = Depends(get_db)
):
    """
    Run the full email classification pipeline.

    Orchestrates the complete workflow:
    1. Fetch emails from Microsoft Graph API
    2. Run deterministic classifier on unprocessed emails
    3. Check overrides on newly-classified Other emails
    4. Run AI classifier on remaining unprocessed emails

    Args:
        fetch_count: Number of emails to fetch (1-200)
        db: Database session

    Returns:
        dict: Comprehensive report with statistics from each stage
    """
    try:
        report = await run_full_pipeline(db, fetch_count)
        return report

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline execution failed: {str(e)}"
        )


@router.get("/score/check")
async def check_scorable_emails(db: Session = Depends(get_db)):
    """
    Debug endpoint: Check how many emails are available for scoring.

    Returns count of emails with status='classified' and in Work categories.
    """
    work_ids = get_work_category_ids(db)
    count = db.query(Email).filter(
        Email.status == "classified",
        Email.category_id.in_(work_ids)
    ).count()

    return {
        "scorable_emails": count,
        "message": f"Found {count} Work emails ready for scoring"
    }


@router.get("/score/debug")
def debug_score_single(db: Session = Depends(get_db)):
    """
    Debug endpoint: Score a single email to test if scoring works.
    """
    # Get one email
    work_ids = get_work_category_ids(db)
    email = db.query(Email).filter(
        Email.status == "classified",
        Email.category_id.in_(work_ids)
    ).first()

    if not email:
        return {"error": "No Work emails found to score"}

    # Create minimal email dict
    email_dict = {
        "subject": email.subject or "",
        "body": email.body or "",
        "body_preview": email.body_preview or "",
        "from_address": email.from_address or "",
        "from_name": email.from_name or "",
        "importance": email.importance or "normal",
        "received_at": email.received_at,
        "conversation_id": email.conversation_id,
        "category_id": email.category_id,
        "to_recipients": email.to_recipients or "[]",
        "cc_recipients": email.cc_recipients or "[]",
        "has_attachments": email.has_attachments or False,
        "message_id": email.message_id or "",
    }

    try:
        # Try scoring without db
        result = score_email(email_dict, db=None, user_domain="live.com")

        return {
            "success": True,
            "email_id": email.id,
            "subject": email.subject,
            "urgency_score": result["urgency_score"],
            "signals": result["signals"],
            "message": "Scoring works!"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "email_id": email.id
        }


@router.post("/score")
def score_work_emails(db: Session = Depends(get_db)):
    """
    Calculate urgency scores for all classified Work emails.

    Fetches all emails with status='classified' in Work categories,
    runs the urgency scoring engine on each, updates the urgency_score field,
    and stores detailed breakdown in urgency_scores table.

    Note: This endpoint is synchronous to avoid thread-safety issues with
    database sessions and blocking operations.

    Args:
        db: Database session

    Returns:
        dict: Statistics with total scored, score distribution, floor/stale details,
              average raw and adjusted scores
    """
    # Fetch all classified Work emails
    work_ids = get_work_category_ids(db)
    work_emails = db.query(Email).filter(
        Email.status == "classified",
        Email.category_id.in_(work_ids)
    ).all()

    total_scored = len(work_emails)

    if total_scored == 0:
        return {
            "total_scored": 0,
            "message": "No classified Work emails found to score",
            "score_distribution": {
                "critical_90_plus": 0,
                "high_70_89": 0,
                "medium_40_69": 0,
                "low_under_40": 0
            },
            "floor_items": {"count": 0, "emails": []},
            "stale_items": {"count": 0, "force_today_count": 0, "emails": []},
            "average_raw_score": 0.0,
            "average_adjusted_score": 0.0
        }

    # Get user for domain detection
    user = db.query(User).first()
    user_domain = "live.com"  # Default
    if user and user.email:
        user_domain = user.email.split('@')[-1] if '@' in user.email else "live.com"

    # Score distribution counters
    score_distribution = {
        "critical_90_plus": 0,
        "high_70_89": 0,
        "medium_40_69": 0,
        "low_under_40": 0
    }

    # Floor and stale tracking
    floor_items = []
    stale_items = []
    force_today_count = 0

    raw_scores = []
    adjusted_scores = []

    # Score each email
    for email in work_emails:
        try:
            # Convert email to dict for scoring
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
                "category_id": email.category_id,
            }

            # Run scoring engine
            result = score_email(email_dict, db=None, user_domain=user_domain)
            score = result["urgency_score"]
            raw_score = result.get("raw_score", score)
            stale_bonus = result.get("stale_bonus", 0)
            stale_days = result.get("stale_days", 0)
            floor_override = result.get("floor_override", False)
            force_today = result.get("force_today", False)

            # Update email's urgency_score field
            email.urgency_score = score
            raw_scores.append(raw_score)
            adjusted_scores.append(score)

            # Update or create urgency_scores record
            urgency_record = db.query(UrgencyScore).filter(
                UrgencyScore.email_id == email.id
            ).first()

            # Prepare signals JSON (include all scoring details)
            signals_data = {
                "signals": result["signals"],
                "weights": result["weights"],
                "breakdown": result["breakdown"]
            }

            if urgency_record:
                # Update existing record
                urgency_record.urgency_score = score
                urgency_record.raw_score = raw_score
                urgency_record.stale_bonus = stale_bonus
                urgency_record.stale_days = stale_days
                urgency_record.floor_override = floor_override
                urgency_record.force_today = force_today
                urgency_record.signals_json = json.dumps(signals_data)
                urgency_record.scored_at = datetime.utcnow()
            else:
                # Create new record
                urgency_record = UrgencyScore(
                    email_id=email.id,
                    urgency_score=score,
                    raw_score=raw_score,
                    stale_bonus=stale_bonus,
                    stale_days=stale_days,
                    floor_override=floor_override,
                    force_today=force_today,
                    signals_json=json.dumps(signals_data),
                    scored_at=datetime.utcnow()
                )
                db.add(urgency_record)

            # Track floor overrides
            if floor_override:
                floor_items.append({
                    "email_id": email.id,
                    "subject": email.subject or "[No subject]",
                    "score": score
                })

            # Track stale bonuses
            if stale_bonus > 0:
                stale_items.append({
                    "email_id": email.id,
                    "subject": email.subject or "[No subject]",
                    "stale_days": stale_days,
                    "stale_bonus": stale_bonus
                })
                if force_today:
                    force_today_count += 1

            # Update distribution
            if score >= 90:
                score_distribution["critical_90_plus"] += 1
            elif score >= 70:
                score_distribution["high_70_89"] += 1
            elif score >= 40:
                score_distribution["medium_40_69"] += 1
            else:
                score_distribution["low_under_40"] += 1

        except Exception as e:
            # Log error but continue scoring other emails
            print(f"Error scoring email {email.id}: {str(e)}")
            continue

    # Commit all changes
    db.commit()

    # Calculate average scores
    average_raw_score = sum(raw_scores) / len(raw_scores) if raw_scores else 0.0
    average_adjusted_score = sum(adjusted_scores) / len(adjusted_scores) if adjusted_scores else 0.0

    return {
        "total_scored": total_scored,
        "score_distribution": score_distribution,
        "floor_items": {
            "count": len(floor_items),
            "emails": floor_items
        },
        "stale_items": {
            "count": len(stale_items),
            "force_today_count": force_today_count,
            "emails": stale_items
        },
        "average_raw_score": round(average_raw_score, 2),
        "average_adjusted_score": round(average_adjusted_score, 2),
        "message": f"Successfully scored {total_scored} Work emails"
    }


@router.get("/scored")
def get_scored_emails(db: Session = Depends(get_db)):
    """
    Get all scored Work emails sorted by urgency score (descending).

    Returns the ranked priority list of all Work emails that have
    been scored, ordered from highest to lowest urgency.

    Args:
        db: Database session

    Returns:
        dict: List of scored emails with email_id, subject, from_name, category_id,
              urgency_score, raw_score, stale_bonus, floor_override, force_today, stale_days
    """
    # Get all Work emails with urgency scores, joined with urgency_scores table
    work_ids = get_work_category_ids(db)
    scored_emails = db.query(Email, UrgencyScore).join(
        UrgencyScore, Email.id == UrgencyScore.email_id
    ).filter(
        Email.status == "classified",
        Email.category_id.in_(work_ids)
    ).order_by(
        UrgencyScore.urgency_score.desc()
    ).all()

    # Build response list
    emails_list = []
    for email, urgency in scored_emails:
        emails_list.append({
            "email_id": email.id,
            "subject": email.subject or "[No subject]",
            "from_name": email.from_name or email.from_address,
            "category_id": email.category_id,
            "urgency_score": urgency.urgency_score,
            "raw_score": urgency.raw_score,
            "stale_bonus": urgency.stale_bonus,
            "floor_override": urgency.floor_override,
            "force_today": urgency.force_today,
            "stale_days": urgency.stale_days
        })

    return {
        "total": len(emails_list),
        "emails": emails_list,
        "message": f"Retrieved {len(emails_list)} scored Work emails in priority order"
    }


@router.post("/assign")
def assign_due_dates_to_emails(db: Session = Depends(get_db)):
    """
    Assign due dates to all scored Work emails using the batch assignment algorithm.

    Fetches all Work emails (categories 1-5) with urgency scores, runs the assignment
    algorithm to distribute them across Today, Tomorrow, This Week (Friday), and
    Next Week (Monday), then updates the database with assigned due dates.

    Args:
        db: Database session

    Returns:
        dict: Assignment summary with total assigned, breakdown by slot, and settings used
    """
    from app.services.assignment import assign_due_dates, get_assignment_summary
    from datetime import datetime

    # Fetch all scored Work emails
    work_ids = get_work_category_ids(db)
    scored_emails_db = db.query(Email, UrgencyScore).join(
        UrgencyScore, Email.id == UrgencyScore.email_id
    ).filter(
        Email.status == "classified",
        Email.category_id.in_(work_ids),
        Email.urgency_score.isnot(None)
    ).order_by(
        UrgencyScore.urgency_score.desc()
    ).all()

    if not scored_emails_db:
        return {
            "total_assigned": 0,
            "slots": {
                "today": {"count": 0, "floor_count": 0, "standard_count": 0},
                "tomorrow": {"count": 0},
                "this_week": {"count": 0},
                "next_week": {"count": 0},
                "no_date": {"count": 0}
            },
            "task_limit": 20,
            "urgency_floor": 90,
            "message": "No scored Work emails found to assign"
        }

    # Convert to format expected by assign_due_dates
    scored_emails = []
    for email, urgency in scored_emails_db:
        scored_emails.append({
            "email_id": email.id,
            "urgency_score": urgency.urgency_score,
            "floor_override": urgency.floor_override,
            "force_today": urgency.force_today
        })

    # Run assignment algorithm with default settings
    settings = {
        "task_limit": 20,
        "urgency_floor": 90,
        "time_pressure_threshold": 15
    }
    assignments = assign_due_dates(scored_emails, settings)

    # Update database with assigned due dates
    for assignment in assignments:
        email = db.query(Email).filter(Email.id == assignment["email_id"]).first()
        if email:
            # Convert ISO date string to datetime (set time to midnight)
            if assignment["due_date"]:
                due_date_str = assignment["due_date"]
                email.due_date = datetime.strptime(due_date_str, "%Y-%m-%d")
            else:
                email.due_date = None

    # Commit all updates
    db.commit()

    # Generate detailed summary
    summary = get_assignment_summary(assignments)

    # Build detailed slot breakdown
    today_assignments = [a for a in assignments if a['slot'] == 'today']
    floor_count = len([a for a in today_assignments if a['pool'] == 'floor'])
    standard_count = len([a for a in today_assignments if a['pool'] == 'standard'])

    return {
        "total_assigned": len(assignments),
        "slots": {
            "today": {
                "count": summary['by_slot']['today'],
                "floor_count": floor_count,
                "standard_count": standard_count
            },
            "tomorrow": {
                "count": summary['by_slot']['tomorrow']
            },
            "this_week": {
                "count": summary['by_slot']['this_week']
            },
            "next_week": {
                "count": summary['by_slot']['next_week']
            },
            "no_date": {
                "count": summary['by_slot']['no_date']
            }
        },
        "task_limit": settings['task_limit'],
        "urgency_floor": settings['urgency_floor'],
        "floor_overflow": summary['floor_overflow'],
        "message": f"Assigned due dates to {len(assignments)} Work emails"
    }


@router.get("/today")
def get_todays_emails(db: Session = Depends(get_db)):
    """
    Get all emails assigned to today's date - the daily action list.

    Returns all Work emails (categories 1-5) that have been assigned a due date
    of today, sorted by urgency score descending. This represents the user's
    prioritized action list for today.

    Args:
        db: Database session

    Returns:
        dict: List of today's emails with email_id, subject, from_name, category_id,
              urgency_score, floor_override, due_date
    """
    from datetime import date

    # Get today's date at midnight
    today = date.today()

    # Query emails with today's due date, joined with urgency_scores
    work_ids = get_work_category_ids(db)
    todays_emails = db.query(Email, UrgencyScore).join(
        UrgencyScore, Email.id == UrgencyScore.email_id
    ).filter(
        Email.status == "classified",
        Email.category_id.in_(work_ids),
        Email.due_date >= datetime.combine(today, datetime.min.time()),
        Email.due_date < datetime.combine(today + timedelta(days=1), datetime.min.time())
    ).order_by(
        UrgencyScore.urgency_score.desc()
    ).all()

    # Build response list
    emails_list = []
    for email, urgency in todays_emails:
        emails_list.append({
            "email_id": email.id,
            "subject": email.subject or "[No subject]",
            "from_name": email.from_name or email.from_address,
            "category_id": email.category_id,
            "urgency_score": urgency.urgency_score,
            "floor_override": urgency.floor_override,
            "due_date": email.due_date.date().isoformat() if email.due_date else None
        })

    return {
        "date": today.isoformat(),
        "total": len(emails_list),
        "emails": emails_list,
        "message": f"Retrieved {len(emails_list)} emails due today"
    }


@router.post("/sync-todo")
async def sync_to_microsoft_todo(db: Session = Depends(get_db)):
    """
    Sync assigned emails to Microsoft To-Do tasks.

    Gets the current access token, fetches all Work emails with due dates that
    haven't been synced yet (todo_task_id is null), and creates corresponding
    tasks in Microsoft To-Do organized by category.

    Args:
        db: Database session

    Returns:
        dict: Sync summary with synced count, lists created, skipped count, and errors
    """
    from app.services.todo_sync_batch import sync_all_tasks_batch as sync_all_tasks, TodoSyncError, TokenExpiredError

    # Get the authenticated user
    user = db.query(User).first()
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated. Please log in first.")

    try:
        # Get valid access token
        graph_client = GraphClient()
        access_token = await graph_client.get_token(user.email, db)

        # Fetch all Work emails with due dates that haven't been synced yet
        work_ids = get_work_category_ids(db)
        emails_query = db.query(Email, UrgencyScore).join(
            UrgencyScore, Email.id == UrgencyScore.email_id
        ).filter(
            Email.status == "classified",
            Email.category_id.in_(work_ids),
            Email.due_date.isnot(None),
            Email.todo_task_id.is_(None)
        ).order_by(
            UrgencyScore.urgency_score.desc()
        ).all()

        if not emails_query:
            return {
                "synced": 0,
                "lists_created": [],
                "skipped": 0,
                "errors": [],
                "message": "No emails found to sync (all emails either already synced or have no due date)"
            }

        # Convert to format expected by sync_all_tasks
        assigned_emails = []
        for email, urgency in emails_query:
            assigned_emails.append({
                "email_id": email.id,
                "message_id": email.message_id,  # Required for flagging email
                "subject": email.subject,
                "body_preview": email.body_preview,
                "from_name": email.from_name,
                "from_address": email.from_address,
                "received_at": email.received_at,
                "due_date": email.due_date,
                "category_id": email.category_id,
                "urgency_score": urgency.urgency_score,
                "floor_override": urgency.floor_override,
                "todo_task_id": email.todo_task_id
            })

        # Sync to Microsoft To-Do
        result = sync_all_tasks(access_token, assigned_emails, db)

        # Commit database updates (todo_task_id values)
        db.commit()

        # Calculate total skipped
        total_skipped = result['skipped_already_synced'] + result['skipped_no_date']

        return {
            "synced": result['synced'],
            "lists_created": result['lists_created'],
            "skipped": total_skipped,
            "errors": result['errors'],
            "message": f"Synced {result['synced']} emails to Microsoft To-Do. Created {len(result['lists_created'])} lists."
        }

    except TokenExpiredError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except TodoSyncError as e:
        raise HTTPException(status_code=500, detail=f"To-Do sync failed: {str(e)}")
    except Exception as e:
        error_message = str(e)
        if "Token expired" in error_message or "re-authenticate" in error_message:
            raise HTTPException(status_code=401, detail=error_message)
        raise HTTPException(status_code=500, detail=f"Failed to sync to To-Do: {error_message}")


@router.delete("/sync-todo/reset")
async def reset_todo_sync(
    delete_tasks: bool = Query(default=False, description="Also delete tasks from Microsoft To-Do"),
    db: Session = Depends(get_db)
):
    """
    Reset To-Do sync tracking (for testing).

    Clears all todo_task_id values in the database, allowing emails to be re-synced.
    Optionally also deletes the actual task lists from Microsoft To-Do.

    Use this endpoint to test the sync functionality or to force a re-sync of all emails.

    Args:
        delete_tasks: If True, also deletes task lists from Microsoft To-Do
        db: Database session

    Returns:
        dict: Number of emails reset and optionally deletion summary
    """
    from app.services.todo_sync import delete_all_todo_lists, clear_cache, TokenExpiredError, TodoSyncError

    # Count emails with todo_task_id before reset
    count = db.query(Email).filter(Email.todo_task_id.isnot(None)).count()

    result = {
        "reset": count,
        "message": f"Reset {count} emails. They can now be re-synced to Microsoft To-Do."
    }

    # Optionally delete task lists from Microsoft To-Do
    if delete_tasks:
        try:
            # Get the authenticated user
            user = db.query(User).first()
            if not user:
                result["todo_deletion"] = {
                    "error": "Not authenticated. Cannot delete To-Do tasks."
                }
            else:
                # Get access token
                graph_client = GraphClient()
                access_token = await graph_client.get_token(user.email, db)

                # Delete all task lists
                deletion_result = delete_all_todo_lists(access_token)
                result["todo_deletion"] = {
                    "deleted": deletion_result['deleted'],
                    "list_names": deletion_result['list_names'],
                    "errors": deletion_result['errors']
                }
                result["message"] = f"Reset {count} emails and deleted {deletion_result['deleted']} task lists from Microsoft To-Do."

                # Clear cache after deletion
                clear_cache()

        except TokenExpiredError as e:
            result["todo_deletion"] = {
                "error": f"Token expired: {str(e)}"
            }
        except Exception as e:
            result["todo_deletion"] = {
                "error": f"Failed to delete tasks: {str(e)}"
            }
    else:
        result["note"] = "This does not delete tasks in Microsoft To-Do. Use ?delete_tasks=true to also delete the tasks."

    # Clear all todo_task_id values in database
    db.query(Email).update({Email.todo_task_id: None})
    db.commit()

    return result


@router.delete("/sync-todo/cleanup")
async def cleanup_todo_tasks(db: Session = Depends(get_db)):
    """
    Clean up duplicate tasks in Microsoft To-Do.

    Deletes all task lists that match our category names from Microsoft To-Do.
    This is useful for removing duplicates after testing.

    Does NOT clear todo_task_id in database - use /sync-todo/reset for that.

    Args:
        db: Database session

    Returns:
        dict: Deletion summary with lists deleted and errors
    """
    from app.services.todo_sync import delete_all_todo_lists, clear_cache, TokenExpiredError, TodoSyncError

    # Get the authenticated user
    user = db.query(User).first()
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated. Please log in first.")

    try:
        # Get access token
        graph_client = GraphClient()
        access_token = await graph_client.get_token(user.email, db)

        # Delete all task lists
        result = delete_all_todo_lists(access_token)

        # Clear cache after deletion
        clear_cache()

        return {
            "deleted": result['deleted'],
            "list_names": result['list_names'],
            "errors": result['errors'],
            "message": f"Deleted {result['deleted']} task lists from Microsoft To-Do. You can now re-sync without duplicates."
        }

    except TokenExpiredError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except TodoSyncError as e:
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")
    except Exception as e:
        error_message = str(e)
        if "Token expired" in error_message or "re-authenticate" in error_message:
            raise HTTPException(status_code=401, detail=error_message)
        raise HTTPException(status_code=500, detail=f"Failed to clean up tasks: {error_message}")


@router.put("/{email_id}/reclassify")
async def reclassify_email(
    email_id: int,
    request: ReclassifyRequest,
    db: Session = Depends(get_db)
):
    """
    Reclassify an email to a different category (manual override).

    This endpoint allows users to manually change an email's category from the UI.
    - If moving to Work categories (1-5): sets status='classified' and triggers urgency scoring
    - If moving to Other categories (6-11): clears urgency_score and due_date
    - Logs the change in classification_log with classifier_type='manual'

    Args:
        email_id: ID of the email to reclassify
        request: Request body containing the new category_id
        db: Database session

    Returns:
        dict: Updated email data
    """
    print(f"[RECLASSIFY] Received request for email_id={email_id}, category_id={request.category_id}")

    try:
        # Get the email
        email = db.query(Email).filter(Email.id == email_id).first()
        print(f"[RECLASSIFY] Found email: {email is not None}")
        if not email:
            raise HTTPException(status_code=404, detail="Email not found")

        # Get the category by number (1-11) to verify it exists
        category = db.query(Category).filter(Category.number == request.category_id).first()
        if not category:
            raise HTTPException(status_code=400, detail=f"Invalid category_id: {request.category_id}")

        # Extract category details for later use
        category_number = category.number
        category_label = category.label

        # Store old category for logging
        old_category_id = email.category_id

        # Update the email's category (use the database ID, not the number)
        email.category_id = category.id

        # Handle category-specific logic based on master_category
        if category.master_category == "Work":
            # Work categories - set as classified and trigger AI due date assignment
            email.status = "classified"

            # Use AI to assign due date based on calendar, context, sender, and urgency
            try:
                from ..services.ai_due_date_assigner import assign_due_date_with_ai, assign_due_date_simple

                # Convert email object to dictionary
                email_dict = {
                    "id": email.id,
                    "message_id": email.message_id,
                    "from_address": email.from_address,
                    "from_name": email.from_name,
                    "subject": email.subject,
                    "body_preview": email.body_preview,
                    "body": email.body,
                    "received_at": email.received_at,
                    "importance": email.importance,
                    "conversation_id": email.conversation_id,
                    "has_attachments": email.has_attachments,
                }

                # Convert category to dict
                category_dict = {
                    "id": category.id,
                    "number": category.number,
                    "label": category.label,
                    "master_category": category.master_category
                }

                # Get access token for calendar API
                user = db.query(User).first()
                if user:
                    graph_client = GraphClient()
                    access_token = await graph_client.get_token(user.email, db)

                    # Use AI to determine due date
                    print(f"[RECLASSIFY] Calling AI to assign due date...")
                    due_date, reasoning = await assign_due_date_with_ai(
                        email_dict,
                        category_dict,
                        access_token,
                        db
                    )

                    email.due_date = due_date
                    print(f"[RECLASSIFY] AI assigned due date: {due_date} - {reasoning}")
                else:
                    # Fallback if no user/token
                    print(f"[RECLASSIFY] No user found, using simple assignment")
                    due_date = assign_due_date_simple(email_dict, category_dict)
                    email.due_date = due_date
                    print(f"[RECLASSIFY] Simple assignment: {due_date}")

            except Exception as e:
                # Log error but don't fail the request
                print(f"Warning: Failed to assign due date during reclassification: {str(e)}")
                import traceback
                traceback.print_exc()

                # Fallback to simple assignment
                from ..services.ai_due_date_assigner import assign_due_date_simple
                email_dict = {
                    "subject": email.subject,
                    "body_preview": email.body_preview,
                    "importance": email.importance,
                    "has_attachments": email.has_attachments,
                }
                category_dict = {
                    "label": category.label,
                    "master_category": category.master_category
                }
                email.due_date = assign_due_date_simple(email_dict, category_dict)
                print(f"[RECLASSIFY] Fallback assignment: {email.due_date}")

            # If moving from Other to Work, flag the email and apply new category
            old_category = db.query(Category).filter(Category.id == old_category_id).first()
            print(f"[RECLASSIFY] Moving to Work. Old category: {old_category.label if old_category else 'None'}, master: {old_category.master_category if old_category else 'None'}")
            if old_category and old_category.master_category == "Other":
                print(f"[RECLASSIFY] Detected Other → Work transition")
                try:
                    # Get access token
                    user = db.query(User).first()
                    if user:
                        print(f"[RECLASSIFY] Got user, getting access token")
                        graph_client = GraphClient()
                        access_token = await graph_client.get_token(user.email, db)

                        async with httpx.AsyncClient() as client:
                            # Flag the email in Outlook with due date
                            print(f"[RECLASSIFY] Flagging email {email_id} with due date {email.due_date}")

                            # Prepare flag data with due date if available
                            flag_data = {"flagStatus": "flagged"}
                            if email.due_date:
                                # Format due date for Graph API (ISO 8601 format)
                                from datetime import datetime
                                due_date_str = email.due_date.isoformat()
                                if 'T' not in due_date_str:
                                    due_date_str = f"{due_date_str}T09:00:00"  # Set to 9 AM UTC

                                # Set startDateTime to now
                                start_date_str = datetime.utcnow().isoformat(timespec='seconds')

                                flag_data["startDateTime"] = {
                                    "dateTime": start_date_str,
                                    "timeZone": "UTC"
                                }
                                flag_data["dueDateTime"] = {
                                    "dateTime": due_date_str,
                                    "timeZone": "UTC"
                                }
                                print(f"[RECLASSIFY] Setting flag dates - start: {start_date_str}, due: {due_date_str}")

                            flag_response = await client.patch(
                                f"https://graph.microsoft.com/v1.0/me/messages/{email.message_id}",
                                headers={
                                    "Authorization": f"Bearer {access_token}",
                                    "Content-Type": "application/json"
                                },
                                json={"flag": flag_data}
                            )
                            if flag_response.status_code in [200, 204]:
                                print(f"[RECLASSIFY] ✓ Flagged email {email_id} with due date")
                            else:
                                print(f"[RECLASSIFY] ✗ Failed to flag email {email_id}: {flag_response.status_code}")
                                print(f"[RECLASSIFY] Response: {flag_response.text}")

                        # Apply new Work category label in Outlook
                        print(f"[RECLASSIFY] Applying category: number={category_number}, label={category_label}")
                        if category_number and category_label:
                            outlook_category_name = f"{category_number}. {category_label}"
                            print(f"[RECLASSIFY] Calling replace_category_on_email with '{outlook_category_name}'")
                            result = await replace_category_on_email(
                                access_token,
                                email.message_id,
                                outlook_category_name
                            )
                            print(f"[RECLASSIFY] ✓ replace_category_on_email returned: {result}")
                        else:
                            print(f"[RECLASSIFY] ✗ Category number or label is None!")


                except Exception as e:
                    print(f"[RECLASSIFY] ✗ Exception: {str(e)}")
                    import traceback
                    traceback.print_exc()
            elif old_category and old_category.master_category == "Work":
                # Moving Work → Work, update Outlook category and due date
                try:
                    user = db.query(User).first()
                    if user and category_number and category_label:
                        graph_client = GraphClient()
                        access_token = await graph_client.get_token(user.email, db)

                        outlook_category_name = f"{category_number}. {category_label}"
                        await replace_category_on_email(
                            access_token,
                            email.message_id,
                            outlook_category_name
                        )
                        print(f"Updated Outlook category to '{outlook_category_name}' for email {email_id}")

                        # Update flag's due date (which updates the To-Do task automatically)
                        if email.due_date:
                            print(f"[RECLASSIFY] Updating flag due date for Work → Work transition to {email.due_date}")

                            # Format due date for Graph API (ISO 8601 format)
                            from datetime import datetime
                            due_date_str = email.due_date.isoformat()
                            if 'T' not in due_date_str:
                                due_date_str = f"{due_date_str}T09:00:00"  # Set to 9 AM UTC

                            # Set startDateTime to now
                            start_date_str = datetime.utcnow().isoformat(timespec='seconds')

                            async with httpx.AsyncClient() as client:
                                flag_update_response = await client.patch(
                                    f"https://graph.microsoft.com/v1.0/me/messages/{email.message_id}",
                                    headers={
                                        "Authorization": f"Bearer {access_token}",
                                        "Content-Type": "application/json"
                                    },
                                    json={
                                        "flag": {
                                            "flagStatus": "flagged",
                                            "startDateTime": {
                                                "dateTime": start_date_str,
                                                "timeZone": "UTC"
                                            },
                                            "dueDateTime": {
                                                "dateTime": due_date_str,
                                                "timeZone": "UTC"
                                            }
                                        }
                                    }
                                )
                                if flag_update_response.status_code in [200, 204]:
                                    print(f"[RECLASSIFY] ✓ Updated flag due date successfully")
                                else:
                                    print(f"[RECLASSIFY] ✗ Failed to update flag due date: {flag_update_response.status_code}")

                except Exception as e:
                    print(f"Warning: Failed to update Outlook category for email {email_id}: {str(e)}")

        elif category.master_category == "Other":
            # Other/noise categories - clear urgency data
            email.urgency_score = None
            email.due_date = None

            # Also clear urgency_score_record if it exists
            if email.urgency_score_record:
                db.delete(email.urgency_score_record)

            # If moving from Work to Other, unflag email, delete To-Do task, and apply Other category
            old_category = db.query(Category).filter(Category.id == old_category_id).first()
            print(f"[RECLASSIFY] Moving to Other. Old category: {old_category.label if old_category else 'None'}, master: {old_category.master_category if old_category else 'None'}")
            if old_category and old_category.master_category == "Work":
                print(f"[RECLASSIFY] Detected Work → Other transition")
                try:
                    # Get access token
                    user = db.query(User).first()
                    if user:
                        graph_client = GraphClient()
                        access_token = await graph_client.get_token(user.email, db)

                        async with httpx.AsyncClient() as client:
                            # Unflag the email in Outlook
                            unflag_response = await client.patch(
                                f"https://graph.microsoft.com/v1.0/me/messages/{email.message_id}",
                                headers={
                                    "Authorization": f"Bearer {access_token}",
                                    "Content-Type": "application/json"
                                },
                                json={"flag": {"flagStatus": "notFlagged"}}
                            )
                            if unflag_response.status_code not in [200, 204]:
                                print(f"Warning: Failed to unflag email {email_id}: {unflag_response.status_code}")

                        # Apply new Other category label
                        print(f"[RECLASSIFY] Applying Other category: number={category_number}, label={category_label}")
                        if category_number and category_label:
                            outlook_category_name = f"{category_number}. {category_label}"
                            print(f"[RECLASSIFY] Calling replace_category_on_email with '{outlook_category_name}'")
                            result = await replace_category_on_email(
                                access_token,
                                email.message_id,
                                outlook_category_name
                            )
                            print(f"[RECLASSIFY] ✓ replace_category_on_email returned: {result}")
                        else:
                            print(f"[RECLASSIFY] ✗ Category number or label is None!")

                        # Delete To-Do task if it exists
                        if email.todo_task_id:
                            # Get the task list
                            lists_response = await client.get(
                                f"https://graph.microsoft.com/v1.0/me/todo/lists",
                                headers={"Authorization": f"Bearer {access_token}"}
                            )

                            if lists_response.status_code == 200:
                                task_list_id = None
                                for task_list in lists_response.json().get('value', []):
                                    if task_list.get('displayName') in ['Flagged Emails', 'Tasks']:
                                        task_list_id = task_list['id']
                                        break

                                if task_list_id:
                                    # Delete the task
                                    delete_response = await client.delete(
                                        f"https://graph.microsoft.com/v1.0/me/todo/lists/{task_list_id}/tasks/{email.todo_task_id}",
                                        headers={"Authorization": f"Bearer {access_token}"}
                                    )
                                    if delete_response.status_code in [200, 204]:
                                        email.todo_task_id = None
                                        print(f"Deleted To-Do task for email {email_id}")
                                    else:
                                        print(f"Warning: Failed to delete To-Do task: {delete_response.status_code}")

                except Exception as e:
                    print(f"Warning: Failed to unflag/remove To-Do for email {email_id}: {str(e)}")
            else:
                # Moving Other → Other, just update the category label
                try:
                    user = db.query(User).first()
                    if user and category_number and category_label:
                        graph_client = GraphClient()
                        access_token = await graph_client.get_token(user.email, db)

                        outlook_category_name = f"{category_number}. {category_label}"
                        await replace_category_on_email(
                            access_token,
                            email.message_id,
                            outlook_category_name
                        )
                        print(f"Updated Outlook category to '{outlook_category_name}' for email {email_id}")

                except Exception as e:
                    print(f"Warning: Failed to update Outlook category for email {email_id}: {str(e)}")

        # Log the manual reclassification
        log_entry = ClassificationLog(
            email_id=email.id,
            classifier_type="manual",
            category_id=category.id,  # Use database ID
            confidence=1.0,  # Manual classification is 100% confident
            rule="manual_reclassification"
        )
        db.add(log_entry)

        # Commit changes
        db.commit()
        db.refresh(email)

        # Prepare response data (match format from list_emails endpoint)
        response_data = {
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
            "due_date": email.due_date.isoformat() if email.due_date else None,
            "todo_task_id": email.todo_task_id,
            "assigned_to": email.assigned_to,
            "recommended_folder": email.recommended_folder,
            "folder_is_new": email.folder_is_new if hasattr(email, 'folder_is_new') else False,
        }

        # Calculate stale_days if there's an urgency score record
        if email.urgency_score_record:
            response_data["floor_override"] = email.urgency_score_record.floor_override or False
            response_data["stale_days"] = email.urgency_score_record.stale_days or 0

        print(f"[RECLASSIFY] Success! Returning response")
        return response_data

    except HTTPException:
        raise
    except Exception as e:
        print(f"[RECLASSIFY] ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Reclassification failed: {str(e)}")


# ============================================================================
# APPROVAL AND EXECUTION ENDPOINTS
# ============================================================================


@router.put("/{email_id}/approve")
async def approve_email(
    email_id: int,
    request: ApproveRequest,
    db: Session = Depends(get_db)
):
    """
    Mark an email as approved.

    Accepts optional body with:
    - due_date: YYYY-MM-DD format
    - category_id: Category ID to override
    - folder: Target folder ID for execution

    Updates the email in SQLite with confirmed values and sets status = 'approved'.

    Args:
        email_id: ID of the email to approve
        request: Optional approval metadata
        db: Database session

    Returns:
        dict: Updated email data
    """
    # Get the email
    email = db.query(Email).filter(Email.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")

    # Get user for action tracking
    user = db.query(User).first()

    # Store previous values for undo
    previous_status = email.status
    previous_category_id = email.category_id
    previous_due_date = email.due_date
    previous_folder = email.folder
    previous_assigned_to = email.assigned_to

    # Update email status
    email.status = "approved"

    # Track timing for calibration
    email.approved_at = datetime.utcnow()

    # Update optional fields if provided
    if request.due_date:
        try:
            # Parse date string to datetime
            email.due_date = datetime.strptime(request.due_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    if request.category_id is not None:
        # Verify category exists
        category = db.query(Category).filter(Category.id == request.category_id).first()
        if not category:
            raise HTTPException(status_code=400, detail="Invalid category_id")
        email.category_id = request.category_id

    if request.folder:
        email.folder = request.folder

    if request.assigned_to is not None:
        email.assigned_to = request.assigned_to

    # Record action for undo
    action_data = {
        "email_ids": [{
            "email_id": email.id,
            "previous_status": previous_status,
            "previous_category_id": previous_category_id,
            "previous_due_date": previous_due_date.isoformat() if previous_due_date else None,
            "previous_folder": previous_folder,
            "previous_assigned_to": previous_assigned_to,
        }]
    }
    if user:
        record_action(
            db,
            action_type="approve",
            description=f"Approved email: {email.subject[:50]}",
            action_data=action_data,
            user_id=user.id
        )

    db.commit()
    db.refresh(email)

    return {
        "id": email.id,
        "message_id": email.message_id,
        "subject": email.subject,
        "from_name": email.from_name,
        "from_address": email.from_address,
        "status": email.status,
        "category_id": email.category_id,
        "due_date": email.due_date.isoformat() if email.due_date else None,
        "folder": email.folder,
        "urgency_score": email.urgency_score,
        "recommended_folder": email.recommended_folder,
        "folder_is_new": email.folder_is_new if hasattr(email, 'folder_is_new') else False,
        "message": "Email approved successfully"
    }


@router.put("/{email_id}/unapprove")
async def unapprove_email(
    email_id: int,
    db: Session = Depends(get_db)
):
    """
    Revert an approved email back to 'classified' status.

    Args:
        email_id: ID of the email to unapprove
        db: Database session

    Returns:
        dict: Updated email data
    """
    # Get the email
    email = db.query(Email).filter(Email.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")

    # Revert status to classified
    email.status = "classified"

    db.commit()
    db.refresh(email)

    return {
        "id": email.id,
        "message_id": email.message_id,
        "subject": email.subject,
        "status": email.status,
        "message": "Email unapproved successfully"
    }


# Folder cache with 1 hour expiry
_folder_cache = {"data": None, "expires_at": None}


@router.get("/folders")
async def get_folders(db: Session = Depends(get_db)):
    """
    Get the user's Outlook folder list from Graph API.

    Caches results for 1 hour to reduce API calls.

    Args:
        db: Database session

    Returns:
        dict: List of folders with id and displayName
    """
    from datetime import datetime

    # Check cache
    if _folder_cache["data"] and _folder_cache["expires_at"]:
        if datetime.utcnow() < _folder_cache["expires_at"]:
            return {"folders": _folder_cache["data"], "cached": True}

    # Get the authenticated user
    user = db.query(User).first()
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated. Please log in first.")

    try:
        # Get valid access token
        graph_client = GraphClient()
        access_token = await graph_client.get_token(user.email, db)

        # Fetch folders from Graph API
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://graph.microsoft.com/v1.0/me/mailFolders",
                headers={"Authorization": f"Bearer {access_token}"}
            )

            if response.status_code == 401:
                raise HTTPException(status_code=401, detail="Token expired. Please re-authenticate.")

            response.raise_for_status()
            data = response.json()

            folders = [
                {"id": folder["id"], "displayName": folder["displayName"]}
                for folder in data.get("value", [])
            ]

            # Cache for 1 hour
            _folder_cache["data"] = folders
            _folder_cache["expires_at"] = datetime.utcnow() + timedelta(hours=1)

            return {"folders": folders, "cached": False}

    except Exception as e:
        error_message = str(e)
        if "Token expired" in error_message or "re-authenticate" in error_message:
            raise HTTPException(status_code=401, detail=error_message)
        raise HTTPException(status_code=500, detail=f"Failed to fetch folders: {error_message}")


@router.post("/execute")
async def execute_approved_emails(db: Session = Depends(get_db)):
    """
    Batch execution endpoint for approved emails.

    For all emails with status = 'approved':
    a) Apply Outlook category to each email
    b) Move each email to its target folder via Graph API
    c) Create/update Microsoft To-Do tasks for items with due dates
    d) Set email status to 'actioned' in SQLite

    Args:
        db: Database session

    Returns:
        dict: Execution summary with counts and errors
    """
    from app.services.todo_sync_batch import sync_all_tasks_batch as sync_all_tasks, TodoSyncError, TokenExpiredError
    from app.services.outlook_categories import ensure_category_exists_and_apply, replace_category_on_email, remove_all_app_categories
    from app.services.undo_service import record_action

    # Get the authenticated user
    user = db.query(User).first()
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated. Please log in first.")

    try:
        # Get valid access token
        graph_client = GraphClient()
        access_token = await graph_client.get_token(user.email, db)

        # Get all approved emails
        approved_emails = db.query(Email).filter(Email.status == "approved").all()

        if not approved_emails:
            return {
                "executed": 0,
                "folders_moved": 0,
                "todos_created": 0,
                "errors": [],
                "message": "No approved emails to execute"
            }

        executed_count = 0
        folders_moved = 0
        todos_created = 0
        errors = []

        # Track action data for undo
        action_data = []

        # Get category mapping for auto-assigning folders
        categories = db.query(Category).all()
        category_map = {cat.id: cat.label for cat in categories}

        # Get folder mapping (fetch once for all operations)
        # Include both top-level folders and child folders (especially under Inbox)
        folder_map = {}
        inbox_folder_id = None
        try:
            async with httpx.AsyncClient() as client:
                # Get top-level folders
                response = await client.get(
                    f"https://graph.microsoft.com/v1.0/me/mailFolders",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                response.raise_for_status()
                data = response.json()

                for folder in data.get("value", []):
                    folder_name = folder["displayName"]
                    folder_id = folder["id"]
                    folder_map[folder_name.lower()] = folder_id

                    # Save Inbox folder ID for creating subfolders
                    if folder_name == "Inbox":
                        inbox_folder_id = folder_id

                    # Also fetch child folders of Inbox
                    if folder_name == "Inbox":
                        try:
                            child_response = await client.get(
                                f"https://graph.microsoft.com/v1.0/me/mailFolders/{folder_id}/childFolders",
                                headers={"Authorization": f"Bearer {access_token}"}
                            )
                            if child_response.status_code == 200:
                                for child in child_response.json().get("value", []):
                                    folder_map[child["displayName"].lower()] = child["id"]
                        except Exception as child_error:
                            errors.append(f"Failed to fetch Inbox child folders: {str(child_error)}")
        except Exception as e:
            errors.append(f"Failed to fetch folder list: {str(e)}")

        # Process each approved email
        for email in approved_emails:
            try:
                # Track if this email was successfully processed
                email_processed_successfully = True

                # Get category info
                category = db.query(Category).filter(Category.id == email.category_id).first()
                category_label = category.label if category else None
                category_number = category.number if category else None
                category_master = category.master_category if category else None

                # Category handling:
                # - Work emails: Apply category label (for action tracking)
                # - Other emails: Remove all categories (they're just being filed)
                if category_master == "Work" and category_number and category_label:
                    # Apply category for Work emails
                    outlook_category_name = f"{category_number}. {category_label}"
                    try:
                        # First ensure category exists in master list
                        from app.services.outlook_categories import get_outlook_categories, create_outlook_category
                        existing_categories = await get_outlook_categories(access_token)
                        if outlook_category_name not in existing_categories:
                            await create_outlook_category(access_token, outlook_category_name)

                        # Replace category on email (removes old app categories)
                        await replace_category_on_email(
                            access_token,
                            email.message_id,
                            outlook_category_name
                        )
                    except Exception as e:
                        errors.append(f"Failed to apply category to email {email.id}: {str(e)}")
                elif category_master == "Other":
                    # Remove all app categories for Other emails (they're being filed)
                    try:
                        await remove_all_app_categories(access_token, email.message_id)
                    except Exception as e:
                        errors.append(f"Failed to remove categories from email {email.id}: {str(e)}")

                # Update To-Do task title if category changed and task exists
                if email.todo_task_id and category_number and category_label:
                    try:
                        async with httpx.AsyncClient() as client:
                            # Get the task list ID
                            lists_response = await client.get(
                                f"https://graph.microsoft.com/v1.0/me/todo/lists",
                                headers={"Authorization": f"Bearer {access_token}"}
                            )

                            if lists_response.status_code == 200:
                                task_list_id = None
                                for task_list in lists_response.json().get('value', []):
                                    if task_list.get('displayName') in ['Flagged Emails', 'Tasks']:
                                        task_list_id = task_list['id']
                                        break

                                if task_list_id:
                                    # Build new task title
                                    from app.services.todo_sync_batch import get_category_prefix
                                    category_prefix = get_category_prefix(category_number, category_label)

                                    # For Discuss (4) and Delegate (5), prepend person name if available
                                    if email.assigned_to and category_number in [4, 5]:
                                        new_title = f"{category_prefix} {email.assigned_to}: {email.subject}"
                                    else:
                                        new_title = f"{category_prefix} {email.subject}"

                                    if len(new_title) > 255:
                                        new_title = new_title[:252] + "..."

                                    # Update the task
                                    update_response = await client.patch(
                                        f"https://graph.microsoft.com/v1.0/me/todo/lists/{task_list_id}/tasks/{email.todo_task_id}",
                                        headers={
                                            "Authorization": f"Bearer {access_token}",
                                            "Content-Type": "application/json"
                                        },
                                        json={"title": new_title}
                                    )

                                    if update_response.status_code not in [200, 204]:
                                        errors.append(f"Failed to update To-Do task for email {email.id}")
                    except Exception as e:
                        errors.append(f"Failed to update To-Do task for email {email.id}: {str(e)}")

                # Folder handling:
                # - Work emails: Stay in Inbox (no folder movement)
                # - Other emails: Move to category folder
                # - FYI - Group (7): Use AI-recommended folder
                if category_master == "Other":
                    # Special handling for FYI - Group (category 7)
                    if category_number == 7 and email.recommended_folder:
                        # Use AI-recommended folder
                        email.folder = email.recommended_folder
                    # Auto-assign folder based on category if not set
                    elif not email.folder or email.folder == "inbox":
                        if category_label:
                            # Categories 8, 9, 10, 12 get numerical prefix in folder name
                            if category_number in [8, 9, 10, 12]:
                                email.folder = f"{category_number}. {category_label}"
                            else:
                                email.folder = category_label

                    # Move to folder if specified
                    if email.folder and email.folder != "inbox" and email.folder.lower() in folder_map:
                        folder_id = folder_map[email.folder.lower()]
                        try:
                            async with httpx.AsyncClient() as client:
                                move_response = await client.post(
                                    f"https://graph.microsoft.com/v1.0/me/messages/{email.message_id}/move",
                                    headers={
                                        "Authorization": f"Bearer {access_token}",
                                        "Content-Type": "application/json"
                                    },
                                    json={"destinationId": folder_id}
                                )

                                if move_response.status_code == 404:
                                    errors.append(f"Email {email.id} not found in Outlook (may have been deleted)")
                                    email_processed_successfully = False
                                elif move_response.status_code in [200, 201]:
                                    folders_moved += 1
                                else:
                                    errors.append(f"Failed to move email {email.id}: {move_response.status_code}")
                                    email_processed_successfully = False
                        except Exception as e:
                            errors.append(f"Failed to move email {email.id} to folder: {str(e)}")
                            email_processed_successfully = False
                    elif email.folder and email.folder != "inbox" and email.folder.lower() not in folder_map:
                        # Try to create the folder as a child of Inbox
                        try:
                            async with httpx.AsyncClient() as client:
                                # Create folder under Inbox
                                if inbox_folder_id:
                                    create_response = await client.post(
                                        f"https://graph.microsoft.com/v1.0/me/mailFolders/{inbox_folder_id}/childFolders",
                                        headers={
                                            "Authorization": f"Bearer {access_token}",
                                            "Content-Type": "application/json"
                                        },
                                        json={"displayName": email.folder}
                                    )
                                else:
                                    # Fallback to root-level folder if Inbox ID not found
                                    create_response = await client.post(
                                        f"https://graph.microsoft.com/v1.0/me/mailFolders",
                                        headers={
                                            "Authorization": f"Bearer {access_token}",
                                            "Content-Type": "application/json"
                                        },
                                        json={"displayName": email.folder}
                                    )

                                if create_response.status_code in [200, 201]:
                                    new_folder = create_response.json()
                                    folder_id = new_folder["id"]
                                    folder_map[email.folder.lower()] = folder_id

                                    # Now move the email
                                    move_response = await client.post(
                                        f"https://graph.microsoft.com/v1.0/me/messages/{email.message_id}/move",
                                        headers={
                                            "Authorization": f"Bearer {access_token}",
                                            "Content-Type": "application/json"
                                        },
                                        json={"destinationId": folder_id}
                                    )
                                    if move_response.status_code in [200, 201]:
                                        folders_moved += 1
                                    else:
                                        errors.append(f"Failed to move email {email.id} after creating folder: {move_response.status_code}")
                                        email_processed_successfully = False
                                else:
                                    errors.append(f"Failed to create folder '{email.folder}': {create_response.status_code}")
                                    email_processed_successfully = False
                        except Exception as e:
                            errors.append(f"Failed to create folder '{email.folder}' and move email {email.id}: {str(e)}")
                            email_processed_successfully = False

                # Only mark as actioned if successfully processed
                if email_processed_successfully:
                    # Track action data for undo
                    email_action_data = {
                        "email_id": email.id,
                        "category_applied": bool(category_number and category_label),
                        "category_name": f"{category_number}. {category_label}" if category_number and category_label else None,
                        "email_flagged": False,  # Will be set by todo sync
                        "todo_created": False,  # Will be set by todo sync
                        "todo_list_id": None,  # Will be set by todo sync
                        "folder_moved": category_master == "Other" and email.folder and email.folder != "inbox",
                        "original_folder": "inbox",
                    }
                    action_data.append(email_action_data)

                    # Mark as actioned
                    email.status = "actioned"

                    # Track execution time for calibration
                    email.executed_at = datetime.utcnow()

                    executed_count += 1
                else:
                    # Keep as approved if processing failed
                    errors.append(f"Email {email.id} kept as 'approved' due to processing errors")

            except Exception as e:
                errors.append(f"Error processing email {email.id}: {str(e)}")
                continue

        # Record action for undo (before commit)
        if executed_count > 0:
            description = f"Executed {executed_count} email{'s' if executed_count > 1 else ''}"
            record_action(
                db,
                action_type="execute",
                description=description,
                action_data={"email_ids": action_data},
                user_id=user.id
            )

        # Commit all status updates
        db.commit()

        # Record actual durations for calibration
        from app.services.duration_estimator import record_actual_duration
        for email in approved_emails:
            if email.status == "actioned":
                try:
                    record_actual_duration(db, email, user.id if user else None)
                except Exception as e:
                    logger.warning(f"Failed to record duration for email {email.id}: {e}")

        # Sync to Microsoft To-Do for emails with due dates
        # Get Work category IDs dynamically
        work_category_ids = [cat.id for cat in categories if cat.master_category == "Work"]

        # Get emails that need todo sync (have due dates but no todo_task_id yet)
        emails_for_todo = db.query(Email, UrgencyScore).join(
            UrgencyScore, Email.id == UrgencyScore.email_id
        ).filter(
            Email.status == "actioned",
            Email.category_id.in_(work_category_ids),
            Email.due_date.isnot(None),
            Email.todo_task_id.is_(None)
        ).all()

        if emails_for_todo:
            try:
                # Convert to format expected by sync function
                assigned_emails = []
                for email, urgency in emails_for_todo:
                    assigned_emails.append({
                        "email_id": email.id,
                        "message_id": email.message_id,
                        "subject": email.subject,
                        "body_preview": email.body_preview,
                        "from_name": email.from_name,
                        "from_address": email.from_address,
                        "received_at": email.received_at,
                        "due_date": email.due_date,
                        "category_id": email.category_id,
                        "urgency_score": urgency.urgency_score,
                        "floor_override": urgency.floor_override,
                        "todo_task_id": email.todo_task_id
                    })

                # Sync to To-Do (pass db session for category loading)
                sync_result = sync_all_tasks(access_token, assigned_emails, db)
                todos_created = sync_result['synced']

                # Commit todo_task_id updates
                db.commit()

                # Add sync errors if any
                if sync_result.get('errors'):
                    errors.extend(sync_result['errors'])

            except Exception as e:
                errors.append(f"Failed to sync to Microsoft To-Do: {str(e)}")

        return {
            "executed": executed_count,
            "folders_moved": folders_moved,
            "todos_created": todos_created,
            "errors": errors,
            "message": f"Executed {executed_count} emails. Moved {folders_moved} to folders. Created {todos_created} To-Do tasks."
        }

    except TokenExpiredError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        error_message = str(e)
        if "Token expired" in error_message or "re-authenticate" in error_message:
            raise HTTPException(status_code=401, detail=error_message)
        raise HTTPException(status_code=500, detail=f"Execution failed: {error_message}")


@router.post("/confirm-other")
async def confirm_other_emails(db: Session = Depends(get_db)):
    """
    Bulk confirm for Other tab emails.

    For all emails with status = 'classified' and category_id 6-11:
    - Move each to its designated folder
    - Set status = 'actioned'

    Default folder mapping:
    - Marketing (6) → Marketing folder
    - Notification (7) → Notifications folder
    - Calendar (8) → Calendar folder
    - FYI (9) → FYI folder
    - Travel (11) → Travel folder
    - Other (10) → Other folder

    Args:
        db: Database session

    Returns:
        dict: Summary with confirmed count and moved count
    """
    # Get the authenticated user
    user = db.query(User).first()
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated. Please log in first.")

    try:
        # Get valid access token
        graph_client = GraphClient()
        access_token = await graph_client.get_token(user.email, db)

        # Get all categories to map IDs to folder names
        categories = db.query(Category).filter(Category.master_category == "Other").all()
        category_folder_map = {}
        for cat in categories:
            # Categories 8, 9, 10, 12 get numerical prefix in folder name
            if cat.number in [8, 9, 10, 12]:
                category_folder_map[cat.id] = f"{cat.number}. {cat.label}"
            else:
                category_folder_map[cat.id] = cat.label

        # Get all classified Other emails
        other_category_ids = [cat.id for cat in categories]
        other_emails = db.query(Email).filter(
            Email.status == "classified",
            Email.category_id.in_(other_category_ids)
        ).all()

        if not other_emails:
            return {
                "confirmed": 0,
                "moved": 0,
                "message": "No Other emails to confirm"
            }

        confirmed_count = 0
        moved_count = 0
        errors = []

        # Get folder mapping
        folder_map = {}
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://graph.microsoft.com/v1.0/me/mailFolders",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                response.raise_for_status()
                data = response.json()

                for folder in data.get("value", []):
                    folder_map[folder["displayName"].lower()] = folder["id"]
        except Exception as e:
            errors.append(f"Failed to fetch folder list: {str(e)}")
            # Continue anyway, we'll try to create folders as needed

        # Process each email
        for email in other_emails:
            try:
                # Get target folder name from category
                target_folder_name = category_folder_map.get(email.category_id)
                if not target_folder_name:
                    errors.append(f"No folder mapping for category {email.category_id}")
                    continue

                target_folder_lower = target_folder_name.lower()

                # Check if folder exists, create if not
                if target_folder_lower not in folder_map:
                    try:
                        async with httpx.AsyncClient() as client:
                            create_response = await client.post(
                                f"https://graph.microsoft.com/v1.0/me/mailFolders",
                                headers={
                                    "Authorization": f"Bearer {access_token}",
                                    "Content-Type": "application/json"
                                },
                                json={"displayName": target_folder_name}
                            )
                            create_response.raise_for_status()
                            new_folder = create_response.json()
                            folder_map[target_folder_lower] = new_folder["id"]
                    except Exception as e:
                        errors.append(f"Failed to create folder '{target_folder_name}': {str(e)}")
                        continue

                # Move email to folder
                folder_id = folder_map[target_folder_lower]
                try:
                    async with httpx.AsyncClient() as client:
                        move_response = await client.post(
                            f"https://graph.microsoft.com/v1.0/me/messages/{email.message_id}/move",
                            headers={
                                "Authorization": f"Bearer {access_token}",
                                "Content-Type": "application/json"
                            },
                            json={"destinationId": folder_id}
                        )

                        if move_response.status_code == 404:
                            errors.append(f"Email {email.id} not found in Outlook (may have been deleted)")
                        else:
                            move_response.raise_for_status()
                            moved_count += 1
                except Exception as e:
                    errors.append(f"Failed to move email {email.id}: {str(e)}")
                    continue

                # Mark as actioned
                email.status = "actioned"
                confirmed_count += 1

            except Exception as e:
                errors.append(f"Error processing email {email.id}: {str(e)}")
                continue

        # Commit all updates
        db.commit()

        return {
            "confirmed": confirmed_count,
            "moved": moved_count,
            "errors": errors,
            "message": f"Confirmed {confirmed_count} Other emails. Moved {moved_count} to folders."
        }

    except Exception as e:
        error_message = str(e)
        if "Token expired" in error_message or "re-authenticate" in error_message:
            raise HTTPException(status_code=401, detail=error_message)
        raise HTTPException(status_code=500, detail=f"Bulk confirm failed: {error_message}")


@router.post("/reassign-dates")
async def reassign_due_dates(db: Session = Depends(get_db)):
    """
    Re-run due date assignment on existing classified emails.
    
    Uses the new duration-aware, calendar-intelligent assignment algorithm.
    This will:
    1. Estimate durations for all Work emails (if not already done)
    2. Fetch calendar availability
    3. Re-assign due dates based on actual available time and task durations
    
    Returns:
        Assignment summary
    """
    from app.services.duration_estimator import estimate_task_duration, apply_calibration
    from app.services.calendar_service import get_daily_capacity_minutes
    from app.services.assignment import assign_due_dates_duration_aware, get_assignment_summary
    from app.services.scoring import URGENCY_FLOOR_THRESHOLD, TIME_PRESSURE_THRESHOLD
    import logging
    
    logger = logging.getLogger(__name__)
    
    # Get user
    user = db.query(User).first()
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        # Get access token for calendar
        graph_client = GraphClient()
        access_token = await graph_client.get_token(user.email, db)
        
        # Get Work category IDs
        work_category_ids = get_work_category_ids(db)
        
        # Step 1: Estimate durations for emails that don't have estimates
        emails_to_estimate = db.query(Email).filter(
            Email.status == "classified",
            Email.category_id.in_(work_category_ids),
            Email.duration_estimate.is_(None)
        ).all()
        
        estimated_count = 0
        for email in emails_to_estimate:
            try:
                category = db.query(Category).filter(Category.id == email.category_id).first()
                raw_estimate, reasoning = await estimate_task_duration(email, category, db)
                calibrated_estimate = apply_calibration(raw_estimate, db, user.id if user else None)
                email.duration_estimate = calibrated_estimate
                estimated_count += 1
            except Exception as e:
                logger.error(f"Duration estimation failed for email {email.id}: {e}")
                email.duration_estimate = 10  # Fallback
        
        db.commit()
        logger.info(f"Estimated durations for {estimated_count} emails")
        
        # Step 2: Fetch all scored Work emails
        scored_emails_db = db.query(Email, UrgencyScore).join(
            UrgencyScore, Email.id == UrgencyScore.email_id
        ).filter(
            Email.status == "classified",
            Email.category_id.in_(work_category_ids),
            Email.urgency_score.isnot(None)
        ).order_by(
            UrgencyScore.urgency_score.desc()
        ).all()
        
        if not scored_emails_db:
            return {
                "reassigned": 0,
                "message": "No classified Work emails to reassign"
            }
        
        # Convert to format for assignment
        scored_emails = []
        for email, urgency in scored_emails_db:
            scored_emails.append({
                "email_id": email.id,
                "urgency_score": urgency.urgency_score,
                "floor_override": urgency.floor_override,
                "force_today": urgency.force_today,
                "duration_estimate": email.duration_estimate or 10
            })
        
        # Step 3: Fetch calendar capacity in minutes
        calendar_capacity_minutes = await get_daily_capacity_minutes(access_token, days_ahead=14)
        
        # Step 4: Run duration-aware assignment
        settings = {
            "urgency_floor": URGENCY_FLOOR_THRESHOLD,
            "time_pressure_threshold": TIME_PRESSURE_THRESHOLD,
            "fallback_daily_minutes": 480
        }
        
        logger.info("Re-running assignment with duration-aware algorithm")
        assignments = assign_due_dates_duration_aware(scored_emails, calendar_capacity_minutes, settings)
        
        # Step 5: Update database with new assignments
        for assignment in assignments:
            email = db.query(Email).filter(Email.id == assignment["email_id"]).first()
            if email:
                if assignment["due_date"]:
                    due_date_str = assignment["due_date"]
                    email.due_date = datetime.strptime(due_date_str, "%Y-%m-%d")
                else:
                    email.due_date = None
        
        db.commit()
        
        # Generate summary
        summary = get_assignment_summary(assignments)
        
        return {
            "status": "success",
            "reassigned": len(assignments),
            "estimated_durations": estimated_count,
            "slots": {
                "today": summary['by_slot']['today'],
                "tomorrow": summary['by_slot']['tomorrow'],
                "this_week": summary['by_slot']['this_week'],
                "next_week": summary['by_slot']['next_week'],
                "no_date": summary['by_slot']['no_date']
            },
            "message": f"Re-assigned {len(assignments)} emails using calendar-aware duration algorithm"
        }
        
    except Exception as e:
        logger.error(f"Re-assignment failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to reassign dates: {str(e)}")


class BatchMoveRequest(BaseModel):
    category_id: int


class BatchDeleteRequest(BaseModel):
    category_id: int


@router.post("/batch-move-to-folder")
async def batch_move_to_folder(
    request: BatchMoveRequest,
    db: Session = Depends(get_db)
):
    """
    Batch move all emails in a category to their corresponding folder.

    This endpoint is used for Marketing (8), Notifications (9), Calendar Items (10), and Travel (12)
    to quickly move all emails to folders named exactly as their category labels:
    - "8. Marketing"
    - "9. Notifications"
    - "10. Calendar Items"
    - "12. Travel"

    Args:
        request: Contains category_id (8, 9, 10, or 12)
        db: Database session

    Returns:
        dict: Count of moved emails
    """
    # Get the authenticated user
    user = db.query(User).first()
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated. Please log in first.")

    try:
        # Get the category
        category = db.query(Category).filter(Category.number == request.category_id).first()
        if not category:
            raise HTTPException(status_code=400, detail=f"Category {request.category_id} not found")

        # Verify it's one of the batch-processable categories
        if request.category_id not in [8, 9, 10, 12]:
            raise HTTPException(
                status_code=400,
                detail=f"Batch move only available for categories 8, 9, 10, and 12"
            )

        # Get all emails in this category with status='classified'
        emails = db.query(Email).filter(
            Email.category_id == category.id,
            Email.status == "classified"
        ).all()

        if not emails:
            return {
                "moved": 0,
                "message": f"No emails to move in category {category.label}"
            }

        # Get access token
        graph_client = GraphClient()
        access_token = await graph_client.get_token(user.email, db)

        # Build folder map
        folder_map = {}
        inbox_folder_id = None

        async with httpx.AsyncClient() as client:
            # Get top-level folders
            response = await client.get(
                f"https://graph.microsoft.com/v1.0/me/mailFolders",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            response.raise_for_status()
            data = response.json()

            for folder in data.get("value", []):
                folder_name = folder["displayName"]
                folder_id = folder["id"]
                folder_map[folder_name.lower()] = folder_id

                # Save Inbox folder ID for creating subfolders
                if folder_name == "Inbox":
                    inbox_folder_id = folder_id

                    # Fetch child folders of Inbox
                    try:
                        child_response = await client.get(
                            f"https://graph.microsoft.com/v1.0/me/mailFolders/{folder_id}/childFolders",
                            headers={"Authorization": f"Bearer {access_token}"}
                        )
                        if child_response.status_code == 200:
                            for child in child_response.json().get("value", []):
                                folder_map[child["displayName"].lower()] = child["id"]
                    except Exception:
                        pass

        # Determine target folder name (number prefix + label, e.g., "8. Marketing")
        target_folder_name = f"{category.number}. {category.label}"
        target_folder_lower = target_folder_name.lower()

        # Check if folder exists, create if not
        if target_folder_lower not in folder_map:
            async with httpx.AsyncClient() as client:
                # Create folder under Inbox
                create_response = await client.post(
                    f"https://graph.microsoft.com/v1.0/me/mailFolders/{inbox_folder_id}/childFolders" if inbox_folder_id else f"https://graph.microsoft.com/v1.0/me/mailFolders",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json"
                    },
                    json={"displayName": target_folder_name}
                )

                if create_response.status_code in [200, 201]:
                    new_folder = create_response.json()
                    folder_map[target_folder_lower] = new_folder["id"]
                else:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to create folder '{target_folder_name}'"
                    )

        # Move all emails to the target folder
        moved_count = 0
        errors = []

        async with httpx.AsyncClient() as client:
            for email in emails:
                try:
                    move_response = await client.post(
                        f"https://graph.microsoft.com/v1.0/me/messages/{email.message_id}/move",
                        headers={
                            "Authorization": f"Bearer {access_token}",
                            "Content-Type": "application/json"
                        },
                        json={"destinationId": folder_map[target_folder_lower]}
                    )

                    if move_response.status_code in [200, 201]:
                        # Update database
                        email.folder = target_folder_name
                        email.status = "actioned"
                        moved_count += 1
                    elif move_response.status_code == 404:
                        errors.append(f"Email {email.id} not found (may have been deleted)")
                    else:
                        errors.append(f"Failed to move email {email.id}: {move_response.status_code}")
                except Exception as e:
                    errors.append(f"Error moving email {email.id}: {str(e)}")

        # Record action for undo (before commit)
        if moved_count > 0:
            email_ids = [email.id for email in emails if email.status == "actioned"]
            description = f"Batch moved {moved_count} email{'s' if moved_count != 1 else ''} to {target_folder_name}"
            record_action(
                db,
                action_type="batch_move",
                description=description,
                action_data={
                    "category_id": request.category_id,
                    "category_label": category.label,
                    "folder_name": target_folder_name,
                    "email_ids": email_ids,
                    "moved_count": moved_count
                },
                user_id=user.id
            )

        # Commit database changes
        db.commit()

        return {
            "moved": moved_count,
            "errors": errors if errors else None,
            "message": f"Moved {moved_count} email{'s' if moved_count != 1 else ''} to {target_folder_name}"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch move failed: {str(e)}")


@router.post("/batch-delete-category")
async def batch_delete_category(
    request: BatchDeleteRequest,
    db: Session = Depends(get_db)
):
    """
    Batch delete all emails in a category (move to trash).

    This endpoint is used for Marketing (8), Notifications (9), Calendar Items (10), and Travel (12)
    to quickly move all emails to the Deleted Items folder.

    Args:
        request: Contains category_id (8, 9, 10, or 12)
        db: Database session

    Returns:
        dict: Count of deleted emails
    """
    # Get the authenticated user
    user = db.query(User).first()
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated. Please log in first.")

    try:
        # Get the category
        category = db.query(Category).filter(Category.number == request.category_id).first()
        if not category:
            raise HTTPException(status_code=400, detail=f"Category {request.category_id} not found")

        # Verify it's one of the batch-processable categories
        if request.category_id not in [8, 9, 10, 12]:
            raise HTTPException(
                status_code=400,
                detail=f"Batch delete only available for categories 8, 9, 10, and 12"
            )

        # Get all emails in this category with status='classified'
        emails = db.query(Email).filter(
            Email.category_id == category.id,
            Email.status == "classified"
        ).all()

        if not emails:
            return {
                "deleted": 0,
                "message": f"No emails to delete in category {category.label}"
            }

        # Get access token
        graph_client = GraphClient()
        access_token = await graph_client.get_token(user.email, db)

        # Get the Deleted Items folder ID
        deleted_items_folder_id = None

        async with httpx.AsyncClient() as client:
            # Get top-level folders
            response = await client.get(
                f"https://graph.microsoft.com/v1.0/me/mailFolders",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            response.raise_for_status()
            data = response.json()

            for folder in data.get("value", []):
                # Look for "Deleted Items" or "Trash"
                if folder["displayName"].lower() in ["deleted items", "trash", "deleted"]:
                    deleted_items_folder_id = folder["id"]
                    break

        if not deleted_items_folder_id:
            raise HTTPException(
                status_code=500,
                detail="Could not find Deleted Items folder"
            )

        # Move all emails to trash
        deleted_count = 0
        errors = []

        async with httpx.AsyncClient() as client:
            for email in emails:
                try:
                    move_response = await client.post(
                        f"https://graph.microsoft.com/v1.0/me/messages/{email.message_id}/move",
                        headers={
                            "Authorization": f"Bearer {access_token}",
                            "Content-Type": "application/json"
                        },
                        json={"destinationId": deleted_items_folder_id}
                    )

                    if move_response.status_code in [200, 201]:
                        # Update database
                        email.folder = "deleted"
                        email.status = "actioned"
                        deleted_count += 1
                    elif move_response.status_code == 404:
                        errors.append(f"Email {email.id} not found (may have been deleted)")
                    else:
                        errors.append(f"Failed to delete email {email.id}: {move_response.status_code}")
                except Exception as e:
                    errors.append(f"Error deleting email {email.id}: {str(e)}")

        # Record action for undo (before commit)
        if deleted_count > 0:
            email_ids = [email.id for email in emails if email.status == "actioned"]
            description = f"Batch deleted {deleted_count} email{'s' if deleted_count != 1 else ''} from {category.label}"
            record_action(
                db,
                action_type="batch_delete",
                description=description,
                action_data={
                    "category_id": request.category_id,
                    "category_label": category.label,
                    "email_ids": email_ids,
                    "deleted_count": deleted_count
                },
                user_id=user.id
            )

        # Commit database changes
        db.commit()

        return {
            "deleted": deleted_count,
            "errors": errors if errors else None,
            "message": f"Moved {deleted_count} email{'s' if deleted_count != 1 else ''} to trash"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch delete failed: {str(e)}")
