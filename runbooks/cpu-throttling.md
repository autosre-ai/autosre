---
symptoms: CPU throttling, high CPU, throttled, slow performance, CPU limit
services: any
tags: cpu, throttling, resource, limits, performance
---

# CPU Throttling

## Symptoms
- Degraded application performance
- Higher than expected latency
- `container_cpu_cfs_throttled_seconds_total` increasing
- CPU usage consistently at or near limits
- Sporadic slowdowns during traffic spikes

## Investigation Steps

### 1. Check for throttling
```promql
# Throttling rate (seconds throttled per second)
rate(container_cpu_cfs_throttled_seconds_total{pod=~"<pod>.*"}[5m])

# Percentage of periods throttled
rate(container_cpu_cfs_throttled_periods_total[5m]) / rate(container_cpu_cfs_periods_total[5m]) * 100
```

### 2. Check CPU usage vs limits
```bash
kubectl top pods -n <namespace>
kubectl describe pod <pod> | grep -A5 "Limits"
```

```promql
# CPU usage vs limit percentage
sum(rate(container_cpu_usage_seconds_total{pod=~"<pod>.*"}[5m])) 
/ sum(kube_pod_container_resource_limits{pod=~"<pod>.*", resource="cpu"}) * 100
```

### 3. Check node CPU pressure
```bash
kubectl top nodes
kubectl describe node <node> | grep -A10 "Allocated resources"
```

### 4. Correlate with latency
```promql
# Plot side by side
histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{pod=~"<pod>.*"}[5m])) by (le))
```

## Understanding CFS Throttling

Kubernetes uses CFS (Completely Fair Scheduler) bandwidth control:
- CPU limit of 1 core = 100ms of CPU time per 100ms period
- If your app needs more, it gets throttled (paused) until next period
- Even brief spikes can cause throttling

```
Limit: 500m (0.5 cores)
Period: 100ms
Quota: 50ms per period

If your app uses 60ms in a burst → 10ms throttled → latency spike
```

## Root Causes

| Cause | Indicators | Solution |
|-------|-----------|----------|
| **Undersized limits** | Constant throttling at steady load | Increase CPU limit |
| **Traffic spikes** | Throttling correlates with request rate | Scale out or increase limits |
| **Inefficient code** | High CPU with low throughput | Profile and optimize |
| **Blocking operations** | CPU spikes with sync calls | Make async, add timeouts |
| **GC pressure** | GC correlates with throttling | Tune GC, reduce allocation |

## Remediation

### Immediate
1. **Increase CPU limits**:
   ```bash
   kubectl set resources deployment/<name> --limits=cpu=2 -n <namespace>
   ```

2. **Scale horizontally**:
   ```bash
   kubectl scale deployment/<name> --replicas=<n> -n <namespace>
   ```

### Short-term
1. Set up HPA (Horizontal Pod Autoscaler):
   ```yaml
   apiVersion: autoscaling/v2
   kind: HorizontalPodAutoscaler
   metadata:
     name: <deployment>
   spec:
     scaleTargetRef:
       apiVersion: apps/v1
       kind: Deployment
       name: <deployment>
     minReplicas: 2
     maxReplicas: 10
     metrics:
     - type: Resource
       resource:
         name: cpu
         target:
           type: Utilization
           averageUtilization: 70
   ```

2. Add CPU throttling alert:
   ```yaml
   - alert: CPUThrottling
     expr: |
       rate(container_cpu_cfs_throttled_periods_total[5m]) 
       / rate(container_cpu_cfs_periods_total[5m]) > 0.25
     for: 5m
     labels:
       severity: warning
   ```

### Long-term
1. Profile CPU hotspots
2. Optimize heavy computation
3. Consider async patterns for I/O-bound work
4. Right-size limits based on actual usage + headroom
5. Implement request-based autoscaling (not just CPU)

## Best Practices

### Setting CPU Limits
- **Requests**: Set to typical usage (P50)
- **Limits**: Set to peak usage + 20-30% headroom
- **Or**: Remove limits entirely if node has headroom (controversial but effective)

### Monitoring
- Alert on throttling rate > 25% of periods
- Track P99 latency correlation with throttling
- Monitor during traffic spikes and deployments
