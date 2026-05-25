# Workflow Automation Guide

AutoSRE's workflow engine provides a powerful, declarative way to automate SRE tasks. Inspired by Temporal and Argo Workflows, it offers a YAML-based DSL designed specifically for infrastructure automation.

## Overview

The workflow engine enables you to:

- **Automate incident response** with intelligent triage and remediation
- **Orchestrate deployments** with canary releases and automated rollbacks
- **Schedule maintenance tasks** with complex dependencies
- **React to events** from alerts, webhooks, or schedules

## Quick Start

### 1. Define a Workflow

Create a YAML file defining your workflow:

```yaml
apiVersion: autosre.io/v1
kind: Workflow
metadata:
  name: my-first-workflow
  version: 1.0.0
spec:
  inputs:
    - name: service
      type: string
      required: true
  steps:
    - name: Check Health
      action: health.check
      inputs:
        service: ${{ inputs.service }}
```

### 2. Register and Execute

```python
from autosre.workflows import (
    WorkflowEngine,
    parse_workflow_file,
)

# Create engine
engine = WorkflowEngine()

# Register action handlers
engine.register_action_handler("health.check", health_check_handler)

# Load workflow
workflow = parse_workflow_file("my-workflow.yaml")
engine.register_workflow(workflow)

# Execute
execution = await engine.execute(
    workflow_id=workflow.id,
    inputs={"service": "my-service"}
)

print(f"Status: {execution.status}")
```

## Workflow DSL Reference

### Structure

Every workflow has three main sections:

```yaml
apiVersion: autosre.io/v1
kind: Workflow
metadata:
  name: workflow-name
  version: 1.0.0
  description: What this workflow does
  author: Your Name
  tags: [tag1, tag2]
  
spec:
  inputs: []      # Input parameters
  outputs: []     # Output values
  triggers: []    # How workflow is triggered
  steps: []       # Workflow steps
  onSuccess: []   # Steps to run on success
  onFailure: []   # Steps to run on failure
  timeout: 3600   # Timeout in seconds
```

### Inputs

Define input parameters for your workflow:

```yaml
inputs:
  - name: service
    type: string
    required: true
    description: Service name to process
    
  - name: environment
    type: string
    required: true
    enum: [dev, staging, prod]
    default: dev
    
  - name: replicas
    type: integer
    default: 3
    
  - name: features
    type: array
    default: []
```

### Outputs

Define output values computed from step results:

```yaml
outputs:
  - name: incident_id
    value: ${{ steps.create_incident.output.id }}
    
  - name: summary
    value: ${{ steps.analyze.output.summary }}
```

### Triggers

Workflows can be triggered by multiple event types:

#### Alert Triggers

```yaml
triggers:
  - type: alert
    severity: [critical, high]
    alert_names:
      - HighErrorRate
      - PodCrashLooping
    sources: [prometheus, pagerduty]
    labels:
      environment: production
```

#### Schedule Triggers

```yaml
triggers:
  - type: schedule
    cron: "0 3 * * *"    # Daily at 3 AM
    timezone: UTC
    catch_up: false       # Don't run missed executions
```

#### Webhook Triggers

```yaml
triggers:
  - type: webhook
    path: /deploy
    methods: [POST]
    required_headers:
      X-API-Key: secret
```

#### Manual Triggers

```yaml
triggers:
  - type: manual
    required_inputs: [service, environment]
    require_confirmation: true
    confirmation_message: "Are you sure?"
```

## Step Types

### Action Steps

Execute a single action:

```yaml
- name: Get Pods
  id: get_pods
  action: kubernetes.get_pods
  inputs:
    namespace: ${{ inputs.namespace }}
    label_selector: app=${{ inputs.service }}
  outputs:
    - pod_list
  timeout: 60
  retries: 3
  retryDelay: 10
  continueOnError: false
```

### Condition Steps

Branch based on conditions:

```yaml
- name: Check Severity
  type: condition
  if: inputs.severity == "critical"
  then:
    - name: Page On-Call
      action: pagerduty.page
      inputs:
        team: sre
  elif:
    - condition: inputs.severity == "high"
      steps:
        - name: Send Alert
          action: slack.alert
          inputs:
            channel: "#alerts"
  else:
    - name: Log Info
      action: log.info
      inputs:
        message: "Low severity, logging only"
```

