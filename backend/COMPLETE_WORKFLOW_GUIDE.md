# Complete Email Triage Workflow

## System Overview

A complete email processing system that fetches, classifies, scores, and assigns due dates to emails automatically.

```
┌─────────────────────────────────────────────────────────────┐
│                    EMAIL TRIAGE SYSTEM                       │
└─────────────────────────────────────────────────────────────┘

1. FETCH          2. CLASSIFY        3. SCORE         4. ASSIGN
   │                 │                  │                │
   ▼                 ▼                  ▼                ▼
┌──────┐        ┌──────────┐      ┌─────────┐     ┌──────────┐
│ MS   │        │Determin- │      │ Urgency │     │   Due    │
│Graph │  ───>  │  istic   │ ───> │ Scoring │ ──> │   Date   │
│ API  │        │   +AI    │      │ Engine  │     │Assignment│
└──────┘        └──────────┘      └─────────┘     └──────────┘
   │                 │                  │                │
   │                 │                  │                │
   ▼                 ▼                  ▼                ▼
50 emails      37 classified      37 scored      37 assigned
               5 Work             avg: 78.6      22 Today
               32 Other                          15 Tomorrow
```

## Complete API Workflow

### Step-by-Step Process

```bash
BASE_URL="http://localhost:8000"

# Step 1: Run Classification Pipeline
# - Fetches emails from Microsoft Graph
# - Runs deterministic classifier
# - Checks for overrides
# - Runs AI classifier on remaining emails
curl -X POST "${BASE_URL}/api/emails/pipeline/run?fetch_count=50"

# Step 2: Score all Work emails
# - Calculates urgency scores for categories 1-5
# - Applies floor and stale escalation
# - Stores detailed scoring breakdown
curl -X POST "${BASE_URL}/api/emails/score"

# Step 3: Assign due dates
# - Distributes emails across Today/Tomorrow/This Week/Next Week
# - Prioritizes floor pool items (critical/stale)
# - Updates database with due dates
curl -X POST "${BASE_URL}/api/emails/assign"

# Step 4: Get today's action list
# - Retrieves all emails due today
# - Sorted by urgency score (highest first)
# - Ready for user to process
curl "${BASE_URL}/api/emails/today"
```

## Current System State

### Your Database (as of last run)

**Total Emails**: 50
- Classified: 37 Work emails
- Scored: 37 emails with urgency scores
- Assigned: 37 emails with due dates

**Today's Statistics**:
```
Today (2026-02-01):  22 emails  (100% floor pool - all 11+ days old)
Tomorrow:            15 emails  (all standard pool)
This Week:            0 emails
Next Week:            0 emails
No Date:              0 emails
```

**Why Floor Overflow?**
- 22 emails are 11+ days old (stale escalation)
- All get `force_today = True`
- Floor pool (22) exceeds task_limit (20)
- No room for standard pool in Today
- All standard items pushed to Tomorrow

## Detailed Component Breakdown

### 1. Classification Pipeline

**Endpoint**: `POST /api/emails/pipeline/run`

**Components**:
1. **Fetch**: Get emails from Microsoft Graph API
2. **Deterministic Classifier**: Header and sender-based rules
3. **Override Checker**: VIP and urgency detection
4. **AI Classifier**: Claude 3.5 Sonnet for remaining emails

**Categories**:
- **Work Categories (1-5)**: Blocking, Action Required, Waiting On, Time-Sensitive, FYI
- **Other Categories (6-11)**: Marketing, Notification, Calendar, FYI, Travel

**Output**: Emails with `category_id` and `status = 'classified'`

---

### 2. Scoring Engine

**Endpoint**: `POST /api/emails/score`

**Signals** (8 total):
1. Category urgency (1-5 mapped to scores)
2. Email importance flag (High/Normal/Low)
3. Keyword urgency (deadline, urgent, asap, etc.)
4. Sender importance (from VIP table)
5. Personal direction (to: user in To/CC)
6. Thread length (conversation depth)
7. Thread velocity (messages per day)
8. Time decay (days since received)

**Escalation Rules**:
- **Urgency Floor**: If raw_score >= 90, final_score = 100
- **Stale Escalation**: Bonus points for old emails
  - Days 0-2: 2-6 points
  - Days 3-10: 5-50 points
  - Days 11+: Force to score 100 (force_today = True)

