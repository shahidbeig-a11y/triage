#!/bin/bash

# Test script for the pipeline endpoint

echo "🧪 Testing POST /api/emails/pipeline/run endpoint"
echo "================================================"
echo ""

# Check if server is running
if ! curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
    echo "❌ Server is not running at http://localhost:8000"
    echo "   Start the server with: uvicorn app.main:app --reload"
    exit 1
fi

echo "✅ Server is running"
echo ""

# Test the pipeline endpoint
echo "📤 Sending POST request to /api/emails/pipeline/run?fetch_count=10"
echo ""

response=$(curl -s -X POST "http://localhost:8000/api/emails/pipeline/run?fetch_count=10" \
    -w "\nHTTP_STATUS:%{http_code}" \
    -H "Content-Type: application/json")

http_status=$(echo "$response" | grep "HTTP_STATUS" | cut -d: -f2)
body=$(echo "$response" | sed '/HTTP_STATUS/d')

echo "📥 Response Status: $http_status"
echo ""

if [ "$http_status" = "200" ]; then
    echo "✅ SUCCESS - Pipeline completed"
    echo ""
    echo "Response:"
    echo "$body" | python3 -m json.tool 2>/dev/null || echo "$body"
else
    echo "❌ FAILED - Pipeline returned error"
    echo ""
    echo "Response:"
    echo "$body"
fi
