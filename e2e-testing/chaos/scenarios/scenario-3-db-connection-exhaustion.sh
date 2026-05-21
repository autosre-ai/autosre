#!/bin/bash
# Scenario 3: Database Connection Pool Exhaustion
# Purpose: Test AutoSRE detection of connection pool issues
# Expected: AutoSRE should detect connection timeouts and identify DB as bottleneck

set -e

NAMESPACE="${NAMESPACE:-bookstore}"
API_HOST="${API_HOST:-localhost:8080}"

echo "=== Scenario 3: Database Connection Pool Exhaustion ==="
echo "Exhausting connection pool..."

# Trigger connection pool exhaustion
kubectl exec -n "$NAMESPACE" deploy/bookstore-api -- \
    curl -s -X POST localhost:3000/chaos/db-exhaust

echo "Connection pool exhausted. Testing API responsiveness..."
echo ""

# Generate traffic to see connection errors
TIMEOUTS=0
ERRORS=0
SUCCESS=0

for i in {1..30}; do
    START=$(date +%s.%N)
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "http://${API_HOST}/books" || echo "000")
    END=$(date +%s.%N)
    DURATION=$(echo "$END - $START" | bc)
    
    if [[ "$HTTP_CODE" == "000" ]]; then
        ((TIMEOUTS++))
        echo "Request $i: TIMEOUT (${DURATION}s)"
    elif [[ "$HTTP_CODE" =~ ^5 ]]; then
        ((ERRORS++))
        echo "Request $i: ERROR $HTTP_CODE (${DURATION}s)"
    else
        ((SUCCESS++))
        echo "Request $i: OK $HTTP_CODE (${DURATION}s)"
    fi
    sleep 0.5
done

echo ""
echo "Connection exhaustion test complete:"
echo "  Success: $SUCCESS"
echo "  Errors: $ERRORS"
echo "  Timeouts: $TIMEOUTS"
echo ""
echo "Check application logs for connection pool errors:"
echo "  kubectl logs -n $NAMESPACE -l app=bookstore-api --tail=50"
