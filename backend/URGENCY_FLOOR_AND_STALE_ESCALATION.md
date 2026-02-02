# Urgency Floor and Stale Escalation

## Overview

Two powerful features have been added to the urgency scoring system to ensure old emails don't get forgotten and critical emails get immediate attention:

1. **Stale Escalation** - Progressively increases urgency for old emails
2. **Urgency Floor** - Flags emails above a threshold for guaranteed Today assignment

---

## Feature 1: Stale Escalation

### Purpose

Prevents emails from languishing in the inbox by progressively increasing their urgency score based on age.

### How It Works

The system calculates `stale_days` = (today - email.received_at).days and applies a progressive bonus:

```
Days 0-3:   +2 points per day
Days 4-5:   +5 points per day
Days 6-10:  +10 points per day
Day 11+:    Force to Today (score = 100, force_today = true)
```

### Example Calculation

**Email received 7 days ago, raw score = 45**

1. Days 0-3: 4 days × 2 points = +8
2. Days 4-5: 2 days × 5 points = +10
3. Days 6-7: 2 days × 10 points = +20
4. **Total bonus:** +38 points
5. **Adjusted score:** 45 + 38 = **83**

### Configuration

```python
# In app/services/scoring.py

STALE_ESCALATION_ENABLED = True  # Toggle on/off

STALE_ESCALATION_CURVE = {
    "tier_1": {"days": (0, 3), "bonus_per_day": 2},
    "tier_2": {"days": (4, 5), "bonus_per_day": 5},
    "tier_3": {"days": (6, 10), "bonus_per_day": 10},
    "tier_4": {"days": (11, 999), "force_today": True}
}
```

### Force Today

Emails 11+ days old are **automatically forced to Today**:
- `force_today = true`
- Score set to 100
- Unconditionally assigned to Today bucket (implemented Wednesday)

---

## Feature 2: Urgency Floor

### Purpose

Ensures that emails with very high urgency scores (default: 90+) are guaranteed Today assignment, regardless of task limits.

### How It Works

After stale escalation is applied, if the adjusted score meets or exceeds the floor threshold, the email is flagged:

```python
if adjusted_score >= URGENCY_FLOOR_THRESHOLD:
    floor_override = True
```

### Configuration

```python
# In app/services/scoring.py

URGENCY_FLOOR_THRESHOLD = 90  # Configurable 80-100
TASK_LIMIT = 20  # Maximum Today items (used in assignment logic)
```

### Floor Override Flag

When `floor_override = true`:
- Email is guaranteed Today assignment
- Bypasses task limit constraints
- Marked visually in UI (implement on Wednesday)

---

## Scoring Flow

### Complete Process

```
1. Calculate Raw Score
   ├─ Extract 8 signals
   ├─ Apply weights
   └─ Sum = raw_score (0-100)

2. Apply Stale Escalation
   ├─ Calculate stale_days
   ├─ Apply progressive curve
   ├─ Add stale_bonus to raw_score
   └─ Result = adjusted_score (0-100)
   └─ Set force_today if days >= 11

3. Check Urgency Floor
   ├─ If adjusted_score >= 90
   └─ Set floor_override = true

4. Return Final Result
   ├─ urgency_score (final score)
   ├─ raw_score (before escalation)
   ├─ stale_bonus (points added)
   ├─ stale_days (age in days)
   ├─ adjusted_score (after escalation)
   ├─ floor_override (meets floor?)
   └─ force_today (11+ days old?)
```

### Example

```python
Email: "Project update needed"
Received: 8 days ago
From: colleague@company.com

# Step 1: Raw Score
deadline: 0 (no deadline)
seniority: 20 (internal peer)
importance: 0 (normal)
language: 60 (action required)
velocity: 0 (no db)
external: 0 (internal)
age: 80 (8 days old)
overdue: 0 (not category 4)

Weighted sum: 0×0.25 + 20×0.15 + 0×0.10 + 60×0.15 + 0×0.10 + 0×0.05 + 80×0.10 + 0×0.10
            = 0 + 3 + 0 + 9 + 0 + 0 + 8 + 0
            = 20

raw_score = 20

# Step 2: Stale Escalation
stale_days = 8
tier_1: 4 days × 2 = +8
tier_2: 2 days × 5 = +10
tier_3: 2 days × 10 = +20
stale_bonus = 38

adjusted_score = 20 + 38 = 58

# Step 3: Urgency Floor
58 < 90, so floor_override = false

# Final Result
{
  "urgency_score": 58,
  "raw_score": 20,
  "stale_bonus": 38,
  "adjusted_score": 58,
  "stale_days": 8,
  "force_today": false,
  "floor_override": false
}
```

