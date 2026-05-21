#!/bin/bash
# Scenario 1: High Error Rate (50%)
# Purpose: Test AutoSRE detection of elevated error rates
# Expected: AutoSRE should detect 5xx spike and correlate with recent changes

set -e

NAMESPACE="${NAMESPACE:-bookstore}"
API_HOST="${API_HOST:-localhost:8080}"
ERROR_RATE="${ERROR_RATE:-0.5}"

echo "=== Scenario 1: High Error Rate ==="
echo "Injecting ${ERROR_RATE} ($(echo "$ERROR_RATE * 100" | bc)%) error rate..."

# Inject error rate via chaos endpoint
kubectl exec -n "$NAMESPACE" deploy/bookstore-api -- \
    curl -s -X POST "localhost:3000/chaos/error-rate?rate=${ERROR_RATE}"

echo "Error injection active. Generating traffic to trigger errors..."

# Generate traffic to trigger errors
ERRORS=0
SUCCESS=0
for i in {1..100}; do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://${API_HOST}/books" || echo "000")
    if [[ "$HTTP_CODE" =~ ^5 ]]; then
        ((ERRORS++))
    else
        ((SUCCESS++))
    fi
    # Small delay to avoid overwhelming
    sleep 0.1
done

echo ""
echo "Traffic generation complete:"
echo "  Success: $SUCCESS"
echo "  Errors: $ERRORS"
echo "  Error Rate: $(echo "scale=2; $ERRORS / 100 * 100" | bc)%"
echo ""
echo "Chaos injection active. Run reset-all.sh to clear."
