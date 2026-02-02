# Email Filtering Rules

## Overview

The app now automatically filters out emails that shouldn't be processed to avoid wasting resources on old or recently-processed emails.

## Filtering Rules

### Rule 1: Age Limit (45 Days)
**Emails older than 45 days are excluded from processing.**

- Calculated from `received_at` timestamp
- Cutoff: Current date/time - 45 days
- Applies to: All classification operations

**Why?**
- Old emails are likely already handled
- Reduces processing load
- Focuses on current/recent work

### Rule 2: Recent Processing Cooldown (3 Days)
**Emails processed in the last 3 days are excluded from re-processing.**

- Checked via `classification_logs` table
- Cooldown period: 3 days from last classification
- Applies to: All classification operations

**Why?**
- Prevents redundant re-processing
- Gives time for action before re-evaluation
- Avoids duplicate work

## Where Filters Apply

These filters are applied in **all classification endpoints**:

1. **Pipeline endpoint** (`POST /api/emails/pipeline/run`)
   - Phase 2: Deterministic classification
   - Phase 4: AI classification

2. **Individual endpoints**
   - `POST /api/emails/classify-deterministic`
   - `POST /api/emails/classify-ai`

## Technical Implementation

### Database Queries

```python
# Age filter
cutoff_date = datetime.utcnow() - timedelta(days=45)
Email.received_at >= cutoff_date

# Recent processing filter
recent_processing_cutoff = datetime.utcnow() - timedelta(days=3)
recently_processed_ids = db.query(ClassificationLog.email_id).filter(
    ClassificationLog.created_at >= recent_processing_cutoff
).distinct().all()

# Combined query
unprocessed_emails = db.query(Email).filter(
    Email.status == "unprocessed",
    Email.received_at >= cutoff_date,
    ~Email.id.in_(recently_processed_ids) if recently_processed_ids else True
).all()
```

## Reporting

The pipeline reports filtered emails:

```json
{
  "phase_2_deterministic": {
    "classified": 35,
    "filtered": 8,  // NEW: Number of emails filtered out
    "breakdown": {...}
  }
}
```

## Examples

### Scenario 1: Old Email
- Email received: 50 days ago
- Status: unprocessed
- **Result**: Filtered out (too old)

### Scenario 2: Recently Processed
- Email received: 10 days ago
- Last classified: 1 day ago
- Status: unprocessed (maybe reset for testing)
- **Result**: Filtered out (recently processed)

### Scenario 3: Eligible for Processing
- Email received: 20 days ago
- Last classified: 5 days ago (or never)
- Status: unprocessed
- **Result**: Processed normally

### Scenario 4: Eligible for Re-Processing
- Email received: 30 days ago
- Last classified: 4 days ago
- Status: unprocessed (reset after failed classification)
- **Result**: Processed (cooldown expired)

## Configuration

Both thresholds are currently hardcoded but can be made configurable:

```python
# In pipeline.py and routes/emails.py
AGE_LIMIT_DAYS = 45  # Could be config setting
PROCESSING_COOLDOWN_DAYS = 3  # Could be config setting
```

To modify these values, update the `timedelta(days=X)` values in:
- `app/services/pipeline.py` (line ~108, ~191)
- `app/routes/emails.py` (line ~315, ~450)

## Edge Cases

### Re-processing After Manual Changes
If you manually reset an email to `unprocessed` status:
- **Within 3 days**: Won't be re-processed (cooldown active)
- **After 3 days**: Will be re-processed

**Workaround**: Delete classification logs for specific emails to bypass cooldown:
```sql
DELETE FROM classification_logs WHERE email_id = <email_id>;
```

### Testing with Old Data
When testing with a database of old emails:
- Most emails may be filtered out by age limit
- Fetch fresh emails from Outlook to see processing in action

### Initial Pipeline Run
On first run with empty `classification_logs`:
- Age filter applies (45 days)
- Cooldown filter doesn't apply (no prior processing)
- Expect all recent emails to be processed

## Monitoring

Check how many emails are being filtered:

```bash
# View filtered count in pipeline response
curl -X POST "http://localhost:8000/api/emails/pipeline/run" | jq '.phase_2_deterministic.filtered'

# Count unprocessed emails older than 45 days
curl "http://localhost:8000/api/emails?status=unprocessed" | jq '.emails[] | select(.received_at < "2024-XX-XX")'
```

## Benefits

✅ **Performance**: Skip unnecessary processing of old/recent emails
✅ **Cost savings**: Reduce AI API calls for emails already handled
✅ **Focus**: Prioritize current actionable work
✅ **Stability**: Prevent re-processing loops

## Trade-offs

⚠️ **Manual re-processing**: Requires waiting 3 days or manual log deletion
⚠️ **Old email recovery**: Can't re-process emails older than 45 days without code change
⚠️ **Testing complexity**: Need fresh data or manual adjustments for testing

## Future Enhancements

Potential improvements:
1. Make thresholds configurable via settings/environment variables
2. Add bypass flag for manual re-processing (`force=true`)
3. Track filter statistics in database
4. Add UI to view filtered emails
5. Configurable filters per classification type
