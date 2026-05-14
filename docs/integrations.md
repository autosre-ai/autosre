# Integrations Guide

AutoSRE integrates with your existing observability stack to gather data and take actions. This guide covers setting up each integration.

---

## Prometheus

Prometheus is the primary metrics source for AutoSRE.

### Configuration

**Environment Variables:**
```bash
PROMETHEUS_URL=http://prometheus:9090
```

**Config File:**
```yaml
integrations:
  prometheus:
    url: http://prometheus:9090
    timeout: 30
    max_points: 10000
    # Optional authentication
    auth:
      type: bearer  # or basic
      token: ${PROMETHEUS_TOKEN}
      # username: user
      # password: pass
```

### Kubernetes Setup

If running in Kubernetes, ensure network access:

```yaml
# Network policy allowing AutoSRE to reach Prometheus
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: autosre-prometheus-access
spec:
  podSelector:
    matchLabels:
      app: autosre-api
  policyTypes:
    - Egress
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              name: monitoring
          podSelector:
            matchLabels:
              app: prometheus
      ports:
        - port: 9090
```

### ServiceMonitor

Monitor AutoSRE itself with Prometheus:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: autosre
  namespace: autosre
spec:
  selector:
    matchLabels:
      app: autosre-api
  endpoints:
    - port: http
      path: /metrics
      interval: 30s
```

### Alert Rules

Example alerting rules for common scenarios:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: autosre-alerts
spec:
  groups:
    - name: service.alerts
      rules:
        - alert: HighErrorRate
          expr: |
            sum(rate(http_requests_total{status=~"5.."}[5m])) by (service)
            / sum(rate(http_requests_total[5m])) by (service)
            > 0.05
          for: 5m
          labels:
            severity: critical
          annotations:
            summary: "High error rate on {{ $labels.service }}"
            description: "Error rate is {{ $value | humanizePercentage }}"
        
        - alert: HighLatency
          expr: |
            histogram_quantile(0.99, 
              sum(rate(http_request_duration_seconds_bucket[5m])) by (le, service)
            ) > 1
          for: 5m
          labels:
            severity: high
          annotations:
            summary: "High latency on {{ $labels.service }}"
        
        - alert: PodCrashLooping
          expr: |
            increase(kube_pod_container_status_restarts_total[1h]) > 5
          labels:
            severity: critical
          annotations:
            summary: "Pod {{ $labels.pod }} is crash looping"
```

---

## Alertmanager

Alertmanager sends alerts to AutoSRE for automatic investigation.

### Configuration

**Environment Variables:**
```bash
ALERTMANAGER_URL=http://alertmanager:9093
```

### Alertmanager Config

Configure Alertmanager to send alerts to AutoSRE:

```yaml
# alertmanager.yml
global:
  resolve_timeout: 5m

route:
  receiver: 'autosre'
  group_by: ['alertname', 'service']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  
  routes:
    # Critical alerts go to AutoSRE immediately
    - match:
        severity: critical
      receiver: 'autosre'
      group_wait: 10s
      continue: true  # Also send to other receivers
    
    # High severity to AutoSRE
    - match:
        severity: high
      receiver: 'autosre'
      continue: true

receivers:
  - name: 'autosre'
    webhook_configs:
      - url: 'http://autosre-api:8000/webhooks/alertmanager'
        send_resolved: true
        http_config:
          bearer_token: ${AUTOSRE_WEBHOOK_TOKEN}
  
  - name: 'slack-notifications'
    slack_configs:
      - channel: '#alerts'
        # ... slack config
```

### Webhook Format

AutoSRE expects the standard Alertmanager webhook format:

```json
{
  "version": "4",
  "groupKey": "{}:{alertname=\"HighErrorRate\"}",
  "status": "firing",
  "receiver": "autosre",
  "alerts": [
    {
      "status": "firing",
      "labels": {
        "alertname": "HighErrorRate",
        "severity": "critical",
        "service": "payment-service",
        "namespace": "production"
      },
      "annotations": {
        "summary": "Error rate above threshold",
        "description": "Error rate is 7.5%",
        "runbook_url": "https://wiki.example.com/runbooks/errors"
      },
      "startsAt": "2024-01-15T10:30:00Z",
      "generatorURL": "http://prometheus:9090/graph?..."
    }
  ]
}
```

---

## Kubernetes

AutoSRE connects to Kubernetes to investigate cluster state.

### In-Cluster Configuration

When running inside Kubernetes, AutoSRE uses the service account:

