# Classification Endpoint Documentation

## POST /api/emails/classify-deterministic

Runs deterministic classification on all unprocessed emails using header-based and sender-based rules.

### Endpoint

```
POST /api/emails/classify-deterministic
```

### Authentication

Uses the first authenticated user in the database for recipient checking (FYI classification).

### Request

No body parameters required.

### Response

```json
{
  "total_processed": 10,
  "classified": 7,
  "remaining": 3,
  "breakdown": {
    "6_marketing": 2,
    "7_notification": 3,
    "8_calendar": 1,
    "9_fyi": 1,
    "11_travel": 0
  },
  "message": "Classified 7 out of 10 emails. 3 emails need AI classification."
}
```

### Response Fields

- **total_processed**: Total number of unprocessed emails found
- **classified**: Number of emails successfully classified by deterministic rules
- **remaining**: Number of emails that still need AI classification (returned None)
- **breakdown**: Count of emails classified into each category:
  - `6_marketing`: Marketing emails, newsletters, promotions
  - `7_notification`: System notifications, alerts, automated emails
  - `8_calendar`: Calendar invites and meeting updates
  - `9_fyi`: Group emails or CC'd emails where user is not primary recipient
  - `11_travel`: Flight confirmations, hotel bookings, travel itineraries
- **message**: Human-readable summary

### Behavior

1. Fetches all emails with `status = 'unprocessed'` from the database
2. Runs `classify_deterministic()` on each email
3. For emails that match a rule:
   - Updates `category_id`, `confidence`, and `status = 'classified'`
   - Creates a `ClassificationLog` entry with:
     - `email_id`: ID of the classified email
     - `category_id`: Assigned category (6-11)
     - `rule`: Description of which rule matched
     - `classifier_type`: Set to "deterministic"
     - `confidence`: Confidence score (0.85-0.95)
     - `created_at`: Timestamp of classification
4. For emails that return None:
   - Leaves `status = 'unprocessed'` for later AI classification
   - No log entry is created

### Database Changes

#### Emails Table Updates

```sql
UPDATE emails
SET
  category_id = <matched_category>,
  confidence = <rule_confidence>,
  status = 'classified'
WHERE id = <email_id>
```

#### Classification Log Entries

```sql
INSERT INTO classification_log (
  email_id,
  category_id,
  rule,
  classifier_type,
  confidence,
  created_at
) VALUES (
  <email_id>,
  <category_id>,
  '<rule_description>',
  'deterministic',
  <confidence>,
  <timestamp>
)
```

### Example Usage

```bash
# Run deterministic classification
curl -X POST http://localhost:8000/api/emails/classify-deterministic

# Response
{
  "total_processed": 50,
  "classified": 35,
  "remaining": 15,
  "breakdown": {
    "6_marketing": 12,
    "7_notification": 18,
    "8_calendar": 3,
    "9_fyi": 2,
    "11_travel": 0
  },
  "message": "Classified 35 out of 50 emails. 15 emails need AI classification."
}
```

### Integration with AI Classifier

This endpoint should be run **before** the AI classifier as a performance optimization:

1. **Fetch emails** → `POST /api/emails/fetch`
2. **Run deterministic classifier** → `POST /api/emails/classify-deterministic`
3. **Run AI classifier on remaining** → `POST /api/emails/classify-ai` (to be implemented)

This approach:
- Saves AI API calls and costs
- Provides faster classification for rule-based categories
- Ensures consistent classification for obvious cases
- Logs which method was used for auditing

### Classification Log Table

The `classification_log` table tracks all classification events for debugging and auditing:

```python
class ClassificationLog(Base):
    __tablename__ = "classification_log"

    id: int                    # Primary key
    email_id: int              # Foreign key to emails table
    category_id: int           # Foreign key to categories table
    rule: str                  # Description of matched rule
    classifier_type: str       # 'deterministic' or 'ai'
    confidence: float          # 0.0 to 1.0
    created_at: datetime       # Timestamp
```

### Query Classification Logs

```python
# Get all classifications for an email
logs = db.query(ClassificationLog).filter(
    ClassificationLog.email_id == email_id
).order_by(ClassificationLog.created_at.desc()).all()

# Get all deterministic classifications
deterministic = db.query(ClassificationLog).filter(
    ClassificationLog.classifier_type == "deterministic"
).all()

# Get classification breakdown by type
from sqlalchemy import func
breakdown = db.query(
    ClassificationLog.category_id,
    ClassificationLog.classifier_type,
    func.count(ClassificationLog.id)
).group_by(
    ClassificationLog.category_id,
    ClassificationLog.classifier_type
).all()
```

### Error Handling

The endpoint handles errors gracefully:
- If no user is found, `user_email` is None (FYI classification will be skipped)
- If database commit fails, all changes are rolled back
- Classification errors are logged but don't stop processing of other emails

### Performance

- Processes emails in a single database transaction
- Commits all changes at once for efficiency
- Typical processing time: ~10-20ms per email
- No external API calls (all rule-based)

### Next Steps

1. Create AI classifier endpoint for remaining unprocessed emails
2. Add a combined endpoint that runs both classifiers in sequence
3. Add category override endpoint for manual corrections
4. Implement classification analytics dashboard
