"""
Due Date Assignment Service

Implements the batch assignment algorithm for distributing emails across
today, tomorrow, this week (Friday), and next week (Monday) based on
urgency scores, floor overrides, and task limits.
"""

from datetime import date, timedelta
from typing import List, Dict, Optional


def assign_due_dates(
    scored_emails: List[Dict],
    settings: Optional[Dict] = None
) -> List[Dict]:
    """
    Assign due dates to scored emails using batch assignment algorithm.

    Algorithm:
    1. Split into Floor Pool (floor_override=True OR force_today=True) and Standard Pool
    2. Sort Standard Pool by urgency_score descending
    3. Calculate available Today slots = task_limit - len(floor_pool)
    4. Assign Floor Pool items to Today with appropriate reason
    5. Assign Standard Pool items:
       - First [available_today_slots] items: Today
       - Next [task_limit] items: Tomorrow
       - Next [task_limit * 2] items: This Friday
       - Items with score < threshold: null (no date)
       - Remaining items >= threshold: Next Monday

    Args:
        scored_emails: List of email dicts with fields:
                      - email_id: int
                      - urgency_score: float
                      - floor_override: bool (email hit urgency floor)
                      - force_today: bool (email is stale and forced today)
        settings: Dict with optional keys:
                 - task_limit: int (default 20) - max tasks per day
                 - urgency_floor: int (default 90) - urgency floor threshold
                 - time_pressure_threshold: int (default 15) - min score to get a date

    Returns:
        List of assignment dicts with fields:
        - email_id: int
        - due_date: str (YYYY-MM-DD) or None
        - pool: str ("floor" or "standard")
        - assignment_reason: str (reason for assignment)
        - slot: str ("today", "tomorrow", "this_week", "next_week", "no_date")
    """
    # Default settings
    if settings is None:
        settings = {}

    task_limit = settings.get('task_limit', 20)
    urgency_floor = settings.get('urgency_floor', 90)
    time_pressure_threshold = settings.get('time_pressure_threshold', 15)

    # Calculate dates
    today = date.today()
    tomorrow = today + timedelta(days=1)

    # Calculate this Friday (end of this week)
    # If today is Mon-Thu: use this week's Friday
    # If today is Fri: use today
    # If today is Sat-Sun: use next week's Friday
    days_until_friday = (4 - today.weekday()) % 7
    this_friday = today + timedelta(days=days_until_friday)

    # Calculate next Monday (always next week, never today)
    days_until_next_monday = (7 - today.weekday()) % 7
    if days_until_next_monday == 0:
        days_until_next_monday = 7
    next_monday = today + timedelta(days=days_until_next_monday)

    # Split into Floor Pool and Standard Pool
    floor_pool = []
    standard_pool = []

    for email in scored_emails:
        if email.get('floor_override') or email.get('force_today'):
            floor_pool.append(email)
        else:
            standard_pool.append(email)

    # Sort Standard Pool by urgency_score descending (highest priority first)
    standard_pool.sort(key=lambda x: x.get('urgency_score', 0), reverse=True)

    # Calculate available today slots for standard pool
    available_today_slots = task_limit - len(floor_pool)
    if available_today_slots < 0:
        available_today_slots = 0

    # Assignments list
    assignments = []

    # ========================================================================
    # Assign Floor Pool items - all get Today
    # ========================================================================
    for email in floor_pool:
        # Determine reason: stale_force_today takes precedence
        if email.get('force_today'):
            reason = "stale_force_today"
        else:
            reason = "urgency_floor"

        assignments.append({
            "email_id": email.get('email_id'),
            "due_date": today.isoformat(),
            "pool": "floor",
            "assignment_reason": reason,
            "slot": "today"
        })

    # ========================================================================
    # Assign Standard Pool items
    # ========================================================================
    standard_idx = 0

    # TODAY SLOTS: First [available_today_slots] items
    while standard_idx < len(standard_pool) and standard_idx < available_today_slots:
        email = standard_pool[standard_idx]
        assignments.append({
            "email_id": email.get('email_id'),
            "due_date": today.isoformat(),
            "pool": "standard",
            "assignment_reason": "high_priority",
            "slot": "today"
        })
        standard_idx += 1

    # TOMORROW SLOTS: Next [task_limit] items
    tomorrow_end = standard_idx + task_limit
    while standard_idx < len(standard_pool) and standard_idx < tomorrow_end:
        email = standard_pool[standard_idx]
        assignments.append({
            "email_id": email.get('email_id'),
            "due_date": tomorrow.isoformat(),
            "pool": "standard",
            "assignment_reason": "next_day",
            "slot": "tomorrow"
        })
        standard_idx += 1

    # THIS WEEK (FRIDAY) SLOTS: Next [task_limit * 2] items
    this_week_end = standard_idx + (task_limit * 2)
    while standard_idx < len(standard_pool) and standard_idx < this_week_end:
        email = standard_pool[standard_idx]
        assignments.append({
            "email_id": email.get('email_id'),
            "due_date": this_friday.isoformat(),
            "pool": "standard",
            "assignment_reason": "this_week",
            "slot": "this_week"
        })
        standard_idx += 1

    # REMAINING ITEMS: Check threshold
    # - Below threshold: no date
    # - Above threshold: next Monday
    while standard_idx < len(standard_pool):
        email = standard_pool[standard_idx]
        score = email.get('urgency_score', 0)

        if score < time_pressure_threshold:
            # Below threshold - no date assigned
            assignments.append({
                "email_id": email.get('email_id'),
                "due_date": None,
                "pool": "standard",
                "assignment_reason": "below_threshold",
                "slot": "no_date"
            })
        else:
            # Above threshold but didn't fit in earlier slots - next week
            assignments.append({
                "email_id": email.get('email_id'),
                "due_date": next_monday.isoformat(),
                "pool": "standard",
                "assignment_reason": "next_week",
                "slot": "next_week"
            })

        standard_idx += 1

    return assignments


def get_assignment_summary(assignments: List[Dict]) -> Dict:
    """
    Generate a summary of the assignment distribution.

    Args:
        assignments: List of assignment dicts from assign_due_dates()

    Returns:
        Dict with summary statistics:
        - total: total emails assigned
        - by_slot: breakdown by slot (today, tomorrow, this_week, next_week, no_date)
        - by_pool: breakdown by pool (floor, standard)
        - today_count: total items due today (floor + standard)
        - floor_overflow: bool (true if floor pool exceeded task limit)
    """
    summary = {
        "total": len(assignments),
        "by_slot": {
            "today": 0,
            "tomorrow": 0,
            "this_week": 0,
            "next_week": 0,
            "no_date": 0
        },
        "by_pool": {
            "floor": 0,
            "standard": 0
        },
        "today_count": 0,
        "floor_overflow": False
    }

    floor_count = 0

    for assignment in assignments:
        slot = assignment.get('slot')
        pool = assignment.get('pool')

        if slot in summary['by_slot']:
            summary['by_slot'][slot] += 1

        if pool in summary['by_pool']:
            summary['by_pool'][pool] += 1

        if slot == 'today':
            summary['today_count'] += 1
            if pool == 'floor':
                floor_count += 1

    # Check if floor pool exceeded typical task limit (assume 20 if not tracked)
    # This is a heuristic: if floor items alone are > 20, we likely have overflow
    summary['floor_overflow'] = floor_count > 20

    return summary
