#!/usr/bin/env python3
"""
Test assignment algorithm with real scored emails from the database.
"""

from app.database import SessionLocal
from app.models import Email, UrgencyScore
from app.services.assignment import assign_due_dates, get_assignment_summary
import json


def test_with_real_data():
    """Test assignment algorithm with real scored emails."""
    db = SessionLocal()

    try:
        # Fetch all scored Work emails
        scored_emails_db = db.query(Email, UrgencyScore).join(
            UrgencyScore, Email.id == UrgencyScore.email_id
        ).filter(
            Email.status == "classified",
            Email.category_id.in_([1, 2, 3, 4, 5])
        ).order_by(
            UrgencyScore.urgency_score.desc()
        ).all()

        if not scored_emails_db:
            print("No scored emails found in database!")
            return

        print(f"\nFound {len(scored_emails_db)} scored Work emails in database")

        # Convert to format expected by assign_due_dates
        scored_emails = []
        for email, urgency in scored_emails_db:
            scored_emails.append({
                "email_id": email.id,
                "urgency_score": urgency.urgency_score,
                "floor_override": urgency.floor_override,
                "force_today": urgency.force_today,
                "subject": email.subject,  # For display purposes
                "raw_score": urgency.raw_score,
                "stale_days": urgency.stale_days
            })

        # Run assignment with default settings
        print("\n" + "="*70)
        print("TEST 1: Default Settings (task_limit=20, threshold=15)")
        print("="*70)

        settings = {"task_limit": 20, "urgency_floor": 90, "time_pressure_threshold": 15}
        assignments = assign_due_dates(scored_emails, settings)
        summary = get_assignment_summary(assignments)

        print(f"\nSummary:")
        print(f"  Total emails: {summary['total']}")
        print(f"  Floor pool: {summary['by_pool']['floor']}")
        print(f"  Standard pool: {summary['by_pool']['standard']}")
        print(f"  Floor overflow: {summary['floor_overflow']}")
        print(f"\nDistribution by slot:")
        print(f"  Today: {summary['by_slot']['today']}")
        print(f"  Tomorrow: {summary['by_slot']['tomorrow']}")
        print(f"  This week (Friday): {summary['by_slot']['this_week']}")
        print(f"  Next week (Monday): {summary['by_slot']['next_week']}")
        print(f"  No date: {summary['by_slot']['no_date']}")

        # Show sample assignments from each category
        print(f"\nSample assignments:")

        today_items = [a for a in assignments if a['slot'] == 'today']
        if today_items:
            print(f"\n  TODAY ({len(today_items)} items):")
            for a in today_items[:5]:
                email = next(e for e in scored_emails if e['email_id'] == a['email_id'])
                print(f"    [{a['pool']}] Email {a['email_id']}: {email['subject'][:50]}")
                print(f"        Score: {email['urgency_score']:.1f} (raw: {email['raw_score']:.1f}, stale: {email['stale_days']}d)")
                print(f"        Reason: {a['assignment_reason']}")
            if len(today_items) > 5:
                print(f"    ... and {len(today_items) - 5} more")

        tomorrow_items = [a for a in assignments if a['slot'] == 'tomorrow']
        if tomorrow_items:
            print(f"\n  TOMORROW ({len(tomorrow_items)} items):")
            for a in tomorrow_items[:3]:
                email = next(e for e in scored_emails if e['email_id'] == a['email_id'])
                print(f"    Email {a['email_id']}: {email['subject'][:50]}")
                print(f"        Score: {email['urgency_score']:.1f}")

        this_week_items = [a for a in assignments if a['slot'] == 'this_week']
        if this_week_items:
            print(f"\n  THIS WEEK/Friday ({len(this_week_items)} items):")
            for a in this_week_items[:3]:
                email = next(e for e in scored_emails if e['email_id'] == a['email_id'])
                print(f"    Email {a['email_id']}: {email['subject'][:50]}")
                print(f"        Score: {email['urgency_score']:.1f}")

        next_week_items = [a for a in assignments if a['slot'] == 'next_week']
        if next_week_items:
            print(f"\n  NEXT WEEK/Monday ({len(next_week_items)} items):")
            for a in next_week_items[:3]:
                email = next(e for e in scored_emails if e['email_id'] == a['email_id'])
                print(f"    Email {a['email_id']}: {email['subject'][:50]}")
                print(f"        Score: {email['urgency_score']:.1f}")

        no_date_items = [a for a in assignments if a['slot'] == 'no_date']
        if no_date_items:
            print(f"\n  NO DATE ({len(no_date_items)} items):")
            for a in no_date_items[:3]:
                email = next(e for e in scored_emails if e['email_id'] == a['email_id'])
                print(f"    Email {a['email_id']}: {email['subject'][:50]}")
                print(f"        Score: {email['urgency_score']:.1f} (below threshold)")

        # Test with smaller task limit
        print("\n\n" + "="*70)
        print("TEST 2: Smaller Task Limit (task_limit=10)")
        print("="*70)

        settings = {"task_limit": 10, "urgency_floor": 90, "time_pressure_threshold": 15}
        assignments2 = assign_due_dates(scored_emails, settings)
        summary2 = get_assignment_summary(assignments2)

        print(f"\nDistribution by slot:")
        print(f"  Today: {summary2['by_slot']['today']}")
        print(f"  Tomorrow: {summary2['by_slot']['tomorrow']}")
        print(f"  This week (Friday): {summary2['by_slot']['this_week']}")
        print(f"  Next week (Monday): {summary2['by_slot']['next_week']}")
        print(f"  No date: {summary2['by_slot']['no_date']}")
        print(f"  Floor overflow: {summary2['floor_overflow']}")

        # Test with higher threshold
        print("\n\n" + "="*70)
        print("TEST 3: Higher Threshold (threshold=50)")
        print("="*70)

        settings = {"task_limit": 20, "urgency_floor": 90, "time_pressure_threshold": 50}
        assignments3 = assign_due_dates(scored_emails, settings)
        summary3 = get_assignment_summary(assignments3)

        print(f"\nDistribution by slot:")
        print(f"  Today: {summary3['by_slot']['today']}")
        print(f"  Tomorrow: {summary3['by_slot']['tomorrow']}")
        print(f"  This week (Friday): {summary3['by_slot']['this_week']}")
        print(f"  Next week (Monday): {summary3['by_slot']['next_week']}")
        print(f"  No date: {summary3['by_slot']['no_date']}")

        print("\n" + "="*70)
        print("ALL TESTS COMPLETED")
        print("="*70 + "\n")

    finally:
        db.close()


if __name__ == "__main__":
    test_with_real_data()
