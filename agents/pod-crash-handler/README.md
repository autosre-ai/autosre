# Pod Crash Handler Agent

Automatically detects and responds to Kubernetes pod crashes (CrashLoopBackOff), collecting diagnostics and optionally performing recovery actions.

## Overview

This agent monitors for pod crash events and:
1. Collects pod details, logs, and events
2. Gathers resource metrics from Prometheus
3. Optionally analyzes the crash using LLM
4. Notifies the team via Slack with actionable buttons
5. Attempts pod restart or deployment rollback
6. Creates incident tickets for severe issues

## Triggers

### Kubernetes Event Webhook
- **Path:** `/webhook/kubernetes`
- **Events:** `Warning.BackOff`, `Warning.CrashLoopBackOff`

### Kubernetes Event Watch
- **Source:** `kubernetes`
- **Resource:** `pods`
- **Filter:** `status.containerStatuses[*].state.waiting.reason=CrashLoopBackOff`

## Configuration

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `slack_channel` | string | `#pod-alerts` | Alert notification channel |
| `max_restart_attempts` | int | `3` | Max restarts before giving up |
| `rollback_on_crash_threshold` | int | `5` | Restart count triggering rollback |
| `log_lines` | int | `200` | Number of log lines to collect |
| `auto_rollback` | boolean | `false` | Auto-rollback on threshold |
| `analysis_enabled` | boolean | `true` | Enable LLM crash analysis |

## Required Skills

- **kubernetes** - Pod management, logs, events
- **slack** - Notifications
- **prometheus** - Resource metrics
- **llm** - Crash analysis (optional)
- **jira** - Incident tickets (optional)

## Example Trigger Payload

```json
{
  "source": "kubernetes",
  "event_type": "Warning.CrashLoopBackOff",
  "pod_name": "api-server-abc123",
  "namespace": "production",
  "container_name": "api",
  "restart_count": 5,
  "message": "Back-off restarting failed container"
}
```

## Workflow

```
┌─────────────────────────┐
│  CrashLoopBackOff       │
│  Event Detected         │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  1. Get Pod Details     │
│  - Status, spec, owner  │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  2. Collect Diagnostics │
│  - Logs (previous)      │
│  - Events               │
│  - Metrics              │
│  - Deployment info      │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  3. Analyze Crash (LLM) │
│  - Root cause           │
│  - Severity             │
│  - Recommendations      │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  4. Notify Slack        │
│  - Summary              │
│  - Action buttons       │
└───────────┬─────────────┘
            │
            ▼
   ┌────────┴────────┐
   │                 │
   ▼                 ▼
┌─────────┐   ┌─────────────────┐
│ Restart │   │ Rollback        │
│ < 3x    │   │ >= 5 restarts   │
└────┬────┘   └────────┬────────┘
     │                 │
     └────────┬────────┘
              │
              ▼
     ┌────────────────┐
     │ Create Ticket  │
     │ (if critical)  │
     └────────────────┘
```

## Recovery Actions

### Automatic Restart
When restart count is below threshold:
- Deletes pod gracefully (30s grace period)
- Kubernetes recreates pod from ReplicaSet/Deployment

### Automatic Rollback
When restart count exceeds threshold and `auto_rollback: true`:
- Identifies parent Deployment
- Rolls back to previous revision
- Notifies team of rollback action

## LLM Analysis

When enabled, the agent asks an LLM to analyze:
- Container logs
- Kubernetes events
- Resource metrics

Output includes:
- Root cause hypothesis
- Severity rating
- Recommended actions
- Rollback recommendation

## Slack Notification

Interactive message includes:
- Pod details (name, namespace, container, restart count)
- LLM analysis summary
- Recent events
- Action buttons:
  - 🔄 **Restart Pod** - Manual restart trigger
  - ⏪ **Rollback** - Manual rollback trigger

## Testing

```bash
# Run unit tests
pytest test_agent.py -v

# Simulate crash event
kubectl run test-crash --image=busybox --restart=Always -- /bin/sh -c "exit 1"

# Check agent response
kubectl get events --field-selector=reason=CrashLoopBackOff
```

## Common Crash Patterns

The agent recognizes and handles:

| Pattern | Typical Cause | Auto-Action |
|---------|--------------|-------------|
| OOMKilled | Memory limit exceeded | Restart, suggest limit increase |
| ImagePullBackOff | Missing/wrong image | Notify only |
| CrashLoopBackOff | App error | Analyze logs, restart/rollback |
| CreateContainerError | Config issue | Notify with config details |
