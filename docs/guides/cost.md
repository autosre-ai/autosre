# Cost Optimization Guide

AutoSRE's cost optimization module provides comprehensive FinOps capabilities
for SRE teams, including cost analysis, recommendations, rightsizing, and
forecasting.

## Overview

The cost module helps you:

- **Analyze Costs**: Break down costs by service, team, environment, and resource type
- **Generate Recommendations**: Get actionable cost optimization recommendations
- **Rightsize Resources**: Identify oversized resources and optimal instance types
- **Forecast Spending**: Predict future costs and set up budget alerts
- **Detect Anomalies**: Find unexpected cost spikes or drops

## Installation

Cost optimization is included in the core AutoSRE package:

```bash
pip install autosre-ai
```

## Quick Start

### Cost Analysis

Analyze your cloud costs:

```python
from autosre.cost import CostAnalyzer, CostMetric, ResourceType, CloudProvider
from datetime import datetime, timedelta, timezone

# Create analyzer
analyzer = CostAnalyzer(currency="USD")

# Load cost data
costs = [
    CostMetric(
        timestamp=datetime.now(timezone.utc) - timedelta(days=1),
        amount=150.00,
        service="api-gateway",
        team="platform",
        environment="production",
        resource_type=ResourceType.COMPUTE,
        provider=CloudProvider.AWS,
    ),
    CostMetric(
        timestamp=datetime.now(timezone.utc) - timedelta(days=1),
        amount=75.00,
        service="database",
        team="data",
        environment="production",
        resource_type=ResourceType.DATABASE,
        provider=CloudProvider.AWS,
    ),
    # ... more cost records
]

analyzer.load_costs(costs)

# Get cost breakdown
breakdown = analyzer.analyze_breakdown(
    start_date=datetime.now(timezone.utc) - timedelta(days=30),
    end_date=datetime.now(timezone.utc),
)

print(f"Total Cost: ${breakdown.total_cost:,.2f}")
print(f"By Service: {breakdown.by_service}")
print(f"By Team: {breakdown.by_team}")
print(f"Top Resources: {breakdown.top_resources[:5]}")
print(f"Untagged: {breakdown.untagged_percentage:.1f}%")
```

### Cost Recommendations

Generate optimization recommendations:

```python
from autosre.cost import RecommendationEngine, RecommendationPriority

# Create recommendation engine
engine = RecommendationEngine(
    idle_threshold_days=7,
    utilization_threshold=0.2,
    min_savings_threshold=10.0,
)

# Define your resources
resources = [
    {
        "id": "i-abc123",
        "type": "compute",
        "size": "m5.2xlarge",
        "cost_per_month": 280,
        "service": "api",
        "team": "platform",
        "environment": "production",
        "age_days": 90,
    },
    {
        "id": "i-def456",
        "type": "compute",
        "size": "m5.xlarge",
        "cost_per_month": 140,
        "service": "batch",
        "team": "data",
        "environment": "dev",
        "stateless": True,
    },
]

# Define utilization data
utilization = {
    "i-abc123": {"cpu_avg": 15, "memory_avg": 25, "last_accessed": datetime.now(timezone.utc)},
    "i-def456": {"cpu_avg": 0.5, "memory_avg": 5, "last_accessed": datetime.now(timezone.utc) - timedelta(days=30)},
}

# Generate recommendations
recommendations = engine.generate_recommendations(resources, [], utilization)

for rec in recommendations:
    print(rec.summary)
    print()

# Get summary
summary = engine.get_summary()
print(f"Total Recommendations: {summary['total_recommendations']}")
print(f"Potential Monthly Savings: ${summary['total_monthly_savings']:,.2f}")
print(f"Potential Annual Savings: ${summary['total_annual_savings']:,.2f}")
```

### Rightsizing Analysis

Analyze resource utilization for rightsizing:

```python
from autosre.cost import (
    RightsizingAnalyzer,
    ResourceUtilization,
    InstanceSpec,
    UtilizationThreshold,
)

# Create analyzer with custom thresholds
analyzer = RightsizingAnalyzer(
    thresholds=UtilizationThreshold(
        idle_cpu=5.0,
        low_cpu=20.0,
        high_cpu=80.0,
        low_memory=30.0,
        high_memory=85.0,
    )
)

# Define resource utilization
utilization_data = [
    ResourceUtilization(
        resource_id="i-abc123",
        resource_type="ec2",
        current_spec=InstanceSpec(
            instance_type="m5.2xlarge",
            vcpus=8,
            memory_gb=32,
            cost_per_hour=0.384,
        ),
        cpu_avg=12.5,
        cpu_max=35.0,
        cpu_p95=28.0,
        memory_avg=18.0,
        memory_max=45.0,
        memory_p95=38.0,
        analysis_period_days=14,
        data_points=2016,
        service="api",
        environment="production",
    ),
]

# Analyze
recommendations = analyzer.analyze(utilization_data)

for rec in recommendations:
    print(rec.summary)
    
# Get summary
summary = analyzer.get_summary(recommendations)
print(f"\nTotal Monthly Savings: ${summary['total_monthly_savings']:,.2f}")
print(f"Resources Needing Action: {summary['resources_needing_action']}")
```

