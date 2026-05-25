# Capacity Planning

AutoSRE provides comprehensive capacity planning capabilities to help SRE teams forecast resource needs, plan scaling activities, and generate insightful capacity reports.

## Overview

The capacity planning module includes:

- **Forecasting**: Time-series forecasting with multiple algorithms
- **Planning**: Capacity assessment, recommendations, and plans
- **Reporting**: Capacity reports, alerts, and insights

## Quick Start

### Basic Forecasting

```python
from autosre.capacity import (
    CapacityForecaster,
    TimeSeriesData,
    ForecastConfig,
    ForecastAlgorithm,
)
from datetime import datetime, timedelta, timezone

# Create time series data
data = TimeSeriesData(
    name="api-server-cpu",
    resource_type="cpu",
    unit="percent",
)

# Add historical data points (e.g., hourly CPU utilization)
now = datetime.now(timezone.utc)
cpu_values = [45, 52, 48, 55, 62, 58, 65, 72, 68, 75, 70, 73]  # Last 12 hours

for i, value in enumerate(cpu_values):
    timestamp = now - timedelta(hours=len(cpu_values) - i)
    data.add_point(timestamp, value)

# Create forecaster and generate forecast
forecaster = CapacityForecaster()
config = ForecastConfig(
    algorithm=ForecastAlgorithm.HOLT_WINTERS,
    horizon_hours=168,  # 7 days ahead
    confidence_level="medium",
)

result = forecaster.forecast(data, config, threshold=85.0)

# Check results
print(f"Trend: {result.metrics.trend_direction.value}")
print(f"Peak predicted: {result.peak_predicted}")
if result.threshold_breach:
    print(f"Will breach 85% at: {result.threshold_breach['timestamp']}")
```

### Quick Forecast

For simple forecasting from a list of values:

```python
from autosre.capacity import quick_forecast, ForecastAlgorithm

# Historical CPU values (assumed hourly)
values = [45, 52, 48, 55, 62, 58, 65, 72, 68, 75, 70, 73]

# Get 48-hour forecast
forecast = quick_forecast(
    values=values,
    horizon_hours=48,
    algorithm=ForecastAlgorithm.LINEAR,
)

for point in forecast[:5]:
    print(f"{point['timestamp']}: {point['value']:.1f}%")
```

### Capacity Assessment

```python
from autosre.capacity import (
    CapacityPlanner,
    CurrentCapacity,
    ResourceSpec,
    ResourceType,
)

# Define current capacity
current = CurrentCapacity(
    name="production-cluster",
    service="api-gateway",
    environment="production",
    region="us-west-2",
)

# Add resources
current.add_resource(ResourceSpec(
    resource_type=ResourceType.CPU,
    unit="cores",
    current_allocation=100,
    current_usage=85,
    max_allocation=200,
    cost_per_unit_hour=0.05,
))

current.add_resource(ResourceSpec(
    resource_type=ResourceType.MEMORY,
    unit="GB",
    current_allocation=256,
    current_usage=180,
    max_allocation=512,
    cost_per_unit_hour=0.01,
))

current.add_resource(ResourceSpec(
    resource_type=ResourceType.DISK,
    unit="TB",
    current_allocation=10,
    current_usage=2,
    max_allocation=50,
    cost_per_unit_hour=0.001,
))

# Assess capacity
planner = CapacityPlanner()
assessment = planner.assess_capacity(current)

print(f"Health: {assessment['health']}")
print(f"Average Utilization: {assessment['average_utilization']:.1f}%")
print(f"Critical Resources: {assessment['critical_resources']}")
print(f"Underutilized Resources: {assessment['underutilized_resources']}")
```

### Creating Capacity Plans

