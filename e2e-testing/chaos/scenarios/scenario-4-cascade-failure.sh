#!/bin/bash
# Scenario 4: Cascade Failure (Database Down)
# Purpose: Test AutoSRE detection of cascade failures from dependency outage
# Expected: AutoSRE should identify postgres as root cause, not blame bookstore-api

set -e

NAMESPACE="${NAMESPACE:-bookstore}"
API_HOST="${API_HOST:-localhost:8080}"

echo "=== Scenario 4: Cascade Failure ==="
echo "WARNING: This will delete postgres pod(s)!"
echo ""

# Get current postgres pod(s)
echo "Current postgres pods:"
kubectl get pods -n "$NAMESPACE" -l app=postgres -o wide

echo ""
echo "Deleting postgres pods to trigger cascade failure..."

# Kill database to trigger cascade
kubectl delete pod -n "$NAMESPACE" -l app=postgres --wait=false

echo ""
echo "Postgres pods deleted. Watching API failures..."
echo ""

# Give it a moment for the cascade to propagate
sleep 2

# Test API to see cascade effect
echo "Testing API (expecting failures due to DB outage):"
for i in {1..20}; do
    START=$(date +%s.%N)
    RESPONSE=$(curl -s -w "\n%{http_code}" --max-time 5 "http://${API_HOST}/books" 2>/dev/null || echo -e "\n000")
    HTTP_CODE=$(echo "$RESPONSE" | tail -1)
    END=$(date +%s.%N)
    DURATION=$(echo "$END - $START" | bc 2>/dev/null || echo "?")
    
    echo "Request $i: HTTP $HTTP_CODE (${DURATION}s)"
    sleep 1
done

echo ""
echo "Checking API logs for connection errors:"
kubectl logs -n "$NAMESPACE" -l app=bookstore-api --tail=10 2>/dev/null || echo "(logs unavailable)"

echo ""
echo "Checking postgres pod status:"
kubectl get pods -n "$NAMESPACE" -l app=postgres -o wide

echo ""
echo "NOTE: Postgres should auto-recover if it's a Deployment/StatefulSet."
echo "If not, manually restart: kubectl rollout restart deployment -n $NAMESPACE postgres"
