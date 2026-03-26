# OpenSRE Agent Catalog

Pre-built agent templates for common SRE automation scenarios.

## Overview

| Agent | Description | Triggers | Primary Skills |
|-------|-------------|----------|----------------|
| [incident-responder](#incident-responder) | Auto-responds to production incidents | Webhook (PagerDuty, Alertmanager) | prometheus, kubernetes, slack, pagerduty |
| [pod-crash-handler](#pod-crash-handler) | Handles pod crashes with analysis | Webhook/Event (Kubernetes) | kubernetes, slack, prometheus, llm |
| [cost-anomaly](#cost-anomaly) | Daily cost monitoring with anomaly detection | Schedule (daily) | cloud-cost, prometheus, slack |
| [cert-checker](#cert-checker) | SSL certificate expiry monitoring | Schedule (daily) | ssl, kubernetes, slack, pagerduty |
| [deploy-validator](#deploy-validator) | Post-deployment health validation | Webhook (K8s, ArgoCD) | kubernetes, prometheus, http, slack |
| [capacity-planner](#capacity-planner) | Weekly capacity analysis and forecasting | Schedule (weekly) | prometheus, kubernetes, slack, llm |
| [runbook-executor](#runbook-executor) | Generic runbook execution engine | Webhook, Slack | runbook, kubernetes, ssh, slack |

---

## Incident Responder

**Path:** `incident-responder/`

Auto-responds to production incidents with automatic acknowledgment, context gathering, and team notification.

### Key Features
- Auto-acknowledges PagerDuty incidents
- Gathers Prometheus metrics context
- Checks Kubernetes pod/deployment status
- Creates incident channels for critical issues
- Posts comprehensive Slack summaries

### Triggers
| Type | Source | Events |
|------|--------|--------|
| Webhook | PagerDuty | `incident.triggered`, `incident.escalated` |
| Webhook | Alertmanager | `alert.firing` |

### Quick Start
```bash
# Deploy agent
opensre agent deploy incident-responder/

# Configure
opensre agent config incident-responder \
  --set slack_channel="#incidents" \
  --set auto_ack=true
```

---

## Pod Crash Handler

**Path:** `pod-crash-handler/`

Automatically handles Kubernetes pod crashes with log collection, analysis, and optional recovery actions.

### Key Features
- Collects pod logs and events
- LLM-powered crash analysis
- Auto-restart for recoverable crashes
- Auto-rollback when threshold exceeded
- Creates Jira tickets for severe issues

### Triggers
| Type | Source | Events |
|------|--------|--------|
| Webhook | Kubernetes | `Warning.CrashLoopBackOff` |
| Event | Kubernetes | Pod status watching |

### Quick Start
```bash
# Deploy agent
opensre agent deploy pod-crash-handler/

# Configure
opensre agent config pod-crash-handler \
  --set max_restart_attempts=3 \
  --set auto_rollback=false
```

---

## Cost Anomaly Detector

**Path:** `cost-anomaly/`

Daily cost monitoring that compares cloud spend against baseline and alerts on anomalies.

### Key Features
- Multi-cloud cost aggregation (AWS, GCP)
- Z-score anomaly detection
- Breakdown by service/team/environment
- Resource change correlation
- Cost trend visualization

### Triggers
| Type | Schedule |
|------|----------|
| Cron | `0 9 * * *` (Daily 9 AM UTC) |
| Webhook | Manual |

### Quick Start
```bash
# Deploy agent
opensre agent deploy cost-anomaly/

# Configure
opensre agent config cost-anomaly \
  --set anomaly_threshold_percent=20 \
  --set cloud_providers='["aws", "gcp"]'
```

---

## Certificate Expiry Checker

**Path:** `cert-checker/`

Daily scan for expiring SSL/TLS certificates with tiered alerts.

### Key Features
- Scans Kubernetes TLS secrets
- Checks external endpoints
- Monitors AWS ACM certificates
- Tiered alerts (30/14/7/3/1 days)
- Optional auto-renewal for ACM

### Triggers
| Type | Schedule |
|------|----------|
| Cron | `0 8 * * *` (Daily 8 AM UTC) |
| Webhook | Manual |

### Alert Tiers
| Days | Severity | Actions |
|------|----------|---------|
| < 0 | Expired | Slack + PagerDuty |
| ≤ 7 | Critical | Slack + PagerDuty + Jira |
| 8-14 | Warning | Slack |
| 15-30 | Notice | Slack |

### Quick Start
```bash
# Deploy agent
opensre agent deploy cert-checker/

# Configure
opensre agent config cert-checker \
  --set pagerduty_on_critical=true \
  --set auto_renew_enabled=false
```

---

## Deployment Validator

**Path:** `deploy-validator/`

Post-deployment validation checking health endpoints, error rates, and latency.

### Key Features
- Waits for rollout completion
- Health/readiness endpoint checks
- Prometheus metrics validation
- Weighted scoring system (80% pass threshold)
- Optional auto-rollback on failure

### Triggers
| Type | Source | Events |
|------|--------|--------|
| Webhook | Kubernetes | `deployment.successful` |
| Webhook | ArgoCD | `sync.succeeded` |
| Webhook | Manual | - |

### Validation Checks
| Check | Weight | Description |
|-------|--------|-------------|
| Health | 30% | /health endpoint responds |
| Readiness | 20% | /ready endpoint responds |
| Metrics | 30% | Error rate, latency OK |
| Pods | 20% | Running, ready, no restarts |

### Quick Start
```bash
# Deploy agent
opensre agent deploy deploy-validator/

# Configure
opensre agent config deploy-validator \
  --set thresholds.error_rate_percent=1.0 \
  --set auto_rollback=false
```

---

## Capacity Planner

**Path:** `capacity-planner/`

Weekly resource utilization analysis with scaling recommendations.

### Key Features
- Cluster and namespace metrics
- Rightsizing recommendations
- 30-day capacity forecasting
- Cost savings calculations
- AI-powered recommendations

### Triggers
| Type | Schedule |
|------|----------|
| Cron | `0 6 * * 1` (Monday 6 AM UTC) |
| Webhook | Manual |

### Analysis Output
- Overprovisioned workloads
- Underprovisioned workloads
- Missing resource limits
- Capacity forecast
- Estimated monthly savings

### Quick Start
```bash
# Deploy agent
opensre agent deploy capacity-planner/

# Configure
opensre agent config capacity-planner \
  --set namespaces='["production", "staging"]' \
  --set enable_ai_recommendations=true
```

---

## Runbook Executor

**Path:** `runbook-executor/`

Generic agent that executes runbook steps with approval workflows.

### Key Features
- Load runbooks from S3/Git
- Action allowlist/blocklist
- Approval workflow via Slack
- Dry-run mode
- Progress tracking
- Failure analysis with LLM

### Triggers
| Type | Source |
|------|--------|
| Webhook | Manual |
| Webhook | PagerDuty |
| Event | Slack command |

### Security Features
- Action allowlist (only specified actions allowed)
- Action blocklist (dangerous actions blocked)
- Mandatory approval for production
- Dry-run simulation mode

### Quick Start
```bash
# Deploy agent
opensre agent deploy runbook-executor/

# Configure
opensre agent config runbook-executor \
  --set runbook_repository="s3://my-runbooks/" \
  --set require_approval=true
```

---

## Installation

### Deploy All Agents
```bash
opensre agent deploy --all
```

### Deploy Specific Agent
```bash
opensre agent deploy <agent-name>/
```

### View Agent Status
```bash
opensre agent list
opensre agent status <agent-name>
```

### Configure Agent
```bash
opensre agent config <agent-name> --set key=value
```

### View Agent Logs
```bash
opensre agent logs <agent-name>
```

---

## Agent YAML Schema

All agents follow this schema:

```yaml
name: string (required)
description: string
version: string

triggers:
  - type: webhook|schedule|event
    # trigger-specific configuration

skills: list[string]

config:
  # agent-specific configuration

variables:
  # runtime variables with Jinja2 templates

steps:
  - name: string
    action: skill.method
    params: dict
    condition: string (optional)
    on_error: continue|fail|retry
    retries: int
```

---

## Custom Agents

Use these templates as starting points for custom agents:

1. Copy an existing agent directory
2. Modify `agent.yaml` for your use case
3. Update tests in `test_agent.py`
4. Deploy with `opensre agent deploy <path>/`

---

## Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines on submitting new agent templates.
