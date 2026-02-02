#!/usr/bin/env python3
"""
Test script for the due date assignment algorithm.

Tests various scenarios including floor pool overflow, standard pool distribution,
and threshold handling.
"""

from app.services.assignment import assign_due_dates, get_assignment_summary
from datetime import date, timedelta


def print_section(title):
    """Print a section header."""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print('='*70)


def print_assignments(assignments, limit=None):
    """Print assignment details."""
    for i, a in enumerate(assignments[:limit] if limit else assignments):
        print(f"{i+1}. Email {a['email_id']}: {a['due_date']} ({a['slot']}) - {a['assignment_reason']}")
    if limit and len(assignments) > limit:
        print(f"... and {len(assignments) - limit} more")


def test_basic_scenario():
    """Test basic scenario with mixed priority emails."""
    print_section("Test 1: Basic Scenario")

    # Create sample emails
    emails = [
        # Floor pool items (3)
        {"email_id": 1, "urgency_score": 100, "floor_override": True, "force_today": True},
        {"email_id": 2, "urgency_score": 100, "floor_override": True, "force_today": False},
        {"email_id": 3, "urgency_score": 95, "floor_override": False, "force_today": True},

        # Standard pool items (sorted by score)
        {"email_id": 4, "urgency_score": 85, "floor_override": False, "force_today": False},
        {"email_id": 5, "urgency_score": 75, "floor_override": False, "force_today": False},
        {"email_id": 6, "urgency_score": 65, "floor_override": False, "force_today": False},
        {"email_id": 7, "urgency_score": 55, "floor_override": False, "force_today": False},
        {"email_id": 8, "urgency_score": 45, "floor_override": False, "force_today": False},
        {"email_id": 9, "urgency_score": 35, "floor_override": False, "force_today": False},
        {"email_id": 10, "urgency_score": 25, "floor_override": False, "force_today": False},
        {"email_id": 11, "urgency_score": 10, "floor_override": False, "force_today": False},
    ]

    settings = {"task_limit": 5, "time_pressure_threshold": 15}
    assignments = assign_due_dates(emails, settings)
    summary = get_assignment_summary(assignments)

    print(f"\nSettings: task_limit=5, threshold=15")
    print(f"Emails: {len(emails)} total, 3 in floor pool, 8 in standard pool")
    print(f"\nExpected distribution:")
    print(f"  Today: 3 floor + 2 standard = 5 (task_limit)")
    print(f"  Tomorrow: 5 (task_limit)")
    print(f"  This week: 1 (remaining with score >= 15)")
    print(f"  No date: 1 (score < 15)")

    print(f"\nActual distribution:")
    print(f"  Today: {summary['by_slot']['today']}")
    print(f"  Tomorrow: {summary['by_slot']['tomorrow']}")
    print(f"  This week: {summary['by_slot']['this_week']}")
    print(f"  Next week: {summary['by_slot']['next_week']}")
    print(f"  No date: {summary['by_slot']['no_date']}")

    print(f"\nAssignments:")
    print_assignments(assignments)


def test_floor_overflow():
    """Test scenario where floor pool exceeds task limit."""
    print_section("Test 2: Floor Pool Overflow")

    # Create 25 floor items with task_limit=20
    emails = []
    for i in range(25):
        emails.append({
            "email_id": i + 1,
            "urgency_score": 100,
            "floor_override": True,
            "force_today": i % 2 == 0  # Mix of floor_override and force_today
        })

    # Add 10 standard items
    for i in range(10):
        emails.append({
            "email_id": 26 + i,
            "urgency_score": 80 - (i * 5),
            "floor_override": False,
            "force_today": False
        })

    settings = {"task_limit": 20, "time_pressure_threshold": 15}
    assignments = assign_due_dates(emails, settings)
    summary = get_assignment_summary(assignments)

    print(f"\nSettings: task_limit=20, threshold=15")
    print(f"Emails: {len(emails)} total, 25 in floor pool, 10 in standard pool")
    print(f"\nExpected distribution:")
    print(f"  Today: 25 floor + 0 standard = 25 (overflow!)")
    print(f"  Tomorrow: 10 (all standard items, within task_limit)")

    print(f"\nActual distribution:")
    print(f"  Today: {summary['by_slot']['today']} (floor overflow: {summary['floor_overflow']})")
    print(f"  Tomorrow: {summary['by_slot']['tomorrow']}")
    print(f"  This week: {summary['by_slot']['this_week']}")
    print(f"  Next week: {summary['by_slot']['next_week']}")

    print(f"\nFirst 10 assignments:")
    print_assignments(assignments, limit=10)


