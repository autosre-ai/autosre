# Golden Signals Skill

The Golden Signals skill implements the four golden signals as defined by Google's SRE book, providing a standardized framework for monitoring service health.

## Overview

The four golden signals are:

1. **Latency** - The time it takes to service a request
2. **Traffic** - The demand being placed on your system
3. **Errors** - The rate of requests that fail
4. **Saturation** - How "full" your service is

## Why Golden Signals?

Golden signals provide a **universal language** for service health. Instead of drowning in hundreds of metrics, teams focus on the four that matter most for user experience.

## Usage

### Basic Health Check

```python
from autosre.skills import GoldenSignalsSkill

skill = GoldenSignalsSkill()

# Get current health status
health = await skill.get_health("payment-service")
print(health)
# {
#   "latency": {"p50": 45, "p90": 120, "p99": 450, "status": "healthy"},
#   "traffic": {"rps": 1250, "trend": "stable", "status": "healthy"},
#   "errors": {"rate": 0.02, "status": "healthy"},
#   "saturation": {"cpu": 0.45, "memory": 0.62, "status": "healthy"}
# }
```

### Latency Monitoring

```python
# Get latency breakdown
latency = await skill.get_latency(
    service="payment-service",
    percentiles=[50, 90, 95, 99],
    window="5m"
)

# Compare against SLO
slo_status = await skill.check_latency_slo(
    service="payment-service",
    target_p99_ms=500
)
```

### Traffic Analysis

```python
# Get traffic patterns
traffic = await skill.get_traffic(
    service="payment-service",
    window="1h"
)

# Detect anomalies
anomalies = await skill.detect_traffic_anomaly(
    service="payment-service",
    baseline_window="7d",
    sensitivity=2.5  # standard deviations
)
```

### Error Tracking

```python
# Get error breakdown
errors = await skill.get_errors(
    service="payment-service",
    window="15m",
    group_by=["status_code", "endpoint"]
)

# Identify error spikes
spikes = await skill.detect_error_spike(
    service="payment-service",
    threshold=0.01,  # 1% error rate
    window="5m"
)
```

### Saturation Monitoring

```python
# Get resource saturation
saturation = await skill.get_saturation(
    service="payment-service",
    resources=["cpu", "memory", "disk", "connections"]
)

# Predict saturation
prediction = await skill.predict_saturation(
    service="payment-service",
    resource="disk",
    horizon="24h"
)
```

## Configuration

```yaml
# config/autosre.yaml
golden_signals:
  latency:
    percentiles: [50, 90, 95, 99]
    targets:
      p50: 100
      p90: 250
      p95: 500
      p99: 1000
  
  traffic:
    baseline_window_hours: 168
    anomaly_sensitivity: 2.5
  
  errors:
    threshold_percentage: 1.0
    error_codes: [500, 502, 503, 504]
  
  saturation:
    warning_threshold: 0.70
    critical_threshold: 0.90
    resources:
      - cpu
      - memory
      - disk
      - network_bandwidth
      - connection_pool
```

## Integration with Prometheus

The skill integrates with Prometheus for metrics collection:

```promql
# Latency (histogram)
histogram_quantile(0.99, 
  sum(rate(http_request_duration_seconds_bucket{service="payment-service"}[5m])) 
  by (le)
)

# Traffic (counter)
sum(rate(http_requests_total{service="payment-service"}[5m]))

# Errors (counter)
sum(rate(http_requests_total{service="payment-service", status=~"5.."}[5m]))
/
sum(rate(http_requests_total{service="payment-service"}[5m]))

# Saturation (gauge)
container_memory_usage_bytes{pod=~"payment-service.*"}
/
container_spec_memory_limit_bytes{pod=~"payment-service.*"}
```

## Best Practices

### 1. Set Meaningful SLOs

Don't just pick arbitrary numbers. Base your targets on:
- User expectations
- Business requirements
- Historical performance

### 2. Alert on Symptoms, Not Causes

Alert on latency degradation, not on CPU usage. Users don't care about CPU; they care about slow responses.

### 3. Use Appropriate Windows

- **Short windows (1-5m)**: Catch acute issues quickly
- **Long windows (1h+)**: Reduce noise, catch trends

### 4. Differentiate Success vs Error Latency

Track latency for successful and failed requests separately. Errors are often fast (immediate rejection), which can skew your latency metrics.

## Troubleshooting

### Missing Metrics

If golden signals aren't populating:

1. Verify Prometheus scrape targets
2. Check metric naming conventions
3. Ensure services are instrumented

### Noisy Alerts

If alerts are too frequent:

1. Increase evaluation window
2. Adjust thresholds based on baseline
3. Use multi-window alerting (short AND long window)

### Inconsistent Data

If metrics seem wrong:

1. Check for clock skew between services
2. Verify rate() vs increase() usage
3. Check for counter resets

## See Also

- [Error Budget Tracking](./error_budget.md)
- [Cascading Failure Analysis](./cascading_failure.md)
- [AI Safety Features](./ai_safety.md)
