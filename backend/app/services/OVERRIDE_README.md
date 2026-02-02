# Override Classifier

The override classifier runs AFTER the deterministic classifier and checks if emails classified into Categories 6–11 (Other) should actually be in the Work pipeline based on urgency, sender importance, or personal direction.

## Purpose

Prevents important work emails from being incorrectly filtered into "Other" categories. Even if an email looks like Marketing, Notification, Calendar, FYI, or Travel, it should be treated as Work if it:
- Contains urgent language
- Comes from a VIP sender
- Is personally directed to the user
- Requires action or response

## Usage

```python
from app.services import check_override

# After deterministic classification
email_dict = {
    "message_id": "123",
    "from_address": "newsletter@example.com",
    "subject": "URGENT: Action required on your account",
    "body": "Your immediate attention is needed...",
    "to_recipients": '[{"address": "user@company.com"}]',
    "cc_recipients": '[]',
    "conversation_id": "conv-123",
}

current_category = 6  # Marketing

# Check for override
result = check_override(
    email=email_dict,
    current_category=current_category,
    user_email="user@company.com",
    first_name="User",
    db=db_session  # For reply chain checking
)

if result["override"]:
    # Reset to unprocessed for AI classification
    email.category_id = None
    email.status = "unprocessed"

    # Log the override
    log_entry = OverrideLog(
        email_id=email.id,
        original_category=current_category,
        trigger_type=result["trigger"],
        reason=result["reason"]
    )
    db.add(log_entry)
    db.commit()
```

## Override Triggers

The classifier checks 5 triggers in priority order. If ANY trigger matches, the email is overridden to the Work pipeline.

### 1. Urgency Language (Highest Priority)

Checks if subject or body contains urgent keywords:
- "urgent"
- "ASAP"
- "time-sensitive" / "time sensitive"
- "immediate attention"
- "action required"
- "critical"
- "deadline today"
- "due today"
- "due immediately"
- "needs your approval"
- "please respond by"
- "respond asap"
- "priority" / "high priority"
- "blocker" / "blocking"

**Example:**
```
From: newsletter@example.com (Marketing)
Subject: URGENT: Your account needs attention
→ Override triggered: urgency_language
```

### 2. VIP Sender

Checks if sender email or domain is in the VIP lists.

**Configuration:**
```python
# In app/services/classifier_override.py

VIP_SENDERS = [
    "boss@company.com",
    "ceo@company.com",
    "important.client@client.com",
]

VIP_DOMAINS = [
    "executive.company.com",
    "keyclient.com",
]
```

**Example:**
```
From: ceo@company.com (Notification)
Subject: Team update
→ Override triggered: vip_sender
```

### 3. Sole Recipient + FYI Mismatch

If the email is classified as FYI (category 9) but the user is the ONLY person in the To: field, this is likely a mistake. FYI should only apply to:
- Group emails (3+ recipients in To:)
- Emails where user is CC'd only

**Example:**
```
To: user@company.com (ONLY recipient)
Category: FYI (9)
→ Override triggered: sole_recipient_mismatch
```

### 4. Reply Chain Participation

If the user previously sent an email in this conversation thread (same `conversation_id`), new messages in the thread need attention regardless of classification.

**Example:**
```
Conversation ID: conv-123
Database has: user@company.com sent email in conv-123 on 2024-01-15
New email arrives in conv-123 from someone else
→ Override triggered: reply_chain_participation
```

### 5. Direct Address

Checks if the email body contains the user's first name in the context of a question or request.

**Patterns:**
- "Mo, can you..."
- "Hi Mo, please..."
- "Hey Mo, would you..."
- "Mo - could you..."
- "@Mo" (mention)

**Example:**
```
From: noreply@delta.com (Travel)
Body: "Hi Mo, can you confirm your seat selection?"
→ Override triggered: direct_address
```

## Configuration

### User Settings

Edit these constants in `app/services/classifier_override.py`:

```python
# User email for recipient checking
USER_EMAIL = "user@company.com"

# User first name for direct address detection
USER_FIRST_NAME = "Mo"
```

**Note:** These will be made dynamic in a future update to pull from the database.

### VIP Lists

Add important contacts to the VIP lists:

```python
VIP_SENDERS = [
    "boss@company.com",
    "ceo@company.com",
    "vp.engineering@company.com",
    "key.client@client.com",
]

VIP_DOMAINS = [
    "executive.company.com",  # All execs
    "keyclient.com",          # Important client
    "partner.com",            # Business partner
]
```