```yaml
# RBAC for AutoSRE
apiVersion: v1
kind: ServiceAccount
metadata:
  name: autosre
  namespace: autosre

---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: autosre-reader
rules:
  - apiGroups: [""]
    resources:
      - pods
      - pods/log
      - services
      - endpoints
      - events
      - configmaps
      - namespaces
    verbs: ["get", "list", "watch"]
  
  - apiGroups: ["apps"]
    resources:
      - deployments
      - replicasets
      - statefulsets
      - daemonsets
    verbs: ["get", "list", "watch"]
  
  - apiGroups: ["networking.k8s.io"]
    resources:
      - ingresses
    verbs: ["get", "list", "watch"]
  
  - apiGroups: ["batch"]
    resources:
      - jobs
      - cronjobs
    verbs: ["get", "list", "watch"]

---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: autosre-reader
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: autosre-reader
subjects:
  - kind: ServiceAccount
    name: autosre
    namespace: autosre
```

### Out-of-Cluster Configuration

For local development or external access:

```bash
# Use default kubeconfig
KUBECONFIG=~/.kube/config

# Or specify path
KUBECONFIG=/path/to/kubeconfig
```

**Docker Compose:**
```yaml
services:
  autosre-api:
    volumes:
      - ${KUBECONFIG:-~/.kube/config}:/app/.kube/config:ro
    environment:
      KUBECONFIG: /app/.kube/config
```

### Configuration Options

```yaml
integrations:
  kubernetes:
    in_cluster: true         # Use in-cluster config
    namespace_default: default
    timeout: 30
    # For out-of-cluster
    kubeconfig: /path/to/config
    context: production-cluster
```

---

## Loki (Log Aggregation)

Loki is the primary log source for AutoSRE.

### Configuration

```bash
LOKI_URL=http://loki:3100
```

```yaml
integrations:
  loki:
    url: http://loki:3100
    timeout: 30
    max_lines: 5000
    # Optional auth
    auth:
      type: basic
      username: ${LOKI_USER}
      password: ${LOKI_PASSWORD}
```

### Required Labels

Ensure your logs have useful labels for filtering:

```yaml
# Promtail config
scrape_configs:
  - job_name: kubernetes-pods
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      # Service name
      - source_labels: [__meta_kubernetes_pod_label_app]
        target_label: service
      # Namespace
      - source_labels: [__meta_kubernetes_namespace]
        target_label: namespace
      # Pod name
      - source_labels: [__meta_kubernetes_pod_name]
        target_label: pod
      # Container name
      - source_labels: [__meta_kubernetes_pod_container_name]
        target_label: container
```

### Query Examples

AutoSRE uses LogQL to search logs:

```
# Errors in a service
{service="payment"} |= "error"

# Errors with JSON parsing
{service="api"} | json | level="error"

# Regex matching
{namespace="production"} |~ "connection.*(refused|timeout)"

# Rate of errors
sum(rate({service="checkout"} |= "error" [5m])) by (service)
```

---

## Slack

Slack integration enables notifications and interactive commands.

### Create Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps)
2. Create New App → From scratch
3. Name it "AutoSRE"

### Required Scopes

**Bot Token Scopes:**
- `chat:write` - Send messages
- `chat:write.public` - Post to public channels
- `channels:read` - List channels
- `groups:read` - List private channels
- `users:read` - Read user info
- `files:write` - Upload files (for reports)

**Event Subscriptions:**
- `app_mention` - Respond to @mentions
- `message.channels` - Read channel messages (if using slash commands)

### Configuration

```bash
# Bot token (starts with xoxb-)
SLACK_BOT_TOKEN=xoxb-your-token

# App token for Socket Mode (starts with xapp-)
SLACK_APP_TOKEN=xapp-your-token

# Default channel for notifications
SLACK_DEFAULT_CHANNEL=#sre-alerts
```

```yaml
integrations:
  slack:
    enabled: true
    default_channel: "#sre-alerts"
    mention_on_critical: true
    mention_users: ["@oncall", "@sre-team"]
    
    # Message formatting
    include_timeline: true
    include_recommendations: true
    max_findings: 5
```

### Notification Format

AutoSRE sends rich Slack messages:

```
🚨 Investigation Complete: HighErrorRate

📊 Summary
Payment-service is experiencing elevated error rates due to database connection timeouts.

🎯 Root Cause (87% confidence)
Database connection pool exhaustion

📋 Key Findings
• 🔴 Connection pool at 100% utilization
• 🟡 5 pod restarts in last hour
• 🟢 Increased traffic from marketing campaign

💡 Recommendations
1. Increase connection pool size
   `kubectl set env deployment/payment-service DB_POOL_SIZE=25`

🔗 View Details: http://autosre.example.com/investigations/inv_abc123
```