```python
from autosre.capacity import (
    CapacityPlanner,
    CurrentCapacity,
    CapacityRequirement,
    ResourceType,
    PlanningHorizon,
)
from datetime import datetime, timedelta, timezone

# Create planner
planner = CapacityPlanner(
    high_utilization_threshold=80.0,
    low_utilization_threshold=30.0,
    target_utilization=70.0,
)

# Define requirements
requirements = [
    CapacityRequirement(
        resource_type=ResourceType.CPU,
        required_capacity=150,
        unit="cores",
        needed_by=datetime.now(timezone.utc) + timedelta(days=30),
        min_headroom_percent=20.0,
        reason="Q4 traffic growth",
        based_on="forecast",
        confidence=0.85,
    ),
    CapacityRequirement(
        resource_type=ResourceType.MEMORY,
        required_capacity=300,
        unit="GB",
        needed_by=datetime.now(timezone.utc) + timedelta(days=45),
        reason="New feature rollout",
        based_on="product_roadmap",
    ),
]

# Create capacity plan
plan = planner.create_plan(
    name="Q4 2024 Capacity Plan",
    current=current,  # From previous example
    horizon=PlanningHorizon.SHORT_TERM,
    requirements=requirements,
    include_optimization=True,
)

# Review recommendations
print(f"Plan: {plan.name}")
print(f"Recommendations: {len(plan.recommendations)}")

for rec in plan.recommendations:
    print(f"\n{rec.priority.value.upper()}: {rec.recommendation_type.value}")
    print(f"  {rec.resource_type.value}: {rec.current_value} -> {rec.recommended_value} {rec.unit}")
    print(f"  Reason: {rec.reason}")
    print(f"  Cost Impact: ${rec.monthly_cost_change:+.2f}/month")

# Budget summary
if plan.budget_estimate:
    budget = plan.budget_estimate
    print(f"\nBudget Summary:")
    print(f"  Current Monthly: ${budget.current_monthly_cost:.2f}")
    print(f"  Projected Monthly: ${budget.projected_monthly_cost:.2f}")
    print(f"  Change: {budget.net_change_percent:+.1f}%")
```

### Generating Reports

```python
from autosre.capacity import (
    CapacityReporter,
    ReportConfig,
    ReportFormat,
    ReportSection,
)

# Utilization data (could come from monitoring system)
utilization_data = [
    {
        "resource_type": "cpu",
        "name": "api-server",
        "utilization": 82,
        "allocation": 100,
        "usage": 82,
        "unit": "cores",
        "change_vs_yesterday": 5,
    },
    {
        "resource_type": "memory",
        "name": "api-server",
        "utilization": 65,
        "allocation": 256,
        "usage": 166,
        "unit": "GB",
        "change_vs_yesterday": -2,
    },
    {
        "resource_type": "disk",
        "name": "database",
        "utilization": 18,
        "allocation": 10,
        "usage": 1.8,
        "unit": "TB",
        "change_vs_yesterday": 0,
    },
]

# Configure report
config = ReportConfig(
    sections=[
        ReportSection.SUMMARY,
        ReportSection.UTILIZATION,
        ReportSection.ALERTS,
        ReportSection.RECOMMENDATIONS,
    ],
    warning_threshold=70.0,
    critical_threshold=85.0,
    format=ReportFormat.MARKDOWN,
)

# Generate report
reporter = CapacityReporter(config)
report = reporter.generate_report(
    title="Weekly Capacity Report",
    utilization_data=utilization_data,
    service="api-gateway",
    environment="production",
)

# Output as Markdown
markdown = reporter.format_report(report, ReportFormat.MARKDOWN)
print(markdown)
```

### Quick Health Check

```python
from autosre.capacity import get_capacity_health

utilization_data = [
    {"resource_type": "cpu", "name": "web-1", "utilization": 75},
    {"resource_type": "cpu", "name": "web-2", "utilization": 88},
    {"resource_type": "memory", "name": "cache", "utilization": 45},
]

health = get_capacity_health(utilization_data)

print(f"Status: {health['emoji']} {health['status']}")
print(f"Score: {health['score']}/100")
print(f"Critical: {health['critical']}, Warning: {health['warning']}")
```

## Forecasting Algorithms

### Linear Regression

Best for steady, linear growth patterns:

```python
config = ForecastConfig(
    algorithm=ForecastAlgorithm.LINEAR,
    horizon_hours=168,
)
```

### Exponential Smoothing

Best for data with noise but consistent trends:

```python
config = ForecastConfig(
    algorithm=ForecastAlgorithm.EXPONENTIAL,
    smoothing_factor=0.3,  # 0-1, higher = more weight on recent data
)
```

### Holt-Winters (Triple Exponential)