**Output**:
```json
{
    "total_scored": 37,
    "score_distribution": {
        "critical_90_plus": 22,
        "high_70_89": 2,
        "medium_40_69": 8,
        "low_under_40": 5
    },
    "floor_items": {"count": 22, "emails": [...]},
    "stale_items": {"count": 37, "force_today_count": 22, "emails": [...]},
    "average_raw_score": 26.96,
    "average_adjusted_score": 78.59
}
```

---

### 3. Assignment Algorithm

**Endpoint**: `POST /api/emails/assign`

**Algorithm**:
1. Split into Floor Pool and Standard Pool
2. Sort Standard Pool by urgency_score descending
3. Calculate available_today_slots = task_limit - len(floor_pool)
4. Assign slots:
   - **Today**: All floor items + top N standard items
   - **Tomorrow**: Next [task_limit] standard items
   - **This Week**: Next [task_limit * 2] standard items
   - **Next Week**: Remaining items above threshold
   - **No Date**: Items below threshold

**Settings**:
```python
{
    "task_limit": 20,              # Max tasks per day
    "urgency_floor": 90,            # Floor threshold
    "time_pressure_threshold": 15   # Min score for date
}
```

**Output**:
```json
{
    "total_assigned": 37,
    "slots": {
        "today": {"count": 22, "floor_count": 22, "standard_count": 0},
        "tomorrow": {"count": 15},
        "this_week": {"count": 0},
        "next_week": {"count": 0},
        "no_date": {"count": 0}
    },
    "task_limit": 20,
    "urgency_floor": 90,
    "floor_overflow": true
}
```

---

### 4. Today's Action List

**Endpoint**: `GET /api/emails/today`

**Query**:
- All Work emails with due_date = today
- Joined with urgency_scores for details
- Sorted by urgency_score descending

**Output**:
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
        ...
    ]
}
```

## Complete Python Automation

```python
#!/usr/bin/env python3
"""
Complete email triage automation script.
Run this daily to process all emails and generate today's action list.
"""

import requests
from datetime import date

BASE_URL = "http://localhost:8000"

def main():
    print("="*70)
    print("EMAIL TRIAGE - DAILY AUTOMATION")
    print("="*70)

    # Step 1: Classification Pipeline
    print("\n[1/4] Running classification pipeline...")
    response = requests.post(f"{BASE_URL}/api/emails/pipeline/run?fetch_count=50")
    pipeline = response.json()
    print(f"  ✓ Fetched: {pipeline.get('fetched', 0)}")
    print(f"  ✓ Classified: {pipeline.get('classified', 0)}")
    print(f"  ✓ AI Classified: {pipeline.get('ai_classified', 0)}")

    # Step 2: Scoring
    print("\n[2/4] Scoring Work emails...")
    response = requests.post(f"{BASE_URL}/api/emails/score")
    scoring = response.json()
    print(f"  ✓ Scored: {scoring['total_scored']}")
    print(f"  ✓ Floor items: {scoring['floor_items']['count']}")
    print(f"  ✓ Stale items: {scoring['stale_items']['count']}")
    print(f"  ✓ Average score: {scoring['average_adjusted_score']}")

    # Step 3: Assignment
    print("\n[3/4] Assigning due dates...")
    response = requests.post(f"{BASE_URL}/api/emails/assign")
    assignment = response.json()
    print(f"  ✓ Assigned: {assignment['total_assigned']}")
    print(f"  ✓ Today: {assignment['slots']['today']['count']}")
    print(f"  ✓ Tomorrow: {assignment['slots']['tomorrow']['count']}")
    print(f"  ✓ This week: {assignment['slots']['this_week']['count']}")
    if assignment.get('floor_overflow'):
        print(f"  ⚠ Floor overflow detected!")

    # Step 4: Today's Action List
    print("\n[4/4] Fetching today's action list...")
    response = requests.get(f"{BASE_URL}/api/emails/today")
    today = response.json()

    print("\n" + "="*70)
    print(f"TODAY'S ACTION LIST - {today['date']}")
    print("="*70)
    print(f"\nTotal: {today['total']} emails\n")

    for i, email in enumerate(today['emails'][:15], 1):
        priority = "🔴" if email['floor_override'] else "  "
        cat_label = {1: "BLK", 2: "ACT", 3: "WAIT", 4: "TIME", 5: "FYI"}
        cat = cat_label.get(email['category_id'], "???")

        print(f"{i:2d}. {priority} [{email['urgency_score']:5.1f}] [{cat}] {email['subject'][:50]}")
        print(f"     From: {email['from_name'][:60]}")

    if today['total'] > 15:
        print(f"\n... and {today['total'] - 15} more emails")

    print("\n" + "="*70)
    print("AUTOMATION COMPLETE")
    print("="*70)

