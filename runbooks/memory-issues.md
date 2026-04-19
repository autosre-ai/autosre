---
symptoms: high memory, OOMKilled, memory leak, out of memory, memory pressure
services: any
tags: memory, resource, oom, limits
---

# High Memory Usage / OOMKilled

## Symptoms
- Container memory usage approaching limits (>85%)
- OOMKilled events in pod status
- Gradual memory increase over time (leak pattern)
- Pod restarts with exit code 137
- `kubectl top pods` shows memory near limits

## Investigation Steps

### 1. Check current memory usage vs limits
```bash
kubectl top pods -n <namespace>
kubectl describe pod <pod> | grep -A5 "Limits"
```

### 2. Check for OOMKilled events
```bash
kubectl get events --field-selector reason=OOMKilled -n <namespace>
kubectl get pod <pod> -o jsonpath='{.status.containerStatuses[0].lastState.terminated.reason}'
```

### 3. Review memory trends
```promql
container_memory_working_set_bytes{pod=~"<pod>.*"} / container_spec_memory_limit_bytes{pod=~"<pod>.*"} * 100
```

### 4. Check for memory leak pattern
```promql
rate(container_memory_working_set_bytes{pod=~"<pod>.*"}[1h]) > 0
```

## Root Causes

| Cause | Indicators | Likelihood |
|-------|-----------|------------|
| **Memory leak** | Gradual increase, no correlation with traffic | High |
| **Undersized limits** | Quick OOMKill after startup, works fine then dies | Medium |
| **Traffic spike** | Correlates with request rate increase | Medium |
| **Cache unbounded** | Memory grows indefinitely, no eviction | High |
| **Connection pool leak** | Memory grows with connection count | Medium |

## Remediation

### Immediate (stop the bleeding)
1. **Restart pod**: `kubectl delete pod <pod> -n <namespace>`
2. **Increase memory limits** (temporary):
   ```bash
   kubectl set resources deployment/<name> -n <namespace> --limits=memory=2Gi
   ```

### Short-term (stabilize)
1. Add memory monitoring alerts:
   ```yaml
   - alert: HighMemoryUsage
     expr: container_memory_working_set_bytes / container_spec_memory_limit_bytes > 0.85
     for: 5m
   ```
2. Enable memory profiling if available (pprof, heapdump)

### Long-term (fix root cause)
1. Profile application memory usage
2. Review garbage collection settings
3. Implement bounded caches with eviction
4. Fix memory leaks in application code
5. Right-size memory limits based on actual usage patterns

## Escalation
- If pod keeps getting OOMKilled after limit increase: escalate to dev team for memory profiling
- If affecting multiple services: check node memory pressure
