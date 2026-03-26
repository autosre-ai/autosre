# Cost Anomaly Detector Agent

Daily cost monitoring that compares cloud spend against baseline and alerts on anomalies.

## Overview

This agent runs daily to:
1. Fetch current day's cloud costs
2. Calculate baseline from historical data
3. Detect anomalies using statistical methods
4. Alert on significant deviations
5. Provide actionable insights on cost drivers

## Triggers

### Scheduled (Primary)
- **Cron:** `0 9 * * *` (Daily at 9 AM UTC)

### Manual Webhook
- **Path:** `/webhook/cost-check`
- **Use:** On-demand cost analysis

## Configuration

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `slack_channel` | string | `#cost-alerts` | Alert channel |
| `email_recipients` | list | `[]` | Email recipients for high-severity alerts |
| `anomaly_threshold_percent` | int | `20` | % change triggering anomaly |
| `baseline_period_days` | int | `30` | Days for baseline calculation |
| `alert_on_increase_only` | bool | `false` | Only alert on cost increases |
| `cloud_providers` | list | `[aws, gcp]` | Providers to monitor |
| `breakdown_by` | list | `[service, team, environment]` | Cost grouping dimensions |

## Required Skills

- **cloud-cost** - Cost data from cloud providers
- **prometheus** - Metrics storage
- **slack** - Notifications
- **email** - Email alerts (optional)
- **jira** - Ticket creation (optional)

## Example Trigger Payload

### Manual Check
```json
{
  "source": "manual",
  "date": "2024-01-15"
}
```

## Workflow

```
┌─────────────────────┐
│  Daily Schedule     │
│  or Manual Trigger  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  1. Get Today's     │
│     Costs           │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  2. Get Baseline    │
│     (30-day avg)    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  3. Detect          │
│     Anomalies       │
│     (Z-score)       │
└──────────┬──────────┘
           │
           ▼
   ┌───────┴───────┐
   │               │
   ▼               ▼
┌───────┐    ┌───────────┐
│ Normal│    │ Anomaly   │
│       │    │ Detected  │
└───┬───┘    └─────┬─────┘
    │              │
    ▼              ▼
┌───────┐    ┌───────────────┐
│ Brief │    │ Full Alert    │
│ Update│    │ + Investigation│
└───────┘    │ + Email/Ticket │
             └───────────────┘
```

## Anomaly Detection

### Method: Z-Score
Compares current spend to baseline using statistical deviation:
- **Normal:** Within 2 standard deviations
- **Warning:** 2-3 standard deviations
- **Critical:** > 3 standard deviations

### Filtering
- Minimum absolute change of $100
- Optional: increase-only alerting

## Alert Severity

| Severity | Condition | Actions |
|----------|-----------|---------|
| Low | < 20% variance | Slack summary only |
| Medium | 20-50% variance | Detailed Slack alert |
| High | 50-100% variance | Slack + Email |
| Critical | > 100% variance | Slack + Email + Jira |

## Report Contents

### Slack Alert (Anomaly)
- Today's total spend
- Baseline comparison
- Top anomalous services/resources
- Possible causes (resource changes)
- Action buttons

### Email Report (High/Critical)
- Full breakdown by service/team
- 7-day trend
- Resource changes
- Investigation suggestions

## Customization

### Custom Threshold per Service
```yaml
config:
  service_thresholds:
    ec2: 30
    rds: 25
    lambda: 50
```

### Multiple Slack Channels
Route anomalies to team-specific channels:
```yaml
steps:
  - name: notify_team
    action: slack.send_message
    params:
      channel: "#{{ anomaly.team }}-costs"
```

## Testing

```bash
# Run unit tests
pytest test_agent.py -v

# Test with specific date
curl -X POST http://localhost:8080/webhook/cost-check \
  -H "Content-Type: application/json" \
  -d '{"date": "2024-01-15"}'
```

## Example Output

### Normal Day
```
✅ Daily Cost Check - 2024-01-15

No anomalies detected.
Total spend: $12,450.00 (+5.2% vs baseline)
```

### Anomaly Detected
```
💰 Cost Anomaly Detected - 2024-01-15

Today's Spend: $18,230.00
Baseline: $12,400.00
Variance: +47.0%
Anomalies: 3

Top Anomalies:
• EC2 - us-east-1: $8,500 (+85% increase)
• RDS - production: $3,200 (+45% increase)
• Lambda: $1,800 (+120% increase)

Possible Causes:
- 15 new EC2 instances launched
- RDS storage auto-scaling triggered
- Lambda function error retry storm
```
