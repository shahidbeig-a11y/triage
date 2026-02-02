# New Endpoints Testing Guide

## Overview

Three new endpoints have been added to the Email Triage API:

1. **GET /api/emails/summary** - Get statistics of all emails
2. **POST /api/pipeline/run** - Run the full classification pipeline
3. **POST /api/emails/{email_id}/reclassify** - Manually reclassify an email

All endpoints are registered and ready to use.

---

## 1. GET /api/emails/summary

### Description
Query the database and return summary statistics of all emails.

### Endpoint
```
GET http://localhost:8000/api/emails/summary
```

### Response Format
```json
{
  "total": 150,
  "by_category": {
    "1_blocking": 5,
    "2_action_required": 12,
    "3_waiting_on": 8,
    "4_time-sensitive": 3,
    "5_fyi": 10,
    "6_discuss": 4,
    "7_decide": 2,
    "8_delegate": 1,
    "9_read_review": 6,
    "10_low_priority": 15,
    "11_archive": 20,
    "uncategorized": 64
  },
  "by_status": {
    "unprocessed": 64,
    "classified": 86
  }
}
```

### Test Command
```bash
curl http://localhost:8000/api/emails/summary
```

---

## 2. POST /api/pipeline/run

### Description
Orchestrates the complete email classification workflow:
1. Fetch emails from Microsoft Graph API
2. Run deterministic classifier on unprocessed emails
3. Check overrides on newly-classified Other emails
4. Run AI classifier on remaining unprocessed emails

### Endpoint
```
POST http://localhost:8000/api/pipeline/run?fetch_count=50
```

### Query Parameters
- `fetch_count` (optional, default=50, range=1-200): Number of emails to fetch

### Response Format
```json
{
  "fetch": {
    "total": 50,
    "new": 25
  },
  "deterministic": {
    "classified": 15,
    "breakdown": {
      "6": 5,
      "7": 3,
      "8": 4,
      "9": 2,
      "11": 1
    }
  },
  "override": {
    "checked": 15,
    "overridden": 2
  },
  "ai": {
    "classified": 12,
    "breakdown": {
      "1": 1,
      "2": 5,
      "3": 3,
      "4": 2,
      "5": 1
    }
  },
  "summary": {
    "total_emails": 175,
    "work_items": 48,
    "other_items": 63,
    "processing_time_seconds": 45.23
  }
}
```

### Test Command
```bash
curl -X POST "http://localhost:8000/api/pipeline/run?fetch_count=50"
```

---

## 3. POST /api/emails/{email_id}/reclassify

### Description
Manually reclassify an email to a different category. Updates the email's category_id and logs it in classification_log with classifier_type = "manual".

### Endpoint
```
POST http://localhost:8000/api/emails/{email_id}/reclassify
```

### Request Body
```json
{
  "category_id": 2
}
```

### Response Format
```json
{
  "email_id": 123,
  "old_category_id": 9,
  "new_category_id": 2,
  "category_label": "Action Required",
  "status": "classified",
  "message": "Email reclassified to Action Required"
}
```

### Error Responses

**404 - Email not found:**
```json
{
  "detail": "Email not found"
}
```

**400 - Invalid category:**
```json
{
  "detail": "Invalid category_id"
}
```

### Test Commands

```bash
# Reclassify email ID 123 to category 2 (Action Required)
curl -X POST "http://localhost:8000/api/emails/123/reclassify" \
  -H "Content-Type: application/json" \
  -d '{"category_id": 2}'

# Reclassify email ID 456 to category 5 (FYI)
curl -X POST "http://localhost:8000/api/emails/456/reclassify" \
  -H "Content-Type: application/json" \
  -d '{"category_id": 5}'
```

---

## Category ID Reference

Based on your database schema:

| ID | Label | Tab | Description |
|----|-------|-----|-------------|
| 1 | Blocking | P1 | Critical blockers requiring immediate action |
| 2 | Action Required | P1 | Important tasks that need completion |
| 3 | Waiting On | P2 | Pending response from others |
| 4 | Time-Sensitive | P2 | Has a deadline or time constraint |
| 5 | FYI | Action | Informational, no action needed |
| 6 | Discuss | Action | Needs discussion or clarification |
| 7 | Decide | Action | Requires a decision to be made |
| 8 | Delegate | Action | Should be assigned to someone else |
| 9 | Read/Review | Action | Documents or content to review |
| 10 | Low Priority | P3 | Can be addressed later |
| 11 | Archive | P3 | Completed or no longer relevant |

---

## Running the Server

```bash
cd backend
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`

### API Documentation

FastAPI automatically generates interactive API documentation:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## Pipeline Flow Diagram

```
START
  │
  ├─► FETCH EMAILS from Microsoft Graph API
  │   └─► Store new emails with status="unprocessed"
  │
  ├─► DETERMINISTIC CLASSIFICATION
  │   ├─► Check calendar invites → Category 8
  │   ├─► Check marketing emails → Category 6
  │   ├─► Check travel bookings → Category 11
  │   ├─► Check notifications → Category 7
  │   └─► Check FYI emails → Category 9
  │
  ├─► OVERRIDE CHECK (for "Other" categories 6-11)
  │   ├─► Urgency language detected? → Reset to unprocessed
  │   ├─► VIP sender? → Reset to unprocessed
  │   ├─► Sole recipient mismatch? → Reset to unprocessed
  │   ├─► Reply chain participation? → Reset to unprocessed
  │   └─► Direct address? → Reset to unprocessed
  │
  ├─► AI CLASSIFICATION (for remaining unprocessed)
  │   ├─► Claude 3.5 Sonnet analyzes email
  │   └─► Classifies into Work categories (1-5)
  │
  └─► GENERATE REPORT
      ├─► Fetch stats
      ├─► Deterministic stats
      ├─► Override stats
      ├─► AI stats
      └─► Overall summary
END
```

---

## Notes

- All three endpoints are registered in `app/routes/emails.py`
- The pipeline service is in `app/services/pipeline.py`
- Manual reclassifications are logged with `classifier_type="manual"` and `confidence=1.0`
- The summary endpoint dynamically generates category keys based on database category labels
- Pipeline execution time is tracked and reported in seconds
