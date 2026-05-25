# SLO Management

AutoSRE provides comprehensive Service Level Objective (SLO) management capabilities, enabling teams to define, track, and report on their service reliability targets.

## Overview

The SLO module provides:

- **SLO Definitions**: Define SLOs with SLIs (Service Level Indicators), targets, and alerting policies
- **Error Budget Tracking**: Track error budget consumption and burn rates in real-time
- **Multi-Window Alerting**: Implement Google's multi-window multi-burn-rate alerting
- **Reporting**: Generate compliance reports, trend analysis, and executive summaries
- **Dashboard**: Real-time SLO monitoring and visualization

## Quick Start

### Creating an SLO

```python
from autosre.slo import (
    SLOManager,
    SLIMetric,
    SLIType,
    SLOPeriod,
    create_availability_slo,
    create_latency_slo,
)

# Quick creation with sensible defaults
availability_slo = create_availability_slo(
    name="API Availability",
    service_id="api-gateway",
    target=0.999,  # 99.9%
)

# Or create with full control
manager = SLOManager()

sli = SLIMetric(
    name="api_success_rate",
    sli_type=SLIType.AVAILABILITY,
    description="Percentage of successful API requests",
    good_events_query='sum(rate(http_requests_total{status!~"5.."}[5m]))',
    total_events_query='sum(rate(http_requests_total[5m]))',
    metric_source="prometheus",
)

slo = manager.create_slo(
    name="API Availability",
    service_id="api-gateway",
    sli=sli,
    target=0.999,  # 99.9%
    period=SLOPeriod.ROLLING_30D,
    owner_team="platform-team",
    add_default_alerts=True,  # Adds multi-window burn-rate alerts
)

print(f"Created SLO: {slo.name}")
print(f"Error budget: {slo.error_budget_percentage:.2f}% ({slo.calculate_error_budget_minutes():.1f} minutes/month)")
```

### Tracking Error Budget

```python
from autosre.slo import (
    ErrorBudgetTracker,
    BudgetPolicy,
)

# Create tracker
tracker = ErrorBudgetTracker()

# Create budget with custom policy
policy = tracker.create_policy(
    name="strict_policy",
    warning_threshold_pct=40.0,     # Warn at 40% consumed
    critical_threshold_pct=70.0,    # Critical at 70% consumed
    freeze_threshold_pct=85.0,      # Freeze deploys at 85%
    auto_freeze_deploys=True,
)

budget = tracker.create_budget(slo, policy=policy)

# Record events from your monitoring system
budget.record_events(
    good_events=9990,
    total_events=10000,
)

# Get current status
status = budget.get_status()
print(f"SLI: {status.current_sli * 100:.3f}%")
print(f"Budget remaining: {status.remaining_percentage:.2f}%")
print(f"Status: {status.compliance_status.value}")
print(f"Recommended action: {status.recommended_action.value}")

# Check burn rates
for window, burn_rate in status.burn_rates.items():
    print(f"  {window}: {burn_rate.burn_rate:.2f}x ({burn_rate.rate_category.value})")
```

### Checking Deployment Safety

```python
from autosre.slo import budget_allows_deployment

# Before deploying, check if error budget allows it
allowed, reason = budget_allows_deployment(
    status=status,
    deployment_risk_factor=0.05,  # Expect 5% risk from deployment
)

if allowed:
    print("✅ Safe to deploy")
else:
    print(f"❌ Deployment blocked: {reason}")
```

### Generating Reports

```python
from autosre.slo import (
    ReportGenerator,
    ReportPeriod,
    ReportFormat,
    generate_weekly_report,
    format_report,
)

# Get all budget statuses
statuses = tracker.get_all_statuses()

# Generate report
report = generate_weekly_report(
    name="Weekly SLO Report",
    statuses=statuses,
)

# Output as Markdown
markdown = report.to_markdown()
print(markdown)

# Or as Slack blocks for notification
blocks = report.to_slack_blocks()

# Or use the generator for more control
generator = ReportGenerator()
monthly_report = generator.generate_report(
    name="Monthly SLO Review",
    statuses=statuses,
    period_type=ReportPeriod.MONTHLY,
)

# Get trend analysis
trend = generator.generate_trend_analysis(
    slo_id=slo.id,
    slo_name=slo.name,
    period_days=30,
)
if trend:
    print(f"Trend: {trend.direction.value}")
    print(f"Average SLI: {trend.average_sli * 100:.3f}%")
    print(f"Compliance: {trend.compliance_percentage:.1f}%")
```

## SLO Types

### Availability SLO

Track the percentage of successful requests:

```python
from autosre.slo import create_availability_slo

slo = create_availability_slo(
    name="Payment Service Availability",
    service_id="payment-service",
    target=0.9999,  # 99.99% (four nines)
    good_events_query='sum(rate(http_requests_total{service="payment",status!~"5.."}[5m]))',
    total_events_query='sum(rate(http_requests_total{service="payment"}[5m]))',
)
```

### Latency SLO

Track response time percentiles:

```python
from autosre.slo import create_latency_slo

slo = create_latency_slo(
    name="API Response Latency",
    service_id="api-gateway",
    target=0.99,  # 99% of requests within thresholds
    p50_threshold_ms=50.0,   # 50ms p50
    p95_threshold_ms=200.0,  # 200ms p95
    p99_threshold_ms=500.0,  # 500ms p99
)
```

### Error Rate SLO

Track error rates:

```python
from autosre.slo import create_error_rate_slo

slo = create_error_rate_slo(
    name="API Error Rate",
    service_id="api-gateway",
    target=0.999,  # Less than 0.1% errors
    error_query='sum(rate(http_requests_total{status=~"5.."}[5m]))',
    total_query='sum(rate(http_requests_total[5m]))',
)
```

### Custom SLI

Create custom SLIs for any metric:

```python
from autosre.slo import SLIMetric, SLIType, SLODefinition, SLOPeriod

# Data freshness SLI
freshness_sli = SLIMetric(
    name="data_freshness",
    sli_type=SLIType.FRESHNESS,
    description="Percentage of data processed within 5 minutes",
    good_events_query='sum(rate(data_processed_within_sla_total[5m]))',
    total_events_query='sum(rate(data_processed_total[5m]))',
    unit="minutes",
)

slo = SLODefinition(
    name="Data Pipeline Freshness",
    service_id="data-pipeline",
    sli=freshness_sli,
    target=0.99,
    period=SLOPeriod.ROLLING_7D,
)
slo.add_default_alert_policies()
```

## Error Budget Policies

Configure how error budgets trigger actions:

```python
from autosre.slo import BudgetPolicy, ErrorBudgetTracker

tracker = ErrorBudgetTracker()

# Conservative policy for critical services
critical_policy = tracker.create_policy(
    name="critical_service_policy",
    warning_threshold_pct=30.0,     # Warn early
    critical_threshold_pct=50.0,    # Critical at 50%
    freeze_threshold_pct=70.0,      # Freeze deploys at 70%
    auto_freeze_deploys=True,
    notify_on_warning=True,
    notify_on_critical=True,
    create_incident_on_violation=True,
    notify_teams=["platform-team", "sre-team"],
    escalation_policy_id="critical-escalation",
)

# Relaxed policy for non-critical services
relaxed_policy = tracker.create_policy(
    name="non_critical_policy",
    warning_threshold_pct=60.0,
    critical_threshold_pct=85.0,
    freeze_threshold_pct=95.0,
    auto_freeze_deploys=False,
    create_incident_on_violation=False,
)

# Apply policies
tracker.apply_policy(critical_slo.id, critical_policy.id)
tracker.apply_policy(internal_slo.id, relaxed_policy.id)
```

## Multi-Window Multi-Burn-Rate Alerting

AutoSRE implements Google's multi-window multi-burn-rate alerting strategy:

```python
from autosre.slo import AlertPolicy, BurnRateWindow, AlertSeverity

# Default alerts are added automatically, but you can customize:
page_alert = AlertPolicy(
    name="API Availability - Page",
    severity=AlertSeverity.PAGE,
    burn_rate_windows=[
        # Page if burning 14.4x in 1 hour (consumes 2% of monthly budget)
        BurnRateWindow(
            name="1h_sustained",
            duration_hours=1.0,
            burn_rate_threshold=14.4,
            short_window_hours=0.083,  # 5 minutes
            short_window_threshold=14.4,
        ),
    ],
    budget_remaining_threshold=2.0,  # Also page if < 2% budget
    notification_channels=["pagerduty", "slack-oncall"],
)

ticket_alert = AlertPolicy(
    name="API Availability - Ticket",
    severity=AlertSeverity.TICKET,
    burn_rate_windows=[
        # Create ticket if burning 6x over 6 hours
        BurnRateWindow(
            name="6h_sustained",
            duration_hours=6.0,
            burn_rate_threshold=6.0,
            short_window_hours=0.5,  # 30 minutes
            short_window_threshold=6.0,
        ),
    ],
    budget_remaining_threshold=10.0,
    notification_channels=["jira", "slack-sre"],
)

# Add to SLO
slo.alert_policies = [page_alert, ticket_alert]
```

## Burn Rate Reference

| Burn Rate | Time to Exhaust Budget | Typical Action |
|-----------|----------------------|----------------|
| 1x | 30 days (full period) | Normal operation |
| 2x | 15 days | Monitor closely |
| 6x | 5 days | Investigate |
| 14.4x | 2 days | Urgent attention |
| 36x | 20 hours | Page immediately |
| 720x | 1 hour | Emergency response |

## Dashboard and Monitoring

```python
from autosre.slo import SLODashboard, ReportGenerator

# Create dashboard
generator = ReportGenerator()
dashboard = SLODashboard(generator)

# Get overview for all SLOs
statuses = tracker.get_all_statuses()
overview = dashboard.get_overview(statuses)

print(f"Health Score: {overview['health_score']}/100")
print(f"Status: {overview['health_status']}")
print(f"Healthy: {overview['status_counts']['healthy']}")
print(f"Warning: {overview['status_counts']['warning']}")
print(f"Critical: {overview['status_counts']['critical']}")
print(f"Violated: {overview['status_counts']['violated']}")

# Top issues
for issue in overview['top_issues']:
    print(f"  - {issue['slo_name']}: {issue['status']} ({issue['remaining_pct']}% remaining)")

# Get detail for specific SLO
detail = dashboard.get_slo_detail(status)
print(f"\nSLO: {detail['slo_name']}")
print(f"Current SLI: {detail['current_sli']}%")
print(f"Target SLI: {detail['target_sli']}%")
print(f"Budget Remaining: {detail['budget']['remaining_pct']}%")
```

