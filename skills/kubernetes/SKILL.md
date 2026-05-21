# Kubernetes Skill

Debug and manage Kubernetes clusters - pods, deployments, and troubleshoot issues.

## Quick Reference

**Your Role:** Diagnose pod, deployment, and cluster issues
**Start With:** Pod status and events, then logs
**Key Signals:** CrashLoopBackOff, OOMKilled, Pending, ImagePullBackOff

## Troubleshooting Decision Tree

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

## Configuration

```yaml
kubeconfig: ~/.kube/config    # Path to kubeconfig (optional, uses default)
context: production           # Kubernetes context to use (optional)
namespace: default            # Default namespace (optional)
```

## Actions

### `get_pods(namespace, labels)`
List pods in a namespace with status, restarts, and age.

**Parameters:**
- `namespace` (str, optional): Namespace to query (default: "default", use "all" for all namespaces)
- `labels` (str, optional): Label selector (e.g., "app=nginx,tier=frontend")

**Returns:** List of pods with status, restarts, age, and resource info

### `get_pod_logs(pod, namespace, lines, container)`
Fetch logs from a pod. Check `--previous` for crashed containers.

**Parameters:**
- `pod` (str, required): Pod name
- `namespace` (str, optional): Namespace (default: "default")
- `lines` (int, optional): Number of lines to tail (default: 100)
- `container` (str, optional): Container name (for multi-container pods)
- `previous` (bool, optional): Get logs from previous container instance

**Returns:** Log text

### `describe_pod(pod, namespace)`
Get detailed pod information including events (like `kubectl describe`).

**Parameters:**
- `pod` (str, required): Pod name
- `namespace` (str, optional): Namespace

**Returns:** Pod details including containers, conditions, events

### `get_events(namespace, minutes)`
Get recent cluster events - key for diagnosing scheduling and startup issues.

**Parameters:**
- `namespace` (str, optional): Namespace
- `minutes` (int, optional): Time window in minutes (default: 15)

**Returns:** List of events with type, reason, and message

### `get_deployments(namespace)`
List deployments with replica counts and rollout status.

**Parameters:**
- `namespace` (str, optional): Namespace (default: "default")

**Returns:** List of deployments with replica counts and status

### `get_rollout_status(deployment, namespace)`
Get deployment rollout status and revision history.

**Parameters:**
- `deployment` (str, required): Deployment name
- `namespace` (str, optional): Namespace

**Returns:** Rollout status with revision history

### `scale_deployment(name, replicas, namespace)`
Scale a deployment up or down. **Requires approval.**

**Parameters:**
- `name` (str, required): Deployment name
- `replicas` (int, required): Desired replica count
- `namespace` (str, optional): Namespace

### `rollback_deployment(name, namespace)`
Rollback deployment to previous revision. **Requires approval.**

**Parameters:**
- `name` (str, required): Deployment name
- `namespace` (str, optional): Namespace

### `exec_command(pod, command, namespace, container)`
Execute command in a pod. **Requires approval for write operations.**

**Parameters:**
- `pod` (str, required): Pod name
- `command` (list[str], required): Command to execute
- `namespace` (str, optional): Namespace
- `container` (str, optional): Container name

## Common Issues by Resource Type

| Resource | Common Issues | What to Check |
|----------|---------------|---------------|
| **Pods** | CrashLoopBackOff, OOMKilled, Pending | Logs, events, resource usage |
| **Deployments** | Rollout stuck, replicas not scaling | Rollout status, revision history, HPA |
| **StatefulSets** | Pod ordering issues, PVC problems | Pod ordinal, volumeClaimTemplates |
| **DaemonSets** | Pods not on all nodes | Node taints, tolerations, selectors |
| **Jobs/CronJobs** | Not completing, backoff limit | Job logs, completion count, schedule |
| **Services** | No endpoints, DNS not resolving | Selector match, endpoint slices |
| **Ingress** | 502/503 errors, cert issues | Backend service, TLS secret |

## Node-Level Issues

| Condition | Impact | Resolution |
|-----------|--------|------------|
| NotReady | Pods evicted | Check kubelet, network, disk |
| MemoryPressure | Pod eviction | Check node memory, eviction thresholds |
| DiskPressure | Image pulls fail | Clean up images, expand disk |
| PIDPressure | New pods fail | Check for fork bombs, increase limits |
| NetworkUnavailable | Pods can't communicate | Check CNI plugin, node network |

## Network Troubleshooting

Connectivity issues? Check in order:
1. **Service selector** - Does it match pod labels?
2. **Endpoints** - Are pods registered? (`kubectl get endpoints`)
3. **NetworkPolicy** - Is traffic being blocked?
4. **DNS** - Can pods resolve service names?
5. **Port mapping** - Service port → targetPort → containerPort correct?

## Investigation Steps

1. **Pod status and events** - What's the current state?
2. **Logs** - Error patterns, stack traces (check previous container if restarting)
3. **Resources** - CPU/memory usage vs requests/limits
4. **Deployment** - Rollout status, revision history, HPA status
5. **Services** - Endpoints, DNS, NetworkPolicies
6. **Node health** - If pods Pending/evicted, check node conditions

## Error Handling

All actions return `ActionResult` with success/failure status and error details.

## Dependencies

- `kubernetes>=28.0.0`
