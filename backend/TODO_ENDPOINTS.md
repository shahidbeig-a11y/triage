# Microsoft To-Do Sync Endpoints

## Overview

Two new endpoints for syncing assigned emails to Microsoft To-Do and managing sync state.

## Endpoints

### POST /api/emails/sync-todo

Syncs all assigned Work emails to Microsoft To-Do tasks.

**URL**: `/api/emails/sync-todo`
**Method**: `POST`
**Auth**: Uses stored OAuth token

#### Process Flow

1. Gets authenticated user from database
2. Retrieves access token using stored OAuth credentials
3. Queries all Work emails (categories 1-5) with:
   - `due_date IS NOT NULL`
   - `todo_task_id IS NULL` (not yet synced)
4. Converts emails to sync format
5. Calls `sync_all_tasks()` to create To-Do tasks
6. Updates database with `todo_task_id` values
7. Commits changes
8. Returns sync summary

#### Response Format

```json
{
    "synced": 37,
    "lists_created": ["2. Action Required"],
    "skipped": 0,
    "errors": [],
    "message": "Synced 37 emails to Microsoft To-Do. Created 1 lists."
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| synced | int | Number of tasks created in Microsoft To-Do |
| lists_created | array | Names of new task lists created |
| skipped | int | Emails skipped (already synced or no due date) |
| errors | array | Error messages (if any) |
| message | string | Summary message |

#### Success Scenarios

**First Sync**:
```json
{
    "synced": 37,
    "lists_created": [
        "1. Blocking",
        "2. Action Required",
        "3. Waiting On",
        "4. Time-Sensitive",
        "5. FYI"
    ],
    "skipped": 0,
    "errors": []
}
```

**Subsequent Sync**:
```json
{
    "synced": 0,
    "lists_created": [],
    "skipped": 0,
    "errors": [],
    "message": "No emails found to sync (all emails either already synced or have no due date)"
}
```

**Partial Success**:
```json
{
    "synced": 35,
    "lists_created": [],
    "skipped": 0,
    "errors": [
        "Failed to create task for email 42: Rate limit exceeded",
        "Failed to create task for email 43: Rate limit exceeded"
    ]
}
```

#### Error Responses

**401 Unauthorized** - Token expired:
```json
{
    "detail": "Access token expired. Please re-authenticate."
}
```

**500 Internal Server Error** - Sync failed:
```json
{
    "detail": "To-Do sync failed: Request timeout"
}
```

#### Example Usage

```bash
# Sync emails to To-Do
curl -X POST http://localhost:8000/api/emails/sync-todo | python3 -m json.tool
```

```python
import requests

response = requests.post("http://localhost:8000/api/emails/sync-todo")
result = response.json()

print(f"✓ Synced {result['synced']} emails")
print(f"  Lists created: {result['lists_created']}")
if result['errors']:
    print(f"  Errors: {len(result['errors'])}")