### Cost Forecasting

Forecast future costs and set up budget alerts:

```python
from autosre.cost import (
    CostForecaster,
    ForecastModel,
    BudgetStatus,
)
from datetime import datetime, timedelta, timezone

# Create forecaster
forecaster = CostForecaster(
    default_model=ForecastModel.LINEAR,
    confidence_level=0.95,
)

# Historical daily costs
daily_costs = {
    datetime(2024, 1, 1, tzinfo=timezone.utc): 1000,
    datetime(2024, 1, 2, tzinfo=timezone.utc): 1050,
    datetime(2024, 1, 3, tzinfo=timezone.utc): 980,
    # ... more daily data
    datetime(2024, 1, 30, tzinfo=timezone.utc): 1200,
}

# Forecast next 30 days
forecast = forecaster.forecast(daily_costs, forecast_days=30)

print(forecast.summary)
print(f"Model Used: {forecast.model_used.value}")

# Check budgets
budgets = [
    {
        "name": "Platform Team",
        "amount": 50000,
        "owner": "platform-lead@company.com",
        "services": ["api", "auth", "gateway"],
    },
    {
        "name": "Data Team",
        "amount": 30000,
        "owner": "data-lead@company.com",
        "services": ["etl", "warehouse", "analytics"],
    },
]

current_costs = {
    "Platform Team": 35000,
    "Data Team": 28000,
}

alerts = forecaster.check_budgets(budgets, current_costs, daily_costs)

for alert in alerts:
    print(alert.summary)
    print()
```

### Anomaly Detection

Detect unusual cost patterns:

```python
from autosre.cost import CostForecaster, AnomalyDetector

# Create detector
detector = AnomalyDetector(sensitivity=2.0)

# Or use via forecaster
forecaster = CostForecaster()

# Detect anomalies
anomalies = forecaster.detect_anomalies(
    daily_costs,
    service="api-gateway",
)

for anomaly in anomalies:
    print(anomaly.summary)
    print(f"Likely Causes: {anomaly.likely_causes}")
    print()

# Get spending trend
trend, details = forecaster.analyze_spending_trend(daily_costs)
print(f"Spending Trend: {trend.value}")
print(f"Average Weekly Change: {details['average_weekly_change']:.1%}")
```

## Components

### CostAnalyzer

Analyzes cost data across multiple dimensions.

**Key Features:**
- Cost breakdown by service, team, environment, region
- Trend analysis
- Period comparisons
- Tagging compliance reports
- Unit cost calculations

**Methods:**
- `load_costs(costs)` - Load cost data for analysis
- `analyze_breakdown(start_date, end_date, filters)` - Get cost breakdown
- `analyze_trend(metric_name, period_days)` - Analyze cost trends
- `compare_periods(period1, period2)` - Compare two time periods
- `calculate_unit_costs(metric_name, values)` - Calculate cost per unit
- `get_tagging_compliance()` - Get tagging compliance report

### RecommendationEngine

Generates actionable cost optimization recommendations.

**Recommendation Types:**
- `UNUSED_RESOURCE` - Idle/unused resources
- `RIGHTSIZING` - Oversized resources
- `RESERVED_INSTANCE` - RI purchase opportunities
- `SAVINGS_PLAN` - Savings plan opportunities
- `SPOT_INSTANCE` - Spot instance candidates
- `STORAGE_OPTIMIZATION` - Storage tier optimization
- `SCHEDULING` - Dev/test scheduling
- `ARCHITECTURE` - Architecture improvements

**Methods:**
- `generate_recommendations(resources, costs, utilization)` - Generate all recommendations
- `get_summary()` - Get summary of all recommendations
- `filter_recommendations(priority, type, service)` - Filter recommendations

### RightsizingAnalyzer

Analyzes resource utilization for rightsizing opportunities.

**Actions:**
- `DOWNSIZE` - Reduce instance size
- `UPSIZE` - Increase instance size
- `TERMINATE` - Resource is unused
- `MODIFY_TYPE` - Change instance family
- `NO_ACTION` - Resource is properly sized

