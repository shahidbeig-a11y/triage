# Microsoft To-Do Sync Guide

## Overview

The To-Do sync service creates Microsoft To-Do tasks from assigned emails via the Microsoft Graph API. Tasks are organized into category-based lists and include email details, due dates, and priority markers.

## Features

✅ **Automatic List Creation**: Creates task lists for each work category
✅ **Smart Task Formatting**: Includes category prefix and priority markers
✅ **Due Date Sync**: Syncs email due dates to To-Do task due dates
✅ **Priority Mapping**: Maps urgency scores to task importance
✅ **Duplicate Prevention**: Tracks synced tasks to avoid duplicates
✅ **Error Handling**: Retry with exponential backoff for rate limits
✅ **Token Expiration**: Clear error messages for authentication issues

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Email Assignment                          │
│  - Emails assigned due dates                                 │
│  - Organized by category (1-5)                               │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    To-Do Sync Service                        │
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │Get/Create    │  │ Format Task  │  │ Create Task  │      │
│  │  Task List   │─>│   Details    │─>│  via Graph   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│         │                  │                  │              │
│         ▼                  ▼                  ▼              │
│    Cache List IDs     Add Metadata      Update Database     │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                 Microsoft Graph API                          │
│               (To-Do Task Creation)                          │
└─────────────────────────────────────────────────────────────┘
```

## Task Organization

### Category-Based Lists

Tasks are organized into lists based on email category:

| Category ID | Category Name | To-Do List Name |
|-------------|---------------|-----------------|
| 1 | Blocking | 1. Blocking |
| 2 | Action Required | 2. Action Required |
| 3 | Waiting On | 3. Waiting On |
| 4 | Time-Sensitive | 4. Time-Sensitive |
| 5 | FYI | 5. FYI |

### Task Format

**Title**: `[PRIORITY][CATEGORY] Subject`

Examples:
- `⚠️ [BLOCKING] Urgent: Project deadline approaching`
- `[ACTION] Review: Q4 Budget Proposal`
- `[FYI] Team meeting notes`

**Body**:
```
Email preview (first 200 chars)...

From: Sender Name
Received: 2026-02-01 14:30
```

**Importance**:
- High: urgency_score >= 70
- Normal: urgency_score < 70

## Core Functions

### 1. get_or_create_task_list(access_token, list_name)

Gets or creates a Microsoft To-Do task list by name.

```python
from app.services.todo_sync import get_or_create_task_list

# Get or create a task list
access_token = "..."  # From Microsoft Graph
list_id = get_or_create_task_list(access_token, "1. Blocking")

print(f"List ID: {list_id}")
```

**Features**:
- Searches for existing list by displayName
- Creates list if not found
- Caches list IDs to avoid repeated API calls
- Handles rate limits with retry

**API Calls**:
- `GET /me/todo/lists` - List all task lists
- `POST /me/todo/lists` - Create new list

---

### 2. create_todo_task(access_token, list_id, email, urgency_score, floor_override, category_id)

Creates a Microsoft To-Do task from an email.

```python
from app.services.todo_sync import create_todo_task

email = {
    "subject": "Review proposal",
    "body_preview": "Please review the attached proposal...",
    "from_name": "John Smith",
    "from_address": "john@example.com",
    "received_at": datetime.now(),
    "due_date": datetime.now()
}

task_id = create_todo_task(
    access_token=access_token,
    list_id=list_id,
    email=email,
    urgency_score=75,
    floor_override=False,
    category_id=2  # Action Required
)

print(f"Created task: {task_id}")
```

**Features**:
- Formats task title with category prefix and priority marker
- Truncates title to 255 characters (Graph API limit)
- Includes email preview and metadata in body
- Sets due date from email.due_date
- Maps urgency score to task importance
- Handles rate limits with retry

**API Calls**:
- `POST /me/todo/lists/{list_id}/tasks` - Create task

---

### 3. sync_all_tasks(access_token, assigned_emails, db)

Syncs all assigned emails to Microsoft To-Do tasks.

```python
from app.services.todo_sync import sync_all_tasks
from app.database import SessionLocal
from app.models import Email, UrgencyScore

