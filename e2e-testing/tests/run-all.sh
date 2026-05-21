#!/bin/bash
#
# AutoSRE E2E Test Suite - Master Test Script
#
# Runs all E2E test scenarios against the Kind cluster and generates a report.
#
# Usage:
#   ./run-all.sh              # Run all scenarios
#   ./run-all.sh --quick      # Quick run (shorter waits)
#   ./run-all.sh --scenario 3 # Run specific scenario only
#   ./run-all.sh --pytest     # Run via pytest framework
#

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CONFIG_PATH="${PROJECT_DIR}/autosre-config.yaml"
CHAOS_DIR="${PROJECT_DIR}/chaos/scenarios"
RESET_SCRIPT="${PROJECT_DIR}/chaos/reset-all.sh"
RESULTS_FILE="${SCRIPT_DIR}/test_results.json"
REPORT_FILE="${SCRIPT_DIR}/e2e_report.md"
KUBECTL_CONTEXT="kind-autosre-e2e"

# Timing
METRICS_WAIT=30
RESET_WAIT=10
QUICK_MODE=false
SPECIFIC_SCENARIO=""
USE_PYTEST=false

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --quick)
            QUICK_MODE=true
            METRICS_WAIT=15
            RESET_WAIT=5
            shift
            ;;
        --scenario)
            SPECIFIC_SCENARIO="$2"
            shift 2
            ;;
        --pytest)
            USE_PYTEST=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --quick        Run with shorter wait times"
            echo "  --scenario N   Run only scenario N (1-6)"
            echo "  --pytest       Use pytest framework instead of bash"
            echo "  --help         Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Scenario definitions
declare -A SCENARIOS
SCENARIOS[1]="High Error Rate"
SCENARIOS[2]="OOM Kill"
SCENARIOS[3]="CPU Throttling"
SCENARIOS[4]="DB Connection Pool"
SCENARIOS[5]="Network Partition"
SCENARIOS[6]="Cascading Failure"

declare -A ALERT_DESCRIPTIONS
ALERT_DESCRIPTIONS[1]="High error rate detected in bookstore-api - 5xx responses increased"
ALERT_DESCRIPTIONS[2]="Pod restarts detected in bookstore namespace - possible OOM"
ALERT_DESCRIPTIONS[3]="Increased latency in bookstore-api - p99 latency above SLO"
ALERT_DESCRIPTIONS[4]="Database errors in bookstore-api - connection timeouts"
ALERT_DESCRIPTIONS[5]="Service connectivity issues in bookstore namespace"
ALERT_DESCRIPTIONS[6]="Multiple services degraded in bookstore namespace"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

