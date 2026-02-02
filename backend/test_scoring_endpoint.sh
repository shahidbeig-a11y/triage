#!/bin/bash

# Test script for the urgency scoring endpoint

echo "🧪 Testing POST /api/emails/score endpoint"
echo "==========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if server is running
echo "Checking if server is running..."
if ! curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
    echo -e "${RED}❌ Server is not running at http://localhost:8000${NC}"
    echo "   Start the server with: uvicorn app.main:app --reload"
    exit 1
fi
echo -e "${GREEN}✅ Server is running${NC}"
echo ""

# Get email summary before scoring
echo "📊 Email Summary (before scoring):"
echo "-----------------------------------"
curl -s http://localhost:8000/api/emails/summary | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"Total emails: {data['total']}\")
print(f\"Classified: {data['by_status'].get('classified', 0)}\")
print(f\"Unprocessed: {data['by_status'].get('unprocessed', 0)}\")
print()
print('Work categories (will be scored):')
for key, value in data['by_category'].items():
    if value > 0 and any(key.startswith(str(i)) for i in [1, 2, 3, 4, 5]):
        print(f\"  {key}: {value}\")
" 2>/dev/null || echo "Failed to get summary"
echo ""

# Run scoring endpoint
echo -e "${YELLOW}📤 Sending POST request to /api/emails/score...${NC}"
echo ""

response=$(curl -s -X POST http://localhost:8000/api/emails/score \
    -w "\nHTTP_STATUS:%{http_code}" \
    -H "Content-Type: application/json")

http_status=$(echo "$response" | grep "HTTP_STATUS" | cut -d: -f2)
body=$(echo "$response" | sed '/HTTP_STATUS/d')

echo "📥 Response Status: $http_status"
echo ""

if [ "$http_status" = "200" ]; then
    echo -e "${GREEN}✅ SUCCESS - Scoring completed${NC}"
    echo ""
    echo "Results:"
    echo "--------"
    echo "$body" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)

    print(f\"📧 Total scored: {data['total_scored']}\")
    print()

    print('📊 Score Distribution:')
    dist = data['score_distribution']
    print(f\"  🔴 Critical (90+):  {dist['critical_90_plus']}\")
    print(f\"  🟠 High (70-89):    {dist['high_70_89']}\")
    print(f\"  🟡 Medium (40-69):  {dist['medium_40_69']}\")
    print(f\"  🟢 Low (<40):       {dist['low_under_40']}\")
    print()

    print(f\"📈 Average Score: {data['average_score']}\")
    print()

    if data.get('highest'):
        highest = data['highest']
        print(f\"⬆️  Highest Score: {highest['score']}/100\")
        print(f\"   Email #{highest['email_id']}: {highest['subject'][:60]}\")
        print()

    if data.get('lowest'):
        lowest = data['lowest']
        print(f\"⬇️  Lowest Score: {lowest['score']}/100\")
        print(f\"   Email #{lowest['email_id']}: {lowest['subject'][:60]}\")
        print()

    print(f\"💬 Message: {data.get('message', '')}\")

except Exception as e:
    print(f'Error parsing response: {e}')
    print('Raw response:')
    print(sys.stdin.read())
"
else
    echo -e "${RED}❌ FAILED - Scoring returned error${NC}"
    echo ""
    echo "Response:"
    echo "$body"
fi

echo ""
echo "==========================================="

# Query database for verification
echo ""
echo "🔍 Database Verification:"
echo "-------------------------"

if command -v sqlite3 &> /dev/null; then
    # Check urgency_scores table
    if [ -f triage.db ]; then
        echo "Checking urgency_scores table..."

        count=$(sqlite3 triage.db "SELECT COUNT(*) FROM urgency_scores;" 2>/dev/null || echo "0")
        echo "Total urgency scores in database: $count"

        if [ "$count" -gt 0 ]; then
            echo ""
            echo "Top 5 highest urgency scores:"
            sqlite3 triage.db -header "
                SELECT
                    e.id AS email_id,
                    SUBSTR(e.subject, 1, 50) AS subject,
                    us.urgency_score AS score
                FROM emails e
                JOIN urgency_scores us ON e.id = us.email_id
                ORDER BY us.urgency_score DESC
                LIMIT 5;
            " 2>/dev/null | column -t -s '|'
        fi
    else
        echo "Database file not found (triage.db)"
    fi
else
    echo "sqlite3 not installed - skipping database verification"
fi

echo ""
echo "==========================================="
echo "✅ Test completed!"
echo ""
echo "Next steps:"
echo "  - View emails sorted by urgency in the UI"
echo "  - Query urgency_scores table for signal details"
echo "  - Re-run scoring periodically to update stale scores"
