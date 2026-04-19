# Agent Reference

Complete configuration reference for OpenSRE agents.

## Agent Configuration Schema

```yaml
# Full agent configuration schema
name: string                    # Required. Unique agent name
description: string             # Agent description
version: string                 # Semantic version (default: 1.0.0)

# Skills used by this agent
skills:                         # Required. List of skill names
  - prometheus
  - kubernetes
  - slack

# What triggers this agent
triggers:                       # Required. At least one trigger
  - type: string               # prometheus_alert, webhook, schedule, manual
    # ... trigger-specific config

# How the agent investigates and responds
runbook: string | object        # Text runbook or structured phases

# Agent-specific configuration
config:
  timeout: number               # Max investigation time (seconds, default: 300)
  max_concurrent: number        # Max concurrent investigations (default: 3)
  retry:
    max_attempts: number        # Retry failed steps (default: 3)
    backoff: string            # none, linear, exponential (default: exponential)
  
  notify:
    on_complete: boolean        # Notify when investigation completes
    on_error: boolean          # Notify on errors
    channel: string            # Default notification channel
  
  memory:
    store_incidents: boolean    # Store investigation results
    pattern_matching: boolean   # Search for similar incidents
    learn_from_outcomes: boolean # Learn from what worked
    retention_days: number      # How long to keep history

# Safety configuration
safety:
  auto_approve: list[string]    # Actions to auto-approve
  require_approval: list[string] # Actions requiring approval
  protected_namespaces: list[string]
  protected_deployments: list[string]
  dry_run: boolean             # Execute in dry-run mode
```

## Triggers Reference

### prometheus_alert

Triggered by Prometheus alerts via Alertmanager webhook.

```yaml
triggers:
  - type: prometheus_alert
    
    # Match by alertname (exact)
    alertname: HighErrorRate
    
    # Match by label selector (like PromQL)
    match: 'severity="critical", team="platform"'
    
    # Match by regex
    match_re: 'alertname=~"High.*Rate"'
    
    # Exclude certain alerts
    exclude: 'alertname="Watchdog"'
    
    # Only handle certain states
    states:
      - firing
      - resolved
```

### webhook

Generic webhook trigger.

```yaml
triggers:
  - type: webhook
    
    # Webhook path (appended to base URL)
    path: /webhook/my-agent
    
    # Source identifier
    source: custom
    
    # HTTP method
    method: POST
    
    # Validate with signature
    signature_header: X-Signature
    signature_secret: ${WEBHOOK_SECRET}
```

### pagerduty_webhook

PagerDuty-specific webhook.

```yaml
triggers:
  - type: pagerduty_webhook
    
    # Events to handle
    events:
      - incident.triggered
      - incident.acknowledged
      - incident.resolved
      - incident.escalated
    
    # Filter by service
    services:
      - P12345  # PagerDuty service ID
    
    # Filter by urgency
    urgency:
      - high
```

### argocd_webhook

ArgoCD-specific webhook.

```yaml
triggers:
  - type: argocd_webhook
    
    # Events to handle
    events:
      - sync_succeeded
      - sync_failed
      - health_degraded
    
    # Filter by application
    applications:
      - checkout-service
      - payment-service
```

### schedule

Cron-based scheduling.

```yaml
triggers:
  - type: schedule
    
    # Cron expression
    cron: "0 9 * * *"  # Daily at 9 AM
    
    # Timezone
    timezone: UTC  # or America/New_York, etc.
    
    # Skip if previous run still active
    skip_if_running: true
```

### manual

Manual invocation via CLI.

```yaml
triggers:
  - type: manual
    
    # CLI command
    command: investigate
    
    # Required arguments
    args:
      - name: description
        required: true
        description: What to investigate
```

## Runbook Reference

### Text Runbook

Simple text instructions for the LLM:

```yaml
runbook: |
  Investigate this alert:
  
  1. Query Prometheus for error rates over the last hour
  2. Check for recent deployments in the affected namespace
  3. Get logs from affected pods
  4. Identify the root cause
  5. If deployment-related, suggest rollback
  6. Post findings to Slack
```

### Structured Runbook

Explicit phases and steps:

```yaml
runbook:
  # Global variables
  variables:
    threshold: 0.05
    lookback: 1h
  
  phases:
    - name: observe
      description: Gather data
      timeout: 120
      parallel: true  # Run steps in parallel
      steps:
        - name: get_error_rate
          action: prometheus.query
          params:
            query: 'rate(errors[{{ variables.lookback }}])'
          store: error_rate
          
        - name: get_pods
          action: kubernetes.get_pods
          params:
            namespace: "{{ alert.labels.namespace }}"
          store: pods
    
    - name: analyze
      description: Identify root cause
      steps:
        - name: llm_analysis
          action: llm.analyze
          params:
            system: "You are an SRE investigating an incident."
            prompt: |
              Error rate: {{ error_rate.value }}
              Pods: {{ pods | length }} total, {{ pods | rejectattr('status', 'eq', 'Running') | length }} unhealthy
              
              What is the likely root cause?
          store: analysis
    
    - name: remediate
      description: Take action
      condition: "{{ analysis.confidence > 0.8 }}"
      steps:
        - name: rollback
          action: kubernetes.rollback
          condition: "{{ analysis.action == 'rollback' }}"
          params:
            deployment: "{{ alert.labels.deployment }}"
          approval_required: true
    
    - name: notify
      description: Inform team
      always_run: true  # Run even if previous phases failed
      steps:
        - name: slack_notification
          action: slack.post_blocks
          params:
            channel: "#incidents"
            blocks: "{{ templates.incident_report }}"
```

