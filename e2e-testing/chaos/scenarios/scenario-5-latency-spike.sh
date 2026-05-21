#!/bin/bash
# Scenario 5: Latency Spike
# Purpose: Test AutoSRE detection of latency degradation
# Expected: AutoSRE should detect p99 latency spike and identify affected endpoints

set -e

NAMESPACE="${NAMESPACE:-bookstore}"
API_HOST="${API_HOST:-localhost:8080}"
LATENCY_MS="${LATENCY_MS:-2000}"

echo "=== Scenario 5: Latency Spike ==="
echo "Injecting ${LATENCY_MS}ms latency..."

# Add latency
kubectl exec -n "$NAMESPACE" deploy/bookstore-api -- \
    curl -s -X POST "localhost:3000/chaos/latency?ms=${LATENCY_MS}"

echo "Latency injection active. Generating traffic to measure impact..."
echo ""

# Generate traffic and measure latency
TOTAL_TIME=0
REQUESTS=20

echo "Making $REQUESTS requests (expecting ~${LATENCY_MS}ms each):"
echo ""

for i in $(seq 1 $REQUESTS); do
    START=$(date +%s.%N)
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "http://${API_HOST}/books" || echo "000")
    END=$(date +%s.%N)
    DURATION=$(echo "($END - $START) * 1000" | bc | cut -d. -f1)
    TOTAL_TIME=$((TOTAL_TIME + DURATION))
    
    if [[ "$HTTP_CODE" == "200" ]]; then
        echo "Request $i: ${DURATION}ms (HTTP $HTTP_CODE)"
    else
        echo "Request $i: ${DURATION}ms (HTTP $HTTP_CODE) ⚠"
    fi
done

AVG_LATENCY=$((TOTAL_TIME / REQUESTS))

echo ""
echo "Latency test complete:"
echo "  Total requests: $REQUESTS"
echo "  Total time: ${TOTAL_TIME}ms"
echo "  Average latency: ${AVG_LATENCY}ms"
echo "  Expected baseline: ~${LATENCY_MS}ms (injected)"
echo ""
echo "Chaos injection active. Run reset-all.sh to clear."
