# Pipeline Update Summary

## Changes Made

The `POST /api/pipeline/run` endpoint has been updated to execute a **complete 7-phase workflow** that processes emails from inbox to Microsoft To-Do tasks.

## File Changes

### 1. `app/services/pipeline.py` (Updated)

**Added imports:**
- `json` - For serializing scoring signals
- `score_email` - From scoring service
- `assign_due_dates`, `get_assignment_summary` - From assignment service
- `sync_all_tasks`, `TokenExpiredError` - From todo_sync service
- `UrgencyScore` - Model for urgency score records

**Updated `run_full_pipeline()` function:**

**Previous workflow (4 phases):**
1. Fetch emails
2. Deterministic classification
3. Override check
4. AI classification

**New workflow (7 phases):**
1. Fetch emails from Outlook
2. Deterministic classification
3. Override check
4. AI classification
5. **Urgency scoring** (NEW)
6. **Batch assignment** (NEW)
7. **Microsoft To-Do sync** (NEW)

**Report structure changed:**
```python
# Old structure
{
  "fetch": {...},
  "deterministic": {...},
  "override": {...},
  "ai": {...},
  "summary": {...}
}

# New structure
{
  "phase_1_fetch": {"total": 0, "new": 0, "time_seconds": 0},
  "phase_2_deterministic": {"classified": 0, "breakdown": {}, "time_seconds": 0},
  "phase_3_override": {"checked": 0, "overridden": 0, "time_seconds": 0},
  "phase_4_ai": {"classified": 0, "breakdown": {}, "time_seconds": 0},
  "phase_5_scoring": {"scored": 0, "floor_items": 0, "stale_items": 0, "time_seconds": 0},
  "phase_6_assignment": {"assigned": 0, "slots": {}, "time_seconds": 0},
  "phase_7_todo_sync": {"synced": 0, "lists_created": [], "time_seconds": 0},
  "summary": {...}
}
```

**Timing added:**
- Each phase now tracks execution time in `time_seconds`
- Total pipeline time tracked in `summary.total_pipeline_time_seconds`

### 2. Documentation Created

**PIPELINE_FULL_WORKFLOW.md** (NEW)
- Comprehensive documentation of all 7 phases
- Detailed explanation of each phase
- Response format with examples
- Performance notes
- Error handling details
- Database changes overview

**PIPELINE_QUICK_START.md** (NEW)
- Quick start guide for testing
- Step-by-step instructions
- Common troubleshooting tips
- API reference

**test_full_pipeline.sh** (NEW)
- Automated test script
- Runs full pipeline and displays formatted results
- Extracts key metrics for easy verification

**PIPELINE_UPDATE_SUMMARY.md** (THIS FILE)
- Summary of all changes
- Migration guide
- Breaking changes notice

## New Phase Details

### Phase 5: Urgency Scoring
- Scores all Work emails (categories 1-5)
- Uses 8-signal scoring engine:
  - Explicit deadline detection
  - Sender seniority
  - Importance flag
  - Urgency language
  - Thread velocity
  - Client/external flag
  - Age of email
  - Follow-up overdue
- Applies stale escalation and urgency floor
- Updates `emails.urgency_score` field
- Creates/updates `urgency_scores` table records

### Phase 6: Batch Assignment
- Distributes scored emails across due dates
- Assignment buckets:
  - **Today**: Floor pool + top priority (task_limit)
  - **Tomorrow**: Next task_limit items
  - **This Week (Friday)**: Next task_limit × 2 items
  - **Next Week (Monday)**: Remaining items above threshold
  - **No Date**: Items below threshold
- Updates `emails.due_date` field
- Default settings:
  - `task_limit`: 20
  - `urgency_floor`: 90
  - `time_pressure_threshold`: 15

### Phase 7: Microsoft To-Do Sync
- Syncs assigned Work emails to Microsoft To-Do
- Creates category-based task lists
- Creates tasks with:
  - Category prefix and priority marker
  - Due dates from assignment
  - Email preview and metadata
