# Incident Response Example

This example shows how to build a comprehensive incident response agent that coordinates investigation, communication, and remediation.

## Use Case

Respond to PagerDuty incidents by:
1. Acknowledging the incident
2. Running a comprehensive investigation
3. Posting findings to Slack
4. Suggesting and executing remediation
5. Updating the incident with resolution notes

## Agent Configuration

```yaml
# agents/incident-responder/agent.yaml
name: incident-responder
description: Comprehensive incident response automation
version: 1.0.0

skills:
  - prometheus
  - kubernetes
  - slack
  - pagerduty
  - github

triggers:
  - type: pagerduty_webhook
    events:
      - incident.triggered
  - type: manual
    command: investigate

config:
  timeout: 600  # 10 minutes
  
  memory:
    store_incidents: true
    pattern_matching: true
    learn_from_outcomes: true

  notify:
    on_complete: true
    on_error: true
    channel: "#incidents"

runbook:
  phases:
    - name: acknowledge
      description: Acknowledge the incident
      timeout: 30
      steps:
        - name: ack_pagerduty
          action: pagerduty.acknowledge
          params:
            incident_id: "{{ incident.id }}"
            message: "OpenSRE is investigating"
        
        - name: notify_start
          action: slack.post_message
          params:
            channel: "#incidents"
            text: "🔍 *OpenSRE* is investigating PagerDuty incident: {{ incident.title }}"
          store: slack_thread
    
    - name: observe
      description: Gather all relevant data
      timeout: 180
      parallel: true
      steps:
        - name: get_error_metrics
          action: prometheus.query_range
          params:
            query: 'rate(http_requests_total{status=~"5.."}[1m])'
            start: "-30m"
            step: "1m"
          store: error_metrics
        
        - name: get_latency_metrics
          action: prometheus.query_range
          params:
            query: 'histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))'
            start: "-30m"
            step: "1m"
          store: latency_metrics
        
        - name: get_resource_metrics
          action: prometheus.query_range
          params:
            query: 'container_memory_usage_bytes'
            start: "-30m"
            step: "1m"
          store: resource_metrics
        
        - name: get_pods
          action: kubernetes.get_pods
          params:
            all_namespaces: true
            field_selector: "status.phase!=Running"
          store: unhealthy_pods
        
        - name: get_events
          action: kubernetes.get_events
          params:
            all_namespaces: true
            field_selector: "type=Warning"
            limit: 50
          store: warning_events
        
        - name: get_deployments
          action: kubernetes.get_deployments
          params:
            all_namespaces: true
          store: deployments
        
        - name: get_recent_changes
          action: github.get_workflow_runs
          params:
            workflow: "deploy.yaml"
            status: "completed"
            per_page: 10
          store: recent_deploys
    
    - name: correlate
      description: Find patterns and correlations
      steps:
        - name: find_similar
          action: memory.find_similar
          params:
            observations:
              error_metrics: "{{ error_metrics }}"
              latency_metrics: "{{ latency_metrics }}"
              events: "{{ warning_events }}"
          store: similar_incidents
        
        - name: update_slack
          action: slack.post_thread
          params:
            channel: "#incidents"
            thread_ts: "{{ slack_thread.ts }}"
            text: |
              📊 *Gathering data...*
              • {{ error_metrics.data | length }} error rate data points
              • {{ unhealthy_pods | length }} unhealthy pods
              • {{ warning_events | length }} warning events
              • {{ recent_deploys | length }} recent deployments
    
    - name: analyze
      description: LLM analysis of all data
      steps:
        - name: llm_analysis
          action: llm.analyze
          params:
            system: |
              You are an expert SRE performing incident analysis.
              You have access to metrics, Kubernetes state, and deployment history.
              
              Provide a structured analysis including:
              1. What is happening (symptoms)
              2. What caused it (root cause)
              3. How confident you are (0-1)
              4. What should be done (recommendation)
              5. Specific action to take
            prompt: |
              ## Incident
              {{ incident.title }}
              {{ incident.description }}
              
              ## Error Metrics (last 30 min)
              {{ error_metrics | summarize_timeseries }}
              
              ## Latency Metrics (last 30 min)
              {{ latency_metrics | summarize_timeseries }}
              
              ## Resource Usage
              {{ resource_metrics | summarize_timeseries }}
              
              ## Unhealthy Pods
              {{ unhealthy_pods | to_yaml }}
              
              ## Warning Events
              {{ warning_events | to_yaml }}
              
              ## Recent Deployments
              {{ recent_deploys | to_yaml }}
              
              ## Similar Past Incidents
              {{ similar_incidents | to_yaml }}
              
              Analyze this incident and provide your assessment.
          store: analysis
    
    - name: report
      description: Post analysis to Slack
      steps:
        - name: post_analysis
          action: slack.post_blocks
          params:
            channel: "#incidents"
            thread_ts: "{{ slack_thread.ts }}"
            blocks:
              - type: header
                text:
                  type: plain_text
                  text: "🔍 Investigation Complete"
              
              - type: section
                text:
                  type: mrkdwn
                  text: |
                    *Incident:* {{ incident.title }}
                    *Duration:* {{ investigation_duration | humanize }}
              
              - type: divider
              
              - type: section
                text:
                  type: mrkdwn
                  text: |
                    *🎯 Root Cause* ({{ (analysis.confidence * 100) | round }}% confidence)
                    
                    {{ analysis.root_cause }}
              
              - type: section
                text:
                  type: mrkdwn
                  text: |
                    *📊 Evidence*
                    {% for item in analysis.evidence %}
                    • {{ item }}
                    {% endfor %}
              
              - type: section
                text:
                  type: mrkdwn
                  text: |
                    *💡 Recommendation*
                    {{ analysis.recommendation }}
              
              - type: actions
                elements:
                  - type: button
                    text:
                      type: plain_text
                      text: "✅ Approve Action"
                    style: primary
                    action_id: approve_action
                    value: "{{ analysis.action | to_json }}"
                  - type: button
                    text:
                      type: plain_text
                      text: "🔍 Need More Info"
                    action_id: more_info
                  - type: button
                    text:
                      type: plain_text
                      text: "❌ Dismiss"
                    style: danger
                    action_id: dismiss
          store: analysis_message
    
    - name: remediate
      description: Execute approved action
      steps:
        - name: wait_approval
          action: slack.wait_for_action
          params:
            message_ts: "{{ analysis_message.ts }}"
            timeout: 300
          store: approval
        
        - name: execute
          condition: "{{ approval.action_id == 'approve_action' }}"
          action: dynamic.execute
          params:
            action: "{{ analysis.action }}"
          store: action_result
        
        - name: post_result
          action: slack.post_thread
          params:
            channel: "#incidents"
            thread_ts: "{{ slack_thread.ts }}"
            text: |
              {% if action_result.success %}
              ✅ *Action completed successfully*
              {{ action_result.details }}
              {% else %}
              ❌ *Action failed*
              {{ action_result.error }}
              {% endif %}
    
    - name: resolve
      description: Update PagerDuty and close out
      always_run: true
      steps:
        - name: add_note
          action: pagerduty.add_note
          params:
            incident_id: "{{ incident.id }}"
            note: |
              OpenSRE Investigation Summary:
              
              Root Cause: {{ analysis.root_cause }}
              Confidence: {{ (analysis.confidence * 100) | round }}%
              
              Action Taken: {{ analysis.action.type }}
              Result: {{ action_result.status | default('pending') }}
        
        - name: resolve_incident
          condition: "{{ action_result.success }}"
          action: pagerduty.resolve
          params:
            incident_id: "{{ incident.id }}"
            message: "Resolved by OpenSRE: {{ analysis.action.type }}"

safety:
  auto_approve:
    - pagerduty.acknowledge
    - pagerduty.add_note
    - slack.*
    - prometheus.query*
    - kubernetes.get_*
    - github.get_*
    - memory.find_similar
  require_approval:
    - kubernetes.rollback
    - kubernetes.scale
    - kubernetes.restart
    - kubernetes.delete_*
    - pagerduty.resolve
```

