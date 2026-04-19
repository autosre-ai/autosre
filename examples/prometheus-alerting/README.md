# Prometheus Alerting Example

Production-ready Prometheus alerting integration with auto-investigation.

## What This Does

1. Receives alerts from Prometheus Alertmanager
2. Automatically investigates critical alerts
3. Correlates metrics, logs, and events
4. Posts detailed analysis to Slack
5. Suggests remediation actions

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Prometheus  │────▶│Alertmanager │────▶│   OpenSRE   │
│             │     │             │     │             │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                                               ▼
                                        ┌─────────────┐
                                        │    Slack    │
                                        └─────────────┘
```

## Setup

### 1. Configure Alertmanager

Add webhook receiver to `alertmanager.yml`:

```yaml
route:
  receiver: opensre
  routes:
    - match:
        severity: critical
      receiver: opensre
      continue: true

receivers:
  - name: opensre
    webhook_configs:
      - url: http://opensre:8000/webhook/alertmanager
        send_resolved: true
```

### 2. Add Alert Rules

Example Prometheus alert rules (`alerts.yaml`):

```yaml
groups:
  - name: service-alerts
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate on {{ $labels.service }}"
          
      - alert: HighLatency
        expr: histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m])) > 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High latency on {{ $labels.service }}"
```

### 3. Deploy OpenSRE Agent

Copy agent configuration:

```bash
cp examples/prometheus-alerting/agent.yaml agents/
```

Configure environment:

```bash
export OPENSRE_PROMETHEUS_URL=http://prometheus:9090
export OPENSRE_SLACK_BOT_TOKEN=xoxb-your-token
```

Start OpenSRE:

```bash
opensre start
```

## Testing

Send a test alert:

```bash
curl -X POST http://localhost:8000/webhook/alertmanager \
  -H "Content-Type: application/json" \
  -d '{
    "status": "firing",
    "alerts": [{
      "status": "firing",
      "labels": {
        "alertname": "HighErrorRate",
        "service": "checkout",
        "severity": "critical"
      },
      "annotations": {
        "summary": "High error rate on checkout service"
      }
    }]
  }'
```

## Files

- `agent.yaml` — Agent configuration
- `alerts.yaml` — Example Prometheus alert rules
- `alertmanager.yaml` — Example Alertmanager config