**Methods:**
- `analyze(utilization_data)` - Analyze resources for rightsizing
- `analyze_kubernetes_pods(pod_metrics)` - Analyze K8s pod resources
- `get_summary(recommendations)` - Get summary of analysis

### CostForecaster

Forecasts future costs and monitors budgets.

**Forecast Models:**
- `LINEAR` - Linear regression
- `EXPONENTIAL` - Exponential smoothing
- `MOVING_AVERAGE` - Moving average
- `SEASONAL` - Seasonal decomposition

**Methods:**
- `forecast(daily_costs, forecast_days, model)` - Forecast costs
- `check_budgets(budgets, current_costs, daily_costs)` - Check budget status
- `analyze_spending_trend(daily_costs)` - Analyze spending trend
- `detect_anomalies(daily_costs)` - Detect cost anomalies
- `get_insights(daily_costs)` - Get comprehensive insights

## Integration Examples

### Slack Budget Alerts

```python
from autosre.cost import CostForecaster, BudgetStatus
from slack_sdk import WebClient

forecaster = CostForecaster()

# Check budgets
alerts = forecaster.check_budgets(budgets, current_costs, daily_costs)

# Send Slack alerts for critical budgets
client = WebClient(token="your-token")

for alert in alerts:
    if alert.status in (BudgetStatus.CRITICAL, BudgetStatus.OVERSPENT):
        client.chat_postMessage(
            channel="#finops-alerts",
            text=f"🚨 Budget Alert: {alert.budget_name}\n{alert.summary}",
        )
```

### AWS Cost Explorer Integration

```python
import boto3
from autosre.cost import CostAnalyzer, CostMetric, ResourceType
from datetime import datetime, timedelta

# Fetch costs from AWS
ce_client = boto3.client('ce')

response = ce_client.get_cost_and_usage(
    TimePeriod={
        'Start': (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'),
        'End': datetime.now().strftime('%Y-%m-%d'),
    },
    Granularity='DAILY',
    Metrics=['UnblendedCost'],
    GroupBy=[
        {'Type': 'DIMENSION', 'Key': 'SERVICE'},
    ],
)

# Convert to CostMetric objects
costs = []
for result in response['ResultsByTime']:
    timestamp = datetime.fromisoformat(result['TimePeriod']['Start'])
    for group in result['Groups']:
        service = group['Keys'][0]
        amount = float(group['Metrics']['UnblendedCost']['Amount'])
        costs.append(CostMetric(
            timestamp=timestamp,
            amount=amount,
            service=service,
            provider=CloudProvider.AWS,
        ))

# Analyze
analyzer = CostAnalyzer()
analyzer.load_costs(costs)
breakdown = analyzer.analyze_breakdown()
```

### Kubernetes Cost Attribution

```python
from autosre.cost import RightsizingAnalyzer
from kubernetes import client, config

config.load_kube_config()
v1 = client.CoreV1Api()
metrics_api = client.CustomObjectsApi()

# Get pod metrics
pod_metrics = []
pods = v1.list_pod_for_all_namespaces()

for pod in pods.items:
    # Get resource requests
    cpu_request = 0
    memory_request = 0
    for container in pod.spec.containers:
        if container.resources.requests:
            cpu_request += parse_cpu(container.resources.requests.get('cpu', '0'))
            memory_request += parse_memory(container.resources.requests.get('memory', '0'))
    
    pod_metrics.append({
        "name": pod.metadata.name,
        "namespace": pod.metadata.namespace,
        "cpu_request_millicores": cpu_request,
        "memory_request_mb": memory_request,
        "cpu_usage_millicores": get_current_cpu(pod),
        "memory_usage_mb": get_current_memory(pod),
    })

# Analyze
analyzer = RightsizingAnalyzer()
recommendations = analyzer.analyze_kubernetes_pods(pod_metrics)

for rec in recommendations:
    if rec["action"] != "no_change":
        print(f"{rec['namespace']}/{rec['pod']}: {rec['action']}")
        print(f"  Current: {rec['current_cpu_request']}m CPU, {rec['current_memory_request']}Mi memory")
        print(f"  Recommended: {rec['recommended_cpu_request']}m CPU, {rec['recommended_memory_request']}Mi memory")
```

### Prometheus Cost Metrics

