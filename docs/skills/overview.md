# Skills Overview

Skills are the building blocks of OpenSRE. They provide the actions that agents use to observe, reason, and act on your infrastructure.

## What is a Skill?

A skill is a self-contained module that:
- Connects to a specific system (Prometheus, Kubernetes, AWS, etc.)
- Provides actions that agents can invoke
- Handles authentication and error handling
- Includes documentation and tests

## Skill Architecture

```
skills/
├── prometheus/
│   ├── SKILL.md         # Documentation
│   ├── skill.yaml       # Metadata
│   ├── actions.py       # Action implementations
│   ├── schemas.py       # Input/output schemas
│   └── tests/
│       └── test_prometheus.py
├── kubernetes/
│   └── ...
└── slack/
    └── ...
```

## Core Skills

These skills are included with OpenSRE:

### Prometheus

Query metrics, manage alerts, and silence notifications.

```yaml
skill: prometheus
actions:
  - query          # Execute PromQL query
  - query_range    # Query over time range
  - alerts         # Get active alerts
  - silence        # Create silence
  - targets        # List scrape targets
```

**Example:**

```python
# Query current error rate
result = await prometheus.query(
    query='rate(http_requests_total{status=~"5.."}[5m])'
)

# Get alerts matching pattern
alerts = await prometheus.alerts(
    match='severity="critical"'
)
```

### Kubernetes

Inspect and manage Kubernetes resources.

```yaml
skill: kubernetes
actions:
  - get_pods         # List/get pods
  - get_deployments  # List/get deployments
  - get_events       # Get recent events
  - get_logs         # Fetch pod logs
  - describe         # Describe any resource
  - scale            # Scale deployment
  - rollback         # Rollback deployment
  - restart          # Restart deployment
  - delete_pod       # Delete pod
```

**Example:**

```python
# Get crashing pods
pods = await kubernetes.get_pods(
    namespace="production",
    field_selector="status.phase=Failed"
)

# Get recent events for a pod
events = await kubernetes.get_events(
    namespace="production",
    resource="pod/checkout-abc123"
)

# Rollback deployment
await kubernetes.rollback(
    deployment="checkout-service",
    namespace="production",
    revision=2  # Optional, defaults to previous
)
```

### Slack

Send messages and interactive notifications.

```yaml
skill: slack
actions:
  - post_message    # Send message
  - post_thread     # Reply in thread
  - post_blocks     # Send rich message
  - react           # Add reaction
  - update_message  # Update existing message
```

**Example:**

```python
# Post analysis with approval buttons
await slack.post_blocks(
    channel="#incidents",
    blocks=[
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*Root Cause Found*\nMemory leak in v2.4.1"}
        },
        {
            "type": "actions",
            "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "✅ Approve Rollback"}, "action_id": "approve"},
                {"type": "button", "text": {"type": "plain_text", "text": "❌ Dismiss"}, "action_id": "dismiss"}
            ]
        }
    ]
)
```

## Installing Skills

### List Available Skills

```bash
opensre skill list

# Output:
# Installed:
#   ✓ prometheus      Query metrics, manage alerts
#   ✓ kubernetes      Manage K8s resources
#   ✓ slack           Slack notifications
#
# Available:
#   • datadog         Datadog metrics and monitors
#   • pagerduty       Incident management
#   • aws             AWS resource management
#   • gcp             GCP resource management
```

### Install a Skill

```bash
# Install from registry
opensre skill install pagerduty

# Install from URL
opensre skill install https://github.com/example/opensre-skill-custom.git

# Install from local path
opensre skill install ./my-skill
```

### Configure a Skill

After installation, configure the skill:

```bash
# Interactive setup
opensre skill configure pagerduty

# Or set environment variables
export OPENSRE_PAGERDUTY_API_KEY=your-key
export OPENSRE_PAGERDUTY_ROUTING_KEY=your-routing-key
```

### Test a Skill

```bash
# Run skill tests
opensre skill test prometheus

# Test specific action
opensre skill test prometheus --action query
```

## Using Skills in Agents

Skills are referenced in agent configurations:

```yaml
# agents/my-agent.yaml
name: my-agent
skills:
  - prometheus
  - kubernetes
  - slack
```

In runbooks, reference actions:

```yaml
runbook: |
  1. Query error rate: prometheus.query("rate(errors[5m])")
  2. Get failing pods: kubernetes.get_pods(status="Failed")
  3. Notify team: slack.post_message(channel="#alerts")
```

## Skill Categories

### Observability

| Skill | Description |
|-------|-------------|
| `prometheus` | Prometheus metrics and alerts |
| `datadog` | Datadog metrics and monitors |
| `grafana` | Grafana dashboards |
| `elastic` | Elasticsearch/Kibana |
| `cloudwatch` | AWS CloudWatch |
| `stackdriver` | GCP Cloud Monitoring |

### Infrastructure

| Skill | Description |
|-------|-------------|
| `kubernetes` | Kubernetes resources |
| `docker` | Docker containers |
| `terraform` | Infrastructure as code |
| `ansible` | Configuration management |

### Cloud Providers

| Skill | Description |
|-------|-------------|
| `aws` | AWS services (EC2, RDS, etc.) |
| `gcp` | GCP services |
| `azure` | Azure services |

### Incident Management

| Skill | Description |
|-------|-------------|
| `pagerduty` | PagerDuty incidents |
| `opsgenie` | OpsGenie alerts |
| `servicenow` | ServiceNow tickets |

### Communication

| Skill | Description |
|-------|-------------|
| `slack` | Slack messaging |
| `teams` | Microsoft Teams |
| `telegram` | Telegram notifications |

### CI/CD

| Skill | Description |
|-------|-------------|
| `github` | GitHub Issues/PRs/Actions |
| `gitlab` | GitLab pipelines |
| `argocd` | Argo CD deployments |
| `jenkins` | Jenkins jobs |

## Skill Permissions

Skills have permission levels that control what actions can be auto-approved:

```yaml
# skill.yaml
permissions:
  read:
    - query
    - get_*
    - list_*
    - describe
  write:
    - post_message
    - update_*
  destructive:
    - delete_*
    - rollback
    - terminate
```

In your safety config:

```yaml
# config/safety.yaml
safety:
  auto_approve:
    - "prometheus.read.*"
    - "kubernetes.read.*"
    - "slack.write.*"
  require_approval:
    - "*.destructive.*"
```

## Next Steps

- **[Creating Skills](creating-skills.md)** — Write your own skills
- **[Skill Reference](skill-reference.md)** — Detailed action documentation
- **[Agent Configuration](../agents/overview.md)** — Use skills in agents
