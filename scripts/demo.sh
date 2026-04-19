#!/bin/bash
# ============================================================================
# OpenSRE Demo Script
# 2-minute demo for video recording
# ============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Demo functions
print_step() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}▶ $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    sleep 1
}

type_command() {
    echo -e "${GREEN}\$ $1${NC}"
    sleep 0.5
}

# ============================================================================
# DEMO STARTS HERE
# ============================================================================

clear
echo ""
echo -e "${BLUE}"
echo "    ██████╗ ██████╗ ███████╗███╗   ██╗███████╗██████╗ ███████╗"
echo "   ██╔═══██╗██╔══██╗██╔════╝████╗  ██║██╔════╝██╔══██╗██╔════╝"
echo "   ██║   ██║██████╔╝█████╗  ██╔██╗ ██║███████╗██████╔╝█████╗  "
echo "   ██║   ██║██╔═══╝ ██╔══╝  ██║╚██╗██║╚════██║██╔══██╗██╔══╝  "
echo "   ╚██████╔╝██║     ███████╗██║ ╚████║███████║██║  ██║███████╗"
echo "    ╚═════╝ ╚═╝     ╚══════╝╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝╚══════╝"
echo -e "${NC}"
echo ""
echo -e "${YELLOW}   AI-Powered Incident Response — Stop Debugging at 3 AM${NC}"
echo ""
sleep 2

# Step 1: Install OpenSRE
print_step "Step 1: Install OpenSRE"
type_command "pip install opensre"
echo "Successfully installed opensre-0.1.0"
sleep 1

# Step 2: Configure
print_step "Step 2: Configure environment"
type_command "export OPENSRE_PROMETHEUS_URL=http://prometheus:9090"
type_command "export OPENSRE_LLM_PROVIDER=ollama"
type_command "opensre status"
echo ""
echo "OpenSRE v0.1.0"
echo ""
echo "✓ Prometheus    http://prometheus:9090    Connected"
echo "✓ Kubernetes    ~/.kube/config            Connected (3 nodes)"
echo "✓ LLM           ollama/llama3.1:8b        Ready"
echo "✓ Slack         #incidents                Connected"
echo ""
echo -e "${GREEN}Ready to investigate incidents!${NC}"
sleep 2

# Step 3: Install Skills
print_step "Step 3: Install skills"
type_command "opensre skill install prometheus kubernetes slack"
echo "✓ prometheus    v1.0.0    Installed"
echo "✓ kubernetes    v1.0.0    Installed"
echo "✓ slack         v1.0.0    Installed"
sleep 1

# Step 4: Create Agent
print_step "Step 4: Create an agent"
type_command "cat agents/incident-responder.yaml"
echo ""
cat << 'EOF'
name: incident-responder
skills:
  - prometheus
  - kubernetes
  - slack

triggers:
  - type: prometheus_alert
    match: 'severity="critical"'

runbook: |
  1. Query error metrics
  2. Check Kubernetes pods
  3. Identify root cause
  4. Post analysis to Slack
EOF
sleep 2

# Step 5: Start OpenSRE
print_step "Step 5: Start the agent daemon"
type_command "opensre start --foreground &"
echo "OpenSRE daemon started"
echo "Listening for alerts on :8000/webhook/alertmanager"
sleep 1

# Step 6: Trigger an alert
print_step "Step 6: Alert triggered! Let's see what happens..."
echo ""
echo -e "${RED}🚨 ALERT: HighErrorRate firing${NC}"
echo "   Service: checkout"
echo "   Namespace: production"
echo "   Error Rate: 8.3%"
sleep 2

# Step 7: Watch investigation
print_step "Step 7: OpenSRE investigates automatically"
echo ""
echo "⏳ Querying Prometheus metrics..."
sleep 1
echo "⏳ Checking Kubernetes pod health..."
sleep 1
echo "⏳ Analyzing recent deployments..."
sleep 1
echo "⏳ Correlating with past incidents..."
sleep 1
echo ""
echo -e "${GREEN}✓ Investigation complete (47 seconds)${NC}"
sleep 1

# Step 8: Show analysis
print_step "Step 8: Analysis posted to Slack"
echo ""
cat << 'EOF'
╭────────────────────────────────────────────────────────────────╮
│  🔍 OpenSRE Investigation                                       │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Alert: HighErrorRate on checkout service                      │
│  Duration: 47 seconds                                          │
│                                                                │
│  📊 Observations:                                               │
│  • Error rate: 0.1% → 8.3% (82x increase)                      │
│  • 3 pods showing OOMKilled restarts                           │
│  • Deployment v2.4.1 rolled out 12 min ago                     │
│                                                                │
│  🎯 Root Cause (94% confidence):                                │
│  Memory leak in checkout-v2.4.1                                │
│                                                                │
│  ✅ Recommended Action:                                         │
│  Rollback to checkout-v2.4.0                                   │
│                                                                │
│  [✅ Approve Rollback] [🔍 More Details] [❌ Dismiss]           │
│                                                                │
╰────────────────────────────────────────────────────────────────╯
EOF
sleep 3

# Step 9: Approve
print_step "Step 9: Human approves with one click"
echo ""
echo -e "${GREEN}✓ Rollback approved by @oncall${NC}"
echo ""
echo "⏳ Rolling back deployment/checkout to revision 4..."
sleep 1
echo -e "${GREEN}✓ Rollback complete${NC}"
echo ""
echo "Verifying..."
sleep 1
echo -e "${GREEN}✓ Error rate: 8.3% → 0.2%${NC}"
echo -e "${GREEN}✓ All pods healthy${NC}"
sleep 2

# Summary
print_step "Demo Complete!"
echo ""
echo "What just happened:"
echo ""
echo "  1. Alert fired → OpenSRE automatically started investigating"
echo "  2. Queried Prometheus, Kubernetes, and deployment history"
echo "  3. AI identified root cause with 94% confidence"
echo "  4. Posted analysis to Slack with approval buttons"
echo "  5. Human approved → OpenSRE executed rollback"
echo "  6. Incident resolved in under 2 minutes"
echo ""
echo -e "${YELLOW}Time saved: ~45 minutes${NC}"
echo -e "${YELLOW}Sleep preserved: ∞${NC}"
echo ""
echo -e "${BLUE}Learn more: https://opensre.dev${NC}"
echo ""