```python
from autosre.cost import CostForecaster, CostAnalyzer
from prometheus_client import Gauge, start_http_server

# Create Prometheus metrics
cost_forecast = Gauge('autosre_cost_forecast_monthly', 'Forecasted monthly cost', ['team'])
budget_utilization = Gauge('autosre_budget_utilization', 'Budget utilization percentage', ['budget'])
cost_anomaly_count = Gauge('autosre_cost_anomalies', 'Number of cost anomalies detected')

# Update metrics periodically
def update_metrics():
    forecaster = CostForecaster()
    
    # Forecast by team
    for team, costs in team_daily_costs.items():
        forecast = forecaster.forecast(costs, 30)
        cost_forecast.labels(team=team).set(forecast.forecasted_cost)
    
    # Budget utilization
    alerts = forecaster.check_budgets(budgets, current_costs, daily_costs)
    for alert in alerts:
        budget_utilization.labels(budget=alert.budget_name).set(alert.percent_used)
    
    # Anomaly count
    anomalies = forecaster.detect_anomalies(daily_costs)
    cost_anomaly_count.set(len(anomalies))

start_http_server(8000)
```

## Best Practices

### Tagging Strategy

Implement consistent tagging for accurate cost allocation:

```yaml
required_tags:
  - service      # Which service owns this resource
  - team         # Which team is responsible
  - environment  # prod, staging, dev, etc.
  - cost_center  # For chargeback
  
optional_tags:
  - project      # Project or initiative
  - owner        # Individual owner email
  - expiry       # For temporary resources
```

Check tagging compliance regularly:

```python
compliance = analyzer.get_tagging_compliance()
if compliance['compliance_rate'] < 80:
    print(f"Warning: Only {compliance['compliance_rate']:.1f}% of costs are properly tagged")
    for rec in compliance['recommendations']:
        print(f"  - {rec}")
```

### Budget Monitoring

Set up tiered alerts:

```python
budgets = [
    {
        "name": "Production Infrastructure",
        "amount": 100000,
        "alert_thresholds": [50, 80, 100],  # Alert at 50%, 80%, 100%
        "owner": "infra-team@company.com",
    },
]

# Check daily
alerts = forecaster.check_budgets(budgets, current_costs, daily_costs)
for alert in alerts:
    if alert.status != BudgetStatus.ON_TRACK:
        send_alert(alert)
```

### Optimization Workflow

1. **Weekly Review**: Generate and review recommendations weekly
2. **Prioritize**: Focus on high-priority recommendations first
3. **Validate**: Verify utilization data before acting
4. **Implement**: Make changes during maintenance windows
5. **Monitor**: Track savings after implementation

```python
# Weekly optimization review
recommendations = engine.generate_recommendations(resources, costs, utilization)

# Filter critical and high priority
high_priority = engine.filter_recommendations(
    priority=RecommendationPriority.HIGH,
    min_savings=100,
)

# Generate report
print(f"High-Priority Recommendations: {len(high_priority)}")
print(f"Potential Savings: ${sum(r.savings.monthly_savings for r in high_priority):,.2f}/month")

for rec in high_priority[:10]:
    print(rec.summary)
```

### Reserved Instance Planning

Review RI opportunities quarterly:

```python
# Find stable production resources for RI
ri_recs = engine.filter_recommendations(
    rec_type=RecommendationType.RESERVED_INSTANCE,
)

for rec in ri_recs:
    print(f"{rec.title}")
    print(f"  Resources: {len(rec.resource_ids)}")
    print(f"  1-Year Savings: ${rec.metadata['ri_savings_1yr']:,.2f}/month")
    print(f"  3-Year Savings: ${rec.metadata['ri_savings_3yr']:,.2f}/month")
```

## Troubleshooting

### No Recommendations Generated

If no recommendations are being generated:
- Ensure resources have cost data attached
- Check that utilization data is available
- Lower `min_savings_threshold` for smaller environments
- Verify resource metadata (environment, team, etc.)

### Forecast Accuracy

If forecasts seem inaccurate:
- Ensure at least 14 days of historical data
- Try different forecast models
- Check for cost anomalies that may skew predictions
- Consider seasonal patterns

### Missing Cost Attribution

If costs aren't being attributed correctly:
- Check tagging compliance
- Verify cost allocation rules
- Review shared resource distribution settings
- Ensure all resources have service/team tags

## Metrics to Track

| Metric | Description | Target |
|--------|-------------|--------|
| Cost per Service | Monthly cost by service | Varies |
| Unit Cost | Cost per request/transaction | Decreasing |
| Utilization | Average resource utilization | 60-80% |
| Tagging Compliance | % of costs with proper tags | >90% |
| RI Coverage | % of eligible spend on RIs | >60% |
| Savings Implemented | Monthly savings from optimizations | Increasing |
| Forecast Accuracy | Actual vs predicted costs | <10% variance |
