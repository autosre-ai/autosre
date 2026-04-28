# OpenSRE Integrations

Guide for integrating OpenSRE with your infrastructure.

## Overview

OpenSRE connects to your existing observability and communication tools:

| Integration | Status | Purpose |
|-------------|--------|---------|
| **Prometheus** | ✅ Supported | Metrics and alerting |
| **Kubernetes** | ✅ Supported | Pod status, events, logs |
| **Slack** | ✅ Supported | Notifications and approvals |
| **Alertmanager** | ✅ Supported | Automatic investigation triggers |
| **Loki** | ✅ Supported | Log aggregation |
| **PagerDuty** | ✅ Supported | Incident management |
| **OpsGenie** | 🔜 Planned | Incident management |
| **Datadog** | 🔜 Planned | APM integration |

---

## Prometheus Setup

### Basic Configuration

```bash
# .env
OPENSRE_PROMETHEUS_URL=http://prometheus:9090
```

### Authentication

#### Bearer Token

```bash
OPENSRE_PROMETHEUS_URL=http://prometheus:9090
OPENSRE_PROMETHEUS_TOKEN=your-bearer-token
```

#### Basic Auth

```bash
OPENSRE_PROMETHEUS_URL=http://prometheus:9090
OPENSRE_PROMETHEUS_USER=admin
OPENSRE_PROMETHEUS_PASSWORD=secret
```

### Required Metrics

OpenSRE works best with these standard metrics:

```yaml
# Essential metrics
- http_requests_total
- http_request_duration_seconds_bucket
- container_memory_usage_bytes
- container_cpu_usage_seconds_total
- kube_pod_status_phase
- kube_pod_container_status_restarts_total

# Recommended metrics
- up
- node_memory_MemAvailable_bytes
- node_cpu_seconds_total
- kube_deployment_status_replicas
- kube_deployment_status_replicas_available
```

### Sample Prometheus Rules

Add these recording rules for better query performance:

```yaml
# prometheus-rules.yaml
groups:
  - name: opensre
    rules:
      - record: job:http_requests:rate5m
        expr: sum(rate(http_requests_total[5m])) by (job)
        
      - record: job:http_errors:rate5m
        expr: sum(rate(http_requests_total{status=~"5.."}[5m])) by (job)
        
      - record: job:http_error_rate:ratio
        expr: |
          job:http_errors:rate5m / job:http_requests:rate5m
```

### Testing Connection

```bash
# Verify Prometheus is accessible
curl -s http://prometheus:9090/api/v1/status/config | jq .status

# Test from OpenSRE
autosre status
```

---

## Kubernetes Setup

### RBAC Requirements

OpenSRE needs read access to investigate and limited write access for remediation.

#### ClusterRole

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: opensre-reader
rules:
  # Read access for investigation
  - apiGroups: [""]
    resources:
      - pods
      - pods/log
      - events
      - services
      - endpoints
      - configmaps
      - nodes
    verbs: ["get", "list", "watch"]
    
  - apiGroups: ["apps"]
    resources:
      - deployments
      - replicasets
      - daemonsets
      - statefulsets
    verbs: ["get", "list", "watch"]
    
  - apiGroups: ["batch"]
    resources:
      - jobs
      - cronjobs
    verbs: ["get", "list", "watch"]
    
  # Write access for remediation (optional)
  - apiGroups: ["apps"]
    resources:
      - deployments
    verbs: ["patch", "update"]  # For rollback/scale
    
  - apiGroups: [""]
    resources:
      - pods
    verbs: ["delete"]  # For pod restart
```

#### Namespace-Scoped (More Restrictive)

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: opensre-reader
  namespace: production
rules:
  - apiGroups: [""]
    resources: ["pods", "pods/log", "events"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["apps"]
    resources: ["deployments", "replicasets"]
    verbs: ["get", "list", "watch"]
```

