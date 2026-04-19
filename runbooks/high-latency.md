---
symptoms: high latency, slow response, timeout, p99 latency, response time, slow requests
services: any
tags: latency, performance, timeout, slow, response time
---

# High Latency / Slow Response Times

## Symptoms
- Increased response time (p50, p95, p99 latency)
- Request timeouts
- User complaints about slowness
- SLA breaches
- Upstream service timeouts

## Investigation Steps

### 1. Identify the scope
```promql
# Which services are affected?
histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (service, le))

# Is it all endpoints or specific ones?
histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (path, le))
```

### 2. Check if it's resource-related
```bash
kubectl top pods -n <namespace>
kubectl top nodes
```

```promql
# CPU throttling?
rate(container_cpu_cfs_throttled_seconds_total[5m]) > 0

# Memory pressure?
container_memory_working_set_bytes / container_spec_memory_limit_bytes > 0.85
```

### 3. Check dependencies
```promql
# Database latency
histogram_quantile(0.99, sum(rate(db_query_duration_seconds_bucket[5m])) by (le))

# External service latency
histogram_quantile(0.99, sum(rate(http_client_duration_seconds_bucket[5m])) by (host, le))
```

### 4. Check for connection pool exhaustion
```promql
# Database connections
pg_stat_activity_count / pg_settings_max_connections > 0.8

# HTTP client connections
http_client_connections_active / http_client_connections_max > 0.8
```

### 5. Check garbage collection
```promql
# GC pause time
rate(jvm_gc_pause_seconds_sum[5m])

# Go GC
rate(go_gc_duration_seconds_sum[5m])
```

## Root Causes

| Cause | Indicators | Check |
|-------|-----------|-------|
| **CPU throttling** | High CPU usage, throttled periods | `container_cpu_cfs_throttled_*` |
| **Database slow queries** | DB latency spike | DB query metrics, slow query log |
| **Connection pool exhaustion** | Connections at limit | Pool metrics, waiting threads |
| **Garbage collection** | GC pause spikes | GC metrics, memory patterns |
| **Lock contention** | Thread waits | Thread dumps, profiler |
| **Cold start** | Latency after deploy/scale | Correlate with pod starts |
| **Network issues** | Intermittent, affects multiple services | Packet loss, DNS latency |
| **Downstream service** | Latency correlates with dependency | Trace waterfall |

## Remediation

### Immediate
1. **Scale out** if resource-bound:
   ```bash
   kubectl scale deployment <name> --replicas=<n> -n <namespace>
   ```

2. **Increase CPU limits** if throttling:
   ```bash
   kubectl set resources deployment/<name> --limits=cpu=2
   ```

3. **Enable circuit breaker** if downstream is slow (if supported)

### For database issues
1. Check slow query log
2. Add missing indexes
3. Increase connection pool size
4. Consider read replicas

### For GC issues
1. Increase heap size
2. Tune GC parameters
3. Profile memory allocation hotspots

### For connection pool exhaustion
1. Increase pool size
2. Reduce connection timeout
3. Check for connection leaks

## Prevention
1. Set up latency SLOs and alerts
2. Implement request timeouts at all layers
3. Use circuit breakers for dependencies
4. Regular load testing
5. Capacity planning based on traffic patterns
