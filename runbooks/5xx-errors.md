---
symptoms: 5xx errors, 500 error, 502 bad gateway, 503 service unavailable, 504 timeout, internal server error, HTTP errors
services: any
tags: errors, 5xx, 500, 502, 503, 504, http, gateway
---

# 5xx HTTP Errors

## Symptoms
- Increased 5xx error rate
- User-facing errors
- API failures
- Health check failures returning 5xx

## Error Code Reference

| Code | Name | Typical Cause |
|------|------|---------------|
| 500 | Internal Server Error | Application exception, unhandled error |
| 501 | Not Implemented | Missing endpoint handler |
| 502 | Bad Gateway | Upstream service unreachable or crashed |
| 503 | Service Unavailable | Service overloaded, maintenance mode |
| 504 | Gateway Timeout | Upstream service too slow |

## Investigation Steps

### 1. Identify error scope and rate
```promql
# Error rate by service
sum(rate(http_requests_total{status=~"5.."}[5m])) by (service)

# Error rate vs total requests
sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) * 100
```

### 2. Check which endpoints are failing
```promql
sum(rate(http_requests_total{status=~"5.."}[5m])) by (path, method) > 0
```

### 3. Check application logs for stack traces
```bash
kubectl logs -l app=<service> -n <namespace> --tail=100 | grep -i error
kubectl logs -l app=<service> -n <namespace> --tail=100 | grep -i exception
```

### 4. Check pod health
```bash
kubectl get pods -n <namespace>
kubectl describe pod <pod> -n <namespace>
```

### 5. For 502/504, check upstream services
```bash
# Check if upstream pods are running
kubectl get pods -l app=<upstream-service> -n <namespace>

# Check service endpoints
kubectl get endpoints <service-name> -n <namespace>
```

## Root Causes by Error Code

### 500 Internal Server Error
- Unhandled exceptions in application code
- Database connection failures
- Missing configuration or secrets
- Failed external API calls without proper error handling

### 502 Bad Gateway
- Upstream pod crashed or restarting
- Upstream service not ready (readiness probe)
- Network policy blocking traffic
- Service selector not matching pods
- Container port mismatch with service

### 503 Service Unavailable
- All pods unhealthy / failing readiness
- Service in maintenance mode
- Rate limiting / circuit breaker open
- Pod scheduling issues (all pending)

### 504 Gateway Timeout
- Upstream service taking too long
- Database query timeouts
- Deadlock in application
- DNS resolution timeouts

## Remediation

### For 500 errors
1. Check logs for the exception:
   ```bash
   kubectl logs <pod> --tail=200 | grep -A10 "Exception\|Error\|Traceback"
   ```
2. Verify database/cache connectivity
3. Check ConfigMaps and Secrets are mounted
4. Roll back if recent deployment caused issues

### For 502 errors
1. Check if pods are running:
   ```bash
   kubectl get pods -l app=<service>
   ```
2. Verify service endpoints exist:
   ```bash
   kubectl get endpoints <service>
   ```
3. Check for CrashLoopBackOff (see crashloop runbook)
4. Verify network policies allow traffic

### For 503 errors
1. Check pod readiness:
   ```bash
   kubectl get pods -o wide
   ```
2. Scale up if all instances are overloaded:
   ```bash
   kubectl scale deployment <name> --replicas=<n>
   ```
3. Check HPA status if autoscaling enabled

### For 504 errors
1. Check upstream latency (see high-latency runbook)
2. Increase timeout in ingress/gateway config
3. Check database for slow queries
4. Look for deadlocks or blocking operations

## Prevention
1. Implement proper error handling
2. Add circuit breakers
3. Set up error rate alerts (e.g., >1% 5xx)
4. Use graceful degradation patterns
5. Regular chaos testing