---

## Database Schema Updates

### urgency_scores Table

New fields added:

```sql
ALTER TABLE urgency_scores ADD COLUMN raw_score FLOAT;
ALTER TABLE urgency_scores ADD COLUMN stale_bonus INTEGER DEFAULT 0;
ALTER TABLE urgency_scores ADD COLUMN force_today BOOLEAN DEFAULT FALSE;

-- Existing fields updated:
-- floor_override: Now set by system (was for manual overrides)
-- stale_days: Now calculated from email age (was for tracking staleness)
```

### Complete Schema

```sql
CREATE TABLE urgency_scores (
    id INTEGER PRIMARY KEY,
    email_id INTEGER UNIQUE NOT NULL,
    urgency_score FLOAT NOT NULL,      -- Final score after escalation
    raw_score FLOAT,                    -- Score before escalation
    stale_bonus INTEGER DEFAULT 0,      -- Bonus points added
    signals_json TEXT NOT NULL,         -- Full breakdown
    scored_at DATETIME NOT NULL,
    floor_override BOOLEAN DEFAULT FALSE, -- Score >= 90
    stale_days INTEGER DEFAULT 0,       -- Days since received
    force_today BOOLEAN DEFAULT FALSE,  -- Days >= 11
    FOREIGN KEY(email_id) REFERENCES emails(id)
);
```

---

## API Response Changes

### score_email() Return Value

```python
{
    "urgency_score": 58,        # Final score (after escalation)
    "raw_score": 20.0,          # Before escalation
    "stale_bonus": 38,          # Points added
    "adjusted_score": 58.0,     # After escalation
    "stale_days": 8,            # Days old
    "force_today": false,       # 11+ days?
    "floor_override": false,    # Score >= 90?
    "signals": { ... },         # 8 signal scores
    "weights": { ... },         # Signal weights
    "breakdown": { ... }        # Weighted contributions
}
```

### POST /api/emails/score

The endpoint now stores all new fields in the urgency_scores table.

---

## Configuration Guide

### Adjusting Stale Escalation Curve

Edit `app/services/scoring.py`:

```python
# More aggressive escalation (catch old emails faster)
STALE_ESCALATION_CURVE = {
    "tier_1": {"days": (0, 2), "bonus_per_day": 5},   # Days 0-2: +5/day
    "tier_2": {"days": (3, 4), "bonus_per_day": 10},  # Days 3-4: +10/day
    "tier_3": {"days": (5, 7), "bonus_per_day": 15},  # Days 5-7: +15/day
    "tier_4": {"days": (8, 999), "force_today": True} # Day 8+: force
}

# Less aggressive (allow more time before escalation)
STALE_ESCALATION_CURVE = {
    "tier_1": {"days": (0, 5), "bonus_per_day": 1},
    "tier_2": {"days": (6, 10), "bonus_per_day": 3},
    "tier_3": {"days": (11, 20), "bonus_per_day": 5},
    "tier_4": {"days": (21, 999), "force_today": True}
}
```

### Adjusting Urgency Floor

```python
# Higher floor (only very urgent emails)
URGENCY_FLOOR_THRESHOLD = 95

# Lower floor (catch more emails)
URGENCY_FLOOR_THRESHOLD = 85

# Disable floor
URGENCY_FLOOR_THRESHOLD = 101  # Never triggered
```

### Adjusting Task Limit

```python
# More Today items
TASK_LIMIT = 30

# Fewer Today items (stricter prioritization)
TASK_LIMIT = 10
```

### Disable Stale Escalation

```python
STALE_ESCALATION_ENABLED = False  # No bonus for old emails
```

---

## Use Cases

### Use Case 1: Prevent Email from Getting Lost

**Scenario:** User receives project update request but it gets buried under new emails.

**Without Stale Escalation:**
- Day 1: Score = 35 (medium priority)
- Day 5: Score = 35 (still medium, lost in queue)
- Day 10: Score = 35 (never surfaces)

