# Dependency Checker Agent

Check upstream service health, API dependencies, and external service availability.

## Overview

The Dependency Checker agent monitors all service dependencies (internal services, external APIs, DNS resolution) to provide early warning of dependency failures that could impact your application.

## Features

- **Internal Service Checks** - Health endpoints for microservices
- **External API Monitoring** - Third-party service availability
- **DNS Resolution Checks** - Verify DNS records resolve correctly
- **Consecutive Failure Tracking** - Alert escalation based on failure count
- **Response Time Monitoring** - Detect degradation before failures
- **Critical Dependency Flagging** - Prioritize alerts for critical services

## Configuration

```yaml
config:
  slack_channel: "#dependency-alerts"
  dependencies:
    internal:
      - name: user-service
        url: "http://user-service.default.svc.cluster.local/health"
        timeout_seconds: 5
        critical: true
      - name: payment-service
        url: "http://payment-service.default.svc.cluster.local/health"
        timeout_seconds: 5
        critical: true
    external:
      - name: stripe-api
        url: "https://api.stripe.com/v1"
        timeout_seconds: 10
        critical: true
        expected_status: 401  # No auth = 401
      - name: aws-s3
        url: "https://s3.amazonaws.com"
        timeout_seconds: 10
        critical: true
    dns:
      - name: primary-db
        host: "primary.db.example.com"
        expected_ip_prefix: "10.0."
  health_criteria:
    response_time_warning_ms: 500
    response_time_critical_ms: 2000
    consecutive_failures_alert: 2
    consecutive_failures_page: 5
```

## Dependency Types

### Internal Services
Kubernetes services within your cluster:
- Health endpoint checks
- Expected 200 OK response
- Short timeout (5s default)

### External APIs
Third-party services your app depends on:
- Stripe, AWS, SendGrid, etc.
- Custom expected status codes
- Longer timeout (10s default)

### DNS Resolution
Critical hostnames that must resolve:
- Database hosts
- Cache clusters
- Expected IP prefix validation

## Alert Escalation

| Failures | Action |
|----------|--------|
| 1 | Log only |
| 2 | Slack warning |
| 5+ | PagerDuty (critical deps) |

## Triggers

- **Schedule**: Every 5 minutes
- **Manual**: `/webhook/dependency-check`

## Alert Examples

### Degraded Performance
```
⚠️ Dependency Degradation Detected

2 service(s) showing degraded performance:

• payment-service - 850ms response time
  Status: 200 | Threshold: 500ms

• inventory-service - 1200ms response time
  Status: 200 | Threshold: 500ms
```

### Unhealthy Dependencies
```
🚨 Dependency Health Issues

Internal: 1 unhealthy
External: 1 unhealthy
DNS: 0 failed

Unhealthy Services:
• payment-service 🔴 CRITICAL
  URL: http://payment-service.default.svc.cluster.local/health
  Error: Connection refused
  Consecutive failures: 3

• stripe-api 🔴 CRITICAL
  URL: https://api.stripe.com/v1
  Error: 503 Service Unavailable
  Consecutive failures: 2
```

## Status Summary

Generated markdown report:

```markdown
## Dependency Status - 2024-01-15 10:00:00

### Internal Services
| Service | Status | Response Time | Error Rate |
|---------|--------|---------------|------------|
| user-service | healthy | 45ms | 0.01% |
| payment-service | unhealthy | N/A | 100% |

### External Services
| Service | Status | Response Time |
|---------|--------|---------------|
| stripe-api | healthy | 120ms |
| aws-s3 | healthy | 85ms |
```

## Metrics

| Metric | Description |
|--------|-------------|
| `opensre_dependency_healthy` | Healthy dependency count |
| `opensre_dependency_unhealthy` | Unhealthy dependency count |
| `opensre_dns_failures` | DNS resolution failures |
| `opensre_dependency_response_time_ms` | Response time per service |

## Prerequisites

- Network access to all dependencies
- DNS resolution for all hosts
- Prometheus for historical metrics

## Usage

```bash
# Run dependency check
opensre agent run agents/dependency-checker/agent.yaml

# Dry run
opensre agent run agents/dependency-checker/agent.yaml --dry-run

# Verbose output
opensre agent run agents/dependency-checker/agent.yaml -v
```

## Related Agents

- [incident-responder](../incident-responder/) - Respond to dependency failures
- [deploy-validator](../deploy-validator/) - Check deps after deployment