def test_full_capacity():
    """Test all slots at capacity with next week overflow."""
    print_section("Test 3: Full Capacity with Next Week Overflow")

    # Create emails to fill all slots
    emails = []

    # 5 floor items
    for i in range(5):
        emails.append({
            "email_id": i + 1,
            "urgency_score": 100,
            "floor_override": True,
            "force_today": False
        })

    # 100 standard items with high scores
    for i in range(100):
        emails.append({
            "email_id": 6 + i,
            "urgency_score": 90 - i,
            "floor_override": False,
            "force_today": False
        })

    settings = {"task_limit": 20, "time_pressure_threshold": 15}
    assignments = assign_due_dates(emails, settings)
    summary = get_assignment_summary(assignments)

    print(f"\nSettings: task_limit=20, threshold=15")
    print(f"Emails: {len(emails)} total, 5 in floor pool, 100 in standard pool")
    print(f"\nExpected distribution:")
    print(f"  Today: 5 floor + 15 standard = 20")
    print(f"  Tomorrow: 20")
    print(f"  This week: 40 (task_limit * 2)")
    print(f"  Next week: 25 (remaining with score >= 15)")
    print(f"  No date: ~15 (items with score < 15)")

    print(f"\nActual distribution:")
    print(f"  Today: {summary['by_slot']['today']}")
    print(f"  Tomorrow: {summary['by_slot']['tomorrow']}")
    print(f"  This week: {summary['by_slot']['this_week']}")
    print(f"  Next week: {summary['by_slot']['next_week']}")
    print(f"  No date: {summary['by_slot']['no_date']}")

    print(f"\nFirst 10 and last 10 assignments:")
    print("First 10:")
    print_assignments(assignments[:10])
    print("\nLast 10:")
    print_assignments(assignments[-10:])


def test_below_threshold():
    """Test items below threshold get no date."""
    print_section("Test 4: Below Threshold Items")

    emails = []

    # Create emails with low scores
    for i in range(20):
        emails.append({
            "email_id": i + 1,
            "urgency_score": 20 - i,  # Scores from 20 down to 1
            "floor_override": False,
            "force_today": False
        })

    settings = {"task_limit": 5, "time_pressure_threshold": 15}
    assignments = assign_due_dates(emails, settings)
    summary = get_assignment_summary(assignments)

    print(f"\nSettings: task_limit=5, threshold=15")
    print(f"Emails: {len(emails)} total, all in standard pool, scores 20-1")
    print(f"\nExpected distribution:")
    print(f"  Today: 5 (scores 20-16)")
    print(f"  Tomorrow: 5 (scores 15-11, but only 1 is >= 15)")
    print(f"  This week: 10 (but some will be < 15)")
    print(f"  No date: items with score < 15")

    print(f"\nActual distribution:")
    print(f"  Today: {summary['by_slot']['today']}")
    print(f"  Tomorrow: {summary['by_slot']['tomorrow']}")
    print(f"  This week: {summary['by_slot']['this_week']}")
    print(f"  Next week: {summary['by_slot']['next_week']}")
    print(f"  No date: {summary['by_slot']['no_date']}")

    print(f"\nAll assignments:")
    print_assignments(assignments)


def test_date_calculations():
    """Test that date calculations are correct."""
    print_section("Test 5: Date Calculations")

    today = date.today()
    tomorrow = today + timedelta(days=1)

    # Calculate this Friday
    days_until_friday = (4 - today.weekday()) % 7
    this_friday = today + timedelta(days=days_until_friday)

    # Calculate next Monday
    days_until_next_monday = (7 - today.weekday()) % 7
    if days_until_next_monday == 0:
        days_until_next_monday = 7
    next_monday = today + timedelta(days=days_until_next_monday)

    weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

    print(f"\nToday: {today.isoformat()} ({weekday_names[today.weekday()]})")
    print(f"Tomorrow: {tomorrow.isoformat()} ({weekday_names[tomorrow.weekday()]})")
    print(f"This Friday: {this_friday.isoformat()} ({weekday_names[this_friday.weekday()]})")
    print(f"Next Monday: {next_monday.isoformat()} ({weekday_names[next_monday.weekday()]})")

    # Create a simple test
    emails = [
        {"email_id": 1, "urgency_score": 50, "floor_override": False, "force_today": False},
        {"email_id": 2, "urgency_score": 40, "floor_override": False, "force_today": False},
        {"email_id": 3, "urgency_score": 30, "floor_override": False, "force_today": False},
        {"email_id": 4, "urgency_score": 20, "floor_override": False, "force_today": False},
    ]

    settings = {"task_limit": 1, "time_pressure_threshold": 15}
    assignments = assign_due_dates(emails, settings)

    print(f"\nAssignments with task_limit=1:")
    for a in assignments:
        print(f"  Email {a['email_id']}: {a['due_date']} ({a['slot']})")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("  DUE DATE ASSIGNMENT ALGORITHM - TEST SUITE")
    print("="*70)

    test_basic_scenario()
    test_floor_overflow()
    test_full_capacity()
    test_below_threshold()
    test_date_calculations()

    print("\n" + "="*70)
    print("  ALL TESTS COMPLETED")
    print("="*70 + "\n")