### Loop Steps

Iterate over collections:

```yaml
# For-each loop
- name: Process Services
  type: loop
  forEach: ${{ inputs.services }}
  itemVar: service
  indexVar: idx
  maxIterations: 100
  delay: 5
  steps:
    - name: Check Service
      action: health.check
      inputs:
        service: ${{ service }}

# While loop
- name: Wait for Ready
  type: loop
  while: steps.check.output.ready != true
  maxIterations: 30
  delay: 10
  steps:
    - name: Check
      id: check
      action: deployment.status

# Until loop
- name: Poll Until Done
  type: loop
  until: steps.poll.output.completed == true
  maxIterations: 60
  delay: 30
  steps:
    - name: Poll
      id: poll
      action: job.status
```

### Parallel Steps

Execute steps concurrently:

```yaml
- name: Gather Context
  type: parallel
  maxConcurrency: 5
  failFast: false
  steps:
    - name: Get Metrics
      action: prometheus.query
      inputs:
        query: up{job="myservice"}
        
    - name: Get Logs
      action: logs.search
      inputs:
        service: myservice
        
    - name: Get Events
      action: kubernetes.get_events
      inputs:
        namespace: default
```

### Sub-Workflow Steps

Invoke another workflow:

```yaml
- name: Run Triage
  type: subworkflow
  workflow: incident-triage-v1
  inputs:
    alert_id: ${{ trigger.alert_id }}
    severity: ${{ trigger.severity }}
  wait: true
```

## Expressions

### Variable References

Access inputs, step outputs, and context:

```yaml
# Input values
${{ inputs.service }}

# Step outputs
${{ steps.my_step.output }}
${{ steps.my_step.output.field_name }}
${{ steps.my_step.status }}

# Trigger data
${{ trigger.alert_id }}
${{ trigger.labels.environment }}

# Execution context
${{ execution.id }}
${{ execution.started_at }}
```

### Conditions

Use in `if` clauses:

```yaml
# Equality
if: inputs.severity == "critical"

# Comparison
if: steps.analyze.output.confidence > 0.8

# Boolean operators
if: inputs.enabled == true and inputs.count > 0

# Membership
if: inputs.env in ["prod", "staging"]

# Complex conditions
if: |
  steps.check.output.error_rate > 5 or
  steps.check.output.latency_ms > 1000
```

## Action Handlers

Register Python functions to handle actions:

```python
from autosre.workflows import WorkflowEngine, WorkflowContext

engine = WorkflowEngine()

async def kubernetes_get_pods(
    inputs: dict, 
    context: WorkflowContext
) -> dict:
    """Handler for kubernetes.get_pods action."""
    namespace = inputs.get("namespace", "default")
    selector = inputs.get("label_selector", "")
    
    # Call Kubernetes API
    pods = await k8s_client.list_pods(namespace, selector)
    
    return {
        "pods": [pod.to_dict() for pod in pods],
        "count": len(pods),
    }

engine.register_action_handler("kubernetes.get_pods", kubernetes_get_pods)
```

## Workflow Templates

Use pre-built templates for common patterns:

```python
from autosre.workflows import (
    TemplateRegistry,
    get_builtin_templates,
    INCIDENT_RESPONSE_TEMPLATE,
)

# Get built-in templates
templates = get_builtin_templates()

# Instantiate a template with custom parameters
workflow = INCIDENT_RESPONSE_TEMPLATE.instantiate({
    "slack_channel": "#my-incidents",
    "investigation_timeout": 600,
})

engine.register_workflow(workflow)
```

### Available Templates

| Template | Description |
|----------|-------------|
| `incident-response` | Automated incident triage and response |
| `auto-scaling` | Resource-based auto-scaling |
| `deployment-rollback` | Automated rollback on degradation |
| `health-check` | Comprehensive service health checks |
| `chaos-engineering` | Controlled chaos experiments |

## Triggers

### Alert Trigger