## Integration with Incident Response

```python
from autosre.slo import ErrorBudgetTracker, budget_allows_deployment

# Check before deployment
def pre_deploy_check(service_id: str) -> tuple[bool, str]:
    """Check if deployment is safe based on error budget."""
    budget = tracker.get_budget(f"{service_id}-availability")
    if not budget:
        return True, "No SLO configured"
    
    status = budget.get_status()
    return budget_allows_deployment(status)

# Use in CI/CD pipeline
allowed, reason = pre_deploy_check("api-gateway")
if not allowed:
    print(f"Deployment blocked: {reason}")
    exit(1)

# After incident, assess impact on budget
def assess_incident_impact(
    slo_id: str,
    bad_events: int,
    total_events: int,
) -> dict:
    """Assess how an incident impacted error budget."""
    budget = tracker.get_budget(slo_id)
    before_status = budget.get_status()
    
    # Record incident events
    budget.record_events(
        good_events=total_events - bad_events,
        total_events=total_events,
    )
    
    after_status = budget.get_status()
    
    return {
        "budget_before": before_status.remaining_percentage,
        "budget_after": after_status.remaining_percentage,
        "budget_consumed": before_status.remaining_percentage - after_status.remaining_percentage,
        "new_status": after_status.compliance_status.value,
    }
```

## Best Practices

### 1. Start with Fewer, Better SLOs

Don't create SLOs for everything. Start with:
- 1-2 availability SLOs for user-facing services
- 1 latency SLO (usually p99) for critical paths
- Expand as you mature

### 2. Set Achievable Targets

Start with targets you can realistically meet:
- If current reliability is 99.5%, don't set 99.99%
- Improve targets incrementally over quarters

### 3. Use Error Budgets for Decision Making

```python
# Example: Feature velocity vs reliability trade-off
if status.remaining_percentage > 50:
    # Healthy budget - proceed with aggressive changes
    deployment_strategy = "canary"
    rollout_speed = "fast"
elif status.remaining_percentage > 20:
    # Budget getting low - be more careful
    deployment_strategy = "blue-green"
    rollout_speed = "slow"
else:
    # Budget critical - minimize risk
    deployment_strategy = "manual"
    rollout_speed = "hold"
```

### 4. Review SLOs Quarterly

```python
# Generate quarterly review report
quarterly_report = generator.generate_report(
    name="Q4 SLO Review",
    statuses=tracker.get_all_statuses(),
    period_type=ReportPeriod.QUARTERLY,
)

# Analyze for target adjustments
for rec in quarterly_report.recommendations:
    print(f"- {rec}")
```

### 5. Align SLOs with User Experience

Your SLOs should reflect what users actually experience:
- Measure from the user's perspective (client-side if possible)
- Consider geographic distribution
- Account for different user journeys

## Prometheus Integration Example

```python
from autosre.slo import SLIMetric, SLIType

# Define SLI with Prometheus queries
sli = SLIMetric(
    name="api_availability",
    sli_type=SLIType.AVAILABILITY,
    description="API request success rate",
    metric_source="prometheus",
    
    # Using histogram_quantile for latency
    good_events_query='''
        sum(rate(http_request_duration_seconds_bucket{
            service="api",
            le="0.5"
        }[5m]))
    ''',
    
    total_events_query='''
        sum(rate(http_request_duration_seconds_count{
            service="api"
        }[5m]))
    ''',
)
```

## API Reference

### SLOManager

| Method | Description |
|--------|-------------|
| `create_slo()` | Create a new SLO definition |
| `get_slo(id)` | Get SLO by ID |
| `get_slos_for_service(service_id)` | Get all SLOs for a service |
| `get_slos_for_team(team)` | Get all SLOs owned by a team |
| `list_slos()` | List all SLOs with filters |
| `update_slo(id, **updates)` | Update an SLO |
| `delete_slo(id)` | Soft-delete an SLO |

### ErrorBudgetTracker

| Method | Description |
|--------|-------------|
| `create_budget(slo, policy)` | Create budget tracker for SLO |
| `get_budget(slo_id)` | Get budget tracker |
| `record_events(slo_id, good, total)` | Record event data |
| `get_all_statuses()` | Get all budget statuses |
| `get_unhealthy_budgets()` | Get budgets below threshold |
| `get_violated_budgets()` | Get exhausted budgets |
| `get_summary()` | Get summary of all budgets |

### ReportGenerator

| Method | Description |
|--------|-------------|
| `record_compliance()` | Record compliance measurement |
| `generate_report()` | Generate comprehensive report |
| `generate_trend_analysis()` | Analyze SLO trends |
| `generate_service_summary()` | Summarize service SLOs |
