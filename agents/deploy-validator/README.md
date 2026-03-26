# Deployment Validator Agent

Post-deployment validation checking health endpoints, error rates, and latency against baselines.

## Overview

This agent runs after deployments to validate:
1. Rollout completion
2. Health and readiness endpoints
3. Error rates and latency metrics
4. Pod status and stability
5. Comparison against pre-deployment baseline

## Triggers

### Kubernetes Deployment Webhook
- **Path:** `/webhook/deployment`
- **Events:** `deployment.successful`

### ArgoCD Sync Webhook
- **Path:** `/webhook/argocd`
- **Events:** `sync.succeeded`

### Manual Validation
- **Path:** `/webhook/validate`

## Configuration

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `slack_channel` | string | `#deployments` | Notification channel |
| `validation_timeout_seconds` | int | `300` | Max wait for rollout |
| `health_check_retries` | int | `5` | Health check retry count |
| `health_check_interval_seconds` | int | `10` | Time between retries |
| `metrics_stabilization_seconds` | int | `60` | Wait before metrics check |
| `auto_rollback` | bool | `false` | Auto-rollback on failure |
| `rollback_on_failure` | bool | `true` | Enable rollback option |

### Thresholds
```yaml
thresholds:
  error_rate_percent: 1.0      # Max 1% 5xx errors
  latency_p99_ms: 500          # Max 500ms P99 latency
  latency_p50_ms: 100          # Max 100ms P50 latency
  success_rate_percent: 99.0   # Min 99% 2xx responses
```

## Required Skills

- **kubernetes** - Deployment and pod management
- **prometheus** - Metrics queries
- **http** - Health checks
- **slack** - Notifications
- **pagerduty** - Failure alerts

## Workflow

```
┌─────────────────────┐
│  Deployment         │
│  Completed          │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  1. Wait for        │
│     Rollout         │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  2. Health Checks   │
│  - /health          │
│  - /ready           │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  3. Wait for        │
│     Metrics (60s)   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  4. Validate        │
│     Metrics         │
│  - Error rate       │
│  - Latency          │
│  - Success rate     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  5. Check Pod       │
│     Health          │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  6. Calculate       │
│     Score           │
└──────────┬──────────┘
           │
     ┌─────┴─────┐
     │           │
     ▼           ▼
┌─────────┐  ┌─────────┐
│ ✅ Pass │  │ ❌ Fail │
│ >80%    │  │ <80%    │
└────┬────┘  └────┬────┘
     │            │
     ▼            ▼
┌─────────┐  ┌─────────────┐
│ Notify  │  │ Rollback?   │
│ Success │  │ + Page      │
└─────────┘  └─────────────┘
```

## Validation Scoring

| Check | Weight | Description |
|-------|--------|-------------|
| Health Check | 30% | All pods respond to /health |
| Readiness Check | 20% | All pods respond to /ready |
| Metrics Validation | 30% | Error rate, latency within thresholds |
| Pod Health | 20% | Running, ready, no restarts |

**Pass Threshold:** 80%

## Metrics Validated

### Error Rate
```promql
sum(rate(http_requests_total{status=~"5.."}[5m])) /
sum(rate(http_requests_total[5m])) * 100
```

### Latency P99
```promql
histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le)) * 1000
```

### Success Rate
```promql
sum(rate(http_requests_total{status=~"2.."}[5m])) /
sum(rate(http_requests_total[5m])) * 100
```

## Example Trigger Payload

```json
{
  "source": "kubernetes",
  "event_type": "deployment.successful",
  "deployment_name": "api-server",
  "namespace": "production",
  "version": "v1.2.3",
  "previous_version": "v1.2.2",
  "deployed_at": "2024-01-15T10:30:00Z",
  "deployed_by": "argocd"
}
```

## Testing

```bash
# Run unit tests
pytest test_agent.py -v

# Manual validation trigger
curl -X POST http://localhost:8080/webhook/validate \
  -H "Content-Type: application/json" \
  -d '{
    "deployment_name": "api-server",
    "namespace": "production",
    "version": "v1.2.3"
  }'
```

## Example Output

### Successful Validation
```
✅ Deployment Validated: api-server

Namespace: production
Version: v1.2.3
Previous: v1.2.2
Score: 95%

Metrics:
• Error Rate: 0.05% (threshold: 1%)
• Latency P99: 245ms (threshold: 500ms)
• Latency P50: 45ms
• Success Rate: 99.8%
• RPS: 1250.5

All checks passed. Deployment is healthy.
```

### Failed Validation
```
❌ Deployment Validation Failed: api-server

Namespace: production
Version: v1.2.3
Score: 60%
Required: 80%

Failed Checks:
• metrics_validation: Error rate 2.5% exceeds threshold 1%
• pod_health: 2 pods have restarts

Current Metrics:
• Error Rate: 2.5%
• Latency P99: 850ms
• Success Rate: 97.5%

[⏪ Rollback] [📊 View Metrics]
```

## Integration

### ArgoCD
```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
spec:
  syncPolicy:
    automated:
      selfHeal: true
  # Add webhook notification
  annotations:
    notifications.argoproj.io/subscribe.on-sync-succeeded.webhook: opensre-validator
```

### Flux
```yaml
apiVersion: notification.toolkit.fluxcd.io/v1beta1
kind: Alert
spec:
  eventSources:
    - kind: Kustomization
      name: '*'
  providerRef:
    name: opensre-webhook
```