# Get assigned emails from database
db = SessionLocal()
emails_query = db.query(Email, UrgencyScore).join(
    UrgencyScore, Email.id == UrgencyScore.email_id
).filter(
    Email.due_date.isnot(None),
    Email.category_id.in_([1, 2, 3, 4, 5])
).all()

# Convert to format expected by sync_all_tasks
assigned_emails = []
for email, urgency in emails_query:
    assigned_emails.append({
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
    })

# Sync to To-Do
result = sync_all_tasks(access_token, assigned_emails, db)

print(f"Synced: {result['synced']}")
print(f"Skipped (already synced): {result['skipped_already_synced']}")
print(f"Skipped (no date): {result['skipped_no_date']}")
print(f"Lists created: {result['lists_created']}")
print(f"Errors: {len(result['errors'])}")

# Commit changes to database
db.commit()
db.close()
```

**Features**:
- Processes all assigned emails with due dates
- Skips emails already synced (todo_task_id present)
- Skips emails without due dates
- Organizes into category-based lists
- Updates database with task IDs
- Returns detailed summary
- Continues on errors (doesn't fail entire batch)

**Return Format**:
```python
{
    "synced": 15,                      # Number of tasks created
    "skipped_already_synced": 3,       # Already had todo_task_id
    "skipped_no_date": 2,              # No due_date assigned
    "lists_created": ["1. Blocking"],  # New lists created
    "errors": []                       # Error messages (if any)
}
```

---

### 4. clear_cache()

Clears the task list ID cache.

```python
from app.services.todo_sync import clear_cache

# Clear cache after errors or for testing
clear_cache()
```

## Error Handling

### 1. Rate Limiting (429)

**Behavior**: Automatic retry with exponential backoff

```python
try:
    result = sync_all_tasks(token, emails)
except RateLimitError as e:
    # After max retries exceeded
    print(f"Rate limit exceeded: {e}")
```

**Retry Logic**:
- Initial delay: 1 second
- Exponential backoff: 1s → 2s → 4s
- Max retries: 3 attempts
- Respects Retry-After header from API

---

### 2. Token Expiration (401)

**Behavior**: Immediate failure with clear error message

```python
try:
    result = sync_all_tasks(token, emails)
except TokenExpiredError as e:
    print(f"Token expired: {e}")
    # Re-authenticate user
```

**Resolution**: User must re-authenticate to get a new token

---

### 3. Not Found (404)

**Behavior**: Returns None, allows graceful handling

```python
# If a task list is deleted externally
list_id = get_or_create_task_list(token, "Deleted List")
# Will create a new list instead of failing
```

---

### 4. Other Errors

**Behavior**: Logged and returned in errors array

```python
result = sync_all_tasks(token, emails)

if result['errors']:
    print(f"Encountered {len(result['errors'])} errors:")
    for error in result['errors']:
        print(f"  - {error}")
```

## Database Integration

### New Column: todo_task_id

```python
class Email(Base):
    # ... existing fields ...
    todo_task_id = Column(String, nullable=True)  # Microsoft To-Do task ID
```

**Purpose**: Track which emails have been synced to avoid duplicates

**Usage**:
- Set by `sync_all_tasks()` when task is created
- Checked to skip already-synced emails
- Persisted across multiple sync operations

### Migration

```sql
-- Add column to existing database
ALTER TABLE emails ADD COLUMN todo_task_id TEXT;
```

Or in Python:
```python
import sqlite3
conn = sqlite3.connect('triage.db')
cursor = conn.cursor()
cursor.execute('ALTER TABLE emails ADD COLUMN todo_task_id TEXT')
conn.commit()
conn.close()
```

## Complete Workflow

### Automated Daily Sync

```python
#!/usr/bin/env python3
"""
Daily email-to-todo sync automation.
"""

import asyncio
from app.database import SessionLocal
from app.models import User, Email, UrgencyScore
from app.services.graph import GraphClient
from app.services.todo_sync import sync_all_tasks

