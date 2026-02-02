# Urgency Scoring Endpoint - Quick Reference

## Endpoint

```
POST /api/emails/score
```

## What It Does

1. Fetches emails: `status='classified'` AND `category_id` in [1, 2, 3, 4, 5]
2. Scores each with 8-signal engine
3. Updates `email.urgency_score`
4. Creates/updates `urgency_scores` table
5. Returns statistics

## Usage

```bash
curl -X POST http://localhost:8000/api/emails/score
```

## Response

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
  "highest": {"email_id": 123, "subject": "...", "score": 95},
  "lowest": {"email_id": 456, "subject": "...", "score": 12},
  "message": "Successfully scored 47 Work emails"
}
```

## Database

### urgency_scores Table

```
email_id          INTEGER (FK, unique)
urgency_score     FLOAT (0-100)
signals_json      TEXT (full breakdown)
scored_at         DATETIME
floor_override    BOOLEAN
stale_days        INTEGER
```

## Score Ranges

```
90-100  🔴 Critical   critical_90_plus
70-89   🟠 High       high_70_89
40-69   🟡 Medium     medium_40_69
0-39    🟢 Low        low_under_40
```

## Work Categories (Scored)

```
1. Blocking
2. Action Required
3. Waiting On
4. Time-Sensitive
5. FYI
```

Other categories (6-11) are NOT scored.

## Test

```bash
./test_scoring_endpoint.sh
```

## Query Scored Emails

```sql
-- Get critical emails
SELECT * FROM emails e
JOIN urgency_scores us ON e.id = us.email_id
WHERE us.urgency_score >= 90
ORDER BY us.urgency_score DESC;

-- Get signal breakdown
SELECT signals_json FROM urgency_scores WHERE email_id = 123;
```

## Files

- `app/models/urgency_score.py` - Model
- `app/routes/emails.py` - Endpoint (line ~695)
- `SCORING_ENDPOINT_GUIDE.md` - Full docs
- `test_scoring_endpoint.sh` - Test script
