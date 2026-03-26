# Change Detector Agent

Track infrastructure changes, detect configuration drift, and correlate changes with incidents.

## Overview

The Change Detector agent monitors multiple change sources (Kubernetes, Terraform, Git) to track infrastructure changes, detect high-risk modifications, and correlate changes with incidents.

## Features

- **Multi-source Change Tracking** - Kubernetes, Terraform, Git
- **High-Risk Change Detection** - Pattern-based risk identification
- **Configuration Drift Detection** - Terraform state drift
- **Incident Correlation** - Link changes to subsequent incidents
- **Change Window Enforcement** - Alert on out-of-window changes
- **AI Analysis** - Intelligent change impact assessment

## Configuration

```yaml
config:
  slack_channel: "#infrastructure-changes"
  change_sources:
    kubernetes:
      enabled: true
      namespaces: ["production", "staging"]
      watch_resources:
        - deployments
        - configmaps
        - secrets
    terraform:
      enabled: true
      state_bucket: "s3://company-terraform-state"
    git:
      enabled: true
      repositories:
        - "github.com/company/infrastructure"
  correlation:
    enabled: true
    lookback_minutes: 60
  change_window:
    enabled: true
    allowed_hours: [9, 10, 11, 14, 15, 16]
    timezone: "America/Los_Angeles"
  high_risk_changes:
    - pattern: "replicas.*0"
      description: "Scale to zero"
    - pattern: "image.*:latest"
      description: "Latest tag deployment"
```

## Change Sources

### Kubernetes
- Deployment changes (replicas, images, env vars)
- ConfigMap modifications
- Secret updates
- Service/Ingress changes
- Warning events

### Terraform
- State drift detection
- Resource additions/deletions
- Configuration changes

### Git
- Infrastructure repository commits
- Kubernetes manifest changes
- Configuration file updates

## High-Risk Patterns

| Pattern | Risk | Description |
|---------|------|-------------|
| `replicas.*0` | High | Scaling to zero pods |
| `image.*:latest` | Medium | Using latest tag |
| `privileged.*true` | Critical | Privileged containers |
| `hostNetwork.*true` | Critical | Host network access |

## Triggers

- **Schedule**: Every 15 minutes
- **Manual**: `/webhook/change-detect`
- **Kubernetes**: `/webhook/k8s-change`

## Alert Examples

### High-Risk Change
```
⚠️ High-Risk Changes Detected

2 high-risk change(s):

• Scale to zero
  Resource: deployment/api-server
  Pattern: replicas.*0

• Latest tag deployment
  Resource: deployment/worker
  Pattern: image.*:latest

AI Analysis:
Scaling api-server to 0 replicas will cause complete 
service outage. The worker deployment with :latest tag
may introduce untested changes.
```

### Change-Incident Correlation
```
🔗 Changes Correlated with Incidents

Potential change-induced incidents:

• Change: deployment/payment-service
  Time: 2024-01-15 10:30:00
  User: deploy-bot

  Incident: PaymentServiceHighErrorRate
  Fired: 5 minutes after change

Consider rolling back recent changes if incidents persist
```

## Change Windows

When enabled, alerts on changes outside approved hours:

```
🚨 Change Window Violation

Changes detected outside of approved change window!

Current hour: 22
Allowed hours: 9, 10, 11, 14, 15, 16

Changes:
• deployment/api-server by john@example.com
```

## Metrics

| Metric | Description |
|--------|-------------|
| `opensre_changes_total` | Total changes detected |
| `opensre_changes_high_risk` | High-risk changes |
| `opensre_changes_correlated_incidents` | Changes linked to incidents |

## Prerequisites

- Kubernetes cluster access
- Terraform state access (for drift detection)
- Git repository access
- Prometheus for incident correlation

## Usage

```bash
# Run change detection
opensre agent run agents/change-detector/agent.yaml

# Dry run
opensre agent run agents/change-detector/agent.yaml --dry-run

# Specific namespace
opensre agent run agents/change-detector/agent.yaml \
  -c "config.change_sources.kubernetes.namespaces=['production']"
```

## Related Agents

- [deploy-validator](../deploy-validator/) - Validate deployments post-change
- [incident-responder](../incident-responder/) - Respond to change-induced incidents
- [security-scanner](../security-scanner/) - Scan for security-relevant changes
