# SLO Tracker Agent

Track Service Level Objectives (SLOs), calculate error budget burn rates, and alert on budget consumption.

## Overview

The SLO Tracker agent continuously monitors your SLOs using multi-window burn rate alerting. It calculates error budget consumption, identifies contributing factors, and provides AI-powered recommendations for remediation.

## Features

- **Multi-window burn rate calculation** - Fast (5m), slow (1h), and long (6h) windows
- **Error budget tracking** - Real-time budget consumption monitoring
- **Tiered alerting** - Warning at 50%, critical at 75%, exhausted at 100%
- **AI-powered analysis** - Root cause analysis and recommendations
- **Weekly compliance reports** - Email summaries for stakeholders
- **Contributing error analysis** - Identify top error sources

## Configuration

```yaml
config:
  slack_channel: "#slo-alerts"
  email_recipients:
    - sre-team@example.com
  burn_rate_windows:
    fast: "5m"      # Fast burn detection
    slow: "1h"      # Slow burn detection
    long: "6h"      # Sustained issues
  error_budget_thresholds:
    warning: 50     # 50% budget consumed
    critical: 75    # 75% budget consumed
    exhausted: 100  # Budget exhausted
  slos:
    - name: "api-availability"
      target: 99.9
      window_days: 30
      service: "api-gateway"
      sli_query: |
        sum(rate(http_requests_total{service="api",status!~"5.."}[5m])) /
        sum(rate(http_requests_total{service="api"}[5m]))
```

## Burn Rate Alerting

The agent implements Google's multi-window burn rate alerting:

| Scenario | Fast Window | Slow Window | Detection Time |
|----------|-------------|-------------|----------------|
| 2% budget in 1h | 14.4x | 14.4x | ~1 min |
| 5% budget in 6h | 6x | 6x | ~5 min |
| 10% budget in 3d | 1x | 1x | ~2 hours |

## SLI Query Format

SLI queries should return a value between 0 and 1:

```promql
# Availability SLI
sum(rate(http_requests_total{status!~"5.."}[5m])) /
sum(rate(http_requests_total[5m]))

# Latency SLI (requests under threshold)
sum(rate(http_request_duration_seconds_bucket{le="0.5"}[5m])) /
sum(rate(http_request_duration_seconds_count[5m]))
```

## Triggers

- **Schedule**: Every 15 minutes
- **Webhook**: `/webhook/slo-check` - Manual check
- **Alertmanager**: `/webhook/slo-alert` - Alert-driven

## Alert Examples

### Slack Warning
```
⚠️ SLO Error Budget Warning

1 SLO(s) consuming budget faster than expected

• api-availability: 52.3% consumed
  Current: 0.9987 | Target: 99.9%
  Time to exhaustion: 14.2h
```

### PagerDuty Critical
```
SLO Budget Exhausted

- api-availability: 102.3% consumed
  Current SLI: 0.9978
  Target: 99.9%
```

## Metrics Pushed

| Metric | Description |
|--------|-------------|
| `opensre_slo_current_value` | Current SLI value |
| `opensre_slo_budget_consumed_percent` | Error budget consumed |
| `opensre_slo_burn_rate` | Current burn rate |

## Prerequisites

- Prometheus with SLI metrics
- Slack workspace
- PagerDuty service (optional)
- Email configured (for weekly reports)

## Usage

```bash
# Run check
opensre agent run agents/slo-tracker/agent.yaml

# Dry run
opensre agent run agents/slo-tracker/agent.yaml --dry-run

# Development mode
opensre agent dev agents/slo-tracker/agent.yaml
```

## Related Agents

- [incident-responder](../incident-responder/) - Respond to SLO breaches
- [cost-anomaly](../cost-anomaly/) - Track cost impact of reliability issues
