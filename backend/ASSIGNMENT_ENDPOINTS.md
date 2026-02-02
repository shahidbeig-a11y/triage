# Assignment Endpoints

## Overview

Two new endpoints for managing email due date assignments:
- **POST /api/emails/assign** - Assign due dates to all scored Work emails
- **GET /api/emails/today** - Retrieve today's action list

## Endpoints

### POST /api/emails/assign

Assigns due dates to all scored Work emails using the batch assignment algorithm.

**URL**: `/api/emails/assign`
**Method**: `POST`
**Auth**: None (for now)

#### Process Flow

1. Fetches all Work emails (categories 1-5) with urgency scores
2. Converts to assignment format with email_id, urgency_score, floor_override, force_today
3. Runs `assign_due_dates()` algorithm with default settings:
   - task_limit: 20
   - urgency_floor: 90
   - time_pressure_threshold: 15
4. Updates each email's `due_date` field in database
5. Returns detailed assignment summary

#### Response Format

```json
{
    "total_assigned": 37,
    "slots": {
        "today": {
            "count": 22,
            "floor_count": 22,
            "standard_count": 0
        },
        "tomorrow": {
            "count": 15
        },
        "this_week": {
            "count": 0
        },
        "next_week": {
            "count": 0
        },
        "no_date": {
            "count": 0
        }
    },
    "task_limit": 20,
    "urgency_floor": 90,
    "floor_overflow": true,
    "message": "Assigned due dates to 37 Work emails"
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| total_assigned | int | Total number of emails assigned |
| slots | object | Breakdown by time slot |
| slots.today | object | Today's assignments |
| slots.today.count | int | Total emails due today |
| slots.today.floor_count | int | Floor pool items (critical/stale) |
| slots.today.standard_count | int | Standard pool items |
| slots.tomorrow.count | int | Emails due tomorrow |
| slots.this_week.count | int | Emails due Friday |
| slots.next_week.count | int | Emails due next Monday |
| slots.no_date.count | int | Emails below threshold (no date) |
| task_limit | int | Task limit setting used |
| urgency_floor | int | Urgency floor setting used |
| floor_overflow | bool | True if floor pool exceeded task limit |
| message | string | Status message |

#### Example Usage

```bash
# Assign due dates to all scored emails
curl -X POST http://localhost:8000/api/emails/assign | python3 -m json.tool
```

```python
import requests

response = requests.post("http://localhost:8000/api/emails/assign")
data = response.json()

