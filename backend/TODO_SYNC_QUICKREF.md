# Microsoft To-Do Sync - Quick Reference

## Summary

The To-Do sync service creates Microsoft To-Do tasks from assigned emails, organized into category-based lists.

## Quick Start

### 1. Basic Sync

```python
from app.services.todo_sync import sync_all_tasks
from app.database import SessionLocal
from app.models import Email, UrgencyScore

# Get database session
db = SessionLocal()

# Get assigned emails
emails_query = db.query(Email, UrgencyScore).join(
    UrgencyScore, Email.id == UrgencyScore.email_id
).filter(
    Email.due_date.isnot(None),
    Email.category_id.in_([1, 2, 3, 4, 5])
).all()

# Convert to sync format
assigned_emails = [
    {
        "email_id": email.id,
        "subject": email.subject,
        "body_preview": email.body_preview,
        "from_name": email.from_name,
        "from_address": email.from_address,
        "received_at": email.received_at,
        "due_date": email.due_date,
        "category_id": email.category_id,
        "urgency_score": urgency.urgency_score,
        "floor_override": urgency.floor_override,
        "todo_task_id": email.todo_task_id
    }
    for email, urgency in emails_query
]

# Sync to To-Do
result = sync_all_tasks(access_token, assigned_emails, db)
db.commit()

print(f"Synced: {result['synced']}")
```

### 2. Using Async with Graph Client

```python
import asyncio
from app.services.graph import GraphClient

async def sync_with_token():
    user = db.query(User).first()
    graph_client = GraphClient()
    access_token = await graph_client.get_token(user.email, db)

    result = sync_all_tasks(access_token, assigned_emails, db)
    return result

result = asyncio.run(sync_with_token())
```

## Task Organization

| Category | List Name | Task Prefix |
|----------|-----------|-------------|
| 1. Blocking | 1. Blocking | [BLOCKING] |
| 2. Action Required | 2. Action Required | [ACTION] |
| 3. Waiting On | 3. Waiting On | [WAITING] |
| 4. Time-Sensitive | 4. Time-Sensitive | [TIME-SENSITIVE] |
| 5. FYI | 5. FYI | [FYI] |

**Priority Marker**: ⚠️ added for floor_override items

**Example Task**:
```
⚠️ [BLOCKING] Urgent: Project deadline approaching
```

## Functions

### get_or_create_task_list(access_token, list_name)

```python
list_id = get_or_create_task_list(token, "1. Blocking")
```

- Finds or creates task list
- Caches list IDs
- Returns list ID

### create_todo_task(access_token, list_id, email, urgency_score, floor_override, category_id)

```python
task_id = create_todo_task(token, list_id, email, 75, False, 2)
```

- Creates single task
- Formats title and body
- Sets due date and importance
- Returns task ID

### sync_all_tasks(access_token, assigned_emails, db)

```python
result = sync_all_tasks(token, emails, db)
```

- Syncs all assigned emails
- Skips duplicates (todo_task_id present)
- Skips emails without due dates
- Updates database with task IDs
- Returns summary dict

### clear_cache()

```python
clear_cache()
```

- Clears cached list IDs
- Use after errors or for testing

## Return Format

```python
{
    "synced": 15,                     # Tasks created
    "skipped_already_synced": 3,      # Had todo_task_id
    "skipped_no_date": 2,             # No due_date
    "lists_created": ["1. Blocking"], # New lists
    "errors": []                      # Error messages
}
```

## Error Handling

### Rate Limits (429)
- Automatic retry with exponential backoff
- Max 3 retries
- Respects Retry-After header

### Token Expired (401)
```python
from app.services.todo_sync import TokenExpiredError

try:
    result = sync_all_tasks(token, emails, db)
except TokenExpiredError:
    # Re-authenticate user
    pass
```

### General Errors
- Logged and added to errors array
- Sync continues for remaining emails
- Check result['errors'] for details

## Testing

```bash
# Run test suite
python test_todo_sync.py

# Test with specific token
python test_todo_sync.py <access_token>
```

## Database Schema

```python
# emails table
class Email(Base):
    # ... existing fields ...
    todo_task_id = Column(String, nullable=True)  # Microsoft To-Do task ID
```

**Migration**:
```sql
ALTER TABLE emails ADD COLUMN todo_task_id TEXT;
```

## Common Patterns

### Pattern 1: Daily Sync Script

```python
#!/usr/bin/env python3
import asyncio
from app.database import SessionLocal
from app.models import User, Email, UrgencyScore
from app.services.graph import GraphClient
from app.services.todo_sync import sync_all_tasks

async def main():
    db = SessionLocal()
    user = db.query(User).first()

    # Get token
    graph_client = GraphClient()
    token = await graph_client.get_token(user.email, db)

    # Get assigned emails
    emails_query = db.query(Email, UrgencyScore).join(
        UrgencyScore, Email.id == UrgencyScore.email_id
    ).filter(
        Email.due_date.isnot(None),
        Email.category_id.in_([1, 2, 3, 4, 5])
    ).all()

    assigned_emails = [...]  # Format emails

    # Sync
    result = sync_all_tasks(token, assigned_emails, db)
    db.commit()

    print(f"✓ Synced {result['synced']} tasks")

    db.close()

if __name__ == "__main__":
    asyncio.run(main())
```

### Pattern 2: After Assignment

```python
# After running POST /api/emails/assign
result = assign_due_dates(scored_emails)

# Immediately sync to To-Do
sync_result = sync_all_tasks(access_token, assigned_emails, db)
db.commit()
```

### Pattern 3: Selective Sync

```python
# Sync only today's emails
today_emails = [
    email for email in assigned_emails
    if email['due_date'].date() == date.today()
]

result = sync_all_tasks(token, today_emails, db)
```

## API Endpoints (Graph)

```
GET  /me/todo/lists                      - List all task lists
POST /me/todo/lists                      - Create task list
POST /me/todo/lists/{list_id}/tasks      - Create task
```

## Permissions Required

- `Tasks.ReadWrite` - Read and write user tasks

## Files

- **Implementation**: `app/services/todo_sync.py`
- **Tests**: `test_todo_sync.py`
- **Full Documentation**: `TODO_SYNC_GUIDE.md`
- **Database Model**: `app/models/email.py`

## Test Results

```bash
✓ Category list names defined
✓ Sample email data created
✓ Sync logic validation passed
✓ Real API test succeeded (synced 1 task to "2. Action Required")
```

## Next Steps

1. **Create API Endpoint**: `POST /api/emails/sync-todo`
2. **Automate**: Run sync after assignment
3. **Monitor**: Track sync errors in logs
4. **Bidirectional**: Update emails when tasks complete
5. **Bulk Updates**: Modify existing tasks instead of duplicates