```python
from autosre.workflows import TriggerManager, AlertTrigger

manager = TriggerManager()

trigger = AlertTrigger(
    id="high-severity-alerts",
    severities=["critical", "high"],
    alert_names=["HighErrorRate", "PodCrashLooping"],
    workflow_ids=["incident-response-v1"],
    dedupe_window_seconds=300,
)

manager.register(trigger)

# Process incoming alert
events = await manager.process_alert({
    "alert_name": "HighErrorRate",
    "severity": "critical",
    "labels": {"service": "api"},
})
```

### Schedule Trigger

```python
from autosre.workflows import ScheduleTrigger

trigger = ScheduleTrigger(
    id="daily-maintenance",
    cron="0 3 * * *",
    timezone="America/New_York",
    workflow_ids=["database-maintenance-v1"],
    catch_up=False,
)

manager.register(trigger)
await manager.start_scheduler()
```

### Webhook Trigger

```python
from autosre.workflows import WebhookTrigger

trigger = WebhookTrigger(
    id="deploy-webhook",
    path="/api/v1/webhooks/deploy",
    methods=["POST"],
    api_key="secret-key",
    workflow_ids=["canary-deployment-v1"],
)

manager.register(trigger)

# Process incoming webhook
event = await manager.process_webhook({
    "method": "POST",
    "path": "/api/v1/webhooks/deploy",
    "headers": {"Authorization": "Bearer secret-key"},
    "body": {"service": "api", "image": "api:v2"},
})
```

## Execution Management

### Monitoring Executions

```python
# Get execution by ID
execution = engine.get_execution(execution_id)

# List executions with filters
executions = engine.list_executions(
    workflow_id="incident-response-v1",
    status=ExecutionStatus.RUNNING,
    limit=50,
)

# Get engine stats
stats = engine.stats
print(f"Running: {stats['running_executions']}")
```

### Lifecycle Operations

```python
# Cancel a running execution
await engine.cancel_execution(execution_id)

# Pause an execution
await engine.pause_execution(execution_id)

# Resume a paused execution
await engine.resume_execution(execution_id)
```

### Lifecycle Hooks

```python
def on_execution_start(execution):
    logger.info(f"Started: {execution.id}")

def on_step_complete(execution, step, result):
    metrics.record_step_duration(
        step.name, 
        result.duration_seconds
    )

engine.register_hook("on_execution_start", on_execution_start)
engine.register_hook("on_step_complete", on_step_complete)
```

## Multi-Tenancy

Workflows support multi-tenant execution:

```python
execution = await engine.execute(
    workflow_id="incident-response-v1",
    inputs={"alert_id": "123"},
    tenant_id="acme-corp",
)

# Filter executions by tenant
executions = engine.list_executions(tenant_id="acme-corp")
```

## Best Practices

### 1. Use Meaningful Step IDs

```yaml
# Good
- name: Get Deployment Status
  id: deployment_status
  
# Avoid
- name: Step 1
  id: step1
```

### 2. Handle Failures Gracefully

```yaml
- name: Non-Critical Step
  action: metrics.record
  continueOnError: true

- name: Critical Step
  action: incident.create
  retries: 3
  retryDelay: 10
```

### 3. Use Timeouts

```yaml
- name: Long Operation
  action: backup.create
  timeout: 3600  # 1 hour
```

### 4. Validate Inputs

```yaml
inputs:
  - name: replicas
    type: integer
    required: true
    enum: [1, 2, 3, 5, 10]
```

### 5. Use Templates for Common Patterns

```python
workflow = INCIDENT_RESPONSE_TEMPLATE.instantiate({
    "slack_channel": "#my-team",
})
```

## Troubleshooting

### Workflow Not Triggering

1. Check trigger configuration matches event data
2. Verify trigger is enabled
3. Check dedupe window for alert triggers
4. Verify schedule trigger is running (`manager.start_scheduler()`)

### Step Failing

1. Check step execution in `execution.step_executions`
2. Verify action handler is registered
3. Check input expressions are valid
4. Review error in `step_execution.error`

### Expression Errors

1. Verify variable references exist
2. Check step IDs match
3. Use proper syntax: `${{ ... }}`

## API Reference

See the [API documentation](../api/workflows.md) for complete class and method references.
