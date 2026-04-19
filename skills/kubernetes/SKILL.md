# Kubernetes Skill

Interact with Kubernetes clusters - manage pods, deployments, and troubleshoot issues.

## Configuration

```yaml
kubeconfig: ~/.kube/config    # Path to kubeconfig (optional, uses default)
context: production           # Kubernetes context to use (optional)
namespace: default            # Default namespace (optional)
```

## Actions

### `get_pods(namespace, labels)`
List pods in a namespace.

**Parameters:**
- `namespace` (str, optional): Namespace to query (default: "default", use "all" for all namespaces)
- `labels` (str, optional): Label selector (e.g., "app=nginx,tier=frontend")

**Returns:** List of pods with status, restarts, age, and resource info

### `get_pod_logs(pod, namespace, lines, container)`
Fetch logs from a pod.

**Parameters:**
- `pod` (str, required): Pod name
- `namespace` (str, optional): Namespace (default: "default")
- `lines` (int, optional): Number of lines to tail (default: 100)
- `container` (str, optional): Container name (for multi-container pods)

**Returns:** Log text

### `describe_pod(pod, namespace)`
Get detailed pod information (like `kubectl describe`).

**Parameters:**
- `pod` (str, required): Pod name
- `namespace` (str, optional): Namespace

**Returns:** Pod details including containers, events, conditions

### `get_deployments(namespace)`
List deployments in a namespace.

**Parameters:**
- `namespace` (str, optional): Namespace (default: "default")

**Returns:** List of deployments with replica counts and status

### `scale_deployment(name, replicas, namespace)`
Scale a deployment up or down.

**Parameters:**
- `name` (str, required): Deployment name
- `replicas` (int, required): Desired replica count
- `namespace` (str, optional): Namespace

**Note:** Requires approval

### `rollback_deployment(name, namespace)`
Rollback deployment to previous revision.

**Parameters:**
- `name` (str, required): Deployment name
- `namespace` (str, optional): Namespace

**Note:** Requires approval

### `get_events(namespace, minutes)`
Get recent events.

**Parameters:**
- `namespace` (str, optional): Namespace
- `minutes` (int, optional): Time window in minutes (default: 15)

**Returns:** List of events with type, reason, and message

### `exec_command(pod, command, namespace, container)`
Execute command in a pod.

**Parameters:**
- `pod` (str, required): Pod name
- `command` (list[str], required): Command to execute
- `namespace` (str, optional): Namespace
- `container` (str, optional): Container name

**Note:** Requires approval for write operations

## Error Handling

All actions return `ActionResult` with success/failure status and error details.

## Dependencies

- `kubernetes>=28.0.0`
