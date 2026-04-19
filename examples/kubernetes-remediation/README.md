# Kubernetes Remediation Example

Automatic remediation for common Kubernetes issues.

## What This Does

1. Monitors for pod crashes, OOMKilled, and resource issues
2. Analyzes root cause automatically
3. Suggests and executes remediation (with approval)
4. Tracks outcomes for learning

## Supported Scenarios

| Issue | Detection | Remediation |
|-------|-----------|-------------|
| OOMKilled | Container killed for memory | Scale memory limits |
| CrashLoopBackOff | Pod keeps crashing | Rollback or restart |
| ImagePullBackOff | Can't pull image | Alert & show image tag |
| Resource exhaustion | High CPU/memory | Scale replicas |
| Failed deployment | Pods not ready | Rollback deployment |

## Setup

### 1. Configure Prometheus Alerts

```yaml
# alerts.yaml
groups:
  - name: kubernetes
    rules:
      - alert: PodCrashLooping
        expr: rate(kube_pod_container_status_restarts_total[15m]) > 0.5
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Pod {{ $labels.pod }} crash looping"
      
      - alert: PodOOMKilled
        expr: kube_pod_container_status_last_terminated_reason{reason="OOMKilled"} > 0
        for: 1m
        labels:
          severity: warning
        annotations:
          summary: "Pod {{ $labels.pod }} OOM killed"
```

### 2. Deploy Agent

```bash
cp examples/kubernetes-remediation/agent.yaml agents/
opensre start
```

### 3. Configure Safety

Review and adjust safety settings in `agent.yaml`:
- Protected namespaces
- Auto-approve vs require approval
- Rollback thresholds

## Testing

### Simulate OOMKilled Pod

```bash
kubectl apply -f examples/kubernetes-remediation/test-oom.yaml
```

### Test Dry Run

```bash
opensre agent test kubernetes-remediation \
  --alert '{"alertname": "PodOOMKilled", "labels": {"pod": "test", "namespace": "default"}}' \
  --dry-run
```

## Files

- `agent.yaml` — Agent configuration
- `test-oom.yaml` — Test pod that triggers OOM
- `test-crashloop.yaml` — Test pod that crash loops