### Dynamic Configuration (Future)

Helper functions are provided for runtime configuration:

```python
from app.services.classifier_override import add_vip_sender, add_vip_domain, get_vip_config

# Add VIP at runtime
add_vip_sender("newboss@company.com")
add_vip_domain("newclient.com")

# Get current config
config = get_vip_config()
# Returns: {"vip_senders": [...], "vip_domains": [...]}
```

## Return Value

```python
# Override triggered
{
    "override": True,
    "reason": "Contains urgency language: 'urgent'",
    "trigger": "urgency_language"
}

# No override needed
{
    "override": False
}
```

## Integration with Classification Pipeline

```python
# 1. Run deterministic classifier
result = classify_deterministic(email_dict, user_email)

if result:
    # Email was classified into category 6-11
    category_id = result["category_id"]

    # 2. Check for override
    override_result = check_override(
        email_dict,
        category_id,
        user_email,
        first_name,
        db
    )

    if override_result["override"]:
        # 3. Reset to unprocessed for AI
        email.category_id = None
        email.status = "unprocessed"

        # 4. Log the override
        log = OverrideLog(
            email_id=email.id,
            original_category=category_id,
            trigger_type=override_result["trigger"],
            reason=override_result["reason"]
        )
        db.add(log)
    else:
        # Keep deterministic classification
        email.category_id = category_id
        email.confidence = result["confidence"]
        email.status = "classified"
else:
    # Email needs AI classification anyway
    email.status = "unprocessed"
```

## Override Log Table

The `override_log` table tracks all override events:

```python
class OverrideLog(Base):
    __tablename__ = "override_log"

    id: int                    # Primary key
    email_id: int              # Foreign key to emails
    original_category: int     # Category that was overridden (6-11)
    trigger_type: str          # Which trigger fired
    reason: str                # Human-readable explanation
    timestamp: datetime        # When override occurred
```

### Query Override Logs

```python
# Get all overrides for an email
overrides = db.query(OverrideLog).filter(
    OverrideLog.email_id == email_id
).all()

# Get overrides by trigger type
urgency_overrides = db.query(OverrideLog).filter(
    OverrideLog.trigger_type == "urgency_language"
).all()

# Count overrides by type
from sqlalchemy import func
trigger_counts = db.query(
    OverrideLog.trigger_type,
    func.count(OverrideLog.id)
).group_by(OverrideLog.trigger_type).all()
```

## Testing

Run the test scripts to verify behavior:

```bash
# Simple logic tests (no dependencies)
python3 test_override_simple.py

# Full integration tests (requires dependencies)
python3 test_override.py
```

## Examples

### Example 1: Marketing with Urgency
```
From: deals@store.com
Subject: Special offer - 50% off
Body: "Shop now and save! Limited time only."
Category: Marketing (6)
Override: NO (no urgency language, regular marketing)
```

### Example 2: Marketing with Action Required
```
From: newsletter@service.com
Subject: ACTION REQUIRED: Update your payment method
Body: "Your subscription needs immediate attention."
Category: Marketing (6)
Override: YES (urgency: "action required", "immediate attention")
Result: Reset to unprocessed for AI classification
```

### Example 3: FYI Group Email
```
To: team@company.com (15 recipients)
CC: user@company.com
Category: FYI (9)
Override: NO (correctly classified as FYI)
```

### Example 4: FYI Sole Recipient
```
To: user@company.com (ONLY recipient)
Category: FYI (9)
Override: YES (sole_recipient_mismatch)
Result: Reset to unprocessed for AI classification
```

### Example 5: Travel with Personal Request
```
From: noreply@united.com
Subject: Flight confirmation UAL123
Body: "Hi Mo, please confirm your meal preference for the flight."
Category: Travel (11)
Override: YES (direct_address: "Hi Mo, please")
Result: Reset to unprocessed for AI classification
```

## Performance

- All checks are rule-based (no API calls)
- Typical processing: 5-10ms per email
- Database query only for reply chain checking
- Can be disabled per-trigger if needed

## Future Enhancements

1. **Dynamic User Configuration**: Pull user email and name from database
2. **Machine Learning**: Learn VIP patterns from user corrections
3. **Customizable Triggers**: Allow users to enable/disable specific triggers
4. **Trigger Weights**: Some triggers more important than others
5. **White/Blacklist**: Explicit sender rules that bypass classification
