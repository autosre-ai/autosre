# Error Budget Tracking Skill

The Error Budget skill implements SLO-based operations, tracking error budgets and making data-driven decisions about reliability vs. velocity.

## Overview

An **error budget** is the inverse of your SLO. If your SLO is 99.9% availability, your error budget is 0.1% unavailability. This budget quantifies how much unreliability you can afford.

## Why Error Budgets?

Error budgets solve the eternal conflict between:
- **Development**: "Ship features faster!"
- **Operations**: "Keep it stable!"

With error budgets:
- Budget remaining → ship features
- Budget exhausted → focus on reliability

Both teams share the same metric and incentives.

## Usage

### Basic Error Budget Status

```python
from autosre.skills import ErrorBudgetSkill

skill = ErrorBudgetSkill()

# Get current error budget status
status = await skill.get_budget_status("payment-service")

print(status)
# {
#   "slo_target": 0.999,
#   "current_sli": 0.9985,
#   "budget_total": 43.2,        # minutes per 30-day window
#   "budget_consumed": 21.6,     # minutes consumed
#   "budget_remaining": 21.6,    # minutes remaining
#   "budget_remaining_percent": 0.50,
#   "burn_rate": 1.2,            # consuming 1.2x faster than sustainable
#   "projected_exhaustion": "2024-01-20T14:30:00Z"
# }
```

### Multi-Window Burn Rate

```python
# Get burn rate across multiple windows
# Fast burn = immediate problem, slow burn = gradual degradation
burn_rates = await skill.get_burn_rates("payment-service")

print(burn_rates)
# {
#   "1h_burn_rate": 14.4,    # Critical! 14x sustainable rate
#   "6h_burn_rate": 3.2,     # High, needs attention
#   "24h_burn_rate": 1.5,    # Slightly elevated
#   "7d_burn_rate": 1.1,     # Near sustainable
#   "status": "critical",
#   "recommended_action": "immediate_investigation"
# }
```

### Budget Forecasting

```python
# Forecast budget status
forecast = await skill.forecast_budget(
    service="payment-service",
    horizon_days=7
)

print(forecast)
# {
#   "current_remaining_percent": 0.50,
#   "forecasted_remaining_percent": 0.15,
#   "exhaustion_date": "2024-01-25",
#   "confidence": 0.85,
#   "recommendation": "Reduce deployment velocity or address reliability issues"
# }
```

### Deployment Gating

```python
# Check if deployment is allowed
deployment_check = await skill.check_deployment_allowed(
    service="payment-service",
    deployment_risk="medium"  # low, medium, high
)

if deployment_check.allowed:
    print("Deployment approved")
else:
    print(f"Deployment blocked: {deployment_check.reason}")
    print(f"Budget remaining: {deployment_check.budget_remaining_percent}%")
    print(f"Required for medium-risk deploy: 30%")
```

### Budget Allocation

```python
# Allocate budget across incident types
allocation = await skill.get_budget_allocation("payment-service")

print(allocation)
# {
#   "deployments": 0.15,      # 15% consumed by deployments
#   "infrastructure": 0.10,   # 10% by infrastructure issues
#   "dependencies": 0.20,     # 20% by dependency failures
#   "unknown": 0.05,          # 5% unattributed
#   "remaining": 0.50         # 50% remaining
# }
```

## Configuration

```yaml
# config/autosre.yaml
slo:
  default_target: 0.999
  error_budget_warning_threshold: 0.20
  block_deploy_when_exhausted: true
  
  error_budget_policies:
    freeze_threshold: 0.10
    caution_threshold: 0.30
    exhausted_actions:
      - block_deployments
      - notify_oncall
      - create_incident
  
  calculation:
    window_days: 30
    exclude_maintenance: true
    good_event_threshold: 0.95
```

### Per-Service SLO Configuration

