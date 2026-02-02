#!/bin/bash

# Test script for assignment endpoints
# Tests POST /api/emails/assign and GET /api/emails/today

echo "=========================================="
echo "Assignment Endpoints Test"
echo "=========================================="
echo ""

# Test 1: Assign due dates to all emails
echo "Test 1: POST /api/emails/assign"
echo "----------------------------------------"
echo "Assigning due dates to all scored Work emails..."
echo ""

curl -X POST http://localhost:8000/api/emails/assign 2>/dev/null | python3 -m json.tool

echo ""
echo ""

# Test 2: Get today's action list
echo "Test 2: GET /api/emails/today"
echo "----------------------------------------"
echo "Fetching today's action list..."
echo ""

curl "http://localhost:8000/api/emails/today" 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"Date: {data['date']}\")
print(f\"Total emails due today: {data['total']}\")
print(f\"\nToday's Action List (sorted by urgency):\")
print(\"=\"*70)
for i, email in enumerate(data['emails'][:10]):
    floor_mark = '🔴' if email['floor_override'] else '  '
    print(f\"{i+1:2d}. {floor_mark} [{email['urgency_score']:5.1f}] {email['subject'][:50]}\")
    print(f\"     From: {email['from_name'][:50]}\")
if data['total'] > 10:
    print(f\"\n... and {data['total'] - 10} more emails\")
"

echo ""
echo ""

# Test 3: Show summary
echo "Test 3: Assignment Summary"
echo "----------------------------------------"

curl -X POST http://localhost:8000/api/emails/assign 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"Settings:\")
print(f\"  Task Limit: {data['task_limit']}\")
print(f\"  Urgency Floor: {data['urgency_floor']}\")
print(f\"  Floor Overflow: {data['floor_overflow']}\")
print(f\"\nAssignment Distribution:\")
print(f\"  Today:     {data['slots']['today']['count']:3d} ({data['slots']['today']['floor_count']} floor + {data['slots']['today']['standard_count']} standard)\")
print(f\"  Tomorrow:  {data['slots']['tomorrow']['count']:3d}\")
print(f\"  This Week: {data['slots']['this_week']['count']:3d}\")
print(f\"  Next Week: {data['slots']['next_week']['count']:3d}\")
print(f\"  No Date:   {data['slots']['no_date']['count']:3d}\")
print(f\"  ────────────\")
print(f\"  Total:     {data['total_assigned']:3d}\")
"

echo ""
echo "=========================================="
echo "All tests completed!"
echo "=========================================="