async def daily_sync():
    """Sync all assigned emails to Microsoft To-Do."""
    db = SessionLocal()

    try:
        # Get user and token
        user = db.query(User).first()
        if not user:
            print("No user found")
            return

        graph_client = GraphClient()
        access_token = await graph_client.get_token(user.email, db)

        # Get assigned emails with due dates
        emails_query = db.query(Email, UrgencyScore).join(
            UrgencyScore, Email.id == UrgencyScore.email_id
        ).filter(
            Email.due_date.isnot(None),
            Email.category_id.in_([1, 2, 3, 4, 5])
        ).all()

        # Convert to sync format
        assigned_emails = []
        for email, urgency in emails_query:
            assigned_emails.append({
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
            })

        # Sync to To-Do
        print(f"Syncing {len(assigned_emails)} assigned emails...")
        result = sync_all_tasks(access_token, assigned_emails, db)

        # Commit database updates
        db.commit()

        # Print summary
        print(f"\n✓ Sync completed!")
        print(f"  Synced: {result['synced']}")
        print(f"  Skipped (already synced): {result['skipped_already_synced']}")
        print(f"  Skipped (no date): {result['skipped_no_date']}")
        print(f"  Lists created: {result['lists_created']}")

        if result['errors']:
            print(f"  Errors: {len(result['errors'])}")
            for error in result['errors'][:5]:
                print(f"    - {error}")

    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(daily_sync())
```

## Testing

### Run Tests

```bash
# Run test suite
python test_todo_sync.py

# Test with specific token
python test_todo_sync.py <access_token>
```

### Test Coverage

1. **Category List Names** - Verify all categories mapped
2. **Sample Email Data** - Test data formatting
3. **Sync Without Token** - Error handling for invalid tokens
4. **Sync Logic Analysis** - Validate skip logic
5. **Real API Test** - Optional test with valid token

## API Reference

### Microsoft Graph API Endpoints

**List Task Lists**:
```
GET https://graph.microsoft.com/v1.0/me/todo/lists
```

**Create Task List**:
```
POST https://graph.microsoft.com/v1.0/me/todo/lists
Body: {"displayName": "List Name"}
```

**Create Task**:
```
POST https://graph.microsoft.com/v1.0/me/todo/lists/{list_id}/tasks
Body: {
  "title": "Task title",
  "body": {
    "contentType": "text",
    "content": "Task body"
  },
  "dueDateTime": {
    "dateTime": "2026-02-01T00:00:00",
    "timeZone": "UTC"
  },
  "importance": "high" | "normal" | "low"
}
```

### Required Permissions

- `Tasks.ReadWrite` - Read and write user tasks

## Best Practices

### 1. Rate Limit Management

- Use the built-in retry mechanism
- Don't manually implement retry logic
- Monitor error logs for repeated rate limits

### 2. Token Management

- Refresh tokens before they expire
- Handle TokenExpiredError gracefully
- Store tokens securely

### 3. Batch Processing

- Sync in reasonable batches (< 100 emails)
- Use the errors array to track failures
- Don't stop on first error

### 4. Cache Management

- Cache persists for the session
- Clear cache after major changes
- Don't rely on cache for critical operations

### 5. Database Updates

- Always commit after successful sync
- Don't commit inside the sync loop
- Handle partial failures gracefully

## Troubleshooting

### Issue: Rate limit errors

**Solution**:
- Reduce batch size
- Add delay between sync operations
- Check if multiple processes are syncing

### Issue: Token expired

**Solution**:
- Re-authenticate user
- Check token refresh logic
- Verify token storage

### Issue: Duplicate tasks

**Solution**:
- Verify todo_task_id is being saved
- Check database commit logic
- Clear To-Do lists and resync

### Issue: Missing lists

**Solution**:
- Check list creation permissions
- Verify displayName matching
- Clear cache and retry

## Future Enhancements

### Planned Features

1. **Bidirectional Sync**: Update emails when tasks are completed in To-Do
2. **Task Updates**: Modify existing tasks instead of creating duplicates
3. **Bulk Operations**: Batch create for better performance
4. **Smart Scheduling**: Respect user's working hours
5. **Custom Lists**: Allow users to customize list names
6. **Task Templates**: Configurable task formatting
7. **Completion Tracking**: Track when tasks are marked complete

## References

- Microsoft Graph To-Do API: https://docs.microsoft.com/en-us/graph/api/resources/todo-overview
- Assignment Algorithm: `ASSIGNMENT_ALGORITHM.md`
- Graph Client: `app/services/graph.py`
- Database Models: `app/models/email.py`
