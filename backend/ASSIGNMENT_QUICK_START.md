# Assignment Algorithm - Quick Start Guide

## What It Does

Assigns due dates to scored emails by distributing them across:
- **Today**: Critical items (floor pool) + top standard items
- **Tomorrow**: Next batch of high-priority items
- **This Week (Friday)**: Medium-priority items
- **Next Week (Monday)**: Lower-priority items above threshold
- **No Date**: Items below urgency threshold

## Quick Start

### 1. Run Assignment with Real Data

```bash
source venv/bin/activate
python test_assignment_real.py
```

This will:
- Load all 37 scored Work emails from database
- Run assignment with default settings (task_limit=20)
- Show distribution across time slots
- Display sample assignments from each category

### 2. Use in Python Code

```python
from app.services.assignment import assign_due_dates, get_assignment_summary

# Prepare email data
scored_emails = [
    {
        "email_id": 1,
        "urgency_score": 100.0,
        "floor_override": True,
        "force_today": True
    },
    # ... more emails
]

# Run assignment (default settings)
assignments = assign_due_dates(scored_emails)

# Get summary stats
summary = get_assignment_summary(assignments)

# Access results
for assignment in assignments:
    print(f"Email {assignment['email_id']}: {assignment['due_date']} ({assignment['slot']})")
```

### 3. Custom Settings

```python
settings = {
    "task_limit": 15,              # Reduce daily capacity
    "urgency_floor": 95,            # Higher floor threshold
    "time_pressure_threshold": 30   # Higher minimum for scheduling
}

assignments = assign_due_dates(scored_emails, settings)
```

## Current State with Real Data

Based on the 37 scored Work emails in your database:

### Default Settings (task_limit=20)
```
Floor Pool: 22 items (all 11+ days old, forced to today)
Standard Pool: 15 items

Distribution:
  Today: 22 (all floor items, overflow!)
  Tomorrow: 15 (all standard items)
  This Week: 0
  Next Week: 0
  No Date: 0
```

**Why Floor Overflow?**
- 22 emails are 11+ days old (stale_days >= 11)
- All get `force_today = True` in scoring
- Floor pool exceeds task_limit, so no Today slots for standard pool
- All standard items shift to Tomorrow

### Smaller Task Limit (task_limit=10)
```
Distribution:
  Today: 22 (floor items still get today)
  Tomorrow: 10 (task_limit)
  This Week: 5 (remaining standard items)
  Next Week: 0
  No Date: 0
```

## Key Concepts

### Floor Pool Priority
Floor pool items ALWAYS get Today, regardless of task_limit:
- `floor_override = True`: Score >= urgency floor (90)
- `force_today = True`: Email is 11+ days old

**This is by design** - critical/stale items must not be delayed.

### Assignment Slots
```
available_today_slots = task_limit - len(floor_pool)

If available_today_slots > 0:
    Assign top standard items to Today

Standard Pool Distribution:
    1. Next [available_today_slots] items → Today
    2. Next [task_limit] items → Tomorrow
    3. Next [task_limit * 2] items → This Friday
    4. Remaining items:
        - If score < threshold → No date
        - If score >= threshold → Next Monday
```

### Date Calculations
- **Today**: `date.today()`
- **Tomorrow**: `today + 1 day`
- **This Friday**: End of current week (or next Friday if past Friday)
- **Next Monday**: Start of next week (never today, even if today is Monday)

## Example Output

```
Email 20: 2026-02-01 (today) - stale_force_today
    One-Year Accelerated MBA Info Session Next Week
    Score: 100.0 (raw: 31.8, stale: 12 days)

Email 18: 2026-02-02 (tomorrow) - next_day
    You added or edited data sharing with AMEX.
    Score: 78.0 (raw: 28.0, stale: 10 days)
```

## Testing

### Unit Tests (Synthetic Data)
```bash
python test_assignment.py
```

Tests:
- Basic scenario with mixed priorities
- Floor pool overflow
- Full capacity with next week overflow
- Below threshold filtering
- Date calculations

### Real Data Tests
```bash
python test_assignment_real.py
```

Tests with actual scored emails from database:
- Default settings (task_limit=20)
- Smaller limit (task_limit=10)
- Higher threshold (threshold=50)

## Integration Points

### Scoring Pipeline
1. `POST /api/emails/score` - Score all Work emails
2. Use assignment algorithm on scored emails
3. Update email records with due dates

### Database Schema
```python
# Email model could be extended with:
class Email(Base):
    # ... existing fields ...
    due_date = Column(Date, nullable=True)
    assignment_slot = Column(String, nullable=True)
    assignment_reason = Column(String, nullable=True)
```

### API Endpoint (Future)
```python
@router.post("/api/emails/assign")
def assign_due_dates_endpoint(
    settings: Optional[Dict] = None,
    db: Session = Depends(get_db)
):
    """
    Assign due dates to all scored Work emails.

    Returns assignment summary and list of assignments.
    """
```

## Files

- **Algorithm Implementation**: `app/services/assignment.py`
- **Unit Tests**: `test_assignment.py`
- **Real Data Tests**: `test_assignment_real.py`
- **Full Documentation**: `ASSIGNMENT_ALGORITHM.md`

## Next Steps

1. **Add Database Fields**: Extend Email model with due_date, assignment_slot
2. **Create API Endpoint**: `POST /api/emails/assign`
3. **Frontend Integration**: Display emails grouped by due date
4. **Recurring Assignment**: Run nightly to reassign emails
5. **User Preferences**: Per-user task limits and thresholds

## Common Scenarios

### Scenario 1: Daily Review
```python
# Morning: Fetch today's assignments
today_assignments = [a for a in assignments if a['slot'] == 'today']
# Work through the list
```

### Scenario 2: Weekly Planning
```python
# View full week distribution
summary = get_assignment_summary(assignments)
print(f"This week total: {summary['by_slot']['today'] + summary['by_slot']['tomorrow'] + summary['by_slot']['this_week']}")
```

### Scenario 3: Capacity Management
```python
# If too many items assigned today, reduce task_limit
if summary['by_slot']['today'] > 25:
    settings = {"task_limit": 15}
    assignments = assign_due_dates(scored_emails, settings)
```

### Scenario 4: Priority Adjustment
```python
# If too many items get no date, lower threshold
if summary['by_slot']['no_date'] > 10:
    settings = {"time_pressure_threshold": 10}
    assignments = assign_due_dates(scored_emails, settings)
```
