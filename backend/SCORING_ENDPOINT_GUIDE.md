# Urgency Scoring Endpoint Documentation

## Overview

The `POST /api/emails/score` endpoint calculates urgency scores for all classified Work emails (categories 1-5) and stores detailed scoring breakdowns in the database.

---

## Endpoint Details

### POST /api/emails/score

**Description:** Score all classified Work emails using the 8-signal urgency scoring engine.

**What it does:**
1. Fetches all emails with `status='classified'` and `category_id` in [1, 2, 3, 4, 5]
2. Runs `score_email()` on each one
3. Updates the `email.urgency_score` field (0-100)
4. Creates/updates record in `urgency_scores` table with full signal breakdown
5. Returns statistics with score distribution

**URL:** `POST http://localhost:8000/api/emails/score`

**Authentication:** None (uses first authenticated user's domain)

**Request Body:** None

---

## Database Schema: urgency_scores

New table created to track detailed scoring information:

```sql
CREATE TABLE urgency_scores (
    id INTEGER PRIMARY KEY,
    email_id INTEGER UNIQUE NOT NULL,  -- FK to emails.id
    urgency_score FLOAT NOT NULL,       -- Final score (0-100)
    signals_json TEXT NOT NULL,         -- JSON with signals, weights, breakdown
    scored_at DATETIME NOT NULL,        -- When score was calculated
    floor_override BOOLEAN DEFAULT FALSE, -- Manual override flag
    stale_days INTEGER DEFAULT 0,       -- Days since last scoring
    FOREIGN KEY(email_id) REFERENCES emails(id)
);
```

### Fields Explained

**email_id:** Links to emails table (one-to-one relationship)

**urgency_score:** The final calculated score (0-100)

**signals_json:** Full scoring breakdown stored as JSON:
```json
{
  "signals": {
    "explicit_deadline": 100,
    "sender_seniority": 90,
    "importance_flag": 80,
    "urgency_language": 90,
    "thread_velocity": 40,
    "client_external": 50,
    "age_of_email": 30,
    "followup_overdue": 0
  },
  "weights": {
    "explicit_deadline": 0.25,
    "sender_seniority": 0.15,
    ...
  },
  "breakdown": {
    "explicit_deadline_weighted": 25.0,
    "sender_seniority_weighted": 13.5,
    ...
  }
}
```

**scored_at:** Timestamp when score was calculated

**floor_override:** Boolean flag for manual overrides (future feature)

**stale_days:** Days since last scoring (auto-calculated on re-score)

---

## Response Format

### Success Response

```json
{
  "total_scored": 47,

  "score_distribution": {
    "critical_90_plus": 3,
    "high_70_89": 12,
    "medium_40_69": 25,
    "low_under_40": 7
  },

  "average_score": 58.34,

  "highest": {
    "email_id": 123,
    "subject": "URGENT: Report due by EOD",
    "score": 95
  },

  "lowest": {
    "email_id": 456,
    "subject": "FYI: Team update",
    "score": 12
  },

  "message": "Successfully scored 47 Work emails"
}
```

### Empty Response (No Work Emails)

```json
{
  "total_scored": 0,
  "message": "No classified Work emails found to score",
  "score_distribution": {
    "critical_90_plus": 0,
    "high_70_89": 0,
    "medium_40_69": 0,
    "low_under_40": 0
  },
  "average_score": 0.0,
  "highest": null,
  "lowest": null
}
```

---

## Score Distribution Ranges

| Range | Category | Count Field | Description |
|-------|----------|-------------|-------------|
| 90-100 | Critical | `critical_90_plus` | 🔴 Drop everything |
| 70-89 | High | `high_70_89` | 🟠 Handle today |
| 40-69 | Medium | `medium_40_69` | 🟡 Handle this week |
| 0-39 | Low | `low_under_40` | 🟢 Standard priority |

---

## Usage Examples

### cURL

```bash
# Score all Work emails
curl -X POST http://localhost:8000/api/emails/score

# Pretty print with jq
curl -X POST http://localhost:8000/api/emails/score | jq
```

### Python

```python
import requests

response = requests.post("http://localhost:8000/api/emails/score")
data = response.json()

print(f"Scored {data['total_scored']} emails")
print(f"Average score: {data['average_score']}")
print(f"Critical emails: {data['score_distribution']['critical_90_plus']}")

if data['highest']:
    print(f"Highest: {data['highest']['subject']} ({data['highest']['score']})")
```

### JavaScript/Fetch

```javascript
fetch('http://localhost:8000/api/emails/score', {
  method: 'POST'
})
  .then(res => res.json())
  .then(data => {
    console.log(`Scored ${data.total_scored} emails`);
    console.log(`Average: ${data.average_score}`);
    console.log('Distribution:', data.score_distribution);
  });
```

---

## Integration Workflow

### 1. Initial Classification

```bash
# Run the full pipeline
curl -X POST "http://localhost:8000/api/emails/pipeline/run"

# This classifies emails into categories 1-11
```

### 2. Score Work Items

```bash
# Score the Work emails (categories 1-5)
curl -X POST "http://localhost:8000/api/emails/score"

# Returns score distribution and statistics
```

### 3. Query Scored Emails

```sql
-- Get all critical emails
SELECT e.id, e.subject, e.from_address, us.urgency_score
FROM emails e
JOIN urgency_scores us ON e.id = us.email_id
WHERE us.urgency_score >= 90
ORDER BY us.urgency_score DESC;

-- Get scoring breakdown for an email
SELECT us.signals_json
FROM urgency_scores us
WHERE us.email_id = 123;
```

### 4. Display in UI

```javascript
// Fetch emails sorted by urgency
fetch('/api/emails?sort=urgency_score&order=desc')
  .then(res => res.json())
  .then(emails => {
    emails.forEach(email => {
      const badge = getUrgencyBadge(email.urgency_score);
      displayEmail(email, badge);
    });
  });

function getUrgencyBadge(score) {
  if (score >= 90) return '🔴 Critical';
  if (score >= 70) return '🟠 High';
  if (score >= 40) return '🟡 Medium';
  return '🟢 Normal';
}
```

---

## Behavior & Logic

### What Gets Scored

✅ **Scored:**
- Emails with `status = 'classified'`
- Emails with `category_id` in [1, 2, 3, 4, 5] (Work items)

❌ **Not Scored:**
- Unclassified emails (`status = 'unprocessed'`)
- Other category emails (6-11): Marketing, Notifications, Calendar, FYI, Travel
- Deleted or archived emails (unless still in inbox)

### Why Only Work Items?

Work items require prioritization to determine what to handle first. "Other" category emails (marketing, notifications, etc.) are typically low priority by nature and don't need urgency scoring.

### Re-Scoring

If you call the endpoint multiple times:
- Existing `urgency_scores` records are **updated** (not duplicated)
- The `stale_days` field is calculated based on time since last score
- New `scored_at` timestamp is set
- Email's `urgency_score` field is updated with latest value

### Domain Detection

The endpoint automatically detects the user's domain for the `client_external` signal:
```python
# Uses authenticated user's email domain
user_domain = "company.com"  # from user@company.com

# Falls back to "live.com" if no user found
```

---

## Performance

### Typical Performance

- **10 emails:** ~150-300ms
- **50 emails:** ~750ms-1.5s
- **100 emails:** ~1.5-3s
- **500 emails:** ~7-15s

Includes:
- Database queries
- Signal extraction (8 signals per email)
- Thread velocity queries
- Database updates

### Optimization Tips

1. **Batch processing:** The endpoint already scores all emails in one request
2. **Background job:** For large volumes, consider running as async background task
3. **Incremental scoring:** Only score new/changed emails
4. **Index:** Ensure `emails.category_id` and `emails.status` are indexed

---

## Error Handling

### Individual Email Errors

If a single email fails to score (e.g., malformed data), the endpoint:
- Logs the error
- Continues scoring other emails
- Returns statistics for successfully scored emails

### Complete Failure

If the endpoint encounters a fatal error:
```json
{
  "detail": "Error message here"
}
```

Status code: 500

---

## Querying Scored Emails

### Get Emails by Urgency

```sql
-- Critical emails only
SELECT * FROM emails
WHERE urgency_score >= 90
ORDER BY urgency_score DESC;

-- High priority work items
SELECT * FROM emails
WHERE urgency_score >= 70 AND urgency_score < 90
ORDER BY urgency_score DESC;
```

### Get Scoring Details

```sql
-- Full scoring breakdown
SELECT
    e.id,
    e.subject,
    e.from_address,
    us.urgency_score,
    us.signals_json,
    us.scored_at
FROM emails e
JOIN urgency_scores us ON e.id = us.email_id
WHERE e.id = 123;
```

### Parse Signals JSON

```python
import json

# Get urgency record
record = db.query(UrgencyScore).filter(UrgencyScore.email_id == 123).first()

# Parse JSON
signals_data = json.loads(record.signals_json)

print(signals_data["signals"]["explicit_deadline"])  # 100
print(signals_data["breakdown"]["explicit_deadline_weighted"])  # 25.0
```

---

## Extending the Endpoint

### Add Filtering

Score only specific categories:

```python
@router.post("/score")
async def score_work_emails(
    category_ids: List[int] = Query(default=[1, 2, 3, 4, 5]),
    db: Session = Depends(get_db)
):
    work_emails = db.query(Email).filter(
        Email.status == "classified",
        Email.category_id.in_(category_ids)
    ).all()
    # ... rest of logic
```

### Add Date Range Filtering

Score emails from specific time period:

```python
from datetime import datetime, timedelta

@router.post("/score")
async def score_work_emails(
    days_back: int = Query(default=7),
    db: Session = Depends(get_db)
):
    cutoff = datetime.utcnow() - timedelta(days=days_back)

    work_emails = db.query(Email).filter(
        Email.status == "classified",
        Email.category_id.in_([1, 2, 3, 4, 5]),
        Email.received_at >= cutoff
    ).all()
    # ... rest of logic
```

### Add Webhook Notification

Notify when critical emails are found:

```python
if score >= 90:
    # Send notification
    notify_critical_email(email.id, email.subject, score)
```

---

## Maintenance

### Re-Score Stale Emails

Emails should be re-scored periodically as signals change over time:

```sql
-- Find emails with stale scores (>7 days old)
SELECT e.id, e.subject, us.scored_at, us.stale_days
FROM emails e
JOIN urgency_scores us ON e.id = us.email_id
WHERE us.stale_days > 7;
```

Schedule re-scoring:
```bash
# Daily cron job
0 2 * * * curl -X POST http://localhost:8000/api/emails/score
```

### Clean Up Old Scores

Remove scores for deleted emails:

```sql
DELETE FROM urgency_scores
WHERE email_id NOT IN (SELECT id FROM emails);
```

---

## Testing

### Test Endpoint

```bash
# 1. Classify some emails first
curl -X POST "http://localhost:8000/api/emails/fetch?count=20"
curl -X POST "http://localhost:8000/api/emails/classify-deterministic"
curl -X POST "http://localhost:8000/api/emails/classify-ai"

# 2. Score the Work emails
curl -X POST "http://localhost:8000/api/emails/score" | jq

# 3. Verify in database
sqlite3 triage.db "SELECT COUNT(*) FROM urgency_scores;"
sqlite3 triage.db "SELECT email_id, urgency_score FROM urgency_scores ORDER BY urgency_score DESC LIMIT 10;"
```

### Verify Signals JSON

```bash
# Get signals for a specific email
sqlite3 triage.db "SELECT signals_json FROM urgency_scores WHERE email_id = 1;" | python3 -m json.tool
```

---

## Summary

The `POST /api/emails/score` endpoint:

✅ Scores all classified Work emails (categories 1-5)
✅ Updates `emails.urgency_score` field
✅ Stores detailed breakdown in `urgency_scores` table
✅ Returns comprehensive statistics
✅ Handles re-scoring gracefully
✅ Production-ready with error handling
✅ Optimized for batch processing

Use it to prioritize your inbox and surface the most urgent work items first!
