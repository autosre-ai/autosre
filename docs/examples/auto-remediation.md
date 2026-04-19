# Auto-Remediation Example

This example shows how to build an agent that automatically remediates common infrastructure issues.

## Use Case

Automatically handle pod crashes by:
1. Detecting OOMKilled or CrashLoopBackOff pods
2. Analyzing the cause
3. Taking appropriate action (rollback, scale, or alert)

## Agent Configuration

```yaml
# agents/auto-remediation/agent.yaml
name: auto-remediation
description: Automatically remediates common pod issues
version: 1.0.0

skills:
  - prometheus
  - kubernetes
  - slack

triggers:
  - type: prometheus_alert
    match: 'alertname=~"PodCrashLooping|OOMKilled|ContainerRestarting"'

config:
  timeout: 300
  max_concurrent: 5
  
  memory:
    store_incidents: true
    pattern_matching: true

runbook:
  phases:
    - name: gather_info
      description: Gather information about the failing pod
      steps:
        - name: get_pod
          action: kubernetes.get_pods
          params:
            namespace: "{{ alert.labels.namespace }}"
            name: "{{ alert.labels.pod }}"
          store: pod
        
        - name: get_logs
          action: kubernetes.get_logs
          params:
            namespace: "{{ alert.labels.namespace }}"
            pod: "{{ alert.labels.pod }}"
            tail_lines: 100
          store: logs
        
        - name: get_events
          action: kubernetes.get_events
          params:
            namespace: "{{ alert.labels.namespace }}"
            field_selector: "involvedObject.name={{ alert.labels.pod }}"
          store: events
        
        - name: get_deployment
          action: kubernetes.get_deployments
          params:
            namespace: "{{ alert.labels.namespace }}"
            label_selector: "app={{ alert.labels.app }}"
          store: deployment
    
    - name: analyze
      description: Determine cause and action
      steps:
        - name: check_recent_deploy
          action: kubernetes.get_events
          params:
            namespace: "{{ alert.labels.namespace }}"
            field_selector: "reason=Scaled"
            limit: 5
          store: recent_deploys
        
        - name: llm_analysis
          action: llm.analyze
          params:
            system: |
              You are an SRE analyzing a pod crash. Based on the data,
              determine the cause and recommend an action.
            prompt: |
              ## Pod Status
              {{ pod | to_yaml }}
              
              ## Logs
              {{ logs }}
              
              ## Events
              {{ events | to_yaml }}
              
              ## Recent Deployments
              {{ recent_deploys | to_yaml }}
              
              Determine:
              1. Root cause (OOM, config error, dependency, etc.)
              2. Is this related to a recent deployment?
              3. Recommended action (rollback, scale, restart, or page)
          store: analysis
    
    - name: remediate
      description: Take action based on analysis
      steps:
        - name: rollback
          condition: "{{ analysis.action == 'rollback' and analysis.confidence > 0.8 }}"
          action: kubernetes.rollback
          params:
            deployment: "{{ deployment.name }}"
            namespace: "{{ alert.labels.namespace }}"
          approval_required: true
          store: rollback_result
        
        - name: scale_up
          condition: "{{ analysis.action == 'scale' }}"
          action: kubernetes.scale
          params:
            deployment: "{{ deployment.name }}"
            namespace: "{{ alert.labels.namespace }}"
            replicas: "{{ deployment.replicas + 2 }}"
          approval_required: true
          store: scale_result
        
        - name: restart
          condition: "{{ analysis.action == 'restart' }}"
          action: kubernetes.restart
          params:
            deployment: "{{ deployment.name }}"
            namespace: "{{ alert.labels.namespace }}"
          approval_required: true
          store: restart_result
    
    - name: notify
      description: Inform the team
      always_run: true
      steps:
        - name: slack_notification
          action: slack.post_blocks
          params:
            channel: "#incidents"
            blocks:
              - type: header
                text:
                  type: plain_text
                  text: "🤖 Auto-Remediation Report"
              - type: section
                fields:
                  - type: mrkdwn
                    text: "*Pod:* {{ alert.labels.pod }}"
                  - type: mrkdwn
                    text: "*Namespace:* {{ alert.labels.namespace }}"
              - type: section
                text:
                  type: mrkdwn
                  text: |
                    *Root Cause:* {{ analysis.root_cause }}
                    *Confidence:* {{ (analysis.confidence * 100) | round }}%
              - type: section
                text:
                  type: mrkdwn
                  text: "*Action Taken:* {{ analysis.action | title }}"
              - type: context
                elements:
                  - type: mrkdwn
                    text: "Investigation ID: {{ investigation_id }}"

safety:
  auto_approve:
    - kubernetes.get_*
    - kubernetes.describe
  require_approval:
    - kubernetes.rollback
    - kubernetes.scale
    - kubernetes.restart
    - kubernetes.delete_*
  protected_namespaces:
    - kube-system
    - monitoring
```

## Testing

### Simulate OOMKilled Pod

```yaml
# test-oom-pod.yaml
apiVersion: v1
kind: Pod
metadata:
  name: oom-test
  namespace: default
  labels:
    app: oom-test
spec:
  containers:
    - name: stress
      image: polinux/stress
      resources:
        limits:
          memory: "128Mi"
      command: ["stress"]
      args: ["--vm", "1", "--vm-bytes", "256M"]
```

Deploy and watch OpenSRE respond:

```bash
kubectl apply -f test-oom-pod.yaml
kubectl get pods -w
```

### Trigger Test Alert

```bash
opensre agent test auto-remediation \
  --alert '{
    "alertname": "OOMKilled",
    "labels": {
      "namespace": "default",
      "pod": "checkout-abc123",
      "app": "checkout"
    }
  }' \
  --dry-run
```

## Decision Tree

```
┌─────────────────────┐
│   Pod Crash Alert   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Gather Info        │
│  • Pod status       │
│  • Logs             │
│  • Events           │
│  • Deployment       │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Analyze            │
│  • Recent deploy?   │
│  • OOM?             │
│  • Config error?    │
└──────────┬──────────┘
           │
     ┌─────┴─────┐
     │           │
     ▼           ▼
┌─────────┐ ┌─────────┐
│ Recent  │ │ Not     │
│ Deploy  │ │ Deploy  │
└────┬────┘ └────┬────┘
     │           │
     ▼           ▼
┌─────────┐ ┌─────────┐
│Rollback │ │  OOM?   │
└─────────┘ └────┬────┘
                 │
           ┌─────┴─────┐
           │           │
           ▼           ▼
     ┌─────────┐ ┌─────────┐
     │  Scale  │ │ Restart │
     │   Up    │ │ /Page   │
     └─────────┘ └─────────┘
```

## Best Practices

1. **Start with dry-run** — Test your agent before enabling auto-remediation
2. **Set confidence thresholds** — Only auto-remediate with high confidence
3. **Require approval initially** — Gain confidence before auto-approving
4. **Protect critical namespaces** — Never auto-remediate kube-system
5. **Set rate limits** — Prevent remediation loops

## Next Steps

- [Incident Response Example](incident-response.md)
- [Cost Monitoring Example](cost-monitoring.md)