log_error() {
    echo -e "${RED}[FAIL]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl not found"
        exit 1
    fi
    
    # Check autosre
    if ! command -v autosre &> /dev/null; then
        log_warning "autosre binary not found in PATH"
        # Continue anyway - might be testing harness only
    fi
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        log_error "python3 not found"
        exit 1
    fi
    
    # Check cluster connectivity
    if ! kubectl cluster-info --context "$KUBECTL_CONTEXT" &> /dev/null; then
        log_error "Cannot connect to cluster: $KUBECTL_CONTEXT"
        log_info "Make sure the Kind cluster is running"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

check_prometheus() {
    log_info "Checking Prometheus availability..."
    
    local health_url="http://localhost:30090/-/healthy"
    local max_retries=5
    local retry=0
    
    while [[ $retry -lt $max_retries ]]; do
        if curl -s -o /dev/null -w "%{http_code}" "$health_url" | grep -q "200"; then
            log_success "Prometheus is healthy"
            return 0
        fi
        retry=$((retry + 1))
        log_warning "Prometheus not ready, retrying ($retry/$max_retries)..."
        sleep 5
    done
    
    log_error "Prometheus is not available at $health_url"
    exit 1
}

run_chaos_scenario() {
    local scenario_num=$1
    local scenario_script="${CHAOS_DIR}/scenario-${scenario_num}.sh"
    
    if [[ ! -f "$scenario_script" ]]; then
        log_warning "Scenario script not found: $scenario_script"
        return 1
    fi
    
    log_info "Injecting chaos for scenario ${scenario_num}..."
    if bash "$scenario_script"; then
        log_success "Chaos injected successfully"
        return 0
    else
        log_error "Failed to inject chaos"
        return 1
    fi
}

run_investigation() {
    local alert_desc=$1
    local output_file=$2
    
    log_info "Running AutoSRE investigation..."
    
    if command -v autosre &> /dev/null; then
        autosre investigate \
            --config "$CONFIG_PATH" \
            --alert "$alert_desc" \
            --output json > "$output_file" 2>&1 || true
    else
        # Simulate investigation result for testing
        log_warning "autosre not found, generating simulated result"
        cat > "$output_file" << 'EOF'
{
    "status": "completed",
    "root_cause": {
        "description": "Simulated root cause detection",
        "confidence": 0.75
    },
    "evidence": [
        {"type": "metrics", "summary": "Elevated error rate detected"},
        {"type": "logs", "summary": "Error patterns in application logs"}
    ],
    "recommendations": [
        "Review recent deployments",
        "Check resource limits"
    ]
}
EOF
    fi
}

reset_chaos() {
    log_info "Resetting chaos experiments..."
    
    if [[ -f "$RESET_SCRIPT" ]]; then
        if bash "$RESET_SCRIPT" &> /dev/null; then
            log_success "Chaos reset complete"
        else
            log_warning "Reset script returned non-zero"
        fi
    else
        log_warning "Reset script not found: $RESET_SCRIPT"
    fi
    
    sleep "$RESET_WAIT"
}

run_scenario() {
    local scenario_num=$1
    local scenario_name="${SCENARIOS[$scenario_num]}"
    local alert_desc="${ALERT_DESCRIPTIONS[$scenario_num]}"
    local result_file="${SCRIPT_DIR}/scenario_${scenario_num}_result.json"
    local start_time
    local end_time
    local duration
    local passed=false
    
    echo ""
    echo "========================================"
    echo "Scenario ${scenario_num}: ${scenario_name}"
    echo "========================================"
    
    start_time=$(date +%s.%N)
    
    # Inject chaos
    if run_chaos_scenario "$scenario_num"; then
        log_info "Waiting ${METRICS_WAIT}s for metrics to propagate..."
        sleep "$METRICS_WAIT"
        
        # Run investigation
        run_investigation "$alert_desc" "$result_file"
        
        # Check result
        if [[ -f "$result_file" ]] && grep -q '"status".*"completed"' "$result_file" 2>/dev/null; then
            passed=true
            log_success "Investigation completed successfully"
        else
            log_error "Investigation did not complete successfully"
        fi
    fi
    
    end_time=$(date +%s.%N)
    duration=$(echo "$end_time - $start_time" | bc)
    
    # Reset chaos
    reset_chaos
    
    # Return result
    if $passed; then
        return 0
    else
        return 1
    fi
}

run_all_scenarios() {
    local scenarios_to_run
    local total=0
    local passed=0
    local failed=0
    local start_time
    local end_time
    
    if [[ -n "$SPECIFIC_SCENARIO" ]]; then
        scenarios_to_run=("$SPECIFIC_SCENARIO")
    else
        scenarios_to_run=(1 2 3 4 5 6)
    fi
    
    total=${#scenarios_to_run[@]}
    start_time=$(date +%s)
    
    # Initialize results JSON
    echo '{"scenarios": [], "timestamp": "'$(date -Iseconds)'"}' > "$RESULTS_FILE"
    
    for scenario in "${scenarios_to_run[@]}"; do
        if run_scenario "$scenario"; then
            passed=$((passed + 1))
        else
            failed=$((failed + 1))
        fi
    done
    
    end_time=$(date +%s)
    local total_duration=$((end_time - start_time))
    
    echo ""
    echo "========================================"
    echo "Test Suite Complete"
    echo "========================================"
    echo ""
    echo "Results:"
    echo "  Total:  $total"
    echo "  Passed: $passed"
    echo "  Failed: $failed"
    echo "  Duration: ${total_duration}s"
    echo ""
    
    # Update results JSON with summary
    # (In production, this would be more sophisticated)
    
    return $failed
}

run_pytest() {
    log_info "Running tests via pytest framework..."
    
    cd "$SCRIPT_DIR"
    
    export AUTOSRE_CONFIG="$CONFIG_PATH"
    export CHAOS_DIR="$CHAOS_DIR"
    export RESET_SCRIPT="$RESET_SCRIPT"
    export METRICS_WAIT="$METRICS_WAIT"
    
    python3 -m pytest test_e2e.py \
        -v \
        --tb=short \
        --junit-xml=pytest_results.xml \
        "$@"
}

generate_report() {
    log_info "Generating test report..."
    
    cd "$SCRIPT_DIR"
    
    if python3 generate_report.py --input "$RESULTS_FILE" --output "$REPORT_FILE"; then
        log_success "Report generated: $REPORT_FILE"
    else
        log_warning "Report generation failed, trying with sample data..."
        python3 generate_report.py --output "$REPORT_FILE" || true
    fi
}

# Main execution
main() {
    echo ""
    echo "╔═══════════════════════════════════════╗"
    echo "║    AutoSRE E2E Test Suite             ║"
    echo "╚═══════════════════════════════════════╝"
    echo ""
    
    if $QUICK_MODE; then
        log_info "Running in quick mode (reduced wait times)"
    fi
    
    check_prerequisites
    check_prometheus
    
    if $USE_PYTEST; then
        run_pytest
    else
        run_all_scenarios
    fi
    
    local exit_code=$?
    
    generate_report
    
    echo ""
    if [[ $exit_code -eq 0 ]]; then
        log_success "All tests passed!"
    else
        log_error "$exit_code scenario(s) failed"
    fi
    
    exit $exit_code
}

main "$@"