### Slash Commands

Configure slash commands for interactive use:

1. In your Slack app settings, go to Slash Commands
2. Create command `/autosre`
3. Set Request URL: `https://autosre.example.com/webhooks/slack/commands`

**Usage:**
```
/autosre investigate payment-service
/autosre status inv_abc123
/autosre alerts --service checkout
```

---

## PagerDuty

PagerDuty integration for incident management.

### Configuration

```bash
PAGERDUTY_API_KEY=your-api-key
PAGERDUTY_SERVICE_ID=your-service-id
```

```yaml
integrations:
  pagerduty:
    enabled: true
    api_key: ${PAGERDUTY_API_KEY}
    service_id: ${PAGERDUTY_SERVICE_ID}
    
    # Auto-create incidents
    auto_create_incident: true
    severity_mapping:
      critical: critical
      high: error
      medium: warning
      low: info
    
    # Add investigation link to incident
    include_investigation_url: true
```

### Event Rules

Configure PagerDuty to route AutoSRE events:

1. Go to Service → Event Rules
2. Create rule: Source = "AutoSRE"
3. Set routing based on severity

### Incident Actions

AutoSRE can:
- Create incidents for critical alerts
- Add investigation notes to existing incidents
- Resolve incidents when root cause is fixed
- Link to investigation reports

---

## Custom Integrations

### Integration Base Class

```python
from autosre.integrations.base import BaseIntegration

class CustomMonitoringIntegration(BaseIntegration):
    """Custom integration for internal monitoring system."""
    
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key
        self._client = self._create_client()
    
    def _create_client(self):
        import httpx
        return httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}"}
        )
    
    async def query_metrics(
        self,
        query: str,
        start_time: datetime,
        end_time: datetime
    ) -> dict:
        """Query custom metrics."""
        response = await self._client.post("/api/v1/query", json={
            "query": query,
            "start": start_time.isoformat(),
            "end": end_time.isoformat()
        })
        response.raise_for_status()
        return response.json()
    
    async def search_logs(
        self,
        query: str,
        limit: int = 1000
    ) -> list:
        """Search logs."""
        response = await self._client.get("/api/v1/logs", params={
            "q": query,
            "limit": limit
        })
        response.raise_for_status()
        return response.json()["results"]
    
    async def health_check(self) -> bool:
        """Check if integration is healthy."""
        try:
            response = await self._client.get("/health")
            return response.status_code == 200
        except Exception:
            return False
```

### Registering Custom Integration

```python
from autosre.integrations import register_integration
from .custom import CustomMonitoringIntegration

# Register the integration
register_integration(
    name="custom_monitoring",
    integration_class=CustomMonitoringIntegration,
    config_schema={
        "base_url": {"type": "string", "required": True},
        "api_key": {"type": "string", "required": True, "secret": True}
    }
)
```

### Using in Agents

```python
from autosre.agents.base_agent import BaseAgent
from autosre.integrations import get_integration

class CustomAgent(BaseAgent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.monitoring = get_integration("custom_monitoring")
        self._register_tools()
    
    def _register_tools(self):
        self.tools.register(
            name="query_custom_metrics",
            description="Query metrics from custom monitoring",
            parameters={"type": "object", "properties": {...}},
            handler=self._query_metrics
        )
    
    async def _query_metrics(self, query: str, time_range: str = "1h"):
        return await self.monitoring.query_metrics(query, ...)
```

---

## Testing Integrations

### Verify Configuration

```bash
# Check all integrations
autosre config validate

# Test specific integration
autosre config test-integration prometheus
autosre config test-integration kubernetes
autosre config test-integration slack
```

### Integration Health Endpoint

```bash
curl http://localhost:8000/health/integrations
```

```json
{
  "integrations": {
    "prometheus": {"status": "healthy", "latency_ms": 45},
    "loki": {"status": "healthy", "latency_ms": 32},
    "kubernetes": {"status": "healthy", "latency_ms": 12},
    "slack": {"status": "healthy"},
    "pagerduty": {"status": "not_configured"}
  }
}
```

### Debug Mode

Enable debug logging for integration troubleshooting:

```bash
AUTOSRE_LOG_LEVEL=DEBUG autosre serve start
```

This logs all API calls, responses, and errors for each integration.
