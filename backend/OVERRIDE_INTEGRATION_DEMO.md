# Override Integration Demo

This document demonstrates how the deterministic classifier and override checker work together in the `POST /api/emails/classify-deterministic` endpoint.

## Flow

```
1. Fetch unprocessed emails from database
2. For each email:
   a. Run deterministic classification
   b. If classified (category 6-11):
      i.  Check for override triggers
      ii. If override triggered:
          → Reset to unprocessed for AI
          → Log override event
      iii. If no override:
          → Keep classification
          → Log classification event
   c. If not classified:
      → Leave as unprocessed for AI
3. Return summary with counts
```

## Example Scenarios

### Scenario 1: Marketing Email - No Override

**Email:**
```
From: newsletter@example.com
Subject: 50% off sale - Limited time only!
Body: Shop now and save on our latest collection...
```

**Processing:**
1. Deterministic classifier: Category 6 (Marketing) ✓
   - Rule: "Marketing sender pattern: ^newsletter@"
   - Confidence: 0.85

2. Override check: No triggers ✗
   - No urgency language
   - Not a VIP sender
   - Regular marketing content

**Result:**
- Status: `classified`
- Category: 6 (Marketing)
- Log: ClassificationLog entry created

---

### Scenario 2: Marketing with Urgency - Override Triggered

**Email:**
```
From: marketing@service.com
Subject: URGENT: Action required on your account
Body: Your immediate attention is needed to update your payment method.
```

**Processing:**
1. Deterministic classifier: Category 6 (Marketing) ✓
   - Rule: "Marketing sender pattern: ^marketing@"
   - Confidence: 0.85

2. Override check: URGENCY LANGUAGE ✓
   - Detected: "urgent", "action required", "immediate attention"
   - Trigger: urgency_language
   - Reason: "Contains urgency language: 'urgent'"

**Result:**
- Status: `unprocessed` (reset for AI)
- Category: NULL
- Log: OverrideLog entry created
  - original_category: 6
  - trigger_type: "urgency_language"
  - reason: "Contains urgency language: 'urgent'"

---

### Scenario 3: Calendar Invite - No Override

**Email:**
```
From: calendar-notification@google.com
Subject: Invitation: Team Meeting
Body: You have been invited to a team meeting on Jan 15...
```

**Processing:**
1. Deterministic classifier: Category 8 (Calendar) ✓
   - Rule: "Calendar subject pattern: ^invitation:"
   - Confidence: 0.90

2. Override check: No triggers ✗
   - No urgency language
   - Regular calendar invite

**Result:**
- Status: `classified`
- Category: 8 (Calendar)
- Log: ClassificationLog entry created

---

### Scenario 4: FYI Email (Sole Recipient) - Override Triggered

**Email:**
```
From: colleague@company.com
To: user@company.com (ONLY recipient)
Subject: Project update
Body: Here's the latest status on the project...
```

**Processing:**
1. Deterministic classifier: Category 9 (FYI) ✓
   - Rule: "Group email with 1 recipients"
   - Wait... actually this wouldn't classify as FYI because it requires 3+ recipients

Let me revise:

**Email:**
```
From: manager@company.com
To: alice@company.com, bob@company.com, carol@company.com
CC: user@company.com
Subject: Team update
Body: Everyone, here's the quarterly update...
```

**Processing:**
1. Deterministic classifier: Category 9 (FYI) ✓
   - Rule: "User in CC field only"
   - Confidence: 0.88

2. Override check: No triggers ✗
   - Multiple To: recipients (correctly FYI)
   - No urgency language
   - Not personally addressed

**Result:**
- Status: `classified`
- Category: 9 (FYI)
- Log: ClassificationLog entry created

---

### Scenario 5: Notification with Direct Address - Override Triggered

**Email:**
```
From: notifications@github.com
Subject: New issue assigned to you
Body: User, can you review this issue? It's blocking the release.
```

**Processing:**
1. Deterministic classifier: Category 7 (Notification) ✓
   - Rule: "Notification sender pattern: ^notifications@"
   - Confidence: 0.85

