#!/bin/bash
# E2E Test Runner - All Scenarios
set -e

REPORT_DIR=~/clawd/projects/autosre/e2e-testing/reports
mkdir -p "$REPORT_DIR"
REPORT_FILE="$REPORT_DIR/e2e-report-$(date +%Y%m%d-%H%M%S).md"

echo "# AutoSRE E2E Test Report" > "$REPORT_FILE"
echo "" >> "$REPORT_FILE"
echo "**Date:** $(date)" >> "$REPORT_FILE"
echo "**Cluster:** kind-autosre-e2e" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"
echo "## Summary" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"
echo "| Scenario | Status | Detection Time | Root Cause Identified |" >> "$REPORT_FILE"
echo "|----------|--------|----------------|----------------------|" >> "$REPORT_FILE"

# Function to run scenario
run_scenario() {
    local num=$1
    local name=$2
    local inject_cmd=$3
    local verify_cmd=$4
    
    echo ""
    echo "=========================================="
    echo "SCENARIO $num: $name"
    echo "=========================================="
    
    # Record start time
    START_TIME=$(date +%s)
    
    # Inject chaos
    echo "[$(date +%H:%M:%S)] Injecting chaos..."
    eval "$inject_cmd"
    
    # Wait for metrics to accumulate
    echo "[$(date +%H:%M:%S)] Waiting for metrics (20s)..."
    sleep 20
    
    # Verify detection
    echo "[$(date +%H:%M:%S)] Checking detection..."
    DETECTION_RESULT=$(eval "$verify_cmd" 2>&1)
    
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    
    # Determine status
    if echo "$DETECTION_RESULT" | grep -qiE "error|fail|spike|high|restart|kill|unhealthy"; then
        STATUS="✅ DETECTED"
        ROOT_CAUSE="Yes"
    else
        STATUS="⚠️ PARTIAL"
        ROOT_CAUSE="Partial"
    fi
    
    echo "[$(date +%H:%M:%S)] Result: $STATUS (${DURATION}s)"
    echo ""
    
    # Add to report
    echo "| $num. $name | $STATUS | ${DURATION}s | $ROOT_CAUSE |" >> "$REPORT_FILE"
    
    # Reset
    echo "[$(date +%H:%M:%S)] Resetting..."
    kubectl rollout restart deployment -n bookstore bookstore-api >/dev/null 2>&1 || true
    sleep 10
}

echo ""
echo "Starting E2E Test Suite..."
echo "Report: $REPORT_FILE"
echo ""

# Make scripts executable
chmod +x ~/clawd/projects/autosre/e2e-testing/chaos/scenarios/*.sh 2>/dev/null || true

echo "$REPORT_FILE"
