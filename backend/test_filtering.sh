#!/bin/bash

# Test email filtering rules
# Checks if old emails and recently processed emails are being filtered

echo "============================================"
echo "Testing Email Filtering Rules"
echo "============================================"
echo ""

# Get summary to see total unprocessed count
echo "1. Checking unprocessed email counts..."
echo ""

summary=$(curl -s "http://localhost:8000/api/emails/summary")
unprocessed_total=$(echo "$summary" | python3 -c "import sys, json; print(json.load(sys.stdin)['by_status']['unprocessed'])")

echo "Total unprocessed emails in DB: $unprocessed_total"
echo ""

# Run pipeline to see how many get filtered
echo "2. Running pipeline to check filtered count..."
echo ""

pipeline_result=$(curl -s -X POST "http://localhost:8000/api/emails/pipeline/run?fetch_count=10")

# Extract filtered count and processed count
if command -v jq &> /dev/null; then
    filtered=$(echo "$pipeline_result" | jq -r '.phase_2_deterministic.filtered // 0')
    processed=$(echo "$pipeline_result" | jq -r '.phase_2_deterministic.classified // 0')
    ai_processed=$(echo "$pipeline_result" | jq -r '.phase_4_ai.classified // 0')
else
    filtered=$(echo "$pipeline_result" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('phase_2_deterministic', {}).get('filtered', 0))")
    processed=$(echo "$pipeline_result" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('phase_2_deterministic', {}).get('classified', 0))")
    ai_processed=$(echo "$pipeline_result" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('phase_4_ai', {}).get('classified', 0))")
fi

echo "============================================"
echo "Filtering Results"
echo "============================================"
echo "Total unprocessed:     $unprocessed_total"
echo "Filtered out:          $filtered"
echo "Processed (determ):    $processed"
echo "Processed (AI):        $ai_processed"
echo ""

if [ "$filtered" -gt 0 ]; then
    echo "✓ Filtering is working! $filtered emails were excluded."
    echo ""
    echo "Reasons for filtering:"
    echo "  - Emails older than 45 days"
    echo "  - Emails processed in last 3 days"
else
    echo "ℹ No emails were filtered."
    echo ""
    if [ "$unprocessed_total" -eq 0 ]; then
        echo "This is expected: no unprocessed emails in database."
    else
        echo "This means all unprocessed emails are:"
        echo "  - Less than 45 days old"
        echo "  - Not processed in the last 3 days"
    fi
fi

echo ""
echo "============================================"
echo "Filter Configuration"
echo "============================================"
echo "Age limit:             45 days"
echo "Processing cooldown:   3 days"
echo ""
echo "To modify these limits, edit:"
echo "  - app/services/pipeline.py"
echo "  - app/routes/emails.py"
echo ""
echo "See EMAIL_FILTERING_RULES.md for details"
echo "============================================"