### Runbook Step Schema

```yaml
steps:
  - name: string              # Step name (for logging/debugging)
    action: string            # Skill action (e.g., prometheus.query)
    params: object            # Action parameters
    store: string             # Variable name to store result
    condition: string         # Jinja2 expression to evaluate
    timeout: number           # Step timeout in seconds
    retry:
      max_attempts: number
      backoff: string
    on_error: string          # continue, stop, retry (default: stop)
    approval_required: boolean # Require human approval
```

## Safety Configuration

```yaml
safety:
  # Pattern-based auto-approval
  auto_approve:
    - "prometheus.*"          # All Prometheus actions
    - "kubernetes.get_*"      # All get operations
    - "kubernetes.describe"
    - "slack.post_*"          # Posting messages
  
  # Pattern-based require approval
  require_approval:
    - "kubernetes.rollback"
    - "kubernetes.delete_*"
    - "kubernetes.scale"
    - "aws.terminate_*"
    - "terraform.apply"
  
  # Protected namespaces require extra confirmation
  protected_namespaces:
    - production
    - kube-system
    - monitoring
  
  # Protected deployments
  protected_deployments:
    - payment-service
    - auth-service
    - database
  
  # Dry-run mode
  dry_run: false
  
  # Require confirmation for destructive actions
  require_confirmation: true
  
  # Maximum automatic retries
  max_auto_remediation: 3
  
  # Cooldown between remediations
  cooldown_minutes: 15
```

## Template Variables

### Alert Variables

Available when triggered by an alert:

```yaml
# Prometheus alert fields
{{ alert.alertname }}
{{ alert.labels.severity }}
{{ alert.labels.service }}
{{ alert.labels.namespace }}
{{ alert.annotations.summary }}
{{ alert.annotations.description }}
{{ alert.status }}               # firing, resolved
{{ alert.starts_at }}
{{ alert.ends_at }}
{{ alert.fingerprint }}
{{ alert.generator_url }}

# PagerDuty incident fields
{{ incident.id }}
{{ incident.title }}
{{ incident.urgency }}
{{ incident.status }}
{{ incident.service.name }}
{{ incident.created_at }}
```

### Environment Variables

```yaml
{{ env.SLACK_CHANNEL }}
{{ env.CLUSTER_NAME }}
{{ env.AWS_REGION }}
```

### Built-in Functions

```yaml
# Jinja2 filters
{{ pods | length }}
{{ error_rate | round(2) }}
{{ timestamp | strftime('%Y-%m-%d') }}
{{ list | join(', ') }}
{{ string | lower }}
{{ string | upper }}

# Custom filters
{{ duration | humanize }}        # "15 minutes ago"
{{ bytes | humanize_bytes }}     # "1.5 GB"
{{ percentage | format_pct }}    # "15.3%"
```

### Stored Variables

```yaml
# Store from step
- action: prometheus.query
  store: error_rate

# Access later
{{ error_rate }}
{{ error_rate.value }}
{{ error_rate.labels }}
```

## Memory Configuration

```yaml
config:
  memory:
    # Store investigation results
    store_incidents: true
    
    # Vector store for semantic search
    vector_store:
      type: chroma          # chroma, pinecone, qdrant
      path: data/vectors
      collection: incidents
    
    # Pattern matching configuration
    pattern_matching:
      enabled: true
      similarity_threshold: 0.8
      max_similar: 5
    
    # Learning configuration
    learning:
      enabled: true
      feedback_channel: "#sre-feedback"
      
    # Retention
    retention_days: 90
```

## Notification Templates

```yaml
templates:
  incident_report:
    - type: header
      text: "🔍 Investigation Complete"
    
    - type: section
      fields:
        - "*Alert:* {{ alert.alertname }}"
        - "*Severity:* {{ alert.labels.severity }}"
        - "*Duration:* {{ alert.duration | humanize }}"
    
    - type: section
      text: |
        *Root Cause:*
        {{ analysis.root_cause }}
        
        *Confidence:* {{ (analysis.confidence * 100) | round }}%
    
    - type: section
      text: |
        *Recommendation:*
        {{ analysis.recommendation }}
    
    - type: actions
      elements:
        - type: button
          text: "✅ Approve"
          style: primary
          action_id: approve
        - type: button
          text: "❌ Dismiss"
          action_id: dismiss
```

## CLI Commands

```bash
# Create new agent
opensre agent create <name>

# List agents
opensre agent list

# Show agent details
opensre agent show <name>

# Test agent
opensre agent test <name> [--alert JSON] [--dry-run] [--verbose]

# Start specific agents
opensre start --agents <name1>,<name2>

# Stop agent
opensre agent stop <name>

# Reload agent configuration
opensre agent reload <name>

# View agent logs
opensre agent logs <name> [--tail 100]

# View agent history
opensre agent history <name> [--limit 20]
```

## Example Agents

See the [examples](../examples/) directory for complete agent examples:

- [Auto-Remediation](../examples/auto-remediation.md)
- [Incident Response](../examples/incident-response.md)
- [Cost Monitoring](../examples/cost-monitoring.md)
