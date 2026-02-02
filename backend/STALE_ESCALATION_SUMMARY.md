# Urgency Floor & Stale Escalation - Implementation Summary

## ✅ What Was Built

Two powerful features added to prevent emails from getting lost and ensure critical items get immediate attention:

1. **Stale Escalation** - Progressively increases urgency for old emails
2. **Urgency Floor** - Flags emails above threshold (90+) for guaranteed Today assignment

---

## Changes Made

### 1. Configuration (app/services/scoring.py)

```python
# New configuration constants
URGENCY_FLOOR_THRESHOLD = 90
TASK_LIMIT = 20
STALE_ESCALATION_ENABLED = True

STALE_ESCALATION_CURVE = {
    "tier_1": {"days": (0, 3), "bonus_per_day": 2},
    "tier_2": {"days": (4, 5), "bonus_per_day": 5},
    "tier_3": {"days": (6, 10), "bonus_per_day": 10},
    "tier_4": {"days": (11, 999), "force_today": True}
}
```

### 2. New Functions (app/services/scoring.py)

**apply_stale_escalation(email, raw_score)**
- Calculates days since email received
- Applies progressive bonus curve
- Returns: adjusted_score, stale_days, stale_bonus, force_today

**apply_urgency_floor(email, adjusted_score, urgency_floor)**
- Checks if score >= threshold
- Returns: final_score, floor_override

### 3. Updated score_email() Function

Now returns:
```python
{
    "urgency_score": 58,       # Final score
    "raw_score": 20.0,         # Before escalation
    "stale_bonus": 38,         # Points added
    "adjusted_score": 58.0,    # After escalation
    "stale_days": 8,           # Days old
    "force_today": false,      # 11+ days?
    "floor_override": false,   # Score >= 90?
    "signals": { ... },
    "weights": { ... },
    "breakdown": { ... }
}
```

### 4. Updated Database Model (app/models/urgency_score.py)

Added fields:
- `raw_score` (FLOAT) - Score before escalation
- `stale_bonus` (INTEGER) - Bonus points added
- `force_today` (BOOLEAN) - True if 11+ days old

Updated fields:
- `floor_override` - Now set by system (score >= 90)
- `stale_days` - Now calculated from email age

### 5. Updated Scoring Endpoint (app/routes/emails.py)

Now stores all new fields in urgency_scores table.

---

## How It Works

### Stale Escalation Progressive Curve

```
Email Age     Bonus Per Day    Cumulative Bonus
---------     -------------    ----------------
Days 0-3      +2/day           Day 3 = +8
Days 4-5      +5/day           Day 5 = +18
Days 6-10     +10/day          Day 10 = +68
Day 11+       Force Today      Score = 100
```

### Example

**Email: "Project update needed"**
- Received: 8 days ago
- Raw score: 20

**Calculation:**
1. Days 0-3: 4 days × 2 = +8
2. Days 4-5: 2 days × 5 = +10
3. Days 6-8: 3 days × 10 = +30
4. **Total bonus:** +48 points
5. **Final score:** 20 + 48 = 68

### Urgency Floor

If adjusted_score >= 90:
- `floor_override = true`
- Email guaranteed Today assignment (Wed feature)
- Bypasses task limit constraints

### Force Today

If email is 11+ days old:
- `force_today = true`
- Score set to 100
- Unconditionally assigned to Today

---

## Configuration Options

### Adjust Escalation Aggressiveness

```python
# More aggressive (catch old emails faster)
STALE_ESCALATION_CURVE = {
    "tier_1": {"days": (0, 2), "bonus_per_day": 5},
    "tier_2": {"days": (3, 4), "bonus_per_day": 10},
    "tier_3": {"days": (5, 7), "bonus_per_day": 15},
    "tier_4": {"days": (8, 999), "force_today": True}
}

# Less aggressive (more time before escalation)
STALE_ESCALATION_CURVE = {
    "tier_1": {"days": (0, 5), "bonus_per_day": 1},
    "tier_2": {"days": (6, 10), "bonus_per_day": 3},
    "tier_3": {"days": (11, 20), "bonus_per_day": 5},
    "tier_4": {"days": (21, 999), "force_today": True}
}
```

### Adjust Floor Threshold

```python
URGENCY_FLOOR_THRESHOLD = 95  # Only very urgent
URGENCY_FLOOR_THRESHOLD = 85  # Catch more emails
```

### Disable Features

```python
STALE_ESCALATION_ENABLED = False  # Disable escalation
URGENCY_FLOOR_THRESHOLD = 101     # Disable floor
```

---

## Testing

### Restart Server

```bash
uvicorn app.main:app --reload --port 8000
```

### Score Emails

```bash
curl -X POST http://localhost:8000/api/emails/score
```

### Check Results

```sql
-- View stale escalation impact
SELECT
    e.id,
    e.subject,
    us.raw_score,
    us.stale_bonus,
    us.urgency_score AS final_score,
    us.stale_days,
    us.force_today,
    us.floor_override
FROM emails e
JOIN urgency_scores us ON e.id = us.email_id
WHERE us.stale_bonus > 0
ORDER BY us.stale_bonus DESC;

-- Find floor override emails
SELECT * FROM urgency_scores WHERE floor_override = TRUE;

-- Find force today emails
SELECT * FROM urgency_scores WHERE force_today = TRUE;
```

---

## Files Modified

1. **app/services/scoring.py**
   - Added configuration constants
   - Added `apply_stale_escalation()` function
   - Added `apply_urgency_floor()` function
   - Updated `score_email()` to use new functions

2. **app/models/urgency_score.py**
   - Added `raw_score` field
   - Added `stale_bonus` field
   - Added `force_today` field
   - Updated field comments

3. **app/routes/emails.py**
   - Updated scoring endpoint to store new fields

4. **Documentation**
   - Created URGENCY_FLOOR_AND_STALE_ESCALATION.md
   - Created STALE_ESCALATION_SUMMARY.md

---

## Benefits

✅ **Prevents Lost Emails** - Old emails automatically surface
✅ **Prioritizes Critical Items** - Floor ensures immediate attention
✅ **Transparent** - All calculations visible in database
✅ **Configurable** - Adjust thresholds to your workflow
✅ **Automatic** - No manual intervention required

---

## Next Steps (Wednesday)

1. Implement Today assignment logic
2. Use `floor_override` to bypass task limits
3. Use `force_today` for unconditional assignment
4. Display visual indicators in UI
5. Add bulk re-scoring for stale emails

---

The urgency floor and stale escalation features are now live! Old emails won't get lost, and critical emails will always get immediate attention. 🚀
