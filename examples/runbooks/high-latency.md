# High Latency Troubleshooting Runbook

## Symptoms
- P99 latency exceeding SLO threshold
- Increased response times reported by users
- Timeout errors in downstream services

## Investigation Steps

### 1. Identify the Scope
```bash
# Check which endpoints are affected
kubectl logs -l app=<service> --tail=500 | grep -i "slow\|timeout\|latency"
```

### 2. Check Resource Saturation
```bash
# CPU usage
kubectl top pods -l app=<service> -n <namespace>

# Get detailed resource usage
kubectl describe pod <pod-name> -n <namespace> | grep -A5 "Resources:"
```

### 3. Check Dependencies
```promql
# Database latency
histogram_quantile(0.99, sum(rate(db_query_duration_seconds_bucket{service="<service>"}[5m])) by (le))

# External API latency
histogram_quantile(0.99, sum(rate(http_client_duration_seconds_bucket{service="<service>"}[5m])) by (le, target))
```

### 4. Check for Recent Changes
```bash
# Recent deployments
kubectl rollout history deployment/<service> -n <namespace>

# Recent config changes
kubectl get configmaps -l app=<service> -n <namespace> -o yaml
```

## Common Causes & Remediation

### CPU Throttling
**Symptoms**: High CPU usage, request queuing

**Fix**:
```bash
# Scale up
kubectl scale deployment/<service> --replicas=<n> -n <namespace>

# Or increase CPU limits
kubectl patch deployment <service> -n <namespace> -p '{"spec":{"template":{"spec":{"containers":[{"name":"<container>","resources":{"limits":{"cpu":"2"}}}]}}}}'
```

### Database Slow Queries
**Symptoms**: High database latency, connection pool exhaustion

**Fix**:
1. Check slow query logs
2. Add missing indexes
3. Increase connection pool size

### Memory Pressure / GC
**Symptoms**: Sawtooth memory pattern, GC pauses

**Fix**:
1. Increase memory limits
2. Review memory-heavy operations
3. Check for memory leaks

### Network Saturation
**Symptoms**: High network I/O, packet drops

**Fix**:
1. Check network policies
2. Review rate limits
3. Consider caching

## Rollback Procedure
If latency started after a recent deployment:
```bash
kubectl rollout undo deployment/<service> -n <namespace>
```

## Escalation
If issue persists after basic troubleshooting:
1. Check infrastructure (node issues, network problems)
2. Engage database team if DB-related
3. Review application-level profiling
