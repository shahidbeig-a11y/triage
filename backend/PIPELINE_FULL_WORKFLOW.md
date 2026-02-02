# Full Pipeline Workflow - 7-Phase Email Processing

## Overview

The `/api/pipeline/run` endpoint now executes a complete 7-phase workflow that takes emails from inbox to Microsoft To-Do tasks with full classification, scoring, and assignment.

## Full Workflow

### Phase 1: Fetch Emails from Outlook
- Connects to Microsoft Graph API
- Fetches specified number of emails (default 50)
- Stores new emails in database
- **Timing tracked**: Graph API fetch + storage

### Phase 2: Deterministic Classification
- Runs rule-based classifier on unprocessed emails
- Classifies into categories 1-11 based on:
  - Email headers (unsubscribe, list-id)
  - Sender patterns (no-reply, notifications)
  - Subject keywords
- **Timing tracked**: Classification loop

### Phase 3: Override Check
- Checks deterministic classifications for special cases:
  - VIP senders (override to Work pipeline)
  - Personal direction keywords (override to Work pipeline)
  - High importance flags (override to Work pipeline)
- Resets overridden emails to `unprocessed` for AI classification
- **Timing tracked**: Included in Phase 2 (runs inline)

### Phase 4: AI Classification (Claude)
- Runs Claude 3.5 Sonnet on remaining unprocessed emails
- Classifies into Work categories (1-5):
  - 1: Blocking
  - 2: Action Required
  - 3: Waiting On
  - 4: Time-Sensitive
  - 5: FYI
- Rate limited to 0.5s between API calls
- **Timing tracked**: AI classification loop with rate limiting

### Phase 5: Urgency Scoring
- Scores all Work emails (categories 1-5) using 8-signal engine
- Signals include:
  - Explicit deadline detection
  - Sender seniority (VIP, external, internal)
  - Importance flag
  - Urgency language
  - Thread velocity
  - Client/external flag
  - Age of email
  - Follow-up overdue
- Applies stale escalation and urgency floor
- Stores detailed breakdown in `urgency_scores` table
- **Timing tracked**: Scoring loop + database updates

### Phase 6: Batch Assignment
- Distributes scored Work emails across due dates:
  - **Today**: Floor pool (urgency ≥90 or forced) + top priority items
  - **Tomorrow**: Next task_limit items
  - **This Week (Friday)**: Next task_limit × 2 items
  - **Next Week (Monday)**: Remaining items above threshold
  - **No Date**: Items below time_pressure_threshold (15)
- Uses configurable settings:
  - `task_limit`: 20 (max items per day)
  - `urgency_floor`: 90 (auto-today threshold)
  - `time_pressure_threshold`: 15 (min score to get a date)
- Updates `due_date` field on emails
- **Timing tracked**: Assignment algorithm + database updates

### Phase 7: Microsoft To-Do Sync
- Syncs assigned Work emails to Microsoft To-Do tasks
- Creates category-based task lists:
  - "1. Blocking"
  - "2. Action Required"
  - "3. Waiting On"
  - "4. Time-Sensitive"
  - "5. FYI"
- Creates tasks with:
  - Category prefix in title
  - Priority marker (⚠️) for floor items
  - Due date from assignment
  - Email preview in body
  - From/received metadata
- Only syncs emails with due dates that haven't been synced
- Updates `todo_task_id` field on emails
- **Timing tracked**: Graph API sync operations

## Response Format

```json
{
  "phase_1_fetch": {
    "total": 50,
    "new": 15,
    "time_seconds": 2.45
  },
  "phase_2_deterministic": {
    "classified": 35,
    "breakdown": {
      "6": 12,
      "7": 15,
      "8": 5,
      "9": 3
    },
    "time_seconds": 0.23
  },
  "phase_3_override": {
    "checked": 35,
    "overridden": 2,
    "time_seconds": 0
  },
  "phase_4_ai": {
    "classified": 17,
    "breakdown": {
      "1": 3,
      "2": 8,
      "3": 2,
      "4": 2,
      "5": 2
    },
    "time_seconds": 34.5
  },
  "phase_5_scoring": {
    "scored": 17,
    "floor_items": 3,
    "stale_items": 1,
    "time_seconds": 0.45
  },
  "phase_6_assignment": {
    "assigned": 17,
    "slots": {
      "today": 8,
      "tomorrow": 5,
      "this_week": 4,
      "next_week": 0,
      "no_date": 0
    },
    "time_seconds": 0.12
  },
  "phase_7_todo_sync": {
    "synced": 17,
    "lists_created": ["1. Blocking", "2. Action Required"],
    "time_seconds": 3.21
  },
  "summary": {
    "total_emails": 150,
    "work_items": 42,
    "other_items": 108,
    "total_pipeline_time_seconds": 40.96
  }
}
```

## Usage

### Run Full Pipeline
```bash
curl -X POST "http://localhost:8000/api/emails/pipeline/run?fetch_count=50"
```

### Run with More Emails
```bash
curl -X POST "http://localhost:8000/api/emails/pipeline/run?fetch_count=100"
```

## Performance Notes

- **Phase 1 (Fetch)**: ~2-5s for 50 emails (depends on Graph API latency)
- **Phase 2 (Deterministic)**: <1s for 100 emails (rule-based, very fast)
- **Phase 3 (Override)**: Negligible (runs inline with Phase 2)
- **Phase 4 (AI)**: ~30-60s for 15 emails (0.5s rate limit + API latency)
- **Phase 5 (Scoring)**: <1s for 50 emails (local computation)
- **Phase 6 (Assignment)**: <0.5s for 100 emails (pure algorithm)
- **Phase 7 (To-Do Sync)**: ~2-5s for 20 tasks (depends on Graph API latency)

**Total Pipeline Time**: ~40-70s for 50 emails (mostly AI classification)

## Error Handling

- Each phase is isolated - if one fails, subsequent phases still run
- Errors are reported in the response under the phase that failed
- Database commits happen after each phase to preserve progress
- Token expiration in Phase 7 is caught and reported

## Database Changes

The pipeline updates the following tables:
- `emails`: status, category_id, confidence, urgency_score, due_date, todo_task_id
- `classification_logs`: Records from deterministic and AI classifiers
- `override_logs`: Records when overrides trigger
- `urgency_scores`: Detailed scoring breakdown for each Work email

## Next Steps

After running the pipeline:
1. Check Microsoft To-Do - your tasks are organized by category
2. Use `/api/emails/today` to get today's prioritized action list
3. Use `/api/emails/scored` to see full urgency ranking
4. Check `/api/emails/summary` for overall statistics
