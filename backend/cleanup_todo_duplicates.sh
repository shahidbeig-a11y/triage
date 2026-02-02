#!/bin/bash

# Script to clean up duplicate tasks in Microsoft To-Do

BASE_URL="http://localhost:8000"

echo "=========================================="
echo "Microsoft To-Do Cleanup"
echo "=========================================="
echo ""

echo "This will delete all task lists from Microsoft To-Do"
echo "that match our category names (1. Blocking, 2. Action Required, etc.)"
echo ""
read -p "Are you sure you want to continue? (y/N): " confirm

if [[ $confirm != [yY] ]]; then
    echo "Cleanup cancelled."
    exit 0
fi

echo ""
echo "Cleaning up task lists..."
echo ""

curl -X DELETE "${BASE_URL}/api/emails/sync-todo/cleanup" 2>/dev/null | python3 -m json.tool

echo ""
echo "=========================================="
echo "Cleanup complete!"
echo "=========================================="
echo ""
echo "You can now re-sync your emails without duplicates:"
echo "  curl -X POST ${BASE_URL}/api/emails/sync-todo"
echo ""