**With Stale Escalation:**
- Day 1: Score = 35
- Day 5: Score = 35 + 18 = 53 (moves up)
- Day 10: Score = 35 + 68 = 100 (surfaces to top)

### Use Case 2: Critical Email Gets Immediate Attention

**Scenario:** Boss sends urgent request: "Need report by EOD"

**Scoring:**
- Deadline: 100 (today)
- Seniority: 90 (VIP)
- Language: 90 (urgent)
- Weighted: 100×0.25 + 90×0.15 + 90×0.15 = 57

**With Urgency Floor:**
- Raw score: 57
- Stale escalation: +0 (just received)
- Adjusted: 57
- Floor check: 57 < 90, **not flagged**

**Better example:**
- Deadline: 100
- Seniority: 90
- Importance: 80
- Language: 90
- Weighted: ~85
- Floor check: 85 < 90, **not flagged**

**Trigger floor:**
- Need score >= 90 from weighted signals
- Or wait for stale escalation to push it over

### Use Case 3: Old Critical Email

**Scenario:** Important client request from 12 days ago

**Scoring:**
- Raw score: 65 (high but not critical)
- Days: 12
- Force today: **TRUE** (11+ days)
- Final score: 100

**Result:** Unconditionally assigned to Today, can't be ignored.

---

## Testing

### Test Stale Escalation

```python
# Create test email
email = {
    "subject": "Test stale escalation",
    "body": "This email is old",
    "received_at": datetime.utcnow() - timedelta(days=8),
    "from_address": "test@company.com",
    "importance": "normal",
    ...
}

# Score it
result = score_email(email, db=None)

# Check escalation
print(f"Raw score: {result['raw_score']}")
print(f"Stale bonus: {result['stale_bonus']}")
print(f"Adjusted: {result['adjusted_score']}")
print(f"Stale days: {result['stale_days']}")
```

### Test Urgency Floor

```python
# Create high-urgency email
email = {
    "subject": "URGENT: Critical issue",
    "body": "Need immediate response by EOD",
    "received_at": datetime.utcnow(),
    "from_address": "ceo@company.com",  # VIP
    "importance": "high",
    ...
}

result = score_email(email, db=None)

print(f"Adjusted score: {result['adjusted_score']}")
print(f"Floor override: {result['floor_override']}")
```

### Test Force Today

```python
# Create very old email
email = {
    "subject": "Old email test",
    "body": "This should force Today",
    "received_at": datetime.utcnow() - timedelta(days=15),
    ...
}

result = score_email(email, db=None)

print(f"Stale days: {result['stale_days']}")
print(f"Force today: {result['force_today']}")
print(f"Final score: {result['urgency_score']}")
```

---

## Queries

### Find All Floor Override Emails

```sql
SELECT e.id, e.subject, us.urgency_score, us.raw_score, us.stale_bonus
FROM emails e
JOIN urgency_scores us ON e.id = us.email_id
WHERE us.floor_override = TRUE
ORDER BY us.urgency_score DESC;
```

### Find All Force Today Emails

```sql
SELECT e.id, e.subject, us.stale_days, us.urgency_score
FROM emails e
JOIN urgency_scores us ON e.id = us.email_id
WHERE us.force_today = TRUE
ORDER BY us.stale_days DESC;
```

### Stale Escalation Impact Report

```sql
SELECT
    e.id,
    e.subject,
    us.raw_score,
    us.stale_bonus,
    us.adjusted_score,
    us.stale_days,
    (us.adjusted_score - us.raw_score) AS total_bonus
FROM emails e
JOIN urgency_scores us ON e.id = us.email_id
WHERE us.stale_bonus > 0
ORDER BY us.stale_bonus DESC;
```

---

## Summary

### Stale Escalation
- ✅ Progressively increases urgency for old emails
- ✅ Prevents emails from getting lost
- ✅ Forces 11+ day old emails to Today
- ✅ Configurable curve and thresholds

### Urgency Floor
- ✅ Flags emails with score >= 90
- ✅ Guarantees Today assignment (implemented Wed)
- ✅ Bypasses task limits
- ✅ Configurable threshold

### Together
- Old critical emails get maximum priority
- Important new emails get immediate attention
- Nothing falls through the cracks
- Fully transparent and explainable scoring

Both features work together to ensure your most important emails always surface, whether they're brand new and critical or old and forgotten! 🚀
