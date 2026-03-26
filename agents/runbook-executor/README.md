# Runbook Executor Agent

Generic agent that executes runbook steps based on runbook ID and parameters, with approval workflows and execution tracking.

## Overview

This agent:
1. Loads runbooks from a repository
2. Validates actions and prerequisites
3. Requests approval (if configured)
4. Executes steps with progress tracking
5. Handles failures with analysis
6. Records execution history

## Triggers

### Manual Webhook
- **Path:** `/webhook/runbook`

### PagerDuty Integration
- **Path:** `/webhook/runbook/pagerduty`
- Links runbook execution to incidents

### Slack Command
- **Source:** `slack`
- **Action:** `runbook_execute`

## Configuration

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `runbook_repository` | string | `s3://company-runbooks/` | Runbook storage location |
| `runbook_format` | string | `yaml` | Runbook file format |
| `slack_channel` | string | `#runbook-executions` | Notification channel |
| `require_approval` | bool | `true` | Require manual approval |
| `approval_timeout_minutes` | int | `30` | Approval timeout |
| `dry_run_default` | bool | `false` | Default dry-run mode |
| `max_execution_time_minutes` | int | `60` | Max execution time |

### Action Control
```yaml
allowed_actions:
  - kubernetes.*
  - ssh.execute
  - database.query
  - http.request
  - slack.send_message
blocked_actions:
  - ssh.delete_files
  - database.drop
```

## Required Skills

- **runbook** - Runbook loading and execution
- **kubernetes** - K8s operations
- **ssh** - Remote execution
- **database** - Database operations
- **slack** - Notifications and approvals
- **pagerduty** - Incident updates
- **llm** - Failure analysis

## Workflow

```
┌─────────────────────┐
│  Trigger Received   │
│  (runbook_id)       │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  1. Load Runbook    │
│  from repository    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  2. Validate        │
│  - Allowed actions  │
│  - Parameters       │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  3. Check           │
│  Prerequisites      │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  4. Request         │
│  Approval           │
│  (if required)      │
└──────────┬──────────┘
           │
     ┌─────┴─────┐
     │           │
     ▼           ▼
┌─────────┐ ┌─────────┐
│ Approved│ │ Rejected│
└────┬────┘ └────┬────┘
     │           │
     │           ▼
     │      ┌─────────┐
     │      │ Abort   │
     │      └─────────┘
     ▼
┌─────────────────────┐
│  5. Execute Steps   │
│  with progress      │
│  tracking           │
└──────────┬──────────┘
           │
     ┌─────┴─────┐
     │           │
     ▼           ▼
┌─────────┐ ┌─────────┐
│ Success │ │ Failure │
└────┬────┘ └────┬────┘
     │           │
     │           ▼
     │      ┌─────────┐
     │      │ Analyze │
     │      │ Failure │
     │      └────┬────┘
     │           │
     └─────┬─────┘
           │
           ▼
┌─────────────────────┐
│  6. Notify &        │
│  Record             │
└─────────────────────┘
```

## Runbook Format

```yaml
name: restart-api-server
description: Safely restart the API server deployment
version: 1.0.0

parameters:
  - name: namespace
    type: string
    required: true
    default: production
  - name: deployment
    type: string
    required: true
  - name: wait_time_seconds
    type: integer
    default: 30

prerequisites:
  - action: kubernetes.check_deployment_exists
    params:
      namespace: "{{ parameters.namespace }}"
      deployment: "{{ parameters.deployment }}"
  - action: kubernetes.check_no_ongoing_rollout
    params:
      namespace: "{{ parameters.namespace }}"
      deployment: "{{ parameters.deployment }}"

steps:
  - name: scale_down
    action: kubernetes.scale_deployment
    params:
      namespace: "{{ parameters.namespace }}"
      deployment: "{{ parameters.deployment }}"
      replicas: 0
    rollback:
      action: kubernetes.scale_deployment
      params:
        replicas: "{{ original_replicas }}"

  - name: wait
    action: compute.sleep
    params:
      seconds: "{{ parameters.wait_time_seconds }}"

  - name: scale_up
    action: kubernetes.scale_deployment
    params:
      namespace: "{{ parameters.namespace }}"
      deployment: "{{ parameters.deployment }}"
      replicas: "{{ original_replicas }}"

  - name: verify
    action: kubernetes.wait_rollout
    params:
      namespace: "{{ parameters.namespace }}"
      deployment: "{{ parameters.deployment }}"
      timeout_seconds: 120

rollback_on_failure: true
notify_on_complete: true
```

## Example Trigger Payload

```json
{
  "runbook_id": "restart-api-server",
  "triggered_by": "user@example.com",
  "parameters": {
    "namespace": "production",
    "deployment": "api-server"
  },
  "dry_run": false
}
```

## Approval Flow

When `require_approval: true`:

1. Agent posts approval request to Slack
2. Request includes:
   - Runbook details
   - Parameters
   - Steps to execute
   - Prerequisite status
3. Buttons: **Approve**, **Reject**, **Dry Run**
4. Timeout after `approval_timeout_minutes`

## Execution Modes

### Live Execution
- Executes all steps
- Modifies real resources
- Records changes

### Dry Run
- Simulates execution
- No actual changes
- Reports what would happen

## Progress Tracking

During execution:
```
🚀 Runbook Execution Started
Runbook: restart-api-server
Mode: LIVE 🔴

  ✅ Step 1/4: scale_down completed
  ✅ Step 2/4: wait completed
  ✅ Step 3/4: scale_up completed
  ⏳ Step 4/4: verify in progress...
```

## Failure Handling

On step failure:
1. Execution stops
2. LLM analyzes failure
3. Rollback triggered (if configured)
4. Failure notification with:
   - Error details
   - Root cause analysis
   - Retry button

## PagerDuty Integration

When triggered from PagerDuty:
- Execution notes added to incident
- Status updates on completion
- Links execution to incident timeline

## Testing

```bash
# Run unit tests
pytest test_agent.py -v

# Test runbook execution (dry run)
curl -X POST http://localhost:8080/webhook/runbook \
  -H "Content-Type: application/json" \
  -d '{
    "runbook_id": "restart-api-server",
    "parameters": {"namespace": "staging", "deployment": "test-app"},
    "dry_run": true
  }'
```

## Metrics

Prometheus metrics pushed:
- `opensre_runbook_execution_total{runbook_id, status}`
- `opensre_runbook_execution_duration_seconds{runbook_id}`

## Security

### Action Allowlist
Only explicitly allowed actions can execute:
```yaml
allowed_actions:
  - kubernetes.scale_deployment
  - kubernetes.restart_pods
```

### Action Blocklist
Dangerous actions are blocked:
```yaml
blocked_actions:
  - database.drop
  - kubernetes.delete_namespace
```

### Approval Required
Production runbooks require manual approval by default.
