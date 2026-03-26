# Capacity Planner Agent

Weekly resource utilization analysis with scaling recommendations and capacity forecasting.

## Overview

This agent runs weekly to:
1. Collect cluster and namespace metrics
2. Analyze resource utilization patterns
3. Identify rightsizing opportunities
4. Forecast capacity needs
5. Calculate potential cost savings
6. Generate actionable recommendations

## Triggers

### Scheduled (Primary)
- **Cron:** `0 6 * * 1` (Every Monday at 6 AM UTC)

### Manual
- **Path:** `/webhook/capacity-report`

## Configuration

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `slack_channel` | string | `#capacity-planning` | Report channel |
| `email_recipients` | list | `[]` | Email recipients |
| `report_period_days` | int | `7` | Analysis period |
| `forecast_days` | int | `30` | Forecast horizon |
| `namespaces` | list | `[production, staging]` | Namespaces to analyze |
| `enable_ai_recommendations` | bool | `true` | Enable LLM analysis |

### Thresholds
```yaml
thresholds:
  cpu_utilization_high: 80     # Alert if above
  cpu_utilization_low: 20      # Rightsizing opportunity
  memory_utilization_high: 85
  memory_utilization_low: 25
  node_utilization_target: 70  # Ideal node utilization
```

### Cost Configuration
```yaml
cost_per_cpu_hour: 0.05    # $/CPU/hour
cost_per_gb_hour: 0.01     # $/GB/hour
```

## Required Skills

- **prometheus** - Metrics collection
- **kubernetes** - Cluster data
- **slack** - Notifications
- **email** - Reports
- **llm** - AI recommendations (optional)
- **jira** - Ticket creation (optional)

## Workflow

```
┌─────────────────────┐
│  Monday 6 AM UTC    │
│  (Weekly Schedule)  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  1. Collect Metrics │
│  - Node metrics     │
│  - Namespace metrics│
│  - Workload metrics │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  2. Calculate       │
│     Utilization     │
│  - Cluster avg/peak │
│  - Namespace efficiency│
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  3. Identify        │
│     Opportunities   │
│  - Overprovisioned  │
│  - Underprovisioned │
│  - Missing limits   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  4. Forecast        │
│     Capacity        │
│  - 30-day projection│
│  - Trend analysis   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  5. Calculate       │
│     Savings         │
│  - Per workload     │
│  - Total potential  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  6. AI Analysis     │
│  (if enabled)       │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  7. Generate &      │
│     Distribute      │
│  - Slack summary    │
│  - Email report     │
│  - Jira tickets     │
└─────────────────────┘
```

## Metrics Collected

### Node Metrics
- CPU utilization (avg, peak)
- Memory utilization (avg, peak)
- Disk utilization

### Namespace Metrics
- CPU requests vs usage
- Memory requests vs usage
- Resource efficiency

### Workload Metrics
- Deployment replicas
- HPA status (current, desired, min, max)

## Rightsizing Analysis

### Overprovisioned Detection
```
condition: (requests - usage) / requests > 0.5
```
Workloads using less than 50% of requested resources.

### Underprovisioned Detection
```
condition: usage / limits > 0.8
```
Workloads using more than 80% of limits.

### Missing Resources
- No CPU/memory limits
- No CPU/memory requests

## Cost Savings Calculation

```python
cpu_savings = (cpu_requests - recommended_cpu) * cost_per_cpu_hour * 24 * 30
memory_savings = (memory_requests - recommended_memory) / 1e9 * cost_per_gb_hour * 24 * 30
total_savings = cpu_savings + memory_savings
```

## Forecasting

Uses linear regression on historical data:
- 7-day lookback
- 30-day forecast
- 95% confidence interval

Alerts when forecast exceeds thresholds:
- CPU > 80%
- Memory > 85%

## Example Output

### Slack Summary
```
📊 Weekly Capacity Report - 2024-01-15

Cluster CPU: 45.2% avg
Cluster Memory: 62.8% avg
Overprovisioned: 23 workloads
Potential Savings: $3,450/mo

30-Day Forecast:
• CPU: 52.1% ✅
• Memory: 71.3% ✅

Top Rightsizing Opportunities:
• production/data-processor - Save $450/mo
• production/batch-worker - Save $320/mo
• staging/api-server - Save $180/mo

[📄 Full Report] [📊 Grafana Dashboard]
```

### Email Report
Full markdown report with:
- Executive summary
- Node utilization table
- Namespace breakdown
- Rightsizing recommendations
- Forecast charts
- AI recommendations

## Testing

```bash
# Run unit tests
pytest test_agent.py -v

# Manual trigger
curl -X POST http://localhost:8080/webhook/capacity-report

# Generate report for specific period
curl -X POST http://localhost:8080/webhook/capacity-report \
  -d '{"period_days": 14}'
```

## Dashboard Integration

Link to Grafana dashboards:
```yaml
config:
  grafana_url: "https://grafana.example.com"
  report_url: "https://wiki.example.com/capacity-reports"
```

## Customization

### Add Custom Namespaces
```yaml
config:
  namespaces:
    - production
    - staging
    - data-processing
    - ml-training
```

### Adjust Cost Model
```yaml
config:
  cost_per_cpu_hour: 0.08    # Higher for on-demand
  cost_per_gb_hour: 0.015
  include_spot_savings: true
```
