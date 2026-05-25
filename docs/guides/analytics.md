# Analytics Guide

AutoSRE's analytics module provides advanced trend analysis, pattern recognition,
predictive analytics, and automated reporting for SRE operations.

## Overview

The analytics module helps you:

- **Identify Trends**: Detect increasing/decreasing incident patterns
- **Recognize Patterns**: Find recurring alerts, correlations, and cascades
- **Predict Incidents**: Forecast potential issues before they occur
- **Generate Reports**: Create comprehensive SRE reports automatically
- **Visualize Data**: Generate charts for dashboards and documentation

## Installation

Analytics is included in the core AutoSRE package:

```bash
pip install autosre-ai
```

## Quick Start

### Trend Analysis

Analyze incident trends over time:

```python
from autosre.analytics import TrendAnalyzer, TrendDataPoint
from datetime import datetime, timedelta

# Create analyzer
analyzer = TrendAnalyzer()

# Prepare incident data
incidents = [
    {"timestamp": "2024-01-15T10:00:00Z", "severity": "high", "service": "api"},
    {"timestamp": "2024-01-16T14:00:00Z", "severity": "medium", "service": "db"},
    # ... more incidents
]

# Analyze trends
summary = analyzer.analyze_incidents(incidents, period_days=30)

print(f"Total incidents: {summary.total_incidents}")
print(f"Incident trend: {summary.incident_trend.direction.value}")
print(f"MTTR trend: {summary.mttr_trend.direction.value}")
print(f"Alert fatigue score: {summary.alert_fatigue_score:.0%}")
print(f"Recommendations: {summary.recommendations}")
```

### Pattern Recognition

Find patterns in alerts and incidents:

```python
from autosre.analytics import PatternRecognizer

recognizer = PatternRecognizer(
    similarity_threshold=0.7,
    correlation_window_minutes=30,
    min_pattern_occurrences=3,
)

# Find all patterns
alerts = [
    {"name": "HighCPU", "service": "api", "timestamp": "2024-01-15T10:00:00Z"},
    {"name": "HighMemory", "service": "api", "timestamp": "2024-01-15T10:05:00Z"},
    # ... more alerts
]

patterns = recognizer.find_patterns(alerts)

for pattern in patterns:
    print(f"Pattern: {pattern.pattern_type.value}")
    print(f"Description: {pattern.description}")
    print(f"Confidence: {pattern.confidence:.0%}")
    print(f"Actions: {pattern.recommended_actions}")
    print("---")

# Cluster similar incidents
clusters = recognizer.cluster_incidents(incidents)
for cluster in clusters:
    print(f"Cluster with {cluster.size} incidents")
    print(f"Common services: {cluster.common_services}")
    print(f"Suggested root cause: {cluster.suggested_root_cause}")
```

### Predictive Analytics

Predict potential incidents:

```python
from autosre.analytics import IncidentPredictor

predictor = IncidentPredictor()

# Predict incidents for a service
prediction = predictor.predict_incidents(
    service="api-gateway",
    historical_incidents=incidents,
    current_metrics={
        "cpu_percent": 85,
        "memory_percent": 70,
        "error_rate": 0.02,
        "latency_p99": 500,
    },
    time_horizon_hours=24,
)

print(f"Incident probability: {prediction.probability:.0%}")
print(f"Risk level: {prediction.risk_level.value}")
print(f"Contributing factors: {prediction.contributing_factors}")
print(f"Recommendations: {prediction.recommended_actions}")

# Forecast capacity exhaustion
usage_history = [
    (datetime(2024, 1, 1), 50.0),
    (datetime(2024, 1, 15), 65.0),
    (datetime(2024, 2, 1), 80.0),
]

forecast = predictor.forecast_capacity(
    resource_name="disk_usage_gb",
    usage_history=usage_history,
    limit=100.0,
    forecast_days=30,
)

if forecast.exhaustion_date:
    print(f"Disk will be full by: {forecast.exhaustion_date}")
    print(f"Days remaining: {forecast.days_until_exhaustion:.1f}")
```

