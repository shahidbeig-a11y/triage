"""
Full email classification pipeline orchestration.

This module coordinates the complete email classification workflow:
1. Fetch emails from Microsoft Graph API
2. Run deterministic classifier on unprocessed emails
3. Check overrides on newly-classified Other emails
4. Run AI classifier on remaining unprocessed emails
5. Run urgency scoring on all Work items
6. Run batch assignment to distribute across due dates
7. Sync assigned items to Microsoft To-Do
"""

import time
import asyncio
import json
from typing import Dict
from datetime import datetime
from sqlalchemy.orm import Session

from .graph import GraphClient
from .classifier_deterministic import classify_deterministic
from .classifier_override import check_override
from .classifier_ai import classify_with_ai
from .scoring import score_email
from .assignment import assign_due_dates, get_assignment_summary
from .todo_sync_batch import sync_all_tasks_batch, TokenExpiredError
from ..models import Email, User, ClassificationLog, OverrideLog, UrgencyScore
from datetime import timedelta
from sqlalchemy import and_, or_


async def run_full_pipeline(db: Session, fetch_count: int = 50) -> Dict:
    """
    Execute the complete email classification and assignment pipeline.

    Full workflow:
    1. Fetch emails from Microsoft Graph API
    2. Run deterministic classifier on unprocessed emails
    3. Check overrides on newly-classified Other emails
    4. Run AI classifier on remaining unprocessed emails
    5. Run urgency scoring on all Work items (categories 1-5)
    6. Run batch assignment to distribute across due dates
    7. Sync assigned items to Microsoft To-Do

    Args:
        db: Database session
        fetch_count: Number of emails to fetch from Graph API

    Returns:
        Comprehensive report with statistics and timing from each stage
    """
    pipeline_start_time = time.time()

    # Initialize report structure with all 7 phases
    report = {
        "phase_1_fetch": {"total": 0, "new": 0, "time_seconds": 0},
        "phase_2_deterministic": {"classified": 0, "breakdown": {}, "time_seconds": 0},
        "phase_3_override": {"checked": 0, "overridden": 0, "time_seconds": 0},
        "phase_4_ai": {"classified": 0, "breakdown": {}, "time_seconds": 0},
        "phase_5_scoring": {"scored": 0, "floor_items": 0, "stale_items": 0, "time_seconds": 0},
        "phase_6_assignment": {"assigned": 0, "slots": {}, "time_seconds": 0},
        "phase_7_todo_sync": {"synced": 0, "lists_created": [], "time_seconds": 0},
        "summary": {
            "total_emails": 0,
            "work_items": 0,
            "other_items": 0,
            "total_pipeline_time_seconds": 0
        }
    }

    # ========================================================================
    # PHASE 1: FETCH EMAILS
    # ========================================================================
    phase_start = time.time()

    user = db.query(User).first()
    user_email = user.email if user else None
    user_first_name = "User"

    if user and user.display_name:
        try:
            user_first_name = user.display_name.split()[0]
        except (IndexError, AttributeError):
            user_first_name = "User"

    try:
        if not user:
            raise Exception("No authenticated user found. Please log in first.")

        graph_client = GraphClient()
        access_token = await graph_client.get_token(user.email, db)
        emails = await graph_client.fetch_inbox_emails(access_token, fetch_count)
        new_count = graph_client.store_emails(emails, db)

        report["phase_1_fetch"]["total"] = len(emails)
        report["phase_1_fetch"]["new"] = new_count

    except Exception as e:
        # If fetch fails, continue with existing unprocessed emails
        report["phase_1_fetch"]["error"] = str(e)

    report["phase_1_fetch"]["time_seconds"] = round(time.time() - phase_start, 2)

    # ========================================================================
    # PHASE 2: DETERMINISTIC CLASSIFICATION
    # ========================================================================
    phase_start = time.time()

    # Filter criteria:
    # 1. Only unprocessed emails
    # 2. Not older than 45 days
    # 3. Not processed in the last 3 days
    cutoff_date = datetime.utcnow() - timedelta(days=45)
    recent_processing_cutoff = datetime.utcnow() - timedelta(days=3)

    # Get email IDs that were classified in the last 3 days
    recently_processed_ids = db.query(ClassificationLog.email_id).filter(
        ClassificationLog.created_at >= recent_processing_cutoff
    ).distinct().all()
    recently_processed_ids = [id_tuple[0] for id_tuple in recently_processed_ids]

    unprocessed_emails = db.query(Email).filter(
        Email.status == "unprocessed",
        Email.received_at >= cutoff_date,  # Not older than 45 days
        ~Email.id.in_(recently_processed_ids) if recently_processed_ids else True  # Not processed recently
    ).all()

    # Track filtered emails for reporting
    total_unprocessed = db.query(Email).filter(Email.status == "unprocessed").count()
    filtered_count = total_unprocessed - len(unprocessed_emails)
    if filtered_count > 0:
        report["phase_2_deterministic"]["filtered"] = filtered_count

    deterministic_breakdown = {}

    for email in unprocessed_emails:
        email_dict = _email_to_dict(email)
        result = classify_deterministic(email_dict, user_email)

        if result:
            category_id = result["category_id"]
            confidence = result["confidence"]
            rule = result["rule"]

            # Check for override immediately
            override_result = check_override(
                email_dict,
                category_id,
                user_email=user_email,
                first_name=user_first_name,
                db=db
            )

            if override_result.get("override"):
                # Override triggered - keep as unprocessed for AI
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

                report["phase_3_override"]["checked"] += 1
                report["phase_3_override"]["overridden"] += 1

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

                report["phase_2_deterministic"]["classified"] += 1
                category_key = f"{category_id}"
                deterministic_breakdown[category_key] = deterministic_breakdown.get(category_key, 0) + 1

                report["phase_3_override"]["checked"] += 1

    db.commit()
    report["phase_2_deterministic"]["breakdown"] = deterministic_breakdown
    report["phase_2_deterministic"]["time_seconds"] = round(time.time() - phase_start, 2)

    # ========================================================================
    # PHASE 3: OVERRIDE CHECK (timing included in phase 2)
    # ========================================================================
    # Note: Override checking happens during phase 2, timing already captured above
    report["phase_3_override"]["time_seconds"] = 0  # Included in phase 2 timing

    # ========================================================================
    # PHASE 4: AI CLASSIFICATION
    # ========================================================================
    phase_start = time.time()

    # Re-query for remaining unprocessed emails (with same filters)
    # Re-fetch recently processed IDs in case classifications just happened
    recently_processed_ids = db.query(ClassificationLog.email_id).filter(
        ClassificationLog.created_at >= recent_processing_cutoff
    ).distinct().all()
    recently_processed_ids = [id_tuple[0] for id_tuple in recently_processed_ids]

    remaining_unprocessed = db.query(Email).filter(
        Email.status == "unprocessed",
        Email.received_at >= cutoff_date,  # Not older than 45 days
        ~Email.id.in_(recently_processed_ids) if recently_processed_ids else True  # Not processed recently
    ).all()

    ai_breakdown = {}
    ai_failed = 0

    for i, email in enumerate(remaining_unprocessed):
        try:
            email_dict = _email_to_dict(email)
            # Run blocking AI classifier in thread pool to avoid blocking event loop
            result = await asyncio.to_thread(classify_with_ai, email_dict)

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

            report["phase_4_ai"]["classified"] += 1
            category_key = f"{result['category_id']}"
            ai_breakdown[category_key] = ai_breakdown.get(category_key, 0) + 1

            # Commit after each successful classification
            db.commit()

            # Rate limiting - use asyncio.sleep for non-blocking sleep
            if i < len(remaining_unprocessed) - 1:
                await asyncio.sleep(0.5)

        except Exception as e:
            ai_failed += 1
            db.rollback()
            # Continue processing other emails
            if i < len(remaining_unprocessed) - 1:
                await asyncio.sleep(0.5)

    report["phase_4_ai"]["breakdown"] = ai_breakdown
    if ai_failed > 0:
        report["phase_4_ai"]["failed"] = ai_failed
    report["phase_4_ai"]["time_seconds"] = round(time.time() - phase_start, 2)

    # ========================================================================
    # PHASE 5: URGENCY SCORING
    # ========================================================================
    phase_start = time.time()

    # Fetch all classified Work emails (categories 1-5)
    work_emails = db.query(Email).filter(
        Email.status == "classified",
        Email.category_id.in_([1, 2, 3, 4, 5])
    ).all()

    # Get user domain for scoring
    user_domain = "live.com"
    if user and user.email:
        user_domain = user.email.split('@')[-1] if '@' in user.email else "live.com"

    floor_items_count = 0
    stale_items_count = 0

    # Score each Work email
    for email in work_emails:
        try:
            email_dict = _email_to_dict(email)

            # Run scoring engine
            result = score_email(email_dict, db=db, user_domain=user_domain)
            score = result["urgency_score"]
            raw_score = result.get("raw_score", score)
            stale_bonus = result.get("stale_bonus", 0)
            stale_days = result.get("stale_days", 0)
            floor_override = result.get("floor_override", False)
            force_today = result.get("force_today", False)

            # Update email's urgency_score
            email.urgency_score = score

            # Track floor and stale items
            if floor_override:
                floor_items_count += 1
            if stale_bonus > 0:
                stale_items_count += 1

            # Update or create urgency_scores record
            urgency_record = db.query(UrgencyScore).filter(
                UrgencyScore.email_id == email.id
            ).first()

            signals_data = {
                "signals": result["signals"],
                "weights": result["weights"],
                "breakdown": result["breakdown"]
            }

            if urgency_record:
                urgency_record.urgency_score = score
                urgency_record.raw_score = raw_score
                urgency_record.stale_bonus = stale_bonus
                urgency_record.stale_days = stale_days
                urgency_record.floor_override = floor_override
                urgency_record.force_today = force_today
                urgency_record.signals_json = json.dumps(signals_data)
                urgency_record.scored_at = datetime.utcnow()
            else:
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

        except Exception as e:
            # Log error but continue scoring other emails
            continue

    db.commit()

    report["phase_5_scoring"]["scored"] = len(work_emails)
    report["phase_5_scoring"]["floor_items"] = floor_items_count
    report["phase_5_scoring"]["stale_items"] = stale_items_count
    report["phase_5_scoring"]["time_seconds"] = round(time.time() - phase_start, 2)

    # ========================================================================
    # PHASE 6: BATCH ASSIGNMENT
    # ========================================================================
    phase_start = time.time()

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

    if scored_emails_db:
        # Convert to format expected by assign_due_dates
        scored_emails = []
        for email, urgency in scored_emails_db:
            scored_emails.append({
                "email_id": email.id,
                "urgency_score": urgency.urgency_score,
                "floor_override": urgency.floor_override,
                "force_today": urgency.force_today
            })

        # Run assignment algorithm
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
                if assignment["due_date"]:
                    due_date_str = assignment["due_date"]
                    email.due_date = datetime.strptime(due_date_str, "%Y-%m-%d")
                else:
                    email.due_date = None

        db.commit()

        # Generate summary
        summary = get_assignment_summary(assignments)

        report["phase_6_assignment"]["assigned"] = len(assignments)
        report["phase_6_assignment"]["slots"] = {
            "today": summary['by_slot']['today'],
            "tomorrow": summary['by_slot']['tomorrow'],
            "this_week": summary['by_slot']['this_week'],
            "next_week": summary['by_slot']['next_week'],
            "no_date": summary['by_slot']['no_date']
        }

    report["phase_6_assignment"]["time_seconds"] = round(time.time() - phase_start, 2)

    # ========================================================================
    # PHASE 7: MICROSOFT TO-DO SYNC
    # ========================================================================
    phase_start = time.time()

    try:
        # Get access token
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

        if emails_query:
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

            # Sync to Microsoft To-Do (batch method)
            sync_result = sync_all_tasks_batch(access_token, assigned_emails, db)

            # Commit database updates (todo_task_id values)
            db.commit()

            report["phase_7_todo_sync"]["synced"] = sync_result['synced']
            report["phase_7_todo_sync"]["lists_created"] = sync_result['lists_created']
            if sync_result.get('errors'):
                report["phase_7_todo_sync"]["errors"] = sync_result['errors']

    except TokenExpiredError as e:
        report["phase_7_todo_sync"]["error"] = f"Token expired: {str(e)}"
    except Exception as e:
        report["phase_7_todo_sync"]["error"] = str(e)

    report["phase_7_todo_sync"]["time_seconds"] = round(time.time() - phase_start, 2)

    # ========================================================================
    # FINAL SUMMARY
    # ========================================================================
    # Count total emails by category
    total_emails = db.query(Email).count()

    # Work items (categories 1-5)
    work_items = db.query(Email).filter(
        Email.category_id.in_([1, 2, 3, 4, 5])
    ).count()

    # Other items (categories 6-11)
    other_items = db.query(Email).filter(
        Email.category_id.in_([6, 7, 8, 9, 10, 11])
    ).count()

    total_pipeline_time = time.time() - pipeline_start_time

    report["summary"]["total_emails"] = total_emails
    report["summary"]["work_items"] = work_items
    report["summary"]["other_items"] = other_items
    report["summary"]["total_pipeline_time_seconds"] = round(total_pipeline_time, 2)

    return report


def _email_to_dict(email: Email) -> Dict:
    """Convert SQLAlchemy Email model to dictionary for classifiers."""
    return {
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