#### ServiceAccount

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: opensre
  namespace: opensre
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: opensre-reader-binding
subjects:
  - kind: ServiceAccount
    name: opensre
    namespace: opensre
roleRef:
  kind: ClusterRole
  name: opensre-reader
  apiGroup: rbac.authorization.k8s.io
```

### Configuration

```bash
# Use default kubeconfig
OPENSRE_KUBECONFIG=~/.kube/config

# Or specify namespaces
OPENSRE_K8S_NAMESPACES=production,staging,default
```

### In-Cluster Authentication

When running inside Kubernetes, OpenSRE automatically uses the pod's service account:

```yaml
# deployment.yaml
spec:
  serviceAccountName: opensre
  containers:
    - name: opensre
      # ...
```

---

## Slack Bot Setup

See [SLACK_SETUP.md](./SLACK_SETUP.md) for the detailed guide.

### Quick Setup

1. **Create Slack App** at [api.slack.com/apps](https://api.slack.com/apps)

2. **Add Bot Scopes:**
   - `chat:write`
   - `chat:write.customize`
   - `app_mentions:read`
   - `channels:history`
   - `channels:read`

3. **Enable Events:**
   - Subscribe to `app_mention`
   - Request URL: `https://your-domain/api/slack/events`

4. **Enable Interactivity:**
   - Request URL: `https://your-domain/api/slack/interactions`

5. **Install to Workspace**

6. **Configure OpenSRE:**

```bash
OPENSRE_SLACK_BOT_TOKEN=xoxb-your-bot-token
OPENSRE_SLACK_SIGNING_SECRET=your-signing-secret
OPENSRE_SLACK_CHANNEL=#incidents
```

### Interactive Buttons

OpenSRE posts messages with action buttons:

| Button | Action |
|--------|--------|
| ✅ Approve | Execute recommended action |
| 🔍 Investigate More | Deeper analysis |
| ❌ Dismiss | Mark as handled |

---

## Alertmanager Webhook

Connect Alertmanager to automatically trigger investigations.

### Alertmanager Configuration

```yaml
# alertmanager.yml
global:
  resolve_timeout: 5m

route:
  receiver: default
  routes:
    # Send critical alerts to OpenSRE
    - match:
        severity: critical
      receiver: opensre
      continue: true
    
    # Or route by service
    - match:
        service: checkout
      receiver: opensre

receivers:
  - name: default
    # Your existing receivers
    
  - name: opensre
    webhook_configs:
      - url: 'http://opensre:8080/api/webhook/alert'
        send_resolved: true
        http_config:
          # Optional auth
          # bearer_token: 'your-token'
```

### Webhook Payload

OpenSRE expects standard Alertmanager webhook format:

```json
{
  "status": "firing",
  "alerts": [
    {
      "labels": {
        "alertname": "HighMemoryUsage",
        "namespace": "production",
        "service": "payment-api",
        "severity": "critical"
      },
      "annotations": {
        "summary": "Memory usage above 90%",
        "description": "payment-api is using 4.2GB of 4.5GB limit"
      },
      "startsAt": "2024-01-15T10:30:00Z"
    }
  ],
  "commonLabels": {
    "alertname": "HighMemoryUsage",
    "namespace": "production"
  }
}
```

### Testing the Webhook

```bash
curl -X POST http://localhost:8080/api/webhook/alert \
  -H "Content-Type: application/json" \
  -d '{
    "status": "firing",
    "alerts": [{
      "labels": {
        "alertname": "TestAlert",
        "namespace": "default",
        "severity": "warning"
      },
      "annotations": {
        "summary": "Test alert for OpenSRE",
        "description": "This is a test alert"
      }
    }]
  }'
```

---

## Loki Setup

Enable log correlation with Loki.

### Configuration

```bash
OPENSRE_LOKI_URL=http://loki:3100
```

### Required Labels

Ensure your logs have these labels:

