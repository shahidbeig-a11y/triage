#!/bin/bash

# Re-score all Work emails with the updated age weights

echo "============================================"
echo "Re-scoring Work Emails"
echo "============================================"
echo ""

# Run scoring endpoint
echo "Running scoring on all Work emails..."
echo ""

response=$(curl -s -X POST "http://localhost:8000/api/emails/score")

# Check if the request was successful
if [ $? -ne 0 ]; then
    echo "❌ Scoring request failed"
    exit 1
fi

echo "$response" | python3 -m json.tool

echo ""
echo "============================================"
echo "Scoring Summary"
echo "============================================"

# Extract key metrics
if command -v jq &> /dev/null; then
    echo "Total scored:        $(echo "$response" | jq -r '.total_scored // 0')"
    echo "Floor items:         $(echo "$response" | jq -r '.floor_items.count // 0')"
    echo "Stale items:         $(echo "$response" | jq -r '.stale_items.count // 0')"
    echo "Force today count:   $(echo "$response" | jq -r '.stale_items.force_today_count // 0')"
    echo ""
    echo "Score Distribution:"
    echo "  Critical (90+):    $(echo "$response" | jq -r '.score_distribution.critical_90_plus // 0')"
    echo "  High (70-89):      $(echo "$response" | jq -r '.score_distribution.high_70_89 // 0')"
    echo "  Medium (40-69):    $(echo "$response" | jq -r '.score_distribution.medium_40_69 // 0')"
    echo "  Low (<40):         $(echo "$response" | jq -r '.score_distribution.low_under_40 // 0')"
    echo ""
    echo "Average raw score:      $(echo "$response" | jq -r '.average_raw_score // 0')"
    echo "Average adjusted score: $(echo "$response" | jq -r '.average_adjusted_score // 0')"
else
    echo "$response" | python3 -c "
import sys
import json

try:
    data = json.load(sys.stdin)
    print(f\"Total scored:        {data.get('total_scored', 0)}\")
    print(f\"Floor items:         {data.get('floor_items', {}).get('count', 0)}\")
    print(f\"Stale items:         {data.get('stale_items', {}).get('count', 0)}\")
    print(f\"Force today count:   {data.get('stale_items', {}).get('force_today_count', 0)}\")
    print()
    print(\"Score Distribution:\")
    dist = data.get('score_distribution', {})
    print(f\"  Critical (90+):    {dist.get('critical_90_plus', 0)}\")
    print(f\"  High (70-89):      {dist.get('high_70_89', 0)}\")
    print(f\"  Medium (40-69):    {dist.get('medium_40_69', 0)}\")
    print(f\"  Low (<40):         {dist.get('low_under_40', 0)}\")
    print()
    print(f\"Average raw score:      {data.get('average_raw_score', 0)}\")
    print(f\"Average adjusted score: {data.get('average_adjusted_score', 0)}\")
except:
    pass
"
fi

echo ""
echo "============================================"
echo "✓ Re-scoring complete!"
echo ""
echo "View scored emails in priority order:"
echo "curl http://localhost:8000/api/emails/scored"
echo "============================================"
