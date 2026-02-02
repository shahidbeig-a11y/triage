# Quick Start Guide: Testing the Complete Email Classification System

This guide walks you through testing all three classifiers end-to-end.

---

## Prerequisites

### 1. Install Dependencies

```bash
cd /Users/shahid/Projects/triage/backend

# Create virtual environment (optional but recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install required packages
pip install fastapi uvicorn sqlalchemy python-dotenv httpx msal anthropic
```

### 2. Configure Environment Variables

Create or update `.env` file:

```bash
# Microsoft Graph API (for fetching emails)
MICROSOFT_CLIENT_ID=your_client_id_here
MICROSOFT_CLIENT_SECRET=your_client_secret_here
MICROSOFT_TENANT=common
MICROSOFT_REDIRECT_URI=http://localhost:8000/api/auth/callback

# Anthropic API (for AI classification)
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxx

# Database
DATABASE_URL=sqlite:///./triage.db
```

**Note:** If you don't have API keys yet:
- **Microsoft:** https://portal.azure.com/ (register app)
- **Anthropic:** https://console.anthropic.com/ (get API key)

---

## Step-by-Step Testing

### Step 1: Start the Server

```bash
# From the backend directory
uvicorn app.main:app --reload --port 8000
```

Expected output:
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
🚀 Starting up FastAPI application...
✅ Database initialized and ready
✅ Seeded 11 system categories
INFO:     Application startup complete.
```

**Keep this terminal open!**

---

### Step 2: Authenticate with Microsoft (Optional - if fetching real emails)

If you want to test with real emails from your inbox:

1. Open browser to: http://localhost:8000/api/auth/login
2. Sign in with your Microsoft account
3. Grant permissions
4. You'll be redirected back

**Skip this step if you just want to test with sample data.**

---

### Step 3: Fetch Emails

**Option A: Fetch from Microsoft Graph** (requires auth)

```bash
curl -X POST "http://localhost:8000/api/emails/fetch?count=50"
```

**Option B: Insert Test Emails** (for testing without auth)

```bash
# We'll create a script for this below
python3 seed_test_emails.py
```

---

### Step 4: Run Deterministic Classification

```bash
curl -X POST http://localhost:8000/api/emails/classify-deterministic | python3 -m json.tool
```

Expected response:
```json
{
  "total_processed": 50,
  "classified": 35,
  "overridden": 5,
  "remaining": 15,
  "breakdown": {
    "6_marketing": 12,
    "7_notification": 15,
    "8_calendar": 5,
    "9_fyi": 3,
    "11_travel": 0
  },
  "message": "Classified 35 out of 50 emails. 5 overridden to Work. 15 emails need AI classification."
}
```

---

### Step 5: Run AI Classification

```bash
curl -X POST http://localhost:8000/api/emails/classify-ai | python3 -m json.tool
```

Expected response:
```json
{
  "total_processed": 20,
  "classified": 20,
  "failed": 0,
  "breakdown": {
    "1_blocking": 2,
    "2_action_required": 8,
    "3_waiting_on": 4,
    "4_time_sensitive": 4,
    "5_fyi": 2
  },
  "api_cost_estimate": "$0.08",
  "message": "Classified 20 out of 20 emails using AI. 0 failed. Estimated cost: $0.08"
}
```

---

### Step 6: View Results

```bash
# Get all classified emails
curl "http://localhost:8000/api/emails?status=classified" | python3 -m json.tool