### Report Generation

Generate comprehensive SRE reports:

```python
from autosre.analytics import ReportGenerator, ReportType, ReportFormat

generator = ReportGenerator()

# Generate incident summary
report = generator.generate(
    report_type=ReportType.INCIDENT_SUMMARY,
    data={
        "incidents": incidents,
        "services": ["api", "db", "cache"],
    },
    period_days=7,
)

# Output as Markdown
print(report.to_markdown())

# Output for Slack
slack_blocks = report.to_slack_blocks()

# Generate weekly summary
weekly = generator.generate_weekly_summary(
    incidents=incidents,
    services=["api", "db", "cache"],
    metrics={"api": {"error_rate": 0.01}},
    slos={"api_availability": {"target": 0.999, "actual": 0.9985}},
)
```

### Visualizations

Generate charts and visualizations:

```python
from autosre.analytics import ChartGenerator

charts = ChartGenerator()

# Incidents over time
timeline = charts.incidents_over_time(incidents, period_days=30)
print(timeline.to_ascii())  # ASCII chart for terminal
print(timeline.to_mermaid())  # Mermaid diagram for docs

# Severity distribution
severity_chart = charts.severity_distribution(incidents)
print(severity_chart.to_ascii())

# Incident heatmap (by hour and day)
heatmap = charts.incident_heatmap(incidents)
print(heatmap.to_ascii())

# Full dashboard
dashboard = charts.render_dashboard(incidents, period_days=30, format="ascii")
print(dashboard)
```

## Components

### TrendAnalyzer

Analyzes time series data for trends and patterns.

**Key Features:**
- Trend direction detection (increasing, decreasing, stable, volatile)
- Seasonal pattern detection (hourly, daily, weekly)
- Anomaly detection
- Change point detection
- Simple forecasting

**Methods:**
- `analyze_time_series(data, metric_name)` - Analyze any time series
- `analyze_incidents(incidents, period_days)` - Comprehensive incident analysis
- `detect_change_points(data, sensitivity)` - Find significant changes
- `compare_periods(current, previous, metric_name)` - Compare two periods

### PatternRecognizer

Identifies patterns in alert and incident data.

**Pattern Types:**
- `RECURRING` - Same incident repeating
- `CORRELATED` - Alerts that fire together
- `CASCADE` - Alert A leads to Alert B
- `TEMPORAL` - Time-based patterns (peak hours/days)
- `INFRASTRUCTURE` - Common infrastructure cause
- `DEPLOYMENT` - Related to deployments
- `CAPACITY` - Resource exhaustion
- `CONFIGURATION` - Config-related issues

**Methods:**
- `find_patterns(alerts)` - Find all patterns
- `cluster_incidents(incidents)` - Group similar incidents
- `find_correlations(alerts)` - Find alert correlations
- `match_known_patterns(alert)` - Match against known patterns

### IncidentPredictor

Provides predictive analytics for proactive incident management.

**Capabilities:**
- Incident probability prediction
- Resource exhaustion forecasting
- SLO burn rate analysis
- Risk assessment
- Proactive recommendations

**Methods:**
- `predict_incidents(service, incidents, metrics, horizon)` - Predict incidents
- `forecast_capacity(resource, history, limit, days)` - Capacity forecasting
- `analyze_slo_burn_rate(slo, budget, consumed, window)` - SLO analysis
- `generate_insights(services, incidents, metrics, slos)` - Comprehensive insights

### ReportGenerator

Generates automated SRE reports.

**Report Types:**
- `INCIDENT_SUMMARY` - Summary of incidents
- `SERVICE_HEALTH` - Service health status
- `SLO_COMPLIANCE` - SLO compliance report
- `TEAM_PERFORMANCE` - Team metrics
- `TREND_ANALYSIS` - Trend analysis report
- `EXECUTIVE_SUMMARY` - High-level summary
- `ON_CALL_SUMMARY` - On-call rotation summary

**Output Formats:**
- Markdown
- HTML (via template)
- JSON
- Slack blocks