print(f"Assigned {data['total_assigned']} emails")
print(f"Today: {data['slots']['today']['count']}")
print(f"Tomorrow: {data['slots']['tomorrow']['count']}")
```

---

### GET /api/emails/today

Returns all emails assigned to today's date - the daily action list.

**URL**: `/api/emails/today`
**Method**: `GET`
**Auth**: None (for now)

#### Process Flow

1. Queries all Work emails (categories 1-5) with due_date = today
2. Joins with urgency_scores table for additional details
3. Sorts by urgency_score descending (highest priority first)
4. Returns email details for the daily action list

#### Response Format

```json
{
    "date": "2026-02-01",
    "total": 22,
    "emails": [
        {
            "email_id": 20,
            "subject": "One-Year Accelerated MBA Info Session Next Week",
            "from_name": "CSUEB Continuing Education",
            "category_id": 2,
            "urgency_score": 100.0,
            "floor_override": true,
            "due_date": "2026-02-01"
        },
        {
            "email_id": 21,
            "subject": "Jeffrey DeHarty: Real Estate Capital Markets Executive",
            "from_name": "Robert Peck",
            "category_id": 2,
            "urgency_score": 100.0,
            "floor_override": true,
            "due_date": "2026-02-01"
        }
    ],
    "message": "Retrieved 22 emails due today"
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| date | string | Today's date (YYYY-MM-DD) |
| total | int | Number of emails due today |
| emails | array | List of email objects |
| emails[].email_id | int | Email ID |
| emails[].subject | string | Email subject |
| emails[].from_name | string | Sender name |
| emails[].category_id | int | Work category (1-5) |
| emails[].urgency_score | float | Urgency score (0-100) |
| emails[].floor_override | bool | True if hit urgency floor |
| emails[].due_date | string | Due date (YYYY-MM-DD) |
| message | string | Status message |

#### Example Usage

```bash
# Get today's action list
curl "http://localhost:8000/api/emails/today" | python3 -m json.tool
```

```python
import requests

response = requests.get("http://localhost:8000/api/emails/today")
data = response.json()

print(f"Today's Action List ({data['date']})")
print(f"Total: {data['total']} emails\n")

for i, email in enumerate(data['emails'], 1):
    priority = "🔴" if email['floor_override'] else "  "
    print(f"{i}. {priority} [{email['urgency_score']:.1f}] {email['subject']}")
```

---

## Workflow Example

### Complete Daily Workflow

```bash
# 1. Fetch new emails from Microsoft Graph
curl -X POST "http://localhost:8000/api/emails/fetch?count=50"

# 2. Run classification pipeline
curl -X POST "http://localhost:8000/api/emails/pipeline/run?fetch_count=50"

# 3. Score all Work emails
curl -X POST "http://localhost:8000/api/emails/score"

# 4. Assign due dates
curl -X POST "http://localhost:8000/api/emails/assign"

# 5. Get today's action list
curl "http://localhost:8000/api/emails/today"
```

### Python Automation Script

```python
import requests
import time

BASE_URL = "http://localhost:8000"

def process_daily_emails():
    """Run the complete email processing workflow."""

    # Step 1: Run classification pipeline (includes fetch)
    print("Running classification pipeline...")
    response = requests.post(f"{BASE_URL}/api/emails/pipeline/run?fetch_count=50")
    pipeline_result = response.json()
    print(f"  Classified: {pipeline_result.get('classified', 0)}")
    print(f"  AI classified: {pipeline_result.get('ai_classified', 0)}")

    # Step 2: Score Work emails
    print("\nScoring Work emails...")
    response = requests.post(f"{BASE_URL}/api/emails/score")
    score_result = response.json()
    print(f"  Scored: {score_result['total_scored']}")
    print(f"  Average score: {score_result['average_adjusted_score']}")

    # Step 3: Assign due dates
    print("\nAssigning due dates...")
    response = requests.post(f"{BASE_URL}/api/emails/assign")
    assign_result = response.json()
    print(f"  Assigned: {assign_result['total_assigned']}")
    print(f"  Today: {assign_result['slots']['today']['count']}")
    print(f"  Tomorrow: {assign_result['slots']['tomorrow']['count']}")

    # Step 4: Get today's action list
    print("\nFetching today's action list...")
    response = requests.get(f"{BASE_URL}/api/emails/today")
    today_result = response.json()

    print(f"\n{'='*70}")
    print(f"TODAY'S ACTION LIST ({today_result['date']})")
    print(f"{'='*70}\n")

    for i, email in enumerate(today_result['emails'][:10], 1):
        priority = "🔴" if email['floor_override'] else "  "
        print(f"{i:2d}. {priority} [{email['urgency_score']:5.1f}] {email['subject'][:50]}")

    if today_result['total'] > 10:
        print(f"\n... and {today_result['total'] - 10} more emails")

    return today_result

if __name__ == "__main__":
    process_daily_emails()
```

---

## Database Schema

### Updated Email Model

```python
class Email(Base):
    __tablename__ = "emails"

    # ... existing fields ...

    # Assignment fields
    due_date = Column(DateTime, nullable=True)  # Assigned due date

    # Relationships
    urgency_score_record = relationship("UrgencyScore", back_populates="email")
```

### Query Example

```sql
-- Get today's emails
SELECT
    e.id,
    e.subject,
    e.from_name,
    e.category_id,
    e.urgency_score,
    e.due_date,
    u.floor_override
FROM emails e
JOIN urgency_scores u ON e.id = u.email_id
WHERE e.status = 'classified'
  AND e.category_id IN (1, 2, 3, 4, 5)
  AND DATE(e.due_date) = CURRENT_DATE
ORDER BY u.urgency_score DESC;
```

---

## Assignment Algorithm Integration

The assignment endpoints use the algorithm from `app/services/assignment.py`:

### Settings Used

```python
{
    "task_limit": 20,              # Max tasks per day/period
    "urgency_floor": 90,            # Score threshold for floor override
    "time_pressure_threshold": 15   # Min score to get a date
}
```

### Floor Pool vs Standard Pool

**Floor Pool** (always gets Today):
- `floor_override = True`: Score >= urgency_floor (90)
- `force_today = True`: Email is 11+ days old (stale escalation)

**Standard Pool** (distributed across slots):
- All other emails
- Sorted by urgency_score descending
- Assigned to Today/Tomorrow/This Week/Next Week based on position

### Slot Distribution

```
Today:     floor_pool + first N standard items (N = task_limit - len(floor_pool))
Tomorrow:  next [task_limit] standard items
This Week: next [task_limit * 2] standard items
Next Week: remaining items with score >= threshold
No Date:   items with score < threshold
```

---

## Testing

### Test Script

Run the comprehensive test:

```bash
./test_assignment_endpoints.sh
```

### Manual Testing

```bash
# Test 1: Assign dates
curl -X POST http://localhost:8000/api/emails/assign | python3 -m json.tool

# Test 2: Get today's list
curl "http://localhost:8000/api/emails/today" | python3 -m json.tool

# Test 3: Verify in database
python3 -c "
from app.database import SessionLocal
from app.models import Email
from sqlalchemy import func

db = SessionLocal()
results = db.query(
    func.date(Email.due_date).label('due_date'),
    func.count(Email.id).label('count')
).filter(
    Email.due_date.isnot(None)
).group_by(
    func.date(Email.due_date)
).all()

for due_date, count in results:
    print(f'{due_date}: {count} emails')

db.close()
"
```

---

## Future Enhancements

### 1. Configurable Settings

Allow users to customize assignment settings via request body:

```python
@router.post("/assign")
def assign_due_dates_to_emails(
    settings: Optional[Dict] = None,
    db: Session = Depends(get_db)
):
    if settings is None:
        settings = {
            "task_limit": 20,
            "urgency_floor": 90,
            "time_pressure_threshold": 15
        }
    # ... rest of implementation
```

### 2. Additional Endpoints

```python
# Get emails by slot
@router.get("/tomorrow")
def get_tomorrows_emails(db: Session = Depends(get_db)):
    """Get all emails due tomorrow."""

@router.get("/this-week")
def get_this_weeks_emails(db: Session = Depends(get_db)):
    """Get all emails due this week (Friday)."""

@router.get("/by-date/{date}")
def get_emails_by_date(date: str, db: Session = Depends(get_db)):
    """Get all emails due on a specific date."""

# Reassign a specific email
@router.post("/{email_id}/reassign")
def reassign_email(email_id: int, new_date: str, db: Session = Depends(get_db)):
    """Manually reassign an email to a different due date."""
```

### 3. Assignment History

Track assignment changes over time:

```python
class AssignmentLog(Base):
    __tablename__ = "assignment_logs"

    id = Column(Integer, primary_key=True)
    email_id = Column(Integer, ForeignKey("emails.id"))
    old_due_date = Column(Date, nullable=True)
    new_due_date = Column(Date, nullable=True)
    reason = Column(String)  # "initial_assignment", "manual_reassign", etc.
    timestamp = Column(DateTime, default=datetime.utcnow)
```

### 4. Scheduled Reassignment

Automatically reassign emails daily:

```python
# Cron job or scheduler
def daily_assignment_task():
    """Run every morning to reassign due dates."""
    db = SessionLocal()
    try:
        # Clear old assignments
        db.query(Email).update({Email.due_date: None})

        # Run new assignment
        assign_due_dates_to_emails(db)

        # Send notification
        send_daily_summary_email()
    finally:
        db.close()
```

---

## References

- Assignment Algorithm: `app/services/assignment.py`
- Full Documentation: `ASSIGNMENT_ALGORITHM.md`
- Quick Start: `ASSIGNMENT_QUICK_START.md`
- Scoring Engine: `SCORING_ENGINE_GUIDE.md`
- Classification Pipeline: `COMPLETE_CLASSIFICATION_PIPELINE.md`
