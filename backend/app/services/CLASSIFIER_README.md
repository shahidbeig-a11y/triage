# Deterministic Email Classifier

The deterministic email classifier (`classifier_deterministic.py`) provides rule-based classification for emails into categories 6–11 before falling back to AI classification.

## Usage

```python
from app.services import classify_deterministic

# Get email from database (as dict)
email = {
    "message_id": "123",
    "from_address": "newsletter@example.com",
    "from_name": "Example Store",
    "subject": "50% off sale!",
    "body": "Shop now...",
    "to_recipients": '[{"name": "User", "address": "user@example.com"}]',
    "cc_recipients": '[]',
}

# Classify (pass user email for FYI detection)
result = classify_deterministic(email, user_email="user@example.com")

if result:
    # Deterministic classification found
    category_id = result["category_id"]  # 6-11
    rule = result["rule"]  # Which rule matched
    confidence = result["confidence"]  # 0.85-0.95
else:
    # No deterministic match - needs AI classification
    pass
```

## Categories

- **Category 6 — Marketing**: Promotional emails, newsletters, deals
- **Category 7 — Notification**: System notifications, alerts, automated emails
- **Category 8 — Calendar**: Meeting invites, calendar events
- **Category 9 — FYI**: Group emails where user is CC'd or one of many recipients
- **Category 11 — Travel**: Flight confirmations, hotel bookings, itineraries
- **Category 10 — Actioned**: *(Not implemented in classifier - populated by resolution detection)*

## Classification Rules

### Category 8 — Calendar (checked first)
- Email has `text/calendar` MIME type or `.ics` attachment
- Subject matches: "Invitation:", "Updated invitation:", "Canceled:", etc.
- Sender is a calendar system (calendar-notification@google.com, etc.)

### Category 6 — Marketing
- Contains `List-Unsubscribe` header
- Sender matches patterns: noreply@, marketing@, newsletter@, deals@, etc.
- Sender domain is known marketing platform (mailchimp.com, sendgrid.net, etc.)
- Subject contains promotional keywords: "% off", "sale", "promo code", etc.

### Category 11 — Travel
- Sender domain is travel-related: airlines, hotels, rental cars, rideshare, booking platforms
- Subject contains: "booking confirmation", "itinerary", "flight confirmation", etc.

### Category 7 — Notification
- Sender matches patterns: noreply@, notifications@, alerts@, donotreply@
- Known notification domains: microsoft.com, google.com, github.com, slack.com, etc.
- Subject matches: "Your order", "Password reset", "Security alert", "Verification code"
- **Exclusion**: If user is sole recipient AND email has urgency language, skip (may need action)

### Category 9 — FYI
- User is in CC field only (not in To field)
- OR To field has 3+ recipients (group email)
- **Exclusions**: Email mentions user by name OR contains urgency language

## Customization

### Adding Known Senders

Edit the registries at the top of `classifier_deterministic.py`:

```python
MARKETING_DOMAINS = {
    "mailchimp.com",
    "sendgrid.net",
    # Add your domains here
}

NOTIFICATION_DOMAINS = {
    "microsoft.com",
    "github.com",
    # Add your domains here
}

TRAVEL_DOMAINS = {
    "delta.com",
    "marriott.com",
    # Add your domains here
}
```

### Adding Patterns

Edit the pattern lists:

```python
MARKETING_SENDER_PATTERNS = [
    r"^noreply@",
    r"^newsletter@",
    # Add regex patterns here
]
```

## Testing

Run the test script to verify classification:

```bash
python3 test_classifier.py
```

## Integration

To integrate with your email processing pipeline:

```python
from app.services import classify_deterministic
from app.models import Email

def process_emails(db_session, user_email):
    unprocessed = db_session.query(Email).filter(
        Email.status == "unprocessed"
    ).all()

    for email in unprocessed:
        # Convert SQLAlchemy model to dict
        email_dict = {
            "message_id": email.message_id,
            "from_address": email.from_address,
            "from_name": email.from_name,
            "subject": email.subject,
            "body": email.body,
            "to_recipients": email.to_recipients,
            "cc_recipients": email.cc_recipients,
        }

        # Try deterministic classification first
        result = classify_deterministic(email_dict, user_email)

        if result:
            # Deterministic classification succeeded
            email.category_id = result["category_id"]
            email.confidence = result["confidence"]
            email.status = "processed"
        else:
            # Fall back to AI classification
            ai_result = classify_with_ai(email_dict)
            email.category_id = ai_result["category_id"]
            email.confidence = ai_result["confidence"]
            email.status = "processed"

        db_session.commit()
```

## Confidence Scores

The classifier returns confidence scores in the range 0.85–0.95:

- **0.95**: Strong signals (MIME type, List-Unsubscribe header, calendar system sender)
- **0.90**: Known domains (marketing platforms, travel companies, calendar patterns)
- **0.88**: Positional rules (CC only, known notification domains)
- **0.85**: Pattern matches (sender patterns, subject keywords)

## Future Enhancements

1. **Headers Support**: Add email headers field to database and fetch from Graph API for List-Unsubscribe detection
2. **Name Mention Detection**: Parse user's display name and check if mentioned in email body (for FYI exclusion)
3. **Attachment Analysis**: Check for .ics files in attachments list (for Calendar detection)
4. **Domain Learning**: Track new domains over time and suggest additions to registries
5. **Rule Metrics**: Log which rules are most frequently matched for tuning

## Notes

- The classifier requires `user_email` parameter for Categories 7 (Notification) and 9 (FYI) to check recipient exclusions
- If `user_email` is not provided, these categories will skip recipient-based checks
- Email headers are optional; if not present, List-Unsubscribe check is skipped
- The classifier is designed to be conservative - when in doubt, it returns `None` to fall back to AI