2. Override check: DIRECT ADDRESS + URGENCY ✓
   - Detected: "User, can you" (direct address pattern)
   - Also detected: "blocking" (urgency keyword)
   - Trigger: urgency_language (checked first)
   - Reason: "Contains urgency language: 'blocking'"

**Result:**
- Status: `unprocessed` (reset for AI)
- Category: NULL
- Log: OverrideLog entry created
  - original_category: 7
  - trigger_type: "urgency_language"
  - reason: "Contains urgency language: 'blocking'"

---

### Scenario 6: Work Email - No Classification

**Email:**
```
From: colleague@company.com
Subject: Can you review this PR?
Body: Hey, I need your input on this pull request...
```

**Processing:**
1. Deterministic classifier: No match ✗
   - Not marketing (not a marketing pattern)
   - Not notification (not a notification sender)
   - Not calendar (no calendar indicators)
   - Not FYI (sole recipient)
   - Not travel (not a travel domain)

2. Override check: Skipped (no classification)

**Result:**
- Status: `unprocessed` (needs AI)
- Category: NULL
- Log: No entries

---

## API Response Example

```json
{
  "total_processed": 6,
  "classified": 3,
  "overridden": 2,
  "remaining": 1,
  "breakdown": {
    "6_marketing": 1,
    "7_notification": 0,
    "8_calendar": 1,
    "9_fyi": 1,
    "11_travel": 0
  },
  "message": "Classified 3 out of 6 emails. 2 overridden to Work. 1 emails need AI classification."
}
```

### Breakdown:
- **Email 1** (Newsletter): Classified as Marketing ✓
- **Email 2** (Urgent marketing): Classified as Marketing → Overridden ⚠️
- **Email 3** (Calendar): Classified as Calendar ✓
- **Email 4** (FYI): Classified as FYI ✓
- **Email 5** (GitHub with urgency): Classified as Notification → Overridden ⚠️
- **Email 6** (Work email): No classification → AI needed ✗

**Final counts:**
- Classified and kept: 3 (Marketing, Calendar, FYI)
- Overridden: 2 (Urgent marketing, GitHub notification)
- Remaining for AI: 1 (Work email) + 2 (overridden) = 3 total unprocessed

## Database State After Processing

### emails table

| id | from_address | subject | category_id | status | confidence |
|----|--------------|---------|-------------|--------|-----------|
| 1 | newsletter@... | 50% off sale | 6 | classified | 0.85 |
| 2 | marketing@... | URGENT: Action... | NULL | unprocessed | NULL |
| 3 | calendar@... | Invitation... | 8 | classified | 0.90 |
| 4 | manager@... | Team update | 9 | classified | 0.88 |
| 5 | notifications@... | New issue... | NULL | unprocessed | NULL |
| 6 | colleague@... | Review PR | NULL | unprocessed | NULL |

### classification_log table

| id | email_id | category_id | rule | classifier_type | confidence |
|----|----------|-------------|------|----------------|-----------|
| 1 | 1 | 6 | Marketing sender pattern: ^newsletter@ | deterministic | 0.85 |
| 2 | 3 | 8 | Calendar subject pattern: ^invitation: | deterministic | 0.90 |
| 3 | 4 | 9 | User in CC field only | deterministic | 0.88 |

### override_log table

| id | email_id | original_category | trigger_type | reason |
|----|----------|------------------|--------------|--------|
| 1 | 2 | 6 | urgency_language | Contains urgency language: 'urgent' |
| 2 | 5 | 7 | urgency_language | Contains urgency language: 'blocking' |

## Next Steps

After this endpoint runs:
1. Emails with `status='classified'` are done (categories 6-11)
2. Emails with `status='unprocessed'` need AI classification
   - Original work emails (never classified)
   - Overridden emails (classified but flagged as potentially important)
3. AI classifier will process all unprocessed emails on Wednesday
4. AI classifier can see override_log entries to understand why an email was flagged
