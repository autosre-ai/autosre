# Infrastructure Debugging

Kubernetes and cloud infrastructure debugging methodology.

## Overview

This skill provides infrastructure debugging methodology for Kubernetes clusters and cloud resources. It combines systematic troubleshooting approaches with cloud-specific knowledge.

## Kubernetes Troubleshooting

### Quick Reference

**Your Role:** Diagnose pod, deployment, and cluster issues
**Start With:** Pod status and events, then logs
**Key Signals:** CrashLoopBackOff, OOMKilled, Pending, ImagePullBackOff

### Troubleshooting Decision Tree

```
Pod not running?
├─ Status: CrashLoopBackOff
│  ├─ Exit code 137 → OOMKilled → check memory limits vs usage
│  ├─ Exit code 1 → App error → check logs for stack trace
│  └─ Exit code 0 → Container completed → should be Job, not Deployment?
├─ Status: Pending
│  ├─ No events → check ResourceQuota, LimitRange
│  ├─ FailedScheduling → check node resources, taints, affinity
│  └─ Unschedulable → check PVC binding, node selectors
├─ Status: ImagePullBackOff
│  ├─ 401/403 → registry auth (imagePullSecrets)
│  └─ Not found → verify image:tag exists
└─ Status: Running but not ready
   ├─ Readiness probe failing → check probe config, app startup time
   └─ Liveness probe failing → check app health, increase timeout
```

### Common Issues by Resource Type

| Resource | Common Issues | What to Check |
|----------|---------------|---------------|
| **Pods** | CrashLoopBackOff, OOMKilled, Pending | Logs, events, resource usage |
| **Deployments** | Rollout stuck, replicas not scaling | Rollout status, HPA |
| **StatefulSets** | Pod ordering, PVC problems | Pod ordinal, volumeClaimTemplates |
| **DaemonSets** | Pods not on all nodes | Node taints, tolerations |
| **Jobs/CronJobs** | Not completing, backoff limit | Job logs, completion count |
| **Services** | No endpoints, DNS not resolving | Selector match, endpoint slices |
| **Ingress** | 502/503 errors, cert issues | Backend service, TLS secret |

### Node-Level Issues

| Condition | Impact | Resolution |
|-----------|--------|------------|
| NotReady | Pods evicted | Check kubelet, network, disk |
| MemoryPressure | Pod eviction | Check node memory, eviction thresholds |
| DiskPressure | Image pulls fail | Clean up images, expand disk |
| PIDPressure | New pods fail | Check for fork bombs, increase limits |
| NetworkUnavailable | Pods can't communicate | Check CNI plugin |

### Network Troubleshooting

Connectivity issues? Check in order:
1. **Service selector** - Does it match pod labels?
2. **Endpoints** - Are pods registered?
3. **NetworkPolicy** - Is traffic being blocked?
4. **DNS** - Can pods resolve service names?
5. **Port mapping** - Service port → targetPort → containerPort correct?

### kubectl Commands Reference

```bash
# Pod status
kubectl get pods -n <namespace> -o wide
kubectl describe pod <pod> -n <namespace>
kubectl logs <pod> -n <namespace> --previous  # Previous container
kubectl logs <pod> -c <container> -n <namespace>  # Multi-container

# Events
kubectl get events -n <namespace> --sort-by='.lastTimestamp'
kubectl get events --field-selector involvedObject.name=<pod>

# Resource usage
kubectl top pods -n <namespace>
kubectl top nodes

# Deployment status
kubectl rollout status deployment/<name> -n <namespace>
kubectl rollout history deployment/<name> -n <namespace>

# Service debugging
kubectl get endpoints <service> -n <namespace>
kubectl run debug --rm -it --image=busybox -- wget -qO- <service>:<port>

# Node debugging
kubectl describe node <node>
kubectl get node <node> -o yaml | grep -A5 conditions
```

## AWS Troubleshooting

### EKS-Specific Issues

| Issue | Likely Cause | Check |
|-------|--------------|-------|
| Nodes not joining | IAM/security groups | Node IAM role, cluster SG rules |
| Pod networking issues | VPC CNI | aws-node daemonset, IP exhaustion |
| LoadBalancer stuck | ALB controller | Controller logs, subnet tags |
| PVC stuck pending | EBS CSI | CSI driver pods, IAM permissions |

### CloudWatch Insights Queries

```
# Container errors in EKS
fields @timestamp, @message
| filter kubernetes.container_name = "app"
| filter @message like /error|exception|failed/i
| sort @timestamp desc
| limit 100

# OOMKill detection
fields @timestamp, @message
| filter @message like /OOMKilled|oom-kill/
| sort @timestamp desc
```

## GCP Troubleshooting

### GKE-Specific Issues

| Issue | Likely Cause | Check |
|-------|--------------|-------|
| Workload identity issues | GSA binding | IAM bindings, annotations |
| Network policy issues | Dataplane V2 | NetworkPolicy resources |
| Autopilot scheduling | Resource requests | Pod resource specs |

## Investigation Steps

1. **Pod status and events** - What's the current state?
2. **Logs** - Error patterns, stack traces (check previous container if restarting)
3. **Resources** - CPU/memory usage vs requests/limits
4. **Deployment** - Rollout status, revision history, HPA status
5. **Services** - Endpoints, DNS, NetworkPolicies
6. **Node health** - If pods Pending/evicted, check node conditions

## Write Operations Require Approval

For remediation actions (restart pod, scale deployment, rollback):
1. **Propose the action** with specific command and expected impact
2. **Run dry-run first** and report output
3. **Do NOT execute directly** - requires human approval

## Output Template

```markdown
## Infrastructure Analysis Summary

### Current State
- Resource: [name] in namespace [ns]
- Status: [status]
- Age: [age]
- Restarts: [count]

### Events
| Time | Type | Reason | Message |
|------|------|--------|---------|
| ... | Warning | OOMKilled | Container exceeded memory limit |

### Resource Usage
| Metric | Current | Request | Limit |
|--------|---------|---------|-------|
| CPU | 450m | 200m | 500m |
| Memory | 1.8Gi | 1Gi | 2Gi |

### Root Cause
[Specific finding with evidence]

### Recommendations
1. [Immediate action]
2. [Preventive measure]

### What Was Checked
- [Resource]: [Finding]
```

## Configuration

```yaml
kubernetes:
  kubeconfig: ~/.kube/config
  context: production  # Optional
  
aws:
  region: us-west-2
  profile: default  # Optional
  
gcp:
  project: my-project
```

## Dependencies

- `kubernetes` Python client
- Cloud provider CLI/SDK (optional)
