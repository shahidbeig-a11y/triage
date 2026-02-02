#!/bin/bash

# Test the full 7-phase pipeline endpoint
# This script runs the complete workflow and displays the results

echo "============================================"
echo "Testing Full Pipeline (7 Phases)"
echo "============================================"
echo ""

# Run the full pipeline
echo "Running pipeline with 50 emails..."
echo ""

response=$(curl -s -X POST "http://localhost:8000/api/emails/pipeline/run?fetch_count=50")

# Check if the request was successful
if [ $? -ne 0 ]; then
    echo "❌ Pipeline request failed"
    exit 1
fi

echo "$response" | python3 -m json.tool

echo ""
echo "============================================"
echo "Pipeline Summary"
echo "============================================"

# Extract key metrics using jq if available, otherwise use python
if command -v jq &> /dev/null; then
    echo "Phase 1 (Fetch):         $(echo "$response" | jq -r '.phase_1_fetch.new // 0') new emails in $(echo "$response" | jq -r '.phase_1_fetch.time_seconds // 0')s"
    echo "Phase 2 (Deterministic): $(echo "$response" | jq -r '.phase_2_deterministic.classified // 0') classified in $(echo "$response" | jq -r '.phase_2_deterministic.time_seconds // 0')s"
    echo "Phase 3 (Override):      $(echo "$response" | jq -r '.phase_3_override.overridden // 0') overridden"
    echo "Phase 4 (AI):            $(echo "$response" | jq -r '.phase_4_ai.classified // 0') classified in $(echo "$response" | jq -r '.phase_4_ai.time_seconds // 0')s"
    echo "Phase 5 (Scoring):       $(echo "$response" | jq -r '.phase_5_scoring.scored // 0') scored in $(echo "$response" | jq -r '.phase_5_scoring.time_seconds // 0')s"
    echo "Phase 6 (Assignment):    $(echo "$response" | jq -r '.phase_6_assignment.assigned // 0') assigned in $(echo "$response" | jq -r '.phase_6_assignment.time_seconds // 0')s"
    echo "Phase 7 (To-Do Sync):    $(echo "$response" | jq -r '.phase_7_todo_sync.synced // 0') synced in $(echo "$response" | jq -r '.phase_7_todo_sync.time_seconds // 0')s"
    echo ""
    echo "Total Time:              $(echo "$response" | jq -r '.summary.total_pipeline_time_seconds // 0')s"
    echo "Work Items:              $(echo "$response" | jq -r '.summary.work_items // 0')"
    echo "Other Items:             $(echo "$response" | jq -r '.summary.other_items // 0')"
else
    echo "$response" | python3 -c "
import sys
import json

try:
    data = json.load(sys.stdin)
    print(f\"Phase 1 (Fetch):         {data.get('phase_1_fetch', {}).get('new', 0)} new emails in {data.get('phase_1_fetch', {}).get('time_seconds', 0)}s\")
    print(f\"Phase 2 (Deterministic): {data.get('phase_2_deterministic', {}).get('classified', 0)} classified in {data.get('phase_2_deterministic', {}).get('time_seconds', 0)}s\")
    print(f\"Phase 3 (Override):      {data.get('phase_3_override', {}).get('overridden', 0)} overridden\")
    print(f\"Phase 4 (AI):            {data.get('phase_4_ai', {}).get('classified', 0)} classified in {data.get('phase_4_ai', {}).get('time_seconds', 0)}s\")
    print(f\"Phase 5 (Scoring):       {data.get('phase_5_scoring', {}).get('scored', 0)} scored in {data.get('phase_5_scoring', {}).get('time_seconds', 0)}s\")
    print(f\"Phase 6 (Assignment):    {data.get('phase_6_assignment', {}).get('assigned', 0)} assigned in {data.get('phase_6_assignment', {}).get('time_seconds', 0)}s\")
    print(f\"Phase 7 (To-Do Sync):    {data.get('phase_7_todo_sync', {}).get('synced', 0)} synced in {data.get('phase_7_todo_sync', {}).get('time_seconds', 0)}s\")
    print()
    print(f\"Total Time:              {data.get('summary', {}).get('total_pipeline_time_seconds', 0)}s\")
    print(f\"Work Items:              {data.get('summary', {}).get('work_items', 0)}\")
    print(f\"Other Items:             {data.get('summary', {}).get('other_items', 0)}\")
except:
    pass
"
fi

echo ""
echo "============================================"
echo "✓ Pipeline test complete!"
echo "Check Microsoft To-Do to see your tasks"
echo "============================================"
