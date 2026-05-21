#!/bin/bash
# Scenario 6: CPU Throttling/Stress
# Purpose: Test AutoSRE detection of CPU saturation and throttling
# Expected: AutoSRE should detect high CPU usage, throttling, and degraded response times

set -e

NAMESPACE="${NAMESPACE:-bookstore}"
API_HOST="${API_HOST:-localhost:8080}"
STRESS_DURATION="${STRESS_DURATION:-60}"

echo "=== Scenario 6: CPU Throttling ==="
echo "Starting CPU stress test..."

# Get baseline metrics
echo "Checking initial CPU state:"
kubectl top pod -n "$NAMESPACE" -l app=bookstore-api 2>/dev/null || echo "(metrics-server may not be available)"
echo ""

# Start CPU stress
kubectl exec -n "$NAMESPACE" deploy/bookstore-api -- \
    curl -s -X POST localhost:3000/chaos/cpu-stress

echo "CPU stress activated."
echo ""

# Monitor for a bit
echo "Monitoring CPU usage for 30 seconds..."
for i in {1..6}; do
    echo "--- Check $i/6 ---"
    kubectl top pod -n "$NAMESPACE" -l app=bookstore-api 2>/dev/null || echo "(metrics unavailable)"
    
    # Also test response time
    START=$(date +%s.%N)
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "http://${API_HOST}/books" || echo "000")
    END=$(date +%s.%N)
    DURATION=$(echo "($END - $START) * 1000" | bc | cut -d. -f1)
    echo "API response: HTTP $HTTP_CODE in ${DURATION}ms"
    echo ""
    
    sleep 5
done

echo "CPU stress test monitoring complete."
echo ""
echo "Check for throttling in pod describe:"
echo "  kubectl describe pod -n $NAMESPACE -l app=bookstore-api | grep -A5 'Conditions'"
echo ""
echo "Chaos injection may still be active. Run reset-all.sh to clear."
