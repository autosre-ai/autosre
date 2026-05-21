#!/bin/bash
# Scenario 2: OOM Kill
# Purpose: Test AutoSRE detection of memory exhaustion and pod restarts
# Expected: AutoSRE should detect OOMKilled pods and identify memory leak pattern

set -e

NAMESPACE="${NAMESPACE:-bookstore}"
WATCH_TIMEOUT="${WATCH_TIMEOUT:-120}"

echo "=== Scenario 2: OOM Kill ==="
echo "Starting memory leak in bookstore-api..."

# Get current restart count for comparison
INITIAL_RESTARTS=$(kubectl get pods -n "$NAMESPACE" -l app=bookstore-api \
    -o jsonpath='{.items[0].status.containerStatuses[0].restartCount}' 2>/dev/null || echo "0")

echo "Initial restart count: $INITIAL_RESTARTS"

# Start memory leak
kubectl exec -n "$NAMESPACE" deploy/bookstore-api -- \
    curl -s -X POST localhost:3000/chaos/memory-leak

echo "Memory leak activated. Watching for OOMKill..."
echo "(This may take 1-2 minutes depending on memory limits)"
echo ""

# Watch for pod events (timeout after WATCH_TIMEOUT seconds)
echo "Monitoring pods for ${WATCH_TIMEOUT}s..."
timeout "$WATCH_TIMEOUT" kubectl get pods -n "$NAMESPACE" -l app=bookstore-api -w &
WATCH_PID=$!

# Also watch events
kubectl get events -n "$NAMESPACE" --field-selector reason=OOMKilling -w &
EVENTS_PID=$!

# Wait for watch to complete or timeout
wait $WATCH_PID 2>/dev/null || true
kill $EVENTS_PID 2>/dev/null || true

echo ""
echo "Checking final state..."
kubectl get pods -n "$NAMESPACE" -l app=bookstore-api -o wide

FINAL_RESTARTS=$(kubectl get pods -n "$NAMESPACE" -l app=bookstore-api \
    -o jsonpath='{.items[0].status.containerStatuses[0].restartCount}' 2>/dev/null || echo "0")

if [[ "$FINAL_RESTARTS" -gt "$INITIAL_RESTARTS" ]]; then
    echo ""
    echo "✓ OOM detected! Pod restarted $((FINAL_RESTARTS - INITIAL_RESTARTS)) time(s)"
else
    echo ""
    echo "⚠ No OOM detected yet. May need more time or higher memory pressure."
fi