```

---

### DELETE /api/emails/sync-todo/reset

Resets To-Do sync tracking for testing purposes.

**URL**: `/api/emails/sync-todo/reset`
**Method**: `DELETE`
**Auth**: None (for now)

#### What It Does

- Clears all `todo_task_id` values in the database
- Allows emails to be re-synced to Microsoft To-Do
- **DOES NOT** delete actual tasks in Microsoft To-Do
- **DOES NOT** delete task lists

#### Use Cases

1. **Testing**: Reset and re-run sync to test functionality
2. **Error Recovery**: Clear tracking after sync errors
3. **Re-sync**: Force all emails to sync again
4. **Development**: Reset state during development

#### Response Format

```json
{
    "reset": 37,
    "message": "Reset 37 emails. They can now be re-synced to Microsoft To-Do.",
    "note": "This does not delete tasks in Microsoft To-Do. To avoid duplicates, manually delete the tasks in To-Do first."
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| reset | int | Number of emails reset (todo_task_id cleared) |
| message | string | Summary message |
| note | string | Warning about manual task deletion |

#### Important Notes

⚠️ **Duplicate Prevention**: After reset, re-syncing will create duplicate tasks in Microsoft To-Do unless you manually delete the existing tasks first.

**Recommended Workflow**:
1. Manually delete task lists in Microsoft To-Do app
2. Call `DELETE /api/emails/sync-todo/reset`
3. Call `POST /api/emails/sync-todo` to re-sync

#### Example Usage

```bash
# Reset sync tracking
curl -X DELETE http://localhost:8000/api/emails/sync-todo/reset | python3 -m json.tool
```

```python
import requests

# Reset tracking
response = requests.delete("http://localhost:8000/api/emails/sync-todo/reset")
result = response.json()

print(f"✓ Reset {result['reset']} emails")
print(f"  Note: {result['note']}")

# Verify reset
response = requests.post("http://localhost:8000/api/emails/sync-todo")
sync_result = response.json()
print(f"✓ Re-synced {sync_result['synced']} emails")
```

---

## Complete Workflow

### Daily Automation

```bash
# 1. Fetch and classify emails
curl -X POST "http://localhost:8000/api/emails/pipeline/run?fetch_count=50"

# 2. Score Work emails
curl -X POST "http://localhost:8000/api/emails/score"

# 3. Assign due dates
curl -X POST "http://localhost:8000/api/emails/assign"

# 4. Sync to Microsoft To-Do
curl -X POST "http://localhost:8000/api/emails/sync-todo"

# 5. Get today's action list
curl "http://localhost:8000/api/emails/today"
```

### Python Automation

```python
#!/usr/bin/env python3
"""
Complete email triage workflow with To-Do sync.
"""

import requests

BASE_URL = "http://localhost:8000"

def main():
    # Step 1: Classification Pipeline
    print("Running classification pipeline...")
    response = requests.post(f"{BASE_URL}/api/emails/pipeline/run?fetch_count=50")
    pipeline = response.json()
    print(f"  ✓ Classified: {pipeline.get('classified', 0)}")

    # Step 2: Scoring
    print("Scoring Work emails...")
    response = requests.post(f"{BASE_URL}/api/emails/score")
    scoring = response.json()
    print(f"  ✓ Scored: {scoring['total_scored']}")

    # Step 3: Assignment
    print("Assigning due dates...")
    response = requests.post(f"{BASE_URL}/api/emails/assign")
    assignment = response.json()
    print(f"  ✓ Assigned: {assignment['total_assigned']}")

    # Step 4: Sync to To-Do
    print("Syncing to Microsoft To-Do...")
    response = requests.post(f"{BASE_URL}/api/emails/sync-todo")
    sync = response.json()
    print(f"  ✓ Synced: {sync['synced']} emails")
    if sync['lists_created']:
        print(f"    Lists created: {sync['lists_created']}")
    if sync['errors']:
        print(f"    Errors: {len(sync['errors'])}")

    # Step 5: Today's action list
    print("\nFetching today's action list...")
    response = requests.get(f"{BASE_URL}/api/emails/today")
    today = response.json()

    print(f"\n{'='*70}")
    print(f"TODAY'S ACTION LIST - {today['date']}")
    print(f"{'='*70}")
    print(f"\nTotal: {today['total']} emails\n")

    for i, email in enumerate(today['emails'][:10], 1):
        priority = "🔴" if email['floor_override'] else "  "
        print(f"{i:2d}. {priority} [{email['urgency_score']:5.1f}] {email['subject'][:50]}")

    if today['total'] > 10:
        print(f"\n... and {today['total'] - 10} more emails")

if __name__ == "__main__":
    main()
```

---

## Database State

### Schema Changes

```python
class Email(Base):
    # ... existing fields ...
    todo_task_id = Column(String, nullable=True)  # Microsoft To-Do task ID
```

### Query Examples

**Emails Ready to Sync**:
```sql
SELECT COUNT(*)
FROM emails
WHERE status = 'classified'
  AND category_id IN (1, 2, 3, 4, 5)
  AND due_date IS NOT NULL
  AND todo_task_id IS NULL;
```

**Already Synced Emails**:
```sql
SELECT id, subject, todo_task_id, due_date
FROM emails
WHERE todo_task_id IS NOT NULL
ORDER BY urgency_score DESC;
```

**Reset Sync Tracking**:
```sql
UPDATE emails
SET todo_task_id = NULL
WHERE todo_task_id IS NOT NULL;
```

---

## Testing

### Test Script

Run the comprehensive test suite:

```bash
./test_todo_endpoints.sh
```

### Test Scenarios

**Scenario 1: First Sync**
```bash
# Should create tasks and lists
curl -X POST http://localhost:8000/api/emails/sync-todo
# Expected: synced=37, lists_created=[5 lists]
```

**Scenario 2: Re-sync (Duplicate Prevention)**
```bash
# Should skip already synced emails
curl -X POST http://localhost:8000/api/emails/sync-todo
# Expected: synced=0, message="No emails found to sync"
```

**Scenario 3: Reset and Re-sync**
```bash
# Reset tracking
curl -X DELETE http://localhost:8000/api/emails/sync-todo/reset
# Expected: reset=37

# Re-sync (creates duplicates in To-Do unless you delete tasks first)
curl -X POST http://localhost:8000/api/emails/sync-todo
# Expected: synced=37
```

**Scenario 4: Partial Assignment**
```bash
# Assign only some emails
curl -X POST "http://localhost:8000/api/emails/assign"

# Sync only assigned emails
curl -X POST http://localhost:8000/api/emails/sync-todo
# Expected: synced=number of emails with due_date
```

---

## Monitoring

### Success Metrics

Track these metrics in production:

```python
# Total synced emails
synced_count = db.query(Email).filter(
    Email.todo_task_id.isnot(None)
).count()

# Sync success rate
total_with_due_date = db.query(Email).filter(
    Email.due_date.isnot(None),
    Email.category_id.in_([1, 2, 3, 4, 5])
).count()

success_rate = synced_count / total_with_due_date if total_with_due_date > 0 else 0

# Sync errors
sync_result = requests.post(f"{BASE_URL}/api/emails/sync-todo").json()
error_count = len(sync_result.get('errors', []))
```

### Common Issues

**Issue: Token expired**
- **Symptom**: 401 error from sync endpoint
- **Solution**: User must re-authenticate via OAuth flow

**Issue: Rate limit exceeded**
- **Symptom**: Errors array contains rate limit messages
- **Solution**: Wait and retry, or reduce batch size

**Issue: Duplicate tasks**
- **Symptom**: Multiple tasks for same email in To-Do
- **Solution**: Delete tasks in To-Do before resetting and re-syncing

---

## API Integration Points

### Upstream Dependencies

- `POST /api/emails/assign` - Assigns due dates (required before sync)
- Microsoft Graph OAuth tokens - Must be valid
- User authentication - Must have authenticated user

### Downstream Effects

- Creates tasks in Microsoft To-Do
- Updates `emails.todo_task_id` in database
- Tracks sync state for duplicate prevention

---

## Future Enhancements

### Planned Features

1. **Incremental Sync**: Only sync new emails since last sync
2. **Batch Size Control**: Limit number of emails synced per request
3. **Selective Sync**: Sync specific categories or priority levels
4. **Task Updates**: Update existing tasks when email details change
5. **Bidirectional Sync**: Update emails when tasks are completed in To-Do
6. **Webhook Support**: Trigger sync on task completion
7. **Conflict Resolution**: Handle cases where tasks are modified externally

### Configuration Options

Allow users to customize sync behavior:

```python
{
    "auto_sync_on_assign": True,       # Sync immediately after assignment
    "sync_only_today": False,          # Only sync today's emails
    "sync_only_floor": False,          # Only sync critical items
    "create_lists_per_date": False,    # Organize by date instead of category
    "task_completion_webhook": None    # URL to notify on task completion
}
```

---

## Test Results

### Current System State

```
✅ Total Work emails: 37
✅ Emails with due_date: 37
✅ Synced to To-Do: 37
✅ Success rate: 100%

Test Results:
  ✅ POST /api/emails/sync-todo - Synced 37 emails
  ✅ Lists created: ["2. Action Required"]
  ✅ Duplicate prevention - Correctly skipped already synced
  ✅ DELETE /api/emails/sync-todo/reset - Reset 37 emails
  ✅ Re-sync after reset - Synced 37 emails again
```

---

## References

- To-Do Sync Service: `app/services/todo_sync.py`
- Full Guide: `TODO_SYNC_GUIDE.md`
- Quick Reference: `TODO_SYNC_QUICKREF.md`
- Assignment Endpoints: `ASSIGNMENT_ENDPOINTS.md`
- Complete Workflow: `COMPLETE_WORKFLOW_GUIDE.md`