```yaml
# Recommended Loki labels
- namespace
- pod
- container
- app
- service
```

### LogQL Queries

OpenSRE uses these query patterns:

```logql
# Error logs for a service
{namespace="production", app="payment"} |= "error" | logfmt

# Logs around alert time
{namespace="production"} 
  | json 
  | level="error" or level="warn"
```

---

## PagerDuty Setup

Integration with PagerDuty for incident management. See [PAGERDUTY.md](./PAGERDUTY.md) for the full guide.

### Quick Setup

1. **Create API Key** at PagerDuty → Integrations → API Access Keys

2. **Configure OpenSRE:**

```bash
OPENSRE_PAGERDUTY_API_KEY=your-api-key
OPENSRE_PAGERDUTY_SERVICE_ID=PXXXXXX  # Optional
OPENSRE_PAGERDUTY_FROM_EMAIL=sre@yourcompany.com
```

3. **Set up Webhook** (for auto-investigation):
   - Go to Services → Your Service → Integrations
   - Add Generic Webhook (v3)
   - URL: `https://your-domain/api/webhook/pagerduty`
   - Subscribe to: `incident.triggered`

### Features

- **Auto-investigate** triggered incidents
- **Post investigation results** as incident notes
- **Acknowledge and resolve** incidents programmatically
- Works alongside Slack notifications

### Testing

```bash
# Check connection
curl http://localhost:8080/api/pagerduty/health

# List incidents
curl http://localhost:8080/api/pagerduty/incidents

# Manually investigate an incident
curl -X POST http://localhost:8080/api/pagerduty/incidents/PXXXXXX/investigate
```

---

## OpsGenie (Planned)

Integration with OpsGenie for alert management.

### Planned Features

- Receive OpsGenie alerts via webhook
- Enrich alerts with investigation results
- Close alerts after remediation
- Update alert notes and tags

### Configuration (Future)

```bash
OPENSRE_OPSGENIE_API_KEY=your-api-key
OPENSRE_OPSGENIE_TEAM=platform-sre
```

---

## Custom Integrations

### Webhook Input

Send custom webhooks to trigger investigations:

```bash
curl -X POST http://opensre:8080/api/investigate \
  -H "Content-Type: application/json" \
  -d '{
    "issue": "Custom alert: High latency on API gateway",
    "namespace": "production",
    "context": {
      "service": "api-gateway",
      "metrics_url": "http://grafana/d/api-gateway"
    }
  }'
```

### Output Webhook

Configure OpenSRE to send results to your systems:

```yaml
# config/webhooks.yaml
output_webhooks:
  - name: servicenow
    url: https://yourinstance.service-now.com/api/x_app/incident
    method: POST
    headers:
      Authorization: "Bearer ${SERVICENOW_TOKEN}"
    events:
      - investigation_completed
      - action_executed
```

---

## Testing Integrations

### Health Check All Integrations

```bash
autosre status
```

Output:

```
┌─────────────────────────────────────────────────────────┐
│              OpenSRE Integration Status                 │
├─────────────────────────────────────────────────────────┤
│ Prometheus   │ ✅ Connected (v2.45.0)                   │
│ Kubernetes   │ ✅ Connected (v1.28.0, 3 namespaces)     │
│ LLM (Ollama) │ ✅ Connected (llama3.1:8b)               │
│ Slack        │ ✅ Connected (@opensre-bot)              │
│ Loki         │ ⚪ Not configured                        │
│ PagerDuty    │ ✅ Connected (sre@company.com)           │
└─────────────────────────────────────────────────────────┘
```

### Test Individual Integrations

```bash
# Test Prometheus
curl http://localhost:8080/api/prometheus/query?query=up

# Test Kubernetes
curl http://localhost:8080/api/kubernetes/pods?namespace=default

# Test Slack
curl http://localhost:8080/api/slack/health

# Test PagerDuty
curl http://localhost:8080/api/pagerduty/health
```
