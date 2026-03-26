# Chaos Agent

Controlled chaos engineering experiments with automated rollback and impact analysis.

## Overview

The Chaos Agent enables safe chaos engineering by running controlled experiments with approval workflows, safety constraints, automatic rollback, and AI-powered impact analysis.

## Features

- **Controlled Experiments** - Pod kill, network chaos, CPU/memory stress
- **Safety Constraints** - Min healthy pods, max affected percentage
- **Approval Workflow** - Require human approval before experiments
- **Automatic Rollback** - Abort on alerts or SLO breach
- **Baseline Collection** - Compare metrics before/during/after
- **AI Analysis** - Intelligent resilience assessment
- **Environment Blocking** - Never run in production automatically

## Configuration

```yaml
config:
  slack_channel: "#chaos-engineering"
  approval_channel: "#chaos-approvals"
  enabled: true
  require_approval: true
  approval_timeout_minutes: 30
  environments:
    allowed: ["staging", "chaos-testing"]
    blocked: ["production"]
  experiments:
    - name: pod-kill
      description: "Random pod termination"
      type: pod-delete
      enabled: true
      target:
        namespace: staging
        label_selector: "chaos-enabled=true"
        count: 1
      duration_seconds: 60
    - name: network-latency
      description: "Inject 200ms network latency"
      type: network-chaos
      enabled: true
      target:
        namespace: staging
        label_selector: "chaos-enabled=true"
      params:
        latency: "200ms"
        jitter: "50ms"
      duration_seconds: 300
  safety:
    max_affected_pods_percent: 30
    min_healthy_pods: 2
    abort_on_alert: true
    alert_names_to_watch:
      - HighErrorRate
      - PodCrashLooping
    rollback_on_slo_breach: true
    slo_threshold_percent: 95
```

## Experiment Types

### Pod Delete
Kill random pods to test recovery:
```yaml
- name: pod-kill
  type: pod-delete
  target:
    namespace: staging
    label_selector: "app=api-server"
    count: 1
  duration_seconds: 60
```

### Network Chaos
Inject latency or packet loss:
```yaml
- name: network-latency
  type: network-chaos
  params:
    latency: "200ms"
    jitter: "50ms"
  duration_seconds: 300
```

### CPU Stress
Consume CPU resources:
```yaml
- name: cpu-stress
  type: stress-chaos
  params:
    cpu_cores: 2
    cpu_load: 80
  duration_seconds: 180
```

### Memory Pressure
Consume memory:
```yaml
- name: memory-hog
  type: stress-chaos
  params:
    memory_bytes: "512Mi"
  duration_seconds: 120
```

## Safety Constraints

| Constraint | Description |
|------------|-------------|
| `max_affected_pods_percent` | Max % of pods affected |
| `min_healthy_pods` | Min pods that must be healthy |
| `abort_on_alert` | Stop if alerts fire |
| `rollback_on_slo_breach` | Rollback if SLO breached |
| `blocked environments` | Environments where chaos is disabled |

## Approval Workflow

When `require_approval: true`:

1. Agent posts approval request to Slack
2. Engineer reviews experiment details
3. Approve or Reject
4. Experiment runs (or aborts)

```
🧪 Chaos Experiment Approval Request

Experiment: pod-kill
Type: pod-delete
Target: staging
Duration: 60s

Description: Random pod termination

Target Pods: 5 pods match selector

Safety Checks: All passed ✅

[✅ Approve] [❌ Reject]
```

## Triggers

- **Schedule**: Tuesdays and Thursdays at 3 AM UTC
- **Manual**: `/webhook/chaos-run`

## Experiment Lifecycle

1. **Validation** - Check environment, select experiment
2. **Safety Check** - Verify constraints pass
3. **Approval** - Wait for human approval (if enabled)
4. **Baseline** - Collect pre-experiment metrics
5. **Execution** - Run experiment with monitoring
6. **Analysis** - Compare metrics, assess impact
7. **Report** - Generate findings and recommendations

## Alert Examples

### Experiment Starting
```
🧪 Chaos Experiment Starting

Experiment: pod-kill
ID: abc-123
Duration: 60s
Approved by: john@example.com

Baseline Metrics:
• Error Rate: 0.05%
• Latency P99: 45ms
• Availability: 99.99%

[🛑 Abort Experiment]
```

### Experiment Complete
```
✅ Chaos Experiment Complete

Experiment: pod-kill
Status: completed
Duration: 60s
SLO Breach: No ✅

Impact Summary:
• Error Rate: 0.05% → 0.15% (+0.10%)
• Latency P99: 45ms → 120ms
• Recovery Time: 25s

AI Analysis:
Resilience Assessment: Strong
The system recovered quickly from pod termination.
Recovery time of 25s is within acceptable limits.
```

## Metrics

| Metric | Description |
|--------|-------------|
| `opensre_chaos_experiment_total` | Experiment count by status |
| `opensre_chaos_error_rate_delta` | Error rate increase |
| `opensre_chaos_recovery_time_seconds` | Time to recover |
| `opensre_chaos_slo_breach` | SLO breach indicator |

## Prerequisites

- Litmus Chaos or similar chaos engineering tool
- Kubernetes cluster access
- Prometheus for metrics
- Slack for approvals

## Usage

```bash
# Run scheduled experiment (with approval)
opensre agent run agents/chaos-agent/agent.yaml

# Run specific experiment
opensre agent run agents/chaos-agent/agent.yaml \
  -c "trigger.experiment=network-latency"

# Dry run (shows what would happen)
opensre agent run agents/chaos-agent/agent.yaml --dry-run
```

## Best Practices

1. **Start small** - Begin with short, low-impact experiments
2. **Use labels** - Tag pods with `chaos-enabled=true`
3. **Block production** - Never auto-run chaos in production
4. **Review results** - Analyze each experiment's impact
5. **Fix weaknesses** - Address resilience gaps found

## Related Agents

- [deploy-validator](../deploy-validator/) - Validate post-chaos recovery
- [slo-tracker](../slo-tracker/) - Monitor SLO during experiments
- [incident-responder](../incident-responder/) - Handle chaos-induced issues
