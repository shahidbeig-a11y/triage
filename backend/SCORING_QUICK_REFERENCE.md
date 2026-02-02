# Urgency Scoring Engine - Quick Reference

## Usage

```python
from app.services.scoring import score_email

result = score_email(email_dict, db=session, user_domain="company.com")
# Returns: {"urgency_score": 87, "signals": {...}, "weights": {...}, "breakdown": {...}}
```

## 8 Signals at a Glance

| # | Signal | Weight | Returns | Description |
|---|--------|--------|---------|-------------|
| 1 | `extract_explicit_deadline` | 0.25 | 0-100 | Finds dates: "by Friday", "EOD", "2/15" |
| 2 | `extract_sender_seniority` | 0.15 | 10-90 | VIP=90, External=40, Internal=20 |
| 3 | `extract_importance_flag` | 0.10 | -20 to 80 | High=80, Normal=0, Low=-20 |
| 4 | `extract_urgency_language` | 0.15 | -10 to 90 | "ASAP"=90, "action required"=60 |
| 5 | `extract_thread_velocity` | 0.10 | 0-80 | 5+ replies/24h=80, 0 replies=0 |
| 6 | `extract_client_external` | 0.05 | 0-50 | External=50, Internal=0 |
| 7 | `extract_age_of_email` | 0.10 | 0-80 | 3+ days=80, <2hrs=0 |
| 8 | `extract_followup_overdue` | 0.10 | 0-100 | Cat 4: days_overdue × 15 |

## Score Ranges

```
90-100  🔴 Critical   Drop everything, handle now
70-89   🟠 High       Handle today
50-69   🟡 Medium     Handle this week
30-49   🟢 Normal     Standard priority
0-29    ⚪ Low        When time permits
```

## Deadline Detection Patterns

```python
"today", "tomorrow"           → 0-1 day  → Score: 100-85
"EOD", "COB"                  → Same day → Score: 100
"by Friday", "next Monday"    → Day calc → Score: varies
"February 15", "2/15/2024"    → Explicit → Score: varies
"this week", "next week"      → ~4-7 days→ Score: 25-40
```

## Urgency Keywords

```python
Strong (90):  "ASAP", "urgent", "immediately", "critical"
Medium (60):  "action required", "time-sensitive", "priority"
Mild (-10):   "no rush", "low priority", "when you get a chance"
```

## Configuration

```python
# scoring.py
USER_DOMAIN = "company.com"
SIGNAL_WEIGHTS = { ... }  # Must sum to 1.0

# classifier_override.py
VIP_SENDERS = ["boss@company.com", ...]
VIP_DOMAINS = ["bigclient.com", ...]
```

## Example Output

```json
{
  "urgency_score": 87,
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
  "breakdown": {
    "explicit_deadline_weighted": 25.0,
    "sender_seniority_weighted": 13.5,
    ...
  }
}
```

## Common Integrations

```python
# Score single email
result = score_email(email_dict, db)

# Update database
email.urgency_score = result["urgency_score"]
db.commit()

# Rank emails
emails = sorted(emails, key=lambda e: e.urgency_score, reverse=True)

# Filter by urgency
critical = [e for e in emails if e.urgency_score >= 90]
```

## Testing

```bash
python3 test_scoring_engine.py
```

## Files

- `app/services/scoring.py` - Implementation (625 lines)
- `SCORING_ENGINE_GUIDE.md` - Full documentation
- `SCORING_ENGINE_SUMMARY.md` - Build summary
- `test_scoring_engine.py` - Test harness

## Formula

```
urgency_score = Σ (signal[i] × weight[i])
clamped to [0, 100]
```