# Get emails by category
curl "http://localhost:8000/api/emails?status=classified&limit=5" | python3 -m json.tool
```

---

## Testing Without Real Emails

If you don't have Microsoft credentials or want to test quickly, create test data:

### Create Test Email Seeder

Create `seed_test_emails.py`:

```python
"""Seed test emails for testing classifiers."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.database import SessionLocal, init_db
from app.models import Email
from datetime import datetime
import json

# Initialize database
init_db()
db = SessionLocal()

# Sample test emails
test_emails = [
    {
        "message_id": "test-1",
        "from_address": "newsletter@store.com",
        "from_name": "Store Newsletter",
        "subject": "50% off sale this weekend!",
        "body": "Shop now and save big...",
        "body_preview": "Shop now and save big...",
        "to_recipients": json.dumps([{"name": "User", "address": "user@company.com"}]),
        "cc_recipients": json.dumps([]),
        "received_at": datetime.utcnow(),
        "importance": "normal",
        "conversation_id": "conv-1",
        "has_attachments": False,
        "is_read": False,
        "folder": "inbox",
        "status": "unprocessed"
    },
    {
        "message_id": "test-2",
        "from_address": "colleague@company.com",
        "from_name": "Colleague Name",
        "subject": "Can you review this PR?",
        "body": "Hey, I finished the feature. Can you take a look at the PR?",
        "body_preview": "Hey, I finished the feature...",
        "to_recipients": json.dumps([{"name": "User", "address": "user@company.com"}]),
        "cc_recipients": json.dumps([]),
        "received_at": datetime.utcnow(),
        "importance": "normal",
        "conversation_id": "conv-2",
        "has_attachments": False,
        "is_read": False,
        "folder": "inbox",
        "status": "unprocessed"
    },
    {
        "message_id": "test-3",
        "from_address": "calendar-notification@google.com",
        "from_name": "Google Calendar",
        "subject": "Invitation: Team Meeting @ Mon 2pm",
        "body": "You have been invited to Team Meeting...",
        "body_preview": "You have been invited...",
        "to_recipients": json.dumps([{"name": "User", "address": "user@company.com"}]),
        "cc_recipients": json.dumps([]),
        "received_at": datetime.utcnow(),
        "importance": "normal",
        "conversation_id": "conv-3",
        "has_attachments": False,
        "is_read": False,
        "folder": "inbox",
        "status": "unprocessed"
    },
    {
        "message_id": "test-4",
        "from_address": "devops@company.com",
        "from_name": "DevOps Team",
        "subject": "URGENT: Production API down",
        "body": "Production is down. Need immediate approval to deploy fix.",
        "body_preview": "Production is down...",
        "to_recipients": json.dumps([{"name": "User", "address": "user@company.com"}]),
        "cc_recipients": json.dumps([]),
        "received_at": datetime.utcnow(),
        "importance": "high",
        "conversation_id": "conv-4",
        "has_attachments": False,
        "is_read": False,
        "folder": "inbox",
        "status": "unprocessed"
    },
    {
        "message_id": "test-5",
        "from_address": "notifications@github.com",
        "from_name": "GitHub",
        "subject": "New issue assigned to you",
        "body": "User, can you review this issue? It's blocking the release.",
        "body_preview": "User, can you review...",
        "to_recipients": json.dumps([{"name": "User", "address": "user@company.com"}]),
        "cc_recipients": json.dumps([]),
        "received_at": datetime.utcnow(),
        "importance": "normal",
        "conversation_id": "conv-5",
        "has_attachments": False,
        "is_read": False,
        "folder": "inbox",
        "status": "unprocessed"
    },
]

print("Seeding test emails...")
for email_data in test_emails:
    # Check if email already exists
    existing = db.query(Email).filter(Email.message_id == email_data["message_id"]).first()
    if existing:
        print(f"  Skipping {email_data['message_id']} (already exists)")
        continue

    email = Email(**email_data)
    db.add(email)
    print(f"  Added: {email_data['from_address']} - {email_data['subject']}")

db.commit()
print(f"✅ Seeded {len(test_emails)} test emails")
db.close()
```

Run it:
```bash
python3 seed_test_emails.py
```

---

## Expected Full Workflow Response

### 1. After Seeding Test Emails

```
✅ Seeded 5 test emails
  - newsletter@store.com (Marketing)
  - colleague@company.com (Work - needs AI)
  - calendar@google.com (Calendar)
  - devops@company.com (Work - needs AI)
  - notifications@github.com (Notification with urgency)
```

### 2. After Deterministic Classification

```bash
curl -X POST http://localhost:8000/api/emails/classify-deterministic
```

```json
{
  "total_processed": 5,
  "classified": 2,
  "overridden": 1,
  "remaining": 2,
  "breakdown": {
    "6_marketing": 1,
    "7_notification": 0,
    "8_calendar": 1,
    "9_fyi": 0,
    "11_travel": 0
  },
  "message": "Classified 2 out of 5 emails. 1 overridden to Work. 2 emails need AI classification."
}
```

**What happened:**
- Newsletter → Marketing (6)
- Calendar → Calendar (8)
- GitHub notification → Notification (7) → **Overridden** (urgency detected)
- Colleague PR review → Needs AI
- DevOps urgent → Needs AI

### 3. After AI Classification

```bash
curl -X POST http://localhost:8000/api/emails/classify-ai
```

```json
{
  "total_processed": 3,
  "classified": 3,
  "failed": 0,
  "breakdown": {
    "1_blocking": 1,
    "2_action_required": 2,
    "3_waiting_on": 0,
    "4_time_sensitive": 0,
    "5_fyi": 0
  },
  "api_cost_estimate": "$0.01",
  "message": "Classified 3 out of 3 emails using AI. 0 failed. Estimated cost: $0.01"
}
```

**Classifications:**
- DevOps urgent → Blocking (1)
- Colleague PR review → Action Required (2)
- GitHub issue (overridden) → Action Required (2)

---

## Troubleshooting

### Error: "ANTHROPIC_API_KEY not found"

**Solution:** Add API key to `.env` file
```bash
echo "ANTHROPIC_API_KEY=sk-ant-xxxxx" >> .env
```

### Error: "No unprocessed emails"

**Solution:** Either fetch emails or run the seeder
```bash
python3 seed_test_emails.py
```

### Error: "Rate limit exceeded"

**Solution:** Wait a moment and try again. The classifier has automatic retry logic.

### Error: Connection refused

**Solution:** Make sure the server is running
```bash
uvicorn app.main:app --reload
```

---

## Verify Results

### Check Database

```bash
# Using sqlite3 CLI
sqlite3 triage.db

# Query emails
SELECT id, from_address, subject, category_id, status, confidence
FROM emails
ORDER BY category_id;

# Query classification logs
SELECT e.subject, c.category_id, c.classifier_type, c.confidence, c.rule
FROM emails e
JOIN classification_log c ON e.id = c.email_id
ORDER BY c.created_at DESC;

# Query override logs
SELECT e.subject, o.original_category, o.trigger_type, o.reason
FROM emails e
JOIN override_log o ON e.id = o.email_id;
```

### Check via API

```bash
# All emails
curl http://localhost:8000/api/emails | python3 -m json.tool

# Just classified emails
curl "http://localhost:8000/api/emails?status=classified" | python3 -m json.tool

# Specific category
curl "http://localhost:8000/api/emails?category_id=2" | python3 -m json.tool
```

---

## Summary

The complete classification pipeline is now working! 🎉

**What you built:**
1. ✅ Deterministic classifier (categories 6-11)
2. ✅ Override checker (catches important work emails)
3. ✅ AI classifier (categories 1-5)
4. ✅ Complete API endpoints
5. ✅ Database logging
6. ✅ Cost estimation

**Next steps:**
- Add more test emails
- Test with real inbox
- Build frontend to display categorized emails
- Add user feedback loop for corrections
- Implement learning from corrections
