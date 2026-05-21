# Metrics Analysis

Statistical anomaly detection and SRE methodology for metrics-based incident investigation.

## Overview

This skill provides metrics analysis methodology using RED/USE methods, anomaly detection with statistical thresholds, and SLO-aware investigation.

## Quick Reference

**Your Role:** Detect anomalies, find correlations, identify change points, assess SLO impact
**Start With:** Error rates and latency around incident time
**Key Output:** Anomalies with timestamps, severity, statistical confidence, and correlation

## Anomaly Detection Thresholds

When reporting anomalies, use these statistical thresholds:

| Severity | Threshold | Meaning |
|----------|-----------|---------|
| **Critical** | > 4σ from baseline | Extremely unusual, almost certainly a problem |
| **High** | > 3σ from baseline | Very unusual, likely a problem (99.7% confidence) |
| **Medium** | > 2σ from baseline | Notable deviation, investigate (95% confidence) |
| **Low** | > 1.5σ from baseline | Minor deviation, may be noise |

Always report: `metric_name: current_value (baseline: X, deviation: Yσ)`

## RED Method (Request-Driven Services)

For microservices, check these in order:
1. **Rate** - Request throughput (requests/sec). Sudden drop = service down?
2. **Errors** - Error rate (%). Spike = bugs, dependencies, or overload?
3. **Duration** - Latency (p50, p95, p99). Increase = saturation or dependency issues?

## USE Method (Resources)

For infrastructure (CPU, memory, disk, network):
1. **Utilization** - % of resource capacity being used
2. **Saturation** - Queue depth, wait time when resource is at capacity
3. **Errors** - Hardware/software errors (disk I/O errors, network drops)

## SLI/SLO Awareness

When analyzing metrics:
1. **Identify the SLI** - What metric represents user experience? (usually latency or availability)
2. **Check error budget** - How much budget has been consumed?
3. **Burn rate** - How fast is the error budget depleting?
   - Normal: < 1x (on track to meet SLO)
   - Warning: 1-3x (may exhaust budget this period)
   - Critical: > 3x (will exhaust budget soon)

## Seasonality & Baseline

When comparing metrics:
- **Same time yesterday** - Compare to same hour yesterday
- **Same time last week** - Account for weekly patterns
- **Rolling average** - 7-day rolling average for baseline
- **Business hours** - 9am-6pm patterns differ from off-hours

Report: `Current: 500 errors/min (yesterday same time: 10, last week: 8)`

## Key Metrics by Category

| Category | Metrics | What to Look For |
|----------|---------|------------------|
| **Errors** | 4xx rate, 5xx rate, exception count | Sudden spikes, error type distribution |
| **Latency** | p50, p95, p99, max | Increases, bimodal distribution, outliers |
| **Throughput** | requests/sec, transactions/sec | Unexpected drops or spikes |
| **Saturation** | CPU %, memory %, queue depth | Approaching limits (>80% warning, >90% critical) |
| **Dependencies** | DB query time, cache hit rate, API latency | Degradation in upstream/downstream |

## PromQL Examples

### Error Rate
```promql
# 5xx error rate as percentage
sum(rate(http_requests_total{status=~"5.."}[5m])) 
/ sum(rate(http_requests_total[5m])) * 100

# Error rate by service
sum by (service) (rate(http_requests_total{status=~"5.."}[5m]))
```

### Latency
```promql
# p99 latency
histogram_quantile(0.99, 
  sum(rate(http_request_duration_seconds_bucket[5m])) by (le)
)

# Latency comparison to yesterday
http_request_duration_seconds:p99 
- http_request_duration_seconds:p99 offset 1d
```

### Saturation
```promql
# CPU saturation
100 - (avg(irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

# Memory pressure
(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100
```

### Change Detection
```promql
# Detect significant change (>2x from 5min ago)
rate(http_requests_total[5m]) 
/ rate(http_requests_total[5m] offset 5m) > 2
```

## Investigation Steps

1. **Identify SLIs** - What metrics represent user-facing impact?
2. **Apply RED method** - Check rate, errors, duration for services
3. **Apply USE method** - Check utilization, saturation, errors for resources
4. **Detect anomalies** - Find deviations > 2σ from baseline
5. **Check seasonality** - Compare to same time yesterday/last week
6. **Find correlations** - Which metrics moved together? What changed first?
7. **Detect change points** - When exactly did behavior change?
8. **Assess SLO impact** - Error budget consumption, burn rate

## Output Template

```markdown
## Metrics Analysis Summary

### Anomalies Detected
| Metric | Value | Baseline | Deviation | Severity |
|--------|-------|----------|-----------|----------|
| error_rate | 15% | 0.1% | 4.5σ | Critical |
| p99_latency | 2.5s | 200ms | 3.2σ | High |

### RED Analysis
- **Rate**: 1000 req/s (normal: 1200, -17%)
- **Errors**: 15% (normal: 0.1%, +150x)
- **Duration**: p99=2.5s (normal: 200ms, +12x)

### USE Analysis (Resources)
- **CPU**: 45% utilization (normal)
- **Memory**: 82% utilization (elevated)
- **Network**: No saturation

### Temporal Correlation
- Error spike started at 10:32:15 UTC
- Correlates with: deployment at 10:30:00 UTC

### SLO Impact
- Error budget: 72% consumed (was 45% yesterday)
- Burn rate: 4.5x (critical)

### Change Points
1. 10:32:15 - Error rate jump from 0.1% to 15%
2. 10:32:20 - Latency increase from 200ms to 2.5s

### Recommendations
1. [Action based on findings]
```

## Configuration

```yaml
prometheus:
  url: http://prometheus:9090
  
grafana:
  url: http://grafana:3000
  api_key: ${GRAFANA_API_KEY}

datadog:
  api_key: ${DATADOG_API_KEY}
  app_key: ${DATADOG_APP_KEY}
```

## Dependencies

- Metrics backend (Prometheus, Grafana, Datadog, etc.)