- Only syncs new emails (checks `todo_task_id`)
- Updates `emails.todo_task_id` field
- Handles token expiration gracefully

## Breaking Changes

### Response Format
The pipeline response format has changed. If you have code that parses the response, update it:

**Old:**
```python
response["fetch"]["new"]
response["deterministic"]["classified"]
response["ai"]["classified"]
```

**New:**
```python
response["phase_1_fetch"]["new"]
response["phase_2_deterministic"]["classified"]
response["phase_4_ai"]["classified"]
response["phase_5_scoring"]["scored"]
response["phase_6_assignment"]["assigned"]
response["phase_7_todo_sync"]["synced"]
```

### Timing Information
All phases now include `time_seconds`:
```python
response["phase_1_fetch"]["time_seconds"]  # Individual phase timing
response["summary"]["total_pipeline_time_seconds"]  # Total pipeline time
```

## Backward Compatibility

The endpoint URL and query parameters remain the same:
```
POST /api/pipeline/run?fetch_count=50
```

Existing endpoints are unaffected:
- `POST /api/emails/fetch`
- `POST /api/emails/classify-deterministic`
- `POST /api/emails/classify-ai`
- `POST /api/emails/score`
- `POST /api/emails/assign`
- `POST /api/emails/sync-todo`

These individual endpoints still work independently if you need granular control.

## Migration Guide

### If you were using the old pipeline response:

1. Update response parsing to use new phase names
2. Add handling for new phases 5, 6, 7
3. Update timing extraction to use `time_seconds` fields

### Example migration:

**Before:**
```python
result = requests.post("http://localhost:8000/api/emails/pipeline/run")
data = result.json()

print(f"Fetched: {data['fetch']['new']}")
print(f"Classified: {data['deterministic']['classified'] + data['ai']['classified']}")
print(f"Time: {data['summary']['processing_time_seconds']}")
```

**After:**
```python
result = requests.post("http://localhost:8000/api/emails/pipeline/run")
data = result.json()

print(f"Fetched: {data['phase_1_fetch']['new']}")
print(f"Classified: {data['phase_2_deterministic']['classified'] + data['phase_4_ai']['classified']}")
print(f"Scored: {data['phase_5_scoring']['scored']}")
print(f"Assigned: {data['phase_6_assignment']['assigned']}")
print(f"Synced: {data['phase_7_todo_sync']['synced']}")
print(f"Time: {data['summary']['total_pipeline_time_seconds']}")
```

## Testing

To test the updated pipeline:

1. **Start backend:**
   ```bash
   source venv/bin/activate
   uvicorn app.main:app --reload --port 8000
   ```

2. **Authenticate:**
   - Visit http://localhost:8000/api/auth/login

3. **Run test script:**
   ```bash
   ./test_full_pipeline.sh
   ```

4. **Verify Microsoft To-Do:**
   - Open Microsoft To-Do app/web
   - Check for new task lists (1. Blocking, 2. Action Required, etc.)
   - Verify tasks have due dates and correct content

## Performance Expectations

Based on 50 emails:
- **Phase 1 (Fetch)**: ~2-5s
- **Phase 2 (Deterministic)**: <1s
- **Phase 3 (Override)**: Included in Phase 2
- **Phase 4 (AI)**: ~30-60s (depends on how many emails need AI)
- **Phase 5 (Scoring)**: <1s
- **Phase 6 (Assignment)**: <0.5s
- **Phase 7 (To-Do Sync)**: ~2-5s
- **Total**: ~40-70s

The bottleneck is Phase 4 (AI classification) due to rate limiting.

## Next Steps

1. Test the pipeline with `./test_full_pipeline.sh`
2. Check Microsoft To-Do to verify tasks were created
3. Review timing metrics to identify bottlenecks
4. Adjust configuration if needed:
   - Task limits in phase 6
   - VIP senders for phase 3
   - Scoring weights in phase 5

## Support

- **Full documentation**: `PIPELINE_FULL_WORKFLOW.md`
- **Quick start**: `PIPELINE_QUICK_START.md`
- **Test script**: `./test_full_pipeline.sh`
