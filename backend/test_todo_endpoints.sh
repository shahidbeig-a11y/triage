#!/bin/bash

# Test script for To-Do sync endpoints
# Tests POST /api/emails/sync-todo and DELETE /api/emails/sync-todo/reset

BASE_URL="http://localhost:8000"

echo "=========================================="
echo "To-Do Sync Endpoints Test"
echo "=========================================="
echo ""

# Test 1: Check current sync status
echo "Test 1: Current Sync Status"
echo "----------------------------------------"
echo "Checking how many emails need syncing..."
echo ""

curl -s "${BASE_URL}/api/emails/score/check" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"Scorable emails: {data.get('scorable_emails', 0)}\")
"

# Query database to check todo_task_id status
python3 -c "
from app.database import SessionLocal
from app.models import Email

db = SessionLocal()

total_with_due_date = db.query(Email).filter(
    Email.due_date.isnot(None),
    Email.category_id.in_([1, 2, 3, 4, 5])
).count()

already_synced = db.query(Email).filter(
    Email.todo_task_id.isnot(None)
).count()

needs_sync = db.query(Email).filter(
    Email.due_date.isnot(None),
    Email.category_id.in_([1, 2, 3, 4, 5]),
    Email.todo_task_id.is_(None)
).count()

print(f'Total with due_date: {total_with_due_date}')
print(f'Already synced: {already_synced}')
print(f'Need sync: {needs_sync}')

db.close()
"

echo ""
echo ""

# Test 2: Sync to Microsoft To-Do
echo "Test 2: POST /api/emails/sync-todo"
echo "----------------------------------------"
echo "Syncing emails to Microsoft To-Do..."
echo ""

curl -X POST "${BASE_URL}/api/emails/sync-todo" 2>/dev/null | python3 -m json.tool

echo ""
echo ""

# Test 3: Check sync status after sync
echo "Test 3: Post-Sync Status"
echo "----------------------------------------"
echo "Checking sync status after sync..."
echo ""

python3 -c "
from app.database import SessionLocal
from app.models import Email

db = SessionLocal()

synced = db.query(Email).filter(
    Email.todo_task_id.isnot(None)
).count()

needs_sync = db.query(Email).filter(
    Email.due_date.isnot(None),
    Email.category_id.in_([1, 2, 3, 4, 5]),
    Email.todo_task_id.is_(None)
).count()

print(f'Synced emails: {synced}')
print(f'Still need sync: {needs_sync}')

# Show sample synced emails
if synced > 0:
    print(f'\nSample synced emails:')
    emails = db.query(Email).filter(
        Email.todo_task_id.isnot(None)
    ).limit(5).all()

    for i, email in enumerate(emails, 1):
        print(f'  {i}. {email.subject[:50]}')
        print(f'     Task ID: {email.todo_task_id[:20]}...')

db.close()
"

echo ""
echo ""

# Test 4: Try syncing again (should skip already synced)
echo "Test 4: Re-sync (Should Skip)"
echo "----------------------------------------"
echo "Attempting to sync again (should skip already synced)..."
echo ""

curl -X POST "${BASE_URL}/api/emails/sync-todo" 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"Synced: {data.get('synced', 0)}\")
print(f\"Skipped: {data.get('skipped', 0)}\")
print(f\"Message: {data.get('message', '')}\")
"

echo ""
echo ""

# Test 5: Reset sync tracking
echo "Test 5: DELETE /api/emails/sync-todo/reset"
echo "----------------------------------------"
echo "Resetting To-Do sync tracking..."
echo ""

curl -X DELETE "${BASE_URL}/api/emails/sync-todo/reset" 2>/dev/null | python3 -m json.tool

echo ""
echo ""

# Test 6: Verify reset
echo "Test 6: Post-Reset Status"
echo "----------------------------------------"
echo "Verifying all todo_task_id values cleared..."
echo ""

python3 -c "
from app.database import SessionLocal
from app.models import Email

db = SessionLocal()

synced = db.query(Email).filter(
    Email.todo_task_id.isnot(None)
).count()

with_due_date = db.query(Email).filter(
    Email.due_date.isnot(None),
    Email.category_id.in_([1, 2, 3, 4, 5])
).count()

print(f'Synced emails: {synced} (should be 0)')
print(f'Emails ready to sync: {with_due_date}')

if synced == 0:
    print('\n✓ Reset successful! All todo_task_id values cleared.')
else:
    print(f'\n✗ Reset incomplete! {synced} emails still have todo_task_id.')

db.close()
"

echo ""
echo ""

# Test 7: Re-sync after reset
echo "Test 7: Re-sync After Reset"
echo "----------------------------------------"
echo "Syncing again after reset..."
echo ""

curl -X POST "${BASE_URL}/api/emails/sync-todo" 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"Synced: {data.get('synced', 0)}\")
print(f\"Lists created: {data.get('lists_created', [])}\")
print(f\"Skipped: {data.get('skipped', 0)}\")
print(f\"Errors: {len(data.get('errors', []))}\")
"

echo ""
echo "=========================================="
echo "All tests completed!"
echo "=========================================="
echo ""
echo "Note: To avoid duplicate tasks in Microsoft To-Do,"
echo "manually delete the task lists in To-Do before re-syncing."
echo ""