Best for data with trends and seasonality:

```python
config = ForecastConfig(
    algorithm=ForecastAlgorithm.HOLT_WINTERS,
    smoothing_factor=0.3,
    trend_smoothing=0.1,
    seasonal_smoothing=0.1,
    seasonality=SeasonalityType.DAILY,
)
```

### Comparing Algorithms

```python
# Compare all algorithms on the same data
results = forecaster.compare_algorithms(data)

for algo, result in results.items():
    if isinstance(result, dict) and "error" in result:
        print(f"{algo}: Error - {result['error']}")
    else:
        print(f"{algo}: Trend={result.metrics.trend_direction.value}")
```

## Anomaly Detection

Automatically detect anomalies in capacity data:

```python
config = ForecastConfig(
    detect_anomalies=True,
    anomaly_threshold_std=3.0,  # Standard deviations from mean
)

result = forecaster.forecast(data, config)

if result.anomaly_detection:
    print(f"Anomalies found: {result.anomaly_detection.anomalies_found}")
    for point in result.anomaly_detection.anomaly_points:
        print(f"  {point['timestamp']}: {point['value']}")
```

## Seasonality Detection

Detect seasonal patterns in your data:

```python
from autosre.capacity import detect_seasonality

# Need at least 48 data points for seasonality detection
values = [...]  # 48+ hourly values

result = detect_seasonality(values)

print(f"Seasonality detected: {result['detected']}")
print(f"Type: {result['type']}")
print(f"Strength: {result['strength']}")
```

## Planning Horizons

Different horizons for different planning needs:

| Horizon | Duration | Use Case |
|---------|----------|----------|
| IMMEDIATE | 0-7 days | Emergency scaling, incident response |
| SHORT_TERM | 7-30 days | Sprint planning, feature launches |
| MEDIUM_TERM | 1-3 months | Quarterly planning, growth scaling |
| LONG_TERM | 3-12 months | Annual budgeting, infrastructure planning |
| STRATEGIC | 1-3 years | Technology roadmap, major migrations |

```python
# For urgent scaling needs
plan = planner.create_plan(
    name="Emergency Scaling",
    current=current,
    horizon=PlanningHorizon.IMMEDIATE,
)

# For quarterly planning
plan = planner.create_plan(
    name="Q1 2025 Capacity",
    current=current,
    horizon=PlanningHorizon.MEDIUM_TERM,
)
```

## Recommendation Types

The planner generates different types of recommendations:

| Type | Description | When Generated |
|------|-------------|----------------|
| SCALE_UP | Increase resource size | High utilization detected |
| SCALE_DOWN | Decrease resource size | Low utilization optimization |
| SCALE_OUT | Add more instances | Horizontal scaling needed |
| SCALE_IN | Remove instances | Over-provisioned |
| OPTIMIZE | Tune configuration | Efficiency improvements |
| RIGHT_SIZE | Match allocation to usage | Cost optimization |
| RESERVE | Reserve capacity ahead | Known future requirements |
| NO_ACTION | No changes needed | Healthy state |

## Cost Estimation

Estimate costs for capacity changes:

```python
# Add cost information to resources
current.add_resource(ResourceSpec(
    resource_type=ResourceType.CPU,
    unit="cores",
    current_allocation=100,
    current_usage=85,
    max_allocation=200,
    cost_per_unit_hour=0.05,  # $0.05/core/hour
))

# Create plan with cost estimates
plan = planner.create_plan(...)

# Review budget
budget = plan.budget_estimate
print(f"Current: ${budget.current_monthly_cost:.2f}/month")
print(f"Projected: ${budget.projected_monthly_cost:.2f}/month")
print(f"Scaling costs: ${budget.scaling_costs:.2f}/month")
print(f"Optimization savings: ${budget.optimization_savings:.2f}/month")
```

## Report Formats

Reports can be generated in multiple formats:

### JSON (Default)

```python
json_output = reporter.format_report(report, ReportFormat.JSON)
```

### Markdown

```python
markdown = reporter.format_report(report, ReportFormat.MARKDOWN)
```

### Slack

```python
slack_message = reporter.format_report(report, ReportFormat.SLACK)
# Send to Slack webhook
```

