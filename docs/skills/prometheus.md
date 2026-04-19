# Prometheus Skill

Query metrics, manage alerts, and create silences in Prometheus.

## Overview

| Property | Value |
|----------|-------|
| **Name** | `prometheus` |
| **Version** | 1.0.0 |
| **Category** | Monitoring |
| **Approval** | Most actions auto-approved |

## Configuration

```yaml
# config/opensre.yaml
prometheus:
  url: http://prometheus:9090
  auth:
    type: none  # none | basic | bearer
    username: admin       # for basic auth
    password: ${PROM_PASS} # for basic auth
    token: ${PROM_TOKEN}   # for bearer auth
  timeout: 30
  tls:
    insecure: false
    ca_cert: /path/to/ca.crt
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENSRE_PROMETHEUS_URL` | Prometheus server URL |
| `OPENSRE_PROMETHEUS_USERNAME` | Basic auth username |
| `OPENSRE_PROMETHEUS_PASSWORD` | Basic auth password |
| `OPENSRE_PROMETHEUS_TOKEN` | Bearer token |

## Actions

### `query`

Execute an instant PromQL query.

```yaml
action: prometheus.query
params:
  query: rate(http_requests_total{status=~"5.."}[5m])
  time: "2024-03-15T14:00:00Z"  # optional, defaults to now
```

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `query` | string | yes | PromQL query |
| `time` | string | no | Evaluation timestamp (RFC3339) |

**Returns:**

```json
{
  "status": "success",
  "data": {
    "resultType": "vector",
    "result": [
      {
        "metric": {"service": "checkout", "status": "500"},
        "value": [1710511200, "0.0523"]
      }
    ]
  }
}
```

### `query_range`

Execute a range PromQL query.

```yaml
action: prometheus.query_range
params:
  query: rate(http_requests_total[5m])
  start: "2024-03-15T13:00:00Z"
  end: "2024-03-15T14:00:00Z"
  step: 60
```

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `query` | string | yes | PromQL query |
| `start` | string | yes | Start timestamp (RFC3339) |
| `end` | string | yes | End timestamp (RFC3339) |
| `step` | integer | no | Query resolution (seconds), default 60 |

### `alerts`

Get active alerts.

```yaml
action: prometheus.alerts
params:
  filter:
    severity: critical
    service: checkout
```

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `filter` | object | no | Label filters |

**Returns:**

```json
{
  "alerts": [
    {
      "labels": {
        "alertname": "HighErrorRate",
        "service": "checkout",
        "severity": "critical"
      },
      "annotations": {
        "summary": "High error rate on checkout service",
        "description": "Error rate is 8.3%"
      },
      "state": "firing",
      "activeAt": "2024-03-15T14:05:00Z"
    }
  ]
}
```

### `silence`

Create or update a silence.

```yaml
action: prometheus.silence
params:
  matchers:
    - name: alertname
      value: HighErrorRate
    - name: service
      value: checkout
  duration: 2h
  comment: Investigating issue
  createdBy: opensre
```

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `matchers` | array | yes | Label matchers |
| `duration` | string | yes | Silence duration (e.g., "2h", "30m") |
| `comment` | string | no | Silence comment |
| `createdBy` | string | no | Creator name |
| `startsAt` | string | no | Start time (defaults to now) |

**Requires Approval:** No (but logged)

### `delete_silence`

Delete an existing silence.

```yaml
action: prometheus.delete_silence
params:
  silence_id: abc123
```

**Requires Approval:** Yes

### `targets`

List scrape targets and their health.

```yaml
action: prometheus.targets
params:
  state: active  # active | dropped | any
```

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `state` | string | no | Filter by target state |

**Returns:**

```json
{
  "activeTargets": [
    {
      "discoveredLabels": {"job": "kubernetes-pods"},
      "labels": {"instance": "checkout-abc:8080"},
      "health": "up",
      "lastScrape": "2024-03-15T14:32:05Z"
    }
  ]
}
```

### `rules`

Get alerting and recording rules.

```yaml
action: prometheus.rules
params:
  type: alert  # alert | record | all
```

### `metadata`

Get metric metadata.

```yaml
action: prometheus.metadata
params:
  metric: http_requests_total
```

## Examples

### Agent Using Prometheus

```yaml
name: error-rate-monitor
skills:
  - prometheus
  - slack

steps:
  - name: check-error-rate
    action: prometheus.query
    params:
      query: |
        sum(rate(http_requests_total{status=~"5.."}[5m])) 
        / sum(rate(http_requests_total[5m])) * 100
    output: error_rate

  - name: get-top-errors
    action: prometheus.query
    params:
      query: |
        topk(5, 
          sum by (service, status) (
            rate(http_requests_total{status=~"5.."}[5m])
          )
        )
    output: top_errors
    condition: "{{ error_rate.data.result[0].value[1] | float > 1.0 }}"

  - name: notify
    action: slack.post_message
    params:
      channel: "#alerts"
      text: |
        🚨 Error rate is {{ error_rate.data.result[0].value[1] }}%
        Top errors: {{ top_errors.data.result | map(attribute='metric') | list }}
    condition: "{{ error_rate.data.result[0].value[1] | float > 1.0 }}"
```

### Common PromQL Queries

```yaml
# Error rate percentage
sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) * 100

# P99 latency
histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, service))

# Memory usage percentage
(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100

# CPU usage
100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

# Pod restart count
sum by (namespace, pod) (increase(kube_pod_container_status_restarts_total[1h]))
```

## Troubleshooting

### Connection Refused

```bash
# Test connectivity
curl http://prometheus:9090/-/healthy

# Check from OpenSRE container
kubectl exec -it opensre-xxx -- curl http://prometheus:9090/-/healthy
```

### Query Timeout

```yaml
prometheus:
  timeout: 60  # Increase timeout
```

### Authentication Failed

```bash
# Test with auth
curl -u admin:password http://prometheus:9090/-/healthy

# Or with bearer token
curl -H "Authorization: Bearer $TOKEN" http://prometheus:9090/-/healthy
```

## See Also

- [Skills Overview](overview.md)
- [Creating Skills](creating-skills.md)
- [Kubernetes Skill](kubernetes.md)
