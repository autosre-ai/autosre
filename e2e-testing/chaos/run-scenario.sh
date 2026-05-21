#!/bin/bash
# Chaos Scenario Runner
# Usage: ./run-scenario.sh <scenario-number> [--no-wait] [--trigger-autosre]
#
# Examples:
#   ./run-scenario.sh 1                    # Run scenario 1, wait 30s
#   ./run-scenario.sh 3 --no-wait          # Run scenario 3, no waiting
#   ./run-scenario.sh 5 --trigger-autosre  # Run scenario 5, trigger AutoSRE

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCENARIOS_DIR="$SCRIPT_DIR/scenarios"

# Parse arguments
SCENARIO_NUM="$1"
WAIT_TIME=30
TRIGGER_AUTOSRE=false

shift || true
while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-wait)
            WAIT_TIME=0
            shift
            ;;
        --trigger-autosre)
            TRIGGER_AUTOSRE=true
            shift
            ;;
        --wait)
            WAIT_TIME="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Validate input
if [[ -z "$SCENARIO_NUM" ]]; then
    echo "Usage: $0 <scenario-number> [--no-wait] [--trigger-autosre] [--wait <seconds>]"
    echo ""
    echo "Available scenarios:"
    echo "  1 - High Error Rate (50%)"
    echo "  2 - OOM Kill"
    echo "  3 - Database Connection Exhaustion"
    echo "  4 - Cascade Failure (Database Down)"
    echo "  5 - Latency Spike"
    echo "  6 - CPU Throttling"
    exit 1
fi

# Find scenario script
SCENARIO_FILE=$(find "$SCENARIOS_DIR" -name "scenario-${SCENARIO_NUM}-*.sh" 2>/dev/null | head -1)

if [[ ! -f "$SCENARIO_FILE" ]]; then
    echo "Error: Scenario $SCENARIO_NUM not found"
    echo "Looking for: scenario-${SCENARIO_NUM}-*.sh in $SCENARIOS_DIR"
    exit 1
fi

SCENARIO_NAME=$(basename "$SCENARIO_FILE" .sh)

echo "╔════════════════════════════════════════════════════════════╗"
echo "║  CHAOS SCENARIO RUNNER                                      ║"
echo "╠════════════════════════════════════════════════════════════╣"
echo "║  Scenario: $SCENARIO_NAME"
echo "║  Wait Time: ${WAIT_TIME}s"
echo "║  Trigger AutoSRE: $TRIGGER_AUTOSRE"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Record start time
START_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "Start Time: $START_TIME"
echo ""

# Run the scenario
echo "Running scenario..."
echo "────────────────────────────────────────────────────────────────"
bash "$SCENARIO_FILE"
EXIT_CODE=$?
echo "────────────────────────────────────────────────────────────────"

if [[ $EXIT_CODE -ne 0 ]]; then
    echo "⚠ Scenario exited with code $EXIT_CODE"
fi

# Wait for metrics to accumulate
if [[ $WAIT_TIME -gt 0 ]]; then
    echo ""
    echo "Waiting ${WAIT_TIME}s for metrics to accumulate..."
    for i in $(seq $WAIT_TIME -10 1); do
        echo -ne "\r  ${i}s remaining...  "
        sleep $((i > 10 ? 10 : i))
    done
    echo -e "\r  Done!              "
fi

# Trigger AutoSRE if requested
if [[ "$TRIGGER_AUTOSRE" == "true" ]]; then
    echo ""
    echo "Triggering AutoSRE investigation..."
    
    END_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    
    # Try multiple methods to trigger AutoSRE
    if command -v autosre &>/dev/null; then
        autosre investigate --namespace bookstore --since "$START_TIME"
    elif [[ -f "$SCRIPT_DIR/../cli/autosre" ]]; then
        "$SCRIPT_DIR/../cli/autosre" investigate --namespace bookstore --since "$START_TIME"
    else
        echo "AutoSRE CLI not found. Manual trigger required:"
        echo "  autosre investigate --namespace bookstore --since $START_TIME"
    fi
fi

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║  SCENARIO COMPLETE                                          ║"
echo "╠════════════════════════════════════════════════════════════╣"
echo "║  Next steps:                                                ║"
echo "║  1. Check metrics/logs for chaos effects                   ║"
echo "║  2. Verify AutoSRE detection (if triggered)                ║"
echo "║  3. Run ./reset-all.sh to clean up                         ║"
echo "╚════════════════════════════════════════════════════════════╝"
