# Pipeline Quick Start Guide

## Quick Test

1. **Start the backend server:**
   ```bash
   source venv/bin/activate
   uvicorn app.main:app --reload --port 8000
   ```

2. **Authenticate:**
   - Open http://localhost:8000/api/auth/login in your browser
   - Sign in with Microsoft

3. **Run the full pipeline:**
   ```bash
   ./test_full_pipeline.sh
   ```

   Or manually:
   ```bash
   curl -X POST "http://localhost:8000/api/emails/pipeline/run?fetch_count=50"
   ```

## What Happens

The pipeline executes **7 phases in sequence**:

1. **Fetch** → Fetches 50 emails from Outlook
2. **Classify (Deterministic)** → Classifies using rules
3. **Override Check** → Checks for VIP/urgent overrides
4. **Classify (AI)** → Classifies remaining with Claude
5. **Score** → Calculates urgency scores (0-100)
6. **Assign** → Distributes to Today/Tomorrow/This Week/Next Week
7. **Sync** → Creates tasks in Microsoft To-Do

## View Results

After running the pipeline, check:

### In Microsoft To-Do
- Open Microsoft To-Do app or web
- Look for lists: "1. Blocking", "2. Action Required", etc.
- Tasks are organized by category with due dates

### Today's Action List
```bash
curl http://localhost:8000/api/emails/today
```

### All Scored Emails (Priority Order)
```bash
curl http://localhost:8000/api/emails/scored
```

### Summary Statistics
```bash
curl http://localhost:8000/api/emails/summary
```

## Expected Output

```json
{
  "phase_1_fetch": {
    "total": 50,
    "new": 15,
    "time_seconds": 2.45
  },
  "phase_2_deterministic": {
    "classified": 35,
    "time_seconds": 0.23
  },
  "phase_3_override": {
    "overridden": 2,
    "time_seconds": 0
  },
  "phase_4_ai": {
    "classified": 17,
    "time_seconds": 34.5
  },
  "phase_5_scoring": {
    "scored": 17,
    "floor_items": 3,
    "time_seconds": 0.45
  },
  "phase_6_assignment": {
    "assigned": 17,
    "slots": {
      "today": 8,
      "tomorrow": 5,
      "this_week": 4
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

## Performance

- **Total time**: ~40-70 seconds for 50 emails
- **Bottleneck**: AI classification (~2s per email with rate limiting)
- **Fastest phases**: Scoring and assignment (<1s each)

## Troubleshooting

### "No authenticated user found"
→ Run authentication first: http://localhost:8000/api/auth/login

### "Token expired"
→ Re-authenticate: http://localhost:8000/api/auth/login

### "No emails to sync"
→ All emails already synced. To test again:
```bash
curl -X DELETE "http://localhost:8000/api/emails/sync-todo/reset?delete_tasks=true"
```

### Pipeline runs but no To-Do tasks
→ Make sure Work emails have due dates assigned (check phase_6_assignment in response)

## Reset for Testing

To re-run the full pipeline on the same emails:

```bash
# Clear To-Do tasks and reset sync
curl -X DELETE "http://localhost:8000/api/emails/sync-todo/reset?delete_tasks=true"

# Re-run pipeline
curl -X POST "http://localhost:8000/api/emails/pipeline/run?fetch_count=50"
```

## Next Steps

- **Customize scoring weights**: Edit `app/services/scoring.py` → `SIGNAL_WEIGHTS`
- **Adjust task limits**: Edit `app/services/pipeline.py` → `settings` in phase 6
- **Add VIPs**: Edit `app/services/classifier_override.py` → `VIP_SENDERS`
- **Monitor logs**: Check console output while pipeline runs

## API Reference

Full documentation: `PIPELINE_FULL_WORKFLOW.md`
