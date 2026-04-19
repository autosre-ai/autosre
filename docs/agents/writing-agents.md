# Writing Agents

This guide walks you through creating custom agents for OpenSRE.

## Quick Start

### Generate Agent Scaffold

```bash
opensre agent create my-agent

# Creates:
# agents/my-agent/
# ├── agent.yaml
# └── README.md
```

## Agent Configuration

### Basic Structure

```yaml
# agents/my-agent/agent.yaml
name: my-agent
description: A custom agent that does something useful
version: 1.0.0

# Skills this agent uses
skills:
  - prometheus
  - kubernetes
  - slack

# What triggers this agent
triggers:
  - type: prometheus_alert
    match: 'alertname="MyAlert"'

# How the agent investigates and responds
runbook: |
  1. Query relevant metrics
  2. Check Kubernetes pod health
  3. Analyze and identify root cause
  4. Suggest remediation
  5. Notify team

# Safety configuration
safety:
  auto_approve:
    - prometheus.query
    - kubernetes.get_*
  require_approval:
    - kubernetes.rollback
```

## Triggers

### Prometheus Alert

```yaml
triggers:
  - type: prometheus_alert
    match: 'severity="critical"'
  
  - type: prometheus_alert
    alertname: HighErrorRate
    labels:
      service: checkout
```

### Webhook

```yaml
triggers:
  - type: webhook
    source: custom
    path: /webhook/my-agent
    
  - type: pagerduty_webhook
    events:
      - incident.triggered
      - incident.escalated
```

### Schedule

```yaml
triggers:
  - type: schedule
    cron: "0 9 * * *"         # Daily at 9 AM
    timezone: UTC
    
  - type: schedule
    cron: "*/15 * * * *"      # Every 15 minutes
```

### Multiple Triggers

```yaml
triggers:
  - type: prometheus_alert
    match: 'alertname=~"High.*Error.*"'
  - type: pagerduty_webhook
    events: [incident.triggered]
  - type: manual
```

## Runbooks

Runbooks tell the agent how to investigate and respond.

### Simple Text Runbook

```yaml
runbook: |
  1. Get error metrics from Prometheus
  2. Check for recent deployments
  3. Get logs from affected pods
  4. Identify root cause
  5. Suggest fix
  6. Post to Slack
```

### Structured Runbook

```yaml
runbook:
  phases:
    - name: observe
      description: Gather data from systems
      steps:
        - action: prometheus.query
          params:
            query: 'rate(http_errors_total[5m])'
          store: error_rate
          
        - action: kubernetes.get_pods
          params:
            namespace: "{{ alert.labels.namespace }}"
            label_selector: "app={{ alert.labels.service }}"
          store: pods
          
        - action: kubernetes.get_events
          params:
            namespace: "{{ alert.labels.namespace }}"
          store: events
    
    - name: analyze
      description: Identify root cause
      steps:
        - action: llm.analyze
          params:
            context:
              error_rate: "{{ error_rate }}"
              pods: "{{ pods }}"
              events: "{{ events }}"
            prompt: |
              Analyze these observations and identify the root cause.
              Consider recent deployments, resource constraints, and errors.
          store: analysis
    
    - name: remediate
      description: Take action
      conditions:
        - "{{ analysis.confidence > 0.8 }}"
      steps:
        - action: kubernetes.rollback
          condition: "{{ analysis.recommendation == 'rollback' }}"
          params:
            deployment: "{{ alert.labels.service }}"
            namespace: "{{ alert.labels.namespace }}"
          approval_required: true
    
    - name: notify
      description: Inform team
      steps:
        - action: slack.post_blocks
          params:
            channel: "#incidents"
            blocks: "{{ templates.analysis_report }}"
```

### Runbook Templates

Reference markdown runbooks:

```yaml
runbook:
  reference: runbooks/memory-leak-remediation.md
```

With runbook file:

```markdown
<!-- runbooks/memory-leak-remediation.md -->
# Memory Leak Remediation

## Symptoms
- Increasing memory usage over time
- OOMKilled pod restarts
- Gradual performance degradation

## Investigation
1. Query memory metrics: `prometheus.query("container_memory_usage_bytes")`
2. Check pod restarts: `kubernetes.get_events(type="Warning")`
3. Look for recent deployments

## Remediation
- **If recent deployment**: Rollback
- **If not recent**: Scale replicas and investigate
- **If critical**: Page on-call
```

## Variables and Templates

### Alert Variables

```yaml
runbook: |
  Service: {{ alert.labels.service }}
  Namespace: {{ alert.labels.namespace }}
  Severity: {{ alert.labels.severity }}
  Summary: {{ alert.annotations.summary }}
```

### Environment Variables

```yaml
runbook: |
  Channel: {{ env.SLACK_CHANNEL }}
  Cluster: {{ env.CLUSTER_NAME }}
```

### Stored Values

```yaml
runbook:
  phases:
    - name: observe
      steps:
        - action: prometheus.query
          params:
            query: 'rate(errors[5m])'
          store: error_rate
    
    - name: notify
      steps:
        - action: slack.post_message
          params:
            text: "Error rate: {{ error_rate.value }}"
```

### Conditional Logic

```yaml
runbook:
  phases:
    - name: remediate
      steps:
        - action: kubernetes.rollback
          condition: |
            {{ analysis.root_cause == "deployment" and 
               analysis.confidence > 0.9 }}
          
        - action: kubernetes.scale
          condition: "{{ analysis.root_cause == 'resource_exhaustion' }}"
          params:
            replicas: "{{ pods.count + 2 }}"
```

