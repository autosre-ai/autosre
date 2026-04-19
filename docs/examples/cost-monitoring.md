# Cost Monitoring Example

This example shows how to build an agent that monitors cloud costs and alerts on anomalies.

## Use Case

Monitor cloud spending by:
1. Fetching daily cost reports
2. Comparing against baselines
3. Detecting anomalies
4. Identifying cost drivers
5. Alerting the team with actionable insights

## Agent Configuration

```yaml
# agents/cost-watcher/agent.yaml
name: cost-watcher
description: Monitors cloud costs and detects anomalies
version: 1.0.0

skills:
  - aws
  - slack

triggers:
  - type: schedule
    cron: "0 9 * * *"  # Daily at 9 AM
    timezone: America/New_York

config:
  timeout: 300
  
  # Cost thresholds
  thresholds:
    daily_increase_pct: 20    # Alert if >20% daily increase
    weekly_increase_pct: 30   # Alert if >30% weekly increase
    absolute_spike: 1000      # Alert if >$1000 daily spike

runbook:
  variables:
    slack_channel: "#finops"
  
  phases:
    - name: gather_costs
      description: Fetch cost data from AWS
      parallel: true
      steps:
        - name: get_daily_costs
          action: aws.cost_report
          params:
            start_date: "-7d"
            end_date: "today"
            granularity: DAILY
            group_by: ["SERVICE"]
          store: daily_costs
        
        - name: get_monthly_costs
          action: aws.cost_report
          params:
            start_date: "-30d"
            end_date: "today"
            granularity: DAILY
            group_by: ["SERVICE"]
          store: monthly_costs
        
        - name: get_account_breakdown
          action: aws.cost_report
          params:
            start_date: "-7d"
            end_date: "today"
            granularity: DAILY
            group_by: ["LINKED_ACCOUNT"]
          store: account_costs
        
        - name: get_tag_breakdown
          action: aws.cost_report
          params:
            start_date: "-7d"
            end_date: "today"
            granularity: DAILY
            group_by: ["TAG:Environment", "TAG:Team"]
          store: tag_costs
    
    - name: analyze
      description: Analyze cost data for anomalies
      steps:
        - name: calculate_metrics
          action: compute.metrics
          params:
            daily: "{{ daily_costs }}"
            monthly: "{{ monthly_costs }}"
            calculations:
              - name: yesterday_total
                expr: "daily[-1].total"
              - name: day_before_total
                expr: "daily[-2].total"
              - name: daily_change_pct
                expr: "(yesterday_total - day_before_total) / day_before_total * 100"
              - name: week_ago_total
                expr: "daily[-7].total"
              - name: weekly_change_pct
                expr: "(yesterday_total - week_ago_total) / week_ago_total * 100"
              - name: monthly_avg
                expr: "mean(monthly.totals)"
              - name: deviation_from_avg
                expr: "(yesterday_total - monthly_avg) / monthly_avg * 100"
          store: metrics
        
        - name: find_anomalies
          action: llm.analyze
          params:
            system: |
              You are a FinOps analyst reviewing cloud cost data.
              Identify any anomalies, unexpected spikes, or concerning trends.
              Be specific about which services or accounts are driving costs.
            prompt: |
              ## Cost Summary
              - Yesterday's total: ${{ metrics.yesterday_total | round(2) }}
              - Day before: ${{ metrics.day_before_total | round(2) }}
              - Daily change: {{ metrics.daily_change_pct | round(1) }}%
              - Week ago: ${{ metrics.week_ago_total | round(2) }}
              - Weekly change: {{ metrics.weekly_change_pct | round(1) }}%
              - Monthly average: ${{ metrics.monthly_avg | round(2) }}
              
              ## Top Services (Yesterday)
              {{ daily_costs.by_service[-1] | to_table }}
              
              ## Top Accounts (Yesterday)
              {{ account_costs[-1] | to_table }}
              
              ## By Environment
              {{ tag_costs.by_environment[-1] | to_table }}
              
              ## 7-Day Trend
              {{ daily_costs | trend_summary }}
              
              Analyze this data and identify:
              1. Any cost anomalies or spikes
              2. Services with unusual growth
              3. Potential causes
              4. Recommended actions
          store: analysis
    
    - name: notify
      description: Send report to Slack
      steps:
        - name: should_alert
          action: compute.eval
          params:
            expr: |
              {{ metrics.daily_change_pct > config.thresholds.daily_increase_pct
                 or metrics.weekly_change_pct > config.thresholds.weekly_increase_pct
                 or (metrics.yesterday_total - metrics.day_before_total) > config.thresholds.absolute_spike }}
          store: should_alert
        
        # Daily summary (always sent)
        - name: daily_summary
          action: slack.post_blocks
          params:
            channel: "{{ variables.slack_channel }}"
            blocks:
              - type: header
                text:
                  type: plain_text
                  text: "💰 Daily Cloud Cost Report"
              
              - type: section
                fields:
                  - type: mrkdwn
                    text: "*Yesterday:* ${{ metrics.yesterday_total | round(2) | format_currency }}"
                  - type: mrkdwn
                    text: "*Daily Change:* {{ '+' if metrics.daily_change_pct > 0 }}{{ metrics.daily_change_pct | round(1) }}%"
                  - type: mrkdwn
                    text: "*Weekly Change:* {{ '+' if metrics.weekly_change_pct > 0 }}{{ metrics.weekly_change_pct | round(1) }}%"
                  - type: mrkdwn
                    text: "*vs 30-Day Avg:* {{ '+' if metrics.deviation_from_avg > 0 }}{{ metrics.deviation_from_avg | round(1) }}%"
              
              - type: section
                text:
                  type: mrkdwn
                  text: |
                    *Top 5 Services*
                    ```
                    {{ daily_costs.by_service[-1].top(5) | to_table }}
                    ```
              
              - type: context
                elements:
                  - type: mrkdwn
                    text: "📊 <{{ dashboard_url }}|View Full Dashboard>"
        
        # Alert if thresholds exceeded
        - name: alert
          condition: "{{ should_alert }}"
          action: slack.post_blocks
          params:
            channel: "{{ variables.slack_channel }}"
            blocks:
              - type: header
                text:
                  type: plain_text
                  text: "🚨 Cost Anomaly Detected"
              
              - type: section
                text:
                  type: mrkdwn
                  text: |
                    *Alert:* Cloud spending exceeded thresholds
                    
                    {{ analysis.summary }}
              
              - type: section
                text:
                  type: mrkdwn
                  text: |
                    *🔍 Analysis*
                    
                    {{ analysis.findings }}
              
              - type: section
                text:
                  type: mrkdwn
                  text: |
                    *💡 Recommendations*
                    {% for rec in analysis.recommendations %}
                    • {{ rec }}
                    {% endfor %}
              
              - type: actions
                elements:
                  - type: button
                    text:
                      type: plain_text
                      text: "📊 View Dashboard"
                    url: "{{ dashboard_url }}"
                  - type: button
                    text:
                      type: plain_text
                      text: "🔧 Create Ticket"
                    action_id: create_ticket
    
    - name: store_metrics
      description: Store metrics for historical analysis
      steps:
        - name: save_daily
          action: memory.store
          params:
            collection: cost_metrics
            data:
              date: "{{ today }}"
              total: "{{ metrics.yesterday_total }}"
              by_service: "{{ daily_costs.by_service[-1] }}"
              by_account: "{{ account_costs[-1] }}"
              anomaly_detected: "{{ should_alert }}"

safety:
  auto_approve:
    - aws.cost_report
    - slack.*
    - compute.*
    - memory.store
```

