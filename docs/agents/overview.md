# Agents Overview

Agents are the autonomous units of OpenSRE that observe, reason, and act on your infrastructure.

## What is an Agent?

An agent is a configurable automation unit that:
- Listens for triggers (alerts, webhooks, schedules)
- Uses skills to gather information
- Follows runbooks to analyze and respond
- Takes actions (with appropriate approvals)

## Agent Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          Agent                                  │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────────┐ │
│  │ Trigger │───▶│ Observe │───▶│ Reason  │───▶│ Act/Notify  │ │
│  └─────────┘    └─────────┘    └─────────┘    └─────────────┘ │
│       │              │              │               │          │
│       ▼              ▼              ▼               ▼          │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │                    Skill Layer                           │  │
│  │  prometheus • kubernetes • slack • pagerduty • ...       │  │
│  └─────────────────────────────────────────────────────────┘  │
│       │              │              │               │          │
│       ▼              ▼              ▼               ▼          │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │                   Knowledge Layer                        │  │
│  │  runbooks • past incidents • patterns                    │  │
│  └─────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Agent Pipeline

### 1. Observer Phase

Gathers signals from connected systems:

```yaml
observe:
  - prometheus.query("rate(errors[5m])")
  - prometheus.query("avg(latency_seconds)")
  - kubernetes.get_pods(namespace="production")
  - kubernetes.get_events(namespace="production", limit=20)
```

### 2. Reasoner Phase

Analyzes gathered data to find root cause:

- Correlates metrics with events
- Compares with historical patterns
- Consults relevant runbooks
- Calculates confidence scores

### 3. Actor Phase

Proposes and executes remediation:

- Suggests actions based on analysis
- Requests human approval for risky actions
- Executes approved actions
- Verifies outcome

### 4. Notifier Phase

Keeps humans informed:

- Posts analysis to Slack/Teams
- Updates incident management tools
- Creates follow-up tickets
- Generates post-incident summaries

## Built-in Agents

### incident-responder

The general-purpose incident response agent.

```yaml
name: incident-responder
triggers:
  - type: prometheus_alert
  - type: pagerduty_webhook
skills:
  - prometheus
  - kubernetes
  - slack
```

**What it does:**
1. Receives alert
2. Queries relevant metrics and logs
3. Checks for recent deployments
4. Identifies root cause
5. Posts analysis to Slack
6. Suggests remediation
7. Executes approved actions

### pod-crash-handler

Specialized for handling crashing pods.

```yaml
name: pod-crash-handler
triggers:
  - type: prometheus_alert
    match: "PodCrashLooping|OOMKilled"
skills:
  - kubernetes
  - slack
```

**What it does:**
1. Gets pod details and logs
2. Identifies crash reason (OOM, config error, etc.)
3. Checks if caused by recent deployment
4. Suggests fix (rollback, resource increase, restart)

### cost-anomaly

Monitors for unexpected cost increases.

```yaml
name: cost-anomaly
schedule: "0 9 * * *"
skills:
  - aws
  - slack
```

**What it does:**
1. Gets daily cost report
2. Compares to baseline
3. Identifies anomalies
4. Posts summary to #finops

### deploy-validator

Validates deployments post-rollout.

```yaml
name: deploy-validator
triggers:
  - type: argocd_webhook
    event: sync_succeeded
skills:
  - argocd
  - prometheus
  - kubernetes
  - slack
```

**What it does:**
1. Waits for deployment stabilization
2. Checks error rates, latency, resource usage
3. Compares to pre-deployment baseline
4. Auto-rolls back if thresholds exceeded

## Agent Triggers

### Webhook Triggers

```yaml
triggers:
  - type: webhook
    source: alertmanager
    path: /webhook/alertmanager
  
  - type: pagerduty_webhook
    event: incident.triggered
  
  - type: argocd_webhook
    event: sync_succeeded
```

### Alert Triggers

```yaml
triggers:
  - type: prometheus_alert
    match: 'severity="critical"'
  
  - type: prometheus_alert
    alertname: HighErrorRate
```

### Schedule Triggers

```yaml
triggers:
  - type: schedule
    cron: "0 9 * * *"      # Daily at 9 AM
  
  - type: schedule
    cron: "*/5 * * * *"    # Every 5 minutes
```

### Manual Triggers

```yaml
triggers:
  - type: manual
    command: investigate
```

Invoked via:
```bash
opensre investigate "high error rate on checkout"
```

## Agent Memory

Agents maintain context between runs:

```yaml
memory:
  # Store past investigations
  store_incidents: true
  
  # Look for similar past incidents
  pattern_matching: true
  
  # Remember what worked before
  learn_from_outcomes: true
```

### Incident Correlation

When a new incident occurs, the agent:
1. Searches for similar past incidents
2. Shows what worked before
3. Adapts runbook based on history

## Agent Safety

### Approval Levels

```yaml
safety:
  # Auto-approve read operations
  auto_approve:
    - prometheus.query
    - kubernetes.get_*
    - slack.post_message
  
  # Require approval for modifications
  require_approval:
    - kubernetes.scale
    - kubernetes.rollback
    - kubernetes.delete_*
```

### Protected Resources

```yaml
safety:
  protected_namespaces:
    - production
    - kube-system
  
  protected_deployments:
    - payment-service
    - auth-service
```

### Dry-Run Mode

```yaml
safety:
  dry_run: true  # Show what would happen without executing
```

## Running Agents

### Daemon Mode

Run agents continuously:

```bash
# Start daemon
opensre start

# Start specific agents only
opensre start --agents incident-responder,pod-crash-handler

# Run in foreground
opensre start --foreground
```

### One-Shot Mode

Run a single investigation:

```bash
opensre investigate "high error rate on checkout service"
```

### Testing

```bash
# Test with synthetic alert
opensre agent test incident-responder --alert '{"alertname": "HighErrorRate"}'

# Dry-run mode
opensre agent test incident-responder --dry-run
```

## Agent Status

```bash
# Check agent status
opensre agent status

# Output:
# Agent                  Status    Last Run              Investigations
# incident-responder     running   2024-01-15 10:30:00   47
# pod-crash-handler      running   2024-01-15 10:28:00   12
# cost-anomaly          running   2024-01-15 09:00:00   30
```

## Next Steps

- **[Writing Agents](writing-agents.md)** — Create custom agents
- **[Agent Reference](agent-reference.md)** — Configuration reference
- **[Skills Overview](../skills/overview.md)** — Available skills
