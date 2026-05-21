#!/bin/bash
# Reset All Chaos
# Purpose: Clear all injected chaos and restore normal operation
# Run this after any scenario to clean up

set -e

NAMESPACE="${NAMESPACE:-bookstore}"
FORCE_RESTART="${FORCE_RESTART:-false}"

echo "=== Resetting All Chaos ==="
echo ""

# Try to reset via chaos endpoint
echo "Calling chaos reset endpoint..."
if kubectl exec -n "$NAMESPACE" deploy/bookstore-api -- \
    curl -s -X POST localhost:3000/chaos/reset 2>/dev/null; then
    echo "✓ Chaos reset endpoint called successfully"
else
    echo "⚠ Could not reach chaos endpoint (pod may be unhealthy)"
    FORCE_RESTART=true
fi

echo ""

# Check pod health
echo "Checking pod health..."
POD_STATUS=$(kubectl get pods -n "$NAMESPACE" -l app=bookstore-api -o jsonpath='{.items[0].status.phase}' 2>/dev/null || echo "Unknown")
RESTARTS=$(kubectl get pods -n "$NAMESPACE" -l app=bookstore-api -o jsonpath='{.items[0].status.containerStatuses[0].restartCount}' 2>/dev/null || echo "?")

echo "  Status: $POD_STATUS"
echo "  Restarts: $RESTARTS"

# Restart if needed or forced
if [[ "$FORCE_RESTART" == "true" ]] || [[ "$POD_STATUS" != "Running" ]]; then
    echo ""
    echo "Restarting bookstore-api deployment..."
    kubectl rollout restart deployment -n "$NAMESPACE" bookstore-api
    
    echo "Waiting for rollout to complete..."
    kubectl rollout status deployment -n "$NAMESPACE" bookstore-api --timeout=120s
    
    echo "✓ Deployment restarted successfully"
fi

# Verify postgres is healthy (in case of cascade failure scenario)
echo ""
echo "Checking postgres health..."
POSTGRES_STATUS=$(kubectl get pods -n "$NAMESPACE" -l app=postgres -o jsonpath='{.items[0].status.phase}' 2>/dev/null || echo "Unknown")

if [[ "$POSTGRES_STATUS" != "Running" ]]; then
    echo "⚠ Postgres not running. Attempting restart..."
    kubectl rollout restart deployment -n "$NAMESPACE" postgres 2>/dev/null || \
    kubectl rollout restart statefulset -n "$NAMESPACE" postgres 2>/dev/null || \
    echo "Could not restart postgres (may be a different resource type)"
else
    echo "✓ Postgres is running"
fi

echo ""
echo "=== Final State ==="
kubectl get pods -n "$NAMESPACE" -o wide

echo ""
echo "✓ Reset complete. System should be back to normal."
