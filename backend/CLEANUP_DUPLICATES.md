# Cleaning Up Duplicate Tasks in Microsoft To-Do

## Problem

When testing the sync functionality, running the sync multiple times can create duplicate tasks in Microsoft To-Do because:

1. The database reset (`DELETE /api/emails/sync-todo/reset`) only clears our local `todo_task_id` tracking
2. It does NOT delete the actual tasks in Microsoft To-Do
3. Re-syncing after reset creates new tasks, resulting in duplicates

## Solution

We now have tools to clean up duplicates before re-syncing.

## Quick Cleanup

### Option 1: Use the Cleanup Script (Recommended)

```bash
./cleanup_todo_duplicates.sh
```

This script:
1. Deletes all task lists from Microsoft To-Do that match our category names
2. Prompts for confirmation before deleting
3. Shows detailed results

### Option 2: Use the API Endpoint

```bash
# Clean up duplicates in Microsoft To-Do
curl -X DELETE http://localhost:8000/api/emails/sync-todo/cleanup
```

### Option 3: Reset with Automatic Cleanup

```bash
# Reset database AND delete tasks in one call
curl -X DELETE "http://localhost:8000/api/emails/sync-todo/reset?delete_tasks=true"
```

## Complete Cleanup and Re-sync Workflow

### Method 1: Separate Steps (Recommended)

```bash
# Step 1: Clean up Microsoft To-Do
curl -X DELETE http://localhost:8000/api/emails/sync-todo/cleanup

# Step 2: Reset database tracking
curl -X DELETE http://localhost:8000/api/emails/sync-todo/reset

# Step 3: Re-sync
curl -X POST http://localhost:8000/api/emails/sync-todo
```

**Result**: Fresh sync with no duplicates

---

### Method 2: Combined Reset

```bash
# Step 1: Reset database AND delete tasks
curl -X DELETE "http://localhost:8000/api/emails/sync-todo/reset?delete_tasks=true"

# Step 2: Re-sync
curl -X POST http://localhost:8000/api/emails/sync-todo
```

**Result**: Fresh sync with no duplicates

---

### Method 3: Manual Cleanup

```bash
# Step 1: Manually delete task lists in Microsoft To-Do app
#         (Open To-Do app → Right-click list → Delete)

# Step 2: Reset database tracking
curl -X DELETE http://localhost:8000/api/emails/sync-todo/reset

# Step 3: Re-sync
curl -X POST http://localhost:8000/api/emails/sync-todo
```

**Result**: Fresh sync with no duplicates

## New Endpoints

### DELETE /api/emails/sync-todo/cleanup

Deletes all task lists from Microsoft To-Do that match our category names.

**What it does**:
- ✅ Deletes task lists in Microsoft To-Do
- ❌ Does NOT clear database tracking

**Response**:
```json
{
    "deleted": 1,
    "list_names": ["2. Action Required"],
    "errors": [],
    "message": "Deleted 1 task lists from Microsoft To-Do. You can now re-sync without duplicates."
}
```

**When to use**:
- After testing sync multiple times
- When you see duplicates in Microsoft To-Do
- Before re-syncing after changes

---

### DELETE /api/emails/sync-todo/reset (Enhanced)

Now supports optional task deletion.

**Parameters**:
- `delete_tasks=false` (default): Only resets database tracking
- `delete_tasks=true`: Also deletes tasks from Microsoft To-Do

**Examples**:

```bash
# Reset database only (old behavior)
curl -X DELETE http://localhost:8000/api/emails/sync-todo/reset

# Reset database AND delete tasks
curl -X DELETE "http://localhost:8000/api/emails/sync-todo/reset?delete_tasks=true"
```

**Response (with delete_tasks=true)**:
```json
{
    "reset": 37,
    "message": "Reset 37 emails and deleted 1 task lists from Microsoft To-Do.",
    "todo_deletion": {
        "deleted": 1,
        "list_names": ["2. Action Required"],
        "errors": []
    }
}
```

## Understanding the Sync State

### Check Current State

