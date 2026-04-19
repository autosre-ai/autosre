#!/bin/bash
#
# Deploy/Cleanup Test Scenarios for OpenSRE Integration Tests
#
# Usage:
#   ./deploy_scenarios.sh deploy [namespace]   - Deploy all test workloads
#   ./deploy_scenarios.sh cleanup [namespace]  - Remove all test workloads
#   ./deploy_scenarios.sh status [namespace]   - Check status of test pods
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
EXAMPLES_DIR="$PROJECT_ROOT/examples"

ACTION=${1:-deploy}
NAMESPACE=${2:-default}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if kubectl is available
check_kubectl() {
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl not found. Please install kubectl first."
        exit 1
    fi
    
    # Check if cluster is accessible
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to Kubernetes cluster. Is minikube running?"
        echo "Try: minikube start"
        exit 1
    fi
}

# Create namespace if it doesn't exist
ensure_namespace() {
    if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
        log_info "Creating namespace: $NAMESPACE"
        kubectl create namespace "$NAMESPACE"
    fi
}

# Deploy all test workloads
deploy() {
    log_info "Deploying test scenarios to namespace: $NAMESPACE"
    
    ensure_namespace
    
    # Deploy each manifest
    for manifest in "$EXAMPLES_DIR"/*.yaml; do
        if [[ -f "$manifest" ]]; then
            filename=$(basename "$manifest")
            log_info "Deploying: $filename"
            kubectl apply -f "$manifest" -n "$NAMESPACE" || log_warn "Failed to deploy $filename"
        fi
    done
    
    log_info "Waiting for pods to stabilize..."
    sleep 10
    
    # Wait for pods to be in Running or CrashLoopBackOff state
    log_info "Checking pod status..."
    
    max_wait=60
    waited=0
    while [[ $waited -lt $max_wait ]]; do
        # Count pods that are not yet ready
        pending=$(kubectl get pods -n "$NAMESPACE" --no-headers 2>/dev/null | grep -c "Pending" || true)
        container_creating=$(kubectl get pods -n "$NAMESPACE" --no-headers 2>/dev/null | grep -c "ContainerCreating" || true)
        
        if [[ $pending -eq 0 && $container_creating -eq 0 ]]; then
            log_info "All pods have started"
            break
        fi
        
        echo -n "."
        sleep 5
        waited=$((waited + 5))
    done
    echo ""
    
    # Additional wait for crashloop and OOM to trigger
    log_info "Waiting additional 20s for failure conditions to manifest..."
    sleep 20
    
    # Show final status
    status
}

# Clean up all test workloads
cleanup() {
    log_info "Cleaning up test scenarios from namespace: $NAMESPACE"
    
    for manifest in "$EXAMPLES_DIR"/*.yaml; do
        if [[ -f "$manifest" ]]; then
            filename=$(basename "$manifest")
            log_info "Removing: $filename"
            kubectl delete -f "$manifest" -n "$NAMESPACE" --ignore-not-found=true || true
        fi
    done
    
    log_info "Cleanup complete"
}

# Check status of test pods
status() {
    log_info "Pod status in namespace: $NAMESPACE"
    echo ""
    kubectl get pods -n "$NAMESPACE" -o wide
    echo ""
    
    # Show events for any non-running pods
    non_running=$(kubectl get pods -n "$NAMESPACE" --no-headers 2>/dev/null | grep -v "Running" | awk '{print $1}' || true)
    
    if [[ -n "$non_running" ]]; then
        log_info "Events for non-running pods:"
        for pod in $non_running; do
            echo -e "\n${YELLOW}=== $pod ===${NC}"
            kubectl get events -n "$NAMESPACE" --field-selector "involvedObject.name=$pod" --sort-by='.lastTimestamp' | tail -5
        done
    fi
}

# Reset (cleanup + deploy)
reset() {
    cleanup
    sleep 5
    deploy
}

# Main
case "$ACTION" in
    deploy)
        check_kubectl
        deploy
        ;;
    cleanup)
        check_kubectl
        cleanup
        ;;
    status)
        check_kubectl
        status
        ;;
    reset)
        check_kubectl
        reset
        ;;
    *)
        echo "Usage: $0 {deploy|cleanup|status|reset} [namespace]"
        echo ""
        echo "Actions:"
        echo "  deploy   - Deploy all test workloads"
        echo "  cleanup  - Remove all test workloads"
        echo "  status   - Check status of test pods"
        echo "  reset    - Cleanup and redeploy"
        echo ""
        echo "Default namespace: default"
        exit 1
        ;;
esac
