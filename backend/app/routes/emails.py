from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
import time
import asyncio
from ..database import get_db
from ..models import Email, User, ClassificationLog, OverrideLog, Category, UrgencyScore
from ..services.graph import GraphClient
from ..services.classifier_deterministic import classify_deterministic
from ..services.classifier_override import check_override
from ..services.classifier_ai import classify_with_ai
from ..services.pipeline import run_full_pipeline
from ..services.scoring import score_email
from pydantic import BaseModel
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

    Returns count of emails with status='classified' and category_id in [1, 2, 3, 4, 5].
    """
    count = db.query(Email).filter(
        Email.status == "classified",
        Email.category_id.in_([1, 2, 3, 4, 5])
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
    email = db.query(Email).filter(
        Email.status == "classified",
        Email.category_id.in_([1, 2, 3, 4, 5])
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
    Calculate urgency scores for all classified Work emails (categories 1-5).

    Fetches all emails with status='classified' and category_id 1-5 (Work items),
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
    # Fetch all classified Work emails (categories 1-5)
    work_emails = db.query(Email).filter(
        Email.status == "classified",
        Email.category_id.in_([1, 2, 3, 4, 5])
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

    Returns the ranked priority list of all Work emails (categories 1-5) that have
    been scored, ordered from highest to lowest urgency.

    Args:
        db: Database session

    Returns:
        dict: List of scored emails with email_id, subject, from_name, category_id,
              urgency_score, raw_score, stale_bonus, floor_override, force_today, stale_days
    """
    # Get all Work emails with urgency scores, joined with urgency_scores table
    scored_emails = db.query(Email, UrgencyScore).join(
        UrgencyScore, Email.id == UrgencyScore.email_id
    ).filter(
        Email.status == "classified",
        Email.category_id.in_([1, 2, 3, 4, 5])
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
    scored_emails_db = db.query(Email, UrgencyScore).join(
        UrgencyScore, Email.id == UrgencyScore.email_id
    ).filter(
        Email.status == "classified",
        Email.category_id.in_([1, 2, 3, 4, 5]),
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
    todays_emails = db.query(Email, UrgencyScore).join(
        UrgencyScore, Email.id == UrgencyScore.email_id
    ).filter(
        Email.status == "classified",
        Email.category_id.in_([1, 2, 3, 4, 5]),
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
        emails_query = db.query(Email, UrgencyScore).join(
            UrgencyScore, Email.id == UrgencyScore.email_id
        ).filter(
            Email.status == "classified",
            Email.category_id.in_([1, 2, 3, 4, 5]),
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
