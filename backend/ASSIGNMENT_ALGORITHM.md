# Due Date Assignment Algorithm

## Overview

The assignment algorithm distributes scored emails across different time slots (Today, Tomorrow, This Week, Next Week) based on urgency scores, floor overrides, and configurable task limits. This ensures high-priority items get immediate attention while spreading the workload over the week.

## Algorithm Flow

### 1. Pool Separation

Emails are split into two pools:

**Floor Pool**: Emails that must be done today
- `floor_override = True` (urgency score >= urgency floor threshold)
- `force_today = True` (stale for 11+ days, escalated to priority)

**Standard Pool**: All other emails
- Sorted by `urgency_score` descending (highest priority first)

### 2. Slot Allocation

Available slots are calculated and filled in order:

```
available_today_slots = task_limit - len(floor_pool)
if available_today_slots < 0: available_today_slots = 0
```

**Today Slots**:
- All Floor Pool items (no limit)
- First `available_today_slots` items from Standard Pool

**Tomorrow Slots**:
- Next `task_limit` items from Standard Pool

**This Week (Friday) Slots**:
- Next `task_limit * 2` items from Standard Pool

**Remaining Items**:
- If `urgency_score < time_pressure_threshold`: No date assigned
- If `urgency_score >= time_pressure_threshold`: Next Monday

### 3. Date Calculations

```python
today = date.today()
tomorrow = today + timedelta(days=1)

# This Friday (or today if today is Friday)
days_until_friday = (4 - today.weekday()) % 7
this_friday = today + timedelta(days=days_until_friday)

# Next Monday (always next week, never today)
days_until_next_monday = (7 - today.weekday()) % 7
if days_until_next_monday == 0:
    days_until_next_monday = 7
next_monday = today + timedelta(days=days_until_next_monday)
```

## Settings

### Default Settings

```python
{
    "task_limit": 20,              # Max tasks per day/period
    "urgency_floor": 90,            # Score threshold for floor override
    "time_pressure_threshold": 15   # Minimum score to get a date
}
```

### Configurable Parameters

- **task_limit**: Maximum number of tasks to assign per time period
  - Controls daily workload capacity
  - Floor pool items are NOT limited by this (they all get Today)
  - Standard pool items are distributed across slots using this limit

- **urgency_floor**: Minimum score for automatic floor override
  - Items with `urgency_score >= urgency_floor` get `floor_override = True`
  - These items bypass the standard pool and go directly to Today

- **time_pressure_threshold**: Minimum score to receive any due date
  - Items below this threshold are considered low priority
  - They receive `due_date = null` and `assignment_reason = "below_threshold"`

## Assignment Reasons

Each assignment includes a reason code:

| Reason | Description | Pool | Slot |
|--------|-------------|------|------|
| `stale_force_today` | Email is 11+ days old, forced to today | Floor | Today |
| `urgency_floor` | Score >= urgency_floor threshold | Floor | Today |
| `high_priority` | Top items from standard pool | Standard | Today |
| `next_day` | High priority, scheduled for tomorrow | Standard | Tomorrow |
| `this_week` | Scheduled for end of week | Standard | This Week |
| `next_week` | Scheduled for next Monday | Standard | Next Week |
| `below_threshold` | Score too low for scheduling | Standard | No Date |

## Floor Pool Overflow

When the Floor Pool exceeds `task_limit`:
- All floor items still get assigned to Today
- `available_today_slots` becomes 0
- All Standard Pool items shift to Tomorrow and beyond
- Summary includes `floor_overflow: true` flag

**Example**:
```
task_limit = 20
floor_pool = 25 items
standard_pool = 15 items

Result:
  Today: 25 (all floor items)
  Tomorrow: 15 (all standard items)
  floor_overflow: true
```

## Usage Examples

### Basic Usage

```python
from app.services.assignment import assign_due_dates, get_assignment_summary

# Prepare scored emails
scored_emails = [
    {
        "email_id": 1,
        "urgency_score": 95,
        "floor_override": True,
        "force_today": False
    },
    {
        "email_id": 2,
        "urgency_score": 75,
        "floor_override": False,
        "force_today": False
    },
    # ... more emails
]

# Assign due dates with default settings
assignments = assign_due_dates(scored_emails)

# Get summary
summary = get_assignment_summary(assignments)
print(f"Today: {summary['by_slot']['today']}")
print(f"Tomorrow: {summary['by_slot']['tomorrow']}")
```

### Custom Settings

```python
# Smaller daily capacity, higher threshold
settings = {
    "task_limit": 10,
    "urgency_floor": 95,
    "time_pressure_threshold": 30
}

assignments = assign_due_dates(scored_emails, settings)
```