## Agent Configuration Options

### Timeout and Concurrency

```yaml
config:
  # Maximum time for investigation
  timeout: 300  # 5 minutes
  
  # Maximum concurrent investigations
  max_concurrent: 3
  
  # Retry failed steps
  retry:
    max_attempts: 3
    backoff: exponential
```

### Notifications

```yaml
config:
  notify:
    # Always notify on completion
    on_complete: true
    
    # Notify on errors
    on_error: true
    
    # Default channel
    channel: "#incidents"
```

### Memory and Learning

```yaml
config:
  memory:
    # Store investigation results
    store_incidents: true
    
    # Search for similar past incidents
    pattern_matching: true
    
    # Learn from outcomes
    learn_from_outcomes: true
    
    # Retention period
    retention_days: 90
```

## Advanced Agents

### Python Agent

For complex logic, write a Python agent:

```python
# agents/my-agent/agent.py
from opensre import Agent, skill, trigger
from opensre.skills import prometheus, kubernetes, slack


class MyAgent(Agent):
    """Custom agent with Python logic."""
    
    name = "my-agent"
    skills = ["prometheus", "kubernetes", "slack"]
    
    @trigger(type="prometheus_alert", match='alertname="MyAlert"')
    async def handle_alert(self, alert: dict):
        """Handle incoming alert."""
        
        # 1. Observe
        error_rate = await prometheus.query(
            f'rate(errors{{service="{alert["labels"]["service"]}"}}[5m])'
        )
        
        pods = await kubernetes.get_pods(
            namespace=alert["labels"]["namespace"],
            label_selector=f"app={alert['labels']['service']}"
        )
        
        # 2. Reason
        analysis = await self.analyze(error_rate, pods, alert)
        
        # 3. Act
        if analysis.confidence > 0.9 and analysis.recommendation == "rollback":
            approved = await self.request_approval(
                action="rollback",
                deployment=alert["labels"]["service"]
            )
            
            if approved:
                await kubernetes.rollback(
                    deployment=alert["labels"]["service"],
                    namespace=alert["labels"]["namespace"]
                )
        
        # 4. Notify
        await slack.post_blocks(
            channel="#incidents",
            blocks=self.format_analysis(analysis)
        )
    
    async def analyze(self, error_rate, pods, alert):
        """Custom analysis logic."""
        # Your analysis code here
        pass
    
    def format_analysis(self, analysis):
        """Format analysis for Slack."""
        # Your formatting code here
        pass
```

### Multi-Phase Agent

Complex investigations with multiple phases:

```yaml
name: comprehensive-investigator
description: Deep-dive investigation with multiple phases

runbook:
  phases:
    - name: triage
      description: Initial assessment
      timeout: 60
      steps:
        - action: prometheus.query
          params:
            query: 'rate(errors[1m])'
        - action: llm.classify
          params:
            prompt: "Is this critical, high, medium, or low priority?"
    
    - name: deep_investigation
      condition: "{{ triage.priority in ['critical', 'high'] }}"
      timeout: 300
      steps:
        - action: kubernetes.get_logs
          params:
            tail_lines: 1000
        - action: prometheus.query_range
          params:
            start: "-1h"
        - action: llm.analyze
          params:
            context: "{{ all_observations }}"
    
    - name: quick_check
      condition: "{{ triage.priority in ['medium', 'low'] }}"
      timeout: 60
      steps:
        - action: prometheus.query
        - action: llm.summarize
    
    - name: resolution
      steps:
        - action: slack.post_blocks
        - action: pagerduty.add_note
```

## Testing Agents

### Unit Test

```bash
# Test with mock alert
opensre agent test my-agent \
  --alert '{"alertname": "HighErrorRate", "labels": {"service": "checkout"}}'

# Dry-run mode (no actual actions)
opensre agent test my-agent --dry-run

# Verbose output
opensre agent test my-agent --verbose
```

### Integration Test

```yaml
# agents/my-agent/test.yaml
tests:
  - name: high_error_rate_triggers_rollback
    alert:
      alertname: HighErrorRate
      labels:
        service: checkout
        namespace: production
    mocks:
      prometheus.query:
        return: 0.15  # 15% error rate
      kubernetes.get_deployments:
        return:
          - name: checkout
            revision: 5
            last_update: "2024-01-15T10:00:00Z"
    assertions:
      - action: kubernetes.rollback
        called: true
        params:
          deployment: checkout
      - action: slack.post_blocks
        called: true
```

### Run Tests

```bash
opensre agent test my-agent --suite agents/my-agent/test.yaml
```

## Best Practices

### 1. Start Simple

Begin with basic investigations, add complexity as needed.

### 2. Use Structured Runbooks

Structured runbooks are easier to test and debug.

### 3. Set Appropriate Timeouts

Don't let investigations run forever:
```yaml
config:
  timeout: 300  # 5 minutes max
```

### 4. Log Everything

```yaml
config:
  logging:
    level: DEBUG
    include_observations: true
```

### 5. Test Thoroughly

Write tests for expected scenarios and edge cases.

### 6. Start with Dry-Run

```yaml
safety:
  dry_run: true  # Start in dry-run mode
```

### 7. Gradual Approval Reduction

Start requiring approval for everything, then gradually auto-approve as you build confidence.

## Next Steps

- **[Agent Reference](agent-reference.md)** — Complete configuration reference
- **[Skills Overview](../skills/overview.md)** — Available skills
- **[Examples](../examples/)** — Example agents