## Example Slack Output

### Daily Summary

```
💰 Daily Cloud Cost Report

Yesterday:      $12,345.67      Daily Change:  +8.2%
Weekly Change:  +15.3%          vs 30-Day Avg: +12.1%

Top 5 Services
┌────────────────────┬──────────────┬─────────┐
│ Service            │ Cost         │ Change  │
├────────────────────┼──────────────┼─────────┤
│ EC2-Instances      │ $4,521.34    │ +5.2%   │
│ RDS                │ $2,890.12    │ +2.1%   │
│ S3                 │ $1,234.56    │ +18.3%  │
│ Lambda             │ $987.65      │ +45.2%  │
│ CloudWatch         │ $654.32      │ +3.4%   │
└────────────────────┴──────────────┴─────────┘

📊 View Full Dashboard
```

### Anomaly Alert

```
🚨 Cost Anomaly Detected

Alert: Cloud spending exceeded thresholds

Yesterday's spending was $12,345.67, which is 45% higher than 
the Lambda service's daily average. This spike correlates with 
the deployment of the new data-pipeline service.

🔍 Analysis

Lambda costs increased from $680/day to $987/day (+45%). 
The increase is driven by:
• New data-pipeline function running every 5 minutes
• Function duration averaging 3x longer than similar functions
• Memory allocation at 3GB may be excessive

💡 Recommendations
• Review data-pipeline function for optimization opportunities
• Consider reducing invocation frequency or batch size
• Check if 3GB memory allocation is necessary
• Set up budget alert at $1000/day for Lambda

[📊 View Dashboard] [🔧 Create Ticket]
```

## Multi-Cloud Support

Extend to monitor multiple clouds:

```yaml
skills:
  - aws
  - gcp
  - azure
  - slack

runbook:
  phases:
    - name: gather_costs
      parallel: true
      steps:
        - name: aws_costs
          action: aws.cost_report
          params:
            start_date: "-7d"
            end_date: "today"
          store: aws_costs
        
        - name: gcp_costs
          action: gcp.billing_report
          params:
            start_date: "-7d"
            end_date: "today"
          store: gcp_costs
        
        - name: azure_costs
          action: azure.cost_report
          params:
            start_date: "-7d"
            end_date: "today"
          store: azure_costs
    
    - name: aggregate
      steps:
        - name: combine
          action: compute.aggregate
          params:
            sources:
              - name: AWS
                data: "{{ aws_costs }}"
              - name: GCP
                data: "{{ gcp_costs }}"
              - name: Azure
                data: "{{ azure_costs }}"
          store: total_costs
```

## Weekly Report

Add a weekly summary agent:

```yaml
# agents/cost-weekly/agent.yaml
name: cost-weekly-report
triggers:
  - type: schedule
    cron: "0 9 * * 1"  # Monday at 9 AM

runbook:
  phases:
    - name: weekly_analysis
      steps:
        - name: get_weekly_data
          action: aws.cost_report
          params:
            start_date: "-7d"
            end_date: "today"
            granularity: DAILY
            group_by: ["SERVICE", "LINKED_ACCOUNT"]
        
        - name: generate_report
          action: llm.generate
          params:
            template: weekly_cost_report
            data: "{{ weekly_data }}"
        
        - name: send_report
          action: slack.post_blocks
          params:
            channel: "#finops"
            blocks: "{{ templates.weekly_report }}"
```

## Best Practices

1. **Set realistic thresholds** — Start with higher thresholds, tighten over time
2. **Group by meaningful dimensions** — Team, environment, service
3. **Include context** — Show trends, not just absolute numbers
4. **Actionable alerts** — Every alert should have clear next steps
5. **Track over time** — Store metrics for trend analysis

## Next Steps

- [Auto-Remediation Example](auto-remediation.md)
- [Incident Response Example](incident-response.md)