## Integration Examples

### With Prometheus

```python
import requests

# Query Prometheus for CPU utilization
response = requests.get(
    "http://prometheus:9090/api/v1/query_range",
    params={
        "query": 'avg(rate(container_cpu_usage_seconds_total[5m])) * 100',
        "start": (datetime.now() - timedelta(days=7)).timestamp(),
        "end": datetime.now().timestamp(),
        "step": "1h",
    }
)

data = response.json()
values = [float(v[1]) for v in data["data"]["result"][0]["values"]]

# Create forecast
forecast = quick_forecast(values, horizon_hours=168)
```

### With AWS CloudWatch

```python
import boto3
from datetime import datetime, timedelta

cloudwatch = boto3.client('cloudwatch')

# Get EC2 CPU metrics
response = cloudwatch.get_metric_data(
    MetricDataQueries=[{
        'Id': 'cpu',
        'MetricStat': {
            'Metric': {
                'Namespace': 'AWS/EC2',
                'MetricName': 'CPUUtilization',
                'Dimensions': [{'Name': 'InstanceId', 'Value': 'i-1234567890abcdef0'}]
            },
            'Period': 3600,
            'Stat': 'Average',
        },
    }],
    StartTime=datetime.now() - timedelta(days=7),
    EndTime=datetime.now(),
)

values = response['MetricDataResults'][0]['Values']
forecast = quick_forecast(values, horizon_hours=168)
```

### Scheduled Reporting

```python
from apscheduler.schedulers.blocking import BlockingScheduler

def generate_daily_report():
    # Fetch current utilization data
    utilization_data = fetch_utilization_from_monitoring()
    
    # Generate report
    report = generate_quick_report(
        utilization_data,
        title=f"Daily Capacity Report - {datetime.now().date()}"
    )
    
    # Send to Slack
    slack_message = reporter.format_report(report, ReportFormat.SLACK)
    send_to_slack(slack_message)

scheduler = BlockingScheduler()
scheduler.add_job(generate_daily_report, 'cron', hour=8)
scheduler.start()
```

## Best Practices

### 1. Use Appropriate Forecasting Windows

- **7+ days of data**: Linear regression
- **30+ days of data**: Exponential smoothing, Holt-Winters
- **90+ days of data**: Seasonality detection

### 2. Set Realistic Thresholds

```python
# Production workloads
planner = CapacityPlanner(
    high_utilization_threshold=80.0,
    low_utilization_threshold=30.0,
    target_utilization=70.0,
)

# Batch/dev workloads (can run hotter)
planner = CapacityPlanner(
    high_utilization_threshold=90.0,
    low_utilization_threshold=20.0,
    target_utilization=80.0,
)
```

### 3. Include Headroom in Requirements

```python
requirement = CapacityRequirement(
    resource_type=ResourceType.CPU,
    required_capacity=100,
    min_headroom_percent=20.0,  # 20% buffer
    max_utilization_percent=80.0,  # Don't exceed 80%
)
```

### 4. Regular Capacity Reviews

- Daily: Quick health checks
- Weekly: Detailed reports with trends
- Monthly: Full capacity plans with budget review
- Quarterly: Strategic planning with long-term forecasts

### 5. Act on Insights

```python
# Prioritize recommendations
for rec in plan.get_critical_recommendations():
    print(f"URGENT: {rec.reason}")
    print(f"Action: {rec.recommendation_type.value}")
    print(f"Deadline: {rec.recommended_by}")
```

## Troubleshooting

### Forecast Accuracy Issues

1. **Check data quality**: Ensure no missing or anomalous data points
2. **Try different algorithms**: Compare results with `compare_algorithms()`
3. **Adjust smoothing factors**: Lower for more responsive, higher for smoother

### High False Positive Alerts

1. **Adjust thresholds**: Increase warning/critical thresholds
2. **Use rolling averages**: Instead of point-in-time utilization
3. **Filter by severity**: Use `min_severity` in report config

### Cost Estimation Accuracy

1. **Include accurate pricing**: Set `cost_per_unit_hour` for each resource
2. **Account for volume discounts**: Adjust costs in `assumptions`
3. **Review reserved instance coverage**: Factor in existing commitments