## Slack Thread Example

```
🔍 OpenSRE is investigating PagerDuty incident: High error rate on checkout service

📊 Gathering data...
• 30 error rate data points
• 2 unhealthy pods  
• 8 warning events
• 3 recent deployments

────────────────────────────────────────────────────────

🔍 Investigation Complete

Incident: High error rate on checkout service
Duration: 47 seconds

────────────────────────────────────────────────────────

🎯 Root Cause (94% confidence)

Memory leak in checkout-service v2.4.1 causing OOM crashes.
The connection pool is not properly releasing connections,
leading to memory growth until the container is killed.

📊 Evidence
• Error rate increased 82x (0.1% → 8.3%) at 10:15 UTC
• Deployment checkout-v2.4.1 rolled out at 10:12 UTC
• 3 pods showing OOMKilled restarts
• Memory usage trending up before each restart

💡 Recommendation
Rollback to checkout-v2.4.0 immediately to restore service.
Create ticket to investigate memory leak in v2.4.1.

[✅ Approve Action] [🔍 Need More Info] [❌ Dismiss]

────────────────────────────────────────────────────────

✅ Action completed successfully
Rolled back deployment/checkout to revision 4 (v2.4.0)
Error rate now: 0.2%
```

## Testing

```bash
# Test with sample incident
opensre agent test incident-responder \
  --trigger '{
    "type": "pagerduty_webhook",
    "incident": {
      "id": "P12345",
      "title": "High error rate on checkout service",
      "urgency": "high",
      "service": {"name": "checkout"}
    }
  }' \
  --dry-run
```

## Integration Points

### PagerDuty Webhook Setup

1. Go to PagerDuty → Services → Your Service → Integrations
2. Add Generic Webhook V3
3. Set URL: `https://opensre.example.com/webhook/pagerduty`
4. Events: incident.triggered, incident.escalated

### Slack App Setup

1. Create Slack app with interactivity enabled
2. Set Request URL: `https://opensre.example.com/slack/events`
3. Add scopes: `chat:write`, `reactions:write`

### GitHub App Setup

1. Create GitHub App or use Personal Access Token
2. Permissions: Actions (read), Contents (read)

## Best Practices

1. **Quick acknowledgment** — Let the team know investigation started
2. **Regular updates** — Post progress to keep stakeholders informed
3. **Clear evidence** — Back up analysis with data
4. **Human approval** — Get sign-off before remediation
5. **Close the loop** — Update incident management tools

## Next Steps

- [Auto-Remediation Example](auto-remediation.md)
- [Cost Monitoring Example](cost-monitoring.md)