```yaml
# config/slos.yaml
services:
  payment-service:
    slo_target: 0.9999  # Four nines (critical service)
    indicators:
      - type: availability
        query: "sum(rate(http_requests_total{status!~'5..'}[5m])) / sum(rate(http_requests_total[5m]))"
      - type: latency
        query: "histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))"
        threshold: 0.5  # 500ms
  
  notification-service:
    slo_target: 0.999  # Three nines (less critical)
    indicators:
      - type: availability
        query: "..."
```

## Error Budget Policies

### Deployment Velocity Matrix

| Budget Remaining | Deployment Policy |
|------------------|-------------------|
| > 50% | Full velocity, any deployment |
| 30-50% | Normal velocity, extra monitoring |
| 10-30% | Reduced velocity, only important changes |
| < 10% | Freeze non-critical deployments |
| 0% | Emergency freeze, reliability focus only |

### Burn Rate Alerts

| Burn Rate | Window | Meaning | Action |
|-----------|--------|---------|--------|
| 14.4x | 1 hour | Exhausts budget in 5 hours | Page immediately |
| 6x | 6 hours | Exhausts budget in 5 days | Investigate soon |
| 3x | 1 day | Exhausts budget in 10 days | Plan remediation |
| 1x | 7 days | Sustainable | Monitor |

## Integration with CI/CD

```yaml
# Example GitHub Actions integration
name: Deploy with Error Budget Check

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Check Error Budget
        run: |
          result=$(autosre budget check payment-service --json)
          remaining=$(echo $result | jq '.budget_remaining_percent')
          
          if (( $(echo "$remaining < 0.10" | bc -l) )); then
            echo "Error budget exhausted. Deployment blocked."
            exit 1
          fi
      
      - name: Deploy
        if: success()
        run: ./deploy.sh
```

## Metrics Exported

```promql
# Error budget metrics
autosre_error_budget_remaining_ratio{service="payment-service"}
autosre_error_budget_consumed_minutes{service="payment-service"}
autosre_error_budget_burn_rate{service="payment-service", window="1h"}
autosre_error_budget_burn_rate{service="payment-service", window="6h"}

# SLO metrics
autosre_slo_target{service="payment-service"}
autosre_sli_current{service="payment-service", indicator="availability"}
autosre_sli_current{service="payment-service", indicator="latency_p99"}

# Deployment gating metrics
autosre_deployment_blocked_total{service="payment-service", reason="budget_exhausted"}
autosre_deployment_allowed_total{service="payment-service"}
```

## Best Practices

### 1. Choose Meaningful SLOs

Your SLO should reflect user expectations:
- **Too strict**: Constant firefighting, no feature velocity
- **Too lenient**: Users unhappy before SLO breaches

Start with current performance, then tighten over time.

### 2. Use Multiple SLIs

Don't rely on availability alone:
- Availability (requests succeeding)
- Latency (requests fast enough)
- Throughput (handling expected load)
- Correctness (returning right answers)

### 3. Attribute Budget Consumption

Track WHY budget is consumed:
- Deployments
- Infrastructure failures
- Dependency issues
- Traffic spikes

This drives improvement focus.

### 4. Reset Thoughtfully

Rolling windows (30 days) reset continuously. But consider:
- Don't "spend" budget recklessly at month start
- Major incidents impact the full window
- Plan releases around budget status

### 5. Communicate Broadly

Everyone should know:
- Current budget status
- What happens if exhausted
- How their work affects the budget

## Common Mistakes

### 1. SLO ≠ SLA

- **SLO**: Internal target (aim for this)
- **SLA**: External commitment (penalty if breached)

Set SLOs tighter than SLAs to have margin.

### 2. Ignoring User Journey

A 99.9% SLO doesn't mean much if:
- 99.9% of successful requests are health checks
- The 0.1% failures are all during checkout

Weight SLIs by user impact.

### 3. Budget Hoarding

Don't be afraid to use the budget:
- Budget exists to enable velocity
- Unused budget ≠ reliability
- Ship features, learn, improve

## See Also

- [Golden Signals Monitoring](./golden_signals.md)
- [Cascading Failure Analysis](./cascading_failure.md)
- [AI Safety Features](./ai_safety.md)