### Integration with Database

```python
from app.database import SessionLocal
from app.models import Email, UrgencyScore
from app.services.assignment import assign_due_dates

db = SessionLocal()

# Fetch scored emails
scored_emails_db = db.query(Email, UrgencyScore).join(
    UrgencyScore, Email.id == UrgencyScore.email_id
).filter(
    Email.status == "classified",
    Email.category_id.in_([1, 2, 3, 4, 5])
).order_by(
    UrgencyScore.urgency_score.desc()
).all()

# Convert to assignment format
scored_emails = [
    {
        "email_id": email.id,
        "urgency_score": urgency.urgency_score,
        "floor_override": urgency.floor_override,
        "force_today": urgency.force_today
    }
    for email, urgency in scored_emails_db
]

# Assign dates
assignments = assign_due_dates(scored_emails)

# Update database with assignments
for assignment in assignments:
    email = db.query(Email).filter(Email.id == assignment["email_id"]).first()
    if email:
        email.due_date = assignment["due_date"]
        email.assignment_slot = assignment["slot"]

db.commit()
db.close()
```

## Return Format

### Assignment Object

```python
{
    "email_id": 123,
    "due_date": "2026-02-01",  # YYYY-MM-DD or None
    "pool": "floor",            # "floor" or "standard"
    "assignment_reason": "urgency_floor",
    "slot": "today"             # "today", "tomorrow", "this_week", "next_week", "no_date"
}
```

### Summary Object

```python
{
    "total": 37,
    "by_slot": {
        "today": 22,
        "tomorrow": 15,
        "this_week": 0,
        "next_week": 0,
        "no_date": 0
    },
    "by_pool": {
        "floor": 22,
        "standard": 15
    },
    "today_count": 22,
    "floor_overflow": True
}
```

## Testing

### Unit Tests

Run the comprehensive test suite:

```bash
python test_assignment.py
```

Tests include:
- Basic scenario with mixed priorities
- Floor pool overflow handling
- Full capacity with next week overflow
- Below threshold filtering
- Date calculation verification

### Real Data Tests

Test with actual database emails:

```bash
python test_assignment_real.py
```

## Design Rationale

### Why Floor Pool Overrides Task Limit?

Floor pool items (floor_override or force_today) represent critical or stale items that MUST be addressed today. These items bypass capacity limits to ensure they get immediate attention.

**Rationale**:
- **Stale emails** (11+ days old): Risk of becoming permanently lost if not addressed
- **High urgency items** (score >= floor): May have time-sensitive consequences
- **User trust**: System must guarantee these items won't be delayed

### Why Sort Standard Pool by Score?

Within the standard pool, higher urgency items should get earlier slots. Sorting ensures:
- Most critical items get Today (if slots available)
- Medium priority items get Tomorrow
- Lower priority items get later in the week

### Why Different Slot Sizes?

```
Today: task_limit
Tomorrow: task_limit
This Week: task_limit * 2
Next Week: unlimited (above threshold)
```

**Rationale**:
- Today and Tomorrow: Daily capacity is limited and consistent
- This Week (Friday): More time to handle items, so 2x capacity
- Next Week: Catch-all for items that didn't fit earlier but are still actionable

### Why Threshold Filtering?

Items below `time_pressure_threshold` don't get scheduled because:
- Low urgency scores indicate they can wait indefinitely
- No sense cluttering the schedule with low-value items
- User can manually review and promote if needed

## Future Enhancements

### Potential Improvements

1. **Load Balancing**: Distribute items across multiple days in "This Week" instead of just Friday
2. **User Preferences**: Allow per-user task limits and thresholds
3. **Category Priorities**: Weight assignments based on email category
4. **Historical Performance**: Adjust limits based on completion rates
5. **Weekend Handling**: Option to assign weekend work or push to Monday
6. **Recurring Reviews**: Auto-reassign items that missed their due date

### API Integration

Consider adding assignment endpoints to the API:

```python
@router.post("/api/emails/assign")
def assign_work_schedule(
    settings: Optional[Dict] = None,
    db: Session = Depends(get_db)
):
    """
    Assign due dates to all scored Work emails.
    """
    # Fetch scored emails from database
    # Run assignment algorithm
    # Update emails with due dates
    # Return assignment summary
```

## References

- Scoring Engine: `app/services/scoring.py`
- Floor and Stale Escalation: `URGENCY_FLOOR_AND_STALE_ESCALATION.md`
- Database Models: `app/models/urgency_score.py`
- Classification Pipeline: `COMPLETE_CLASSIFICATION_PIPELINE.md`
