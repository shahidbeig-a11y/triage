# Scoring and To-Do Sync Updates

## Changes Made

### 1. Age Scoring Adjustment

**Problem**: Emails were rising to the top based on age alone, which shouldn't be the primary factor.

**Solution**: Capped the age signal at 40 points maximum (previously 80).

**Updated Scoring Tiers** (`app/services/scoring.py`):

| Time Range | Old Score | New Score |
|------------|-----------|-----------|
| 0-2 hours  | 0         | 0         |
| 2-12 hours | 15        | 10        |
| 12-24 hours| 30        | 20        |
| 1-2 days   | 50        | 30        |
| 2-3 days   | 65        | 40        |
| 3+ days    | 80        | **40 (capped)** |

**Impact**:
- Age signal weight remains 0.10 (10%)
- Maximum contribution from age: 40 × 0.10 = **4 points** (down from 8)
- Older emails will still gain urgency over time, but won't dominate the ranking
- Combined with stale escalation, very old emails (11+ days) still force to Today

### 2. To-Do Sync Method Change

**Old Method**: Directly created tasks via Graph API
- Created task in specific category list
- Set title, body, due date immediately

**New Method**: Flag email → Wait → Update task
1. **Flag the email** using PATCH to `/me/messages/{id}`
2. **Wait 10 seconds** for Microsoft to auto-create the task
3. **Find the task** in the default "Tasks" list
4. **Update the task** with proper title and due date

**Why?**:
- Uses native Outlook → To-Do integration
- Task automatically linked to email in Outlook
- Better integration with existing workflows

**Updated Code** (`app/services/todo_sync.py`):
- `create_todo_task()` now flags emails instead of direct task creation
- Searches for auto-created task by matching original subject
- Updates task with category prefix and due date

**Trade-offs**:
- ✅ Better email-task integration
- ✅ Native Outlook workflow
- ⚠️ Slower: 10 second delay per email
- ⚠️ Tasks appear in default "Tasks" list, not category lists

## Testing

### Re-score Existing Emails

Run the scoring endpoint to apply new age weights:

```bash
./rescore_emails.sh
```

Or manually:

```bash
curl -X POST http://localhost:8000/api/emails/score | python3 -m json.tool
```

### View Updated Scores

```bash
# See all scored emails in priority order
curl http://localhost:8000/api/emails/scored | python3 -m json.tool

# See today's action list
curl http://localhost:8000/api/emails/today | python3 -m json.tool
```

### Test New To-Do Sync

```bash
# Reset existing sync (optional)
curl -X DELETE "http://localhost:8000/api/emails/sync-todo/reset?delete_tasks=true"

# Run full pipeline (includes sync)
curl -X POST "http://localhost:8000/api/emails/pipeline/run?fetch_count=50" | python3 -m json.tool
```

**Important**: The new sync method takes ~10 seconds per email due to the wait period. For 20 emails, expect ~3-4 minutes for Phase 7.

## Verification

### 1. Check Age Scoring

Look at the urgency breakdown for old emails:

```bash
curl http://localhost:8000/api/emails/scored | python3 -c "
import sys, json
data = json.load(sys.stdin)
for email in data['emails'][:10]:  # Top 10
    print(f\"{email['email_id']}: {email['urgency_score']} (raw: {email['raw_score']}, stale: +{email['stale_bonus']})\")
    print(f\"  Subject: {email['subject'][:60]}...\")
    print()
"
```

Verify that old emails without other urgency signals don't have scores above ~50-60.

### 2. Check To-Do Tasks

After running the pipeline:
1. Open Microsoft To-Do app or web
2. Check the "Tasks" list (default list)
3. Verify tasks have:
   - Category prefixes: [BLOCKING], [ACTION], etc.
   - Priority markers: ⚠️ for floor items
   - Due dates assigned correctly

In Outlook:
1. Check that flagged emails appear in To-Do
2. Verify email-task linking works

## Performance Impact

### Scoring
- No significant performance change
- Age calculation is still O(1) per email

### To-Do Sync (Phase 7)
- **Old**: ~2-5 seconds for 20 emails (batch creation)
- **New**: ~200-250 seconds for 20 emails (10s wait × 20 emails)
- **Impact**: Pipeline will take ~3-4 minutes longer for Phase 7

To reduce sync time, consider:
- Syncing in smaller batches
- Running sync as a background job
- Only syncing Today items first

## Rollback Instructions

If you need to revert these changes:

### Revert Age Scoring
Edit `app/services/scoring.py` and change the age tiers back:
```python
# Score based on age
if hours_old < 2:
    return 0
elif hours_old < 12:
    return 15  # was 10
elif hours_old < 24:
    return 30  # was 20
elif days_old < 2:
    return 50  # was 30
elif days_old < 3:
    return 65  # was 40
else:  # 3+ days
    return 80  # was 40
```

### Revert To-Do Sync
Restore `app/services/todo_sync.py` from git:
```bash
git checkout app/services/todo_sync.py
git checkout app/services/pipeline.py
git checkout app/routes/emails.py
```

## Files Modified

1. **`app/services/scoring.py`**
   - Updated `extract_age_of_email()` to cap at 40 points

2. **`app/services/todo_sync.py`**
   - Completely rewrote `create_todo_task()` to use email flagging method

3. **`app/services/pipeline.py`**
   - Added `message_id` to Phase 7 email dict

4. **`app/routes/emails.py`**
   - Added `message_id` to sync endpoint email dict

5. **`rescore_emails.sh`** (NEW)
   - Script to re-run scoring on existing emails

## Next Steps

1. Run `./rescore_emails.sh` to apply new age weights
2. Verify age scores are capped appropriately
3. Test the new To-Do sync method with a few emails
4. Monitor sync performance and adjust if needed
5. Consider implementing background sync for better UX