if __name__ == "__main__":
    main()
```

## API Quick Reference

### All Endpoints

```bash
# Fetch emails
POST /api/emails/fetch?count=50

# Classification
POST /api/emails/classify-deterministic
POST /api/emails/classify-ai
POST /api/emails/check-overrides
POST /api/emails/pipeline/run?fetch_count=50

# Scoring
POST /api/emails/score
GET  /api/emails/scored

# Assignment
POST /api/emails/assign
GET  /api/emails/today

# Utilities
GET  /api/emails/
GET  /api/emails/summary
POST /api/emails/{email_id}/reclassify
```

## Database Tables

### Core Tables

```sql
-- Emails table
emails (
    id, message_id, from_address, from_name, subject,
    body_preview, body, received_at, importance,
    conversation_id, has_attachments, is_read,
    to_recipients, cc_recipients, category_id,
    confidence, urgency_score, due_date, folder, status
)

-- Categories table
categories (
    id, label, description, is_work
)

-- Urgency Scores table
urgency_scores (
    id, email_id, urgency_score, raw_score,
    stale_bonus, stale_days, floor_override,
    force_today, signals_json, scored_at
)

-- VIP Senders table
vip_senders (
    id, email, name, importance_boost, is_active
)

-- Classification Logs
classification_logs (
    id, email_id, category_id, rule,
    classifier_type, confidence, created_at
)

-- Override Logs
override_logs (
    id, email_id, original_category,
    trigger_type, reason, timestamp
)
```

## Testing

### Run All Tests

```bash
# Classification tests
python test_classifier.py
python test_ai_classifier.py
python test_override.py

# Scoring tests
python test_scoring_engine.py

# Assignment tests
python test_assignment.py
python test_assignment_real.py

# Endpoint tests
./test_assignment_endpoints.sh
./test_pipeline_endpoint.sh
```

## Documentation Index

1. **COMPLETE_CLASSIFICATION_PIPELINE.md** - Classification system
2. **SCORING_ENGINE_GUIDE.md** - Urgency scoring details
3. **URGENCY_FLOOR_AND_STALE_ESCALATION.md** - Floor/stale logic
4. **ASSIGNMENT_ALGORITHM.md** - Assignment algorithm details
5. **ASSIGNMENT_QUICK_START.md** - Assignment quick start
6. **ASSIGNMENT_ENDPOINTS.md** - API endpoint documentation
7. **COMPLETE_WORKFLOW_GUIDE.md** - This document

## Next Steps

### Recommended Improvements

1. **Frontend Dashboard**
   - Display today's action list
   - Show assignment distribution
   - Allow manual reassignment
   - Track completion status

2. **Scheduled Automation**
   - Cron job for daily processing
   - Email notifications with summary
   - Slack/Teams integration

3. **User Preferences**
   - Per-user task limits
   - Custom urgency thresholds
   - Personalized VIP lists

4. **Analytics**
   - Completion rate tracking
   - Response time metrics
   - Category distribution over time
   - Scoring accuracy feedback

5. **Advanced Features**
   - Smart scheduling (avoid weekends)
   - Load balancing across days
   - Auto-escalation for missed items
   - Snooze/defer functionality

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (Future)                       │
│  - Today's Action List                                       │
│  - Weekly Calendar View                                      │
│  - Assignment Controls                                       │
└─────────────────────────────────────────────────────────────┘
                          ▲
                          │ REST API
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Backend                          │
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Classification│  │   Scoring    │  │  Assignment  │      │
│  │   Pipeline    │─>│    Engine    │─>│  Algorithm   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│         │                  │                  │              │
│         ▼                  ▼                  ▼              │
│  ┌──────────────────────────────────────────────────┐      │
│  │              SQLite Database                      │      │
│  │  emails | urgency_scores | categories            │      │
│  └──────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────┘
                          ▲
                          │ Graph API
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                 Microsoft Graph API                          │
│                   (Email Source)                             │
└─────────────────────────────────────────────────────────────┘
```

---

**System Status**: ✅ Fully Operational

All components tested and working with real data from your inbox!
