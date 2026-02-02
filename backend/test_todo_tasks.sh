#!/bin/bash

# Test script to check what tasks exist in Microsoft To-Do

echo "============================================"
echo "Checking Microsoft To-Do Tasks"
echo "============================================"
echo ""

# This will show the raw response from the sync
echo "Running pipeline and checking sync errors..."
echo ""

response=$(curl -s -X POST "http://localhost:8000/api/emails/pipeline/run?fetch_count=10")

echo "Phase 7 (To-Do Sync) Results:"
echo "$response" | python3 -c "
import sys, json
data = json.load(sys.stdin)
phase7 = data.get('phase_7_todo_sync', {})
print(f\"Synced: {phase7.get('synced', 0)}\")
print(f\"Time: {phase7.get('time_seconds', 0)}s\")
print(f\"Errors: {len(phase7.get('errors', []))}\")
if phase7.get('errors'):
    print('\nFirst 5 errors:')
    for err in phase7['errors'][:5]:
        print(f\"  - {err}\")
"

echo ""
echo "============================================"
echo "To manually check Microsoft To-Do:"
echo "1. Open Microsoft To-Do app or web"
echo "2. Look in the 'Tasks' list (default list)"
echo "3. Check if flagged emails appear there"
echo "============================================"
