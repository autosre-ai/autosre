# Incident Responder Agent

Auto-responds to production incidents with automatic acknowledgment, context gathering, and team notification.

## Overview

This agent handles incoming incidents from PagerDuty and Prometheus Alertmanager, automatically:
1. Acknowledges the incident (if configured)
2. Gathers relevant metrics and context
3. Checks Kubernetes pod and deployment status
4. Notifies the team via Slack with a comprehensive summary
5. Creates a dedicated incident channel for critical issues

## Triggers

### PagerDuty Webhook
- **Path:** `/webhook/pagerduty`
- **Events:** `incident.triggered`, `incident.escalated`

### Prometheus Alertmanager
- **Path:** `/webhook/prometheus`
- **Events:** `alert.firing`

## Configuration

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `slack_channel` | string | `#incidents` | Channel for incident notifications |
| `auto_ack` | boolean | `true` | Auto-acknowledge PagerDuty incidents |
| `escalation_timeout_minutes` | int | `30` | Minutes before escalation |
| `severity_threshold` | string | `warning` | Minimum severity to respond to |

## Required Skills

- **prometheus** - Query metrics
- **kubernetes** - Check pod/deployment status
- **slack** - Send notifications
- **pagerduty** - Acknowledge and update incidents

## Example Trigger Payload

### PagerDuty
```json
{
  "source": "pagerduty",
  "incident_id": "P1234567",
  "title": "High Error Rate on api-gateway",
  "severity": "critical",
  "namespace": "production",
  "labels": {
    "app": "api-gateway"
  },
  "alert_query": "rate(http_requests_total{status=~\"5..\"}[5m]) > 0.1"
}
```

### Alertmanager
```json
{
  "source": "alertmanager",
  "alert_name": "HighErrorRate",
  "severity": "critical",
  "namespace": "production",
  "job": "api-gateway",
  "alert_query": "rate(http_requests_total{status=~\"5..\"}[5m])",
  "fired_at": "2024-01-15T10:30:00Z"
}
```

## Workflow

```
┌─────────────────┐     ┌─────────────────┐
│   PagerDuty     │     │   Alertmanager  │
│   Webhook       │     │   Webhook       │
└────────┬────────┘     └────────┬────────┘
         │                       │
         └───────────┬───────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │   1. Acknowledge      │
         │   (if auto_ack=true)  │
         └───────────┬───────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │  2. Gather Context    │
         │  - Prometheus metrics │
         │  - Pod status         │
         │  - K8s events         │
         │  - Deployments        │
         └───────────┬───────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │  3. Notify Slack      │
         │  - Incident details   │
         │  - Metrics summary    │
         │  - Pod status         │
         └───────────┬───────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │  4. Create Channel    │
         │  (if critical)        │
         └───────────┬───────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │  5. Update PagerDuty  │
         │  Notes                │
         └───────────────────────┘
```

## Customization

### Adding Custom Steps

```yaml
steps:
  # ... existing steps ...
  
  - name: check_database
    action: mysql.query
    params:
      query: "SHOW PROCESSLIST"
    condition: "{{ 'database' in trigger.labels.app }}"
```

### Custom Slack Message

Override the `notify_slack` step to customize the notification format.

## Testing

```bash
# Run unit tests
pytest test_agent.py -v

# Test with mock webhook
curl -X POST http://localhost:8080/webhook/pagerduty \
  -H "Content-Type: application/json" \
  -d '{"incident_id": "test-123", "title": "Test Incident", "severity": "warning"}'
```