### ChartGenerator

Generates visualizations for analytics data.

**Chart Types:**
- Time series (line, area)
- Distribution (pie, bar)
- Heatmaps
- Gauges
- Burndown charts

**Output Formats:**
- ASCII (for terminal)
- Mermaid (for documentation)
- JSON (for web dashboards)

## Integration Examples

### Slack Weekly Report

```python
from autosre.analytics import ReportGenerator, ReportType
from slack_sdk import WebClient

# Generate report
generator = ReportGenerator()
report = generator.generate_weekly_summary(
    incidents=get_weekly_incidents(),
    services=get_services(),
    metrics=get_current_metrics(),
)

# Send to Slack
client = WebClient(token="your-token")
client.chat_postMessage(
    channel="#sre-reports",
    blocks=report.to_slack_blocks(),
)
```

### Prometheus Alerting

```python
from autosre.analytics import IncidentPredictor
from prometheus_client import Gauge

# Create predictor
predictor = IncidentPredictor()

# Prometheus gauge for predictions
incident_risk = Gauge(
    'autosre_incident_risk',
    'Predicted incident probability',
    ['service']
)

# Update predictions periodically
for service in services:
    prediction = predictor.predict_incidents(
        service=service,
        historical_incidents=get_incidents(service),
        current_metrics=get_metrics(service),
    )
    incident_risk.labels(service=service).set(prediction.probability)
```

### Dashboard Integration

```python
from autosre.analytics import ChartGenerator, TrendAnalyzer
from fastapi import FastAPI

app = FastAPI()

@app.get("/api/analytics/dashboard")
async def get_dashboard():
    incidents = await get_incidents()
    
    charts = ChartGenerator()
    analyzer = TrendAnalyzer()
    
    return {
        "incidents_timeline": charts.incidents_over_time(incidents).to_dict(),
        "severity_distribution": charts.severity_distribution(incidents).to_dict(),
        "heatmap": charts.incident_heatmap(incidents).to_dict(),
        "trends": analyzer.analyze_incidents(incidents).to_dict(),
    }
```

## Best Practices

### Data Quality

- Ensure consistent timestamp formats (ISO 8601)
- Include severity in incident data
- Add service/component labels
- Track TTR (time to resolve) and TTD (time to detect)

### Alert Fatigue

Monitor alert fatigue score and take action when > 50%:

```python
summary = analyzer.analyze_incidents(incidents)
if summary.alert_fatigue_score > 0.5:
    # Take action: review alerts, consolidate, tune thresholds
    print("Alert fatigue detected!")
    print(summary.recommendations)
```

### Predictive Alerts

Set up predictive alerting for high-risk services:

```python
for service in critical_services:
    prediction = predictor.predict_incidents(service, ...)
    
    if prediction.risk_level in (RiskLevel.CRITICAL, RiskLevel.HIGH):
        send_proactive_alert(
            service=service,
            prediction=prediction,
        )
```

### Regular Reporting

Automate weekly reports:

```python
# Run weekly (e.g., via cron)
report = generator.generate_weekly_summary(...)
send_to_slack(report.to_slack_blocks())
archive_report(report.to_markdown())
```

## Metrics Tracked

The analytics module tracks and analyzes:

- **Incident Volume**: Total incidents, by severity, by service
- **MTTR**: Mean time to resolve
- **MTTD**: Mean time to detect
- **Error Budget**: SLO compliance and burn rate
- **Alert Fatigue**: Frequency, repetition, time-of-day patterns
- **Patterns**: Recurring issues, correlations, cascades

## Troubleshooting

### Insufficient Data

If you see "Unknown" trends:
- Ensure you have at least 7 data points
- Increase the `period_days` parameter
- Check timestamp parsing

### Low Confidence

If predictions have low confidence:
- Add more historical data
- Include current metrics
- Ensure data quality

### No Patterns Found

If no patterns are detected:
- Lower `min_pattern_occurrences`
- Increase `correlation_window_minutes`
- Check alert naming consistency