```python
from app.database import SessionLocal
from app.models import Email

db = SessionLocal()

# Emails in database with todo_task_id
synced_db = db.query(Email).filter(
    Email.todo_task_id.isnot(None)
).count()

# Emails ready to sync
ready_to_sync = db.query(Email).filter(
    Email.due_date.isnot(None),
    Email.category_id.in_([1, 2, 3, 4, 5]),
    Email.todo_task_id.is_(None)
).count()

print(f"Synced in DB: {synced_db}")
print(f"Ready to sync: {ready_to_sync}")

db.close()
```

### Check Microsoft To-Do State

```bash
# List all task lists
curl "https://graph.microsoft.com/v1.0/me/todo/lists" \
  -H "Authorization: Bearer <token>"
```

## Prevention

### Best Practices

1. **Use cleanup before re-syncing**:
   ```bash
   ./cleanup_todo_duplicates.sh
   ```

2. **Don't reset without cleanup**:
   - ❌ Bad: Reset → Sync → Reset → Sync (creates duplicates)
   - ✅ Good: Reset → Sync → Cleanup → Reset → Sync

3. **Use delete_tasks parameter**:
   ```bash
   curl -X DELETE "http://localhost:8000/api/emails/sync-todo/reset?delete_tasks=true"
   ```

4. **Check before syncing**:
   ```bash
   # Check how many ready to sync
   curl -s http://localhost:8000/api/emails/sync-todo | grep -o '"synced":[0-9]*'
   ```

## Troubleshooting

### Issue: Sync creates duplicates

**Cause**: Database was reset but tasks weren't deleted from To-Do

**Solution**:
```bash
# Clean up duplicates
curl -X DELETE http://localhost:8000/api/emails/sync-todo/cleanup

# Reset database
curl -X DELETE http://localhost:8000/api/emails/sync-todo/reset

# Re-sync
curl -X POST http://localhost:8000/api/emails/sync-todo
```

---

### Issue: Can't delete tasks (401 error)

**Cause**: Access token expired

**Solution**:
1. Re-authenticate in the app
2. Try cleanup again

---

### Issue: Lists deleted but tasks remain

**Cause**: Microsoft To-Do automatically deletes tasks when list is deleted

**Solution**: This is normal behavior. Deleting the list deletes all its tasks.

---

### Issue: Not all lists deleted

**Cause**: Only deletes lists matching our category names

**Solution**: This is intentional. We only delete:
- "1. Blocking"
- "2. Action Required"
- "3. Waiting On"
- "4. Time-Sensitive"
- "5. FYI"

Other lists are left untouched.

## Testing Workflow

When testing the sync functionality:

```bash
# 1. Initial sync
curl -X POST http://localhost:8000/api/emails/sync-todo

# 2. Make changes to assignment logic
# ... modify code ...

# 3. Clean up before re-testing
curl -X DELETE "http://localhost:8000/api/emails/sync-todo/reset?delete_tasks=true"

# 4. Test new logic
curl -X POST http://localhost:8000/api/emails/assign
curl -X POST http://localhost:8000/api/emails/sync-todo

# Repeat steps 2-4 as needed
```

## Production Workflow

In production, you typically sync once per day:

```bash
# Daily automation
curl -X POST http://localhost:8000/api/emails/pipeline/run
curl -X POST http://localhost:8000/api/emails/score
curl -X POST http://localhost:8000/api/emails/assign
curl -X POST http://localhost:8000/api/emails/sync-todo

# No cleanup needed - each email syncs once
```

## Summary

**To clean up duplicates**:
1. Run `./cleanup_todo_duplicates.sh`
2. Or use `DELETE /api/emails/sync-todo/cleanup`
3. Then reset and re-sync

**To prevent duplicates**:
1. Use `delete_tasks=true` when resetting
2. Or run cleanup before re-syncing
3. Don't sync multiple times without cleanup

**Current state**:
```
✅ Duplicates cleaned up
✅ Database reset
✅ Fresh sync completed
✅ 37 tasks in "2. Action Required"
```
