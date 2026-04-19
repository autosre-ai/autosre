# Kubernetes Skill

Manage pods, deployments, and troubleshoot Kubernetes clusters.

## Overview

| Property | Value |
|----------|-------|
| **Name** | `kubernetes` |
| **Version** | 1.0.0 |
| **Category** | Infrastructure |
| **Approval** | Write actions require approval |

## Configuration

```yaml
# config/opensre.yaml
kubernetes:
  kubeconfig: ~/.kube/config  # or use in-cluster
  context: production         # optional, uses current if not set
  namespace: default          # default namespace
  timeout: 30
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENSRE_KUBECONFIG` | Path to kubeconfig file |
| `OPENSRE_KUBE_CONTEXT` | Kubernetes context to use |
| `OPENSRE_KUBE_NAMESPACE` | Default namespace |

### In-Cluster Configuration

When running inside Kubernetes, OpenSRE auto-detects in-cluster config. Ensure proper RBAC:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: opensre
  namespace: opensre
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: opensre
rules:
  - apiGroups: [""]
    resources: ["pods", "pods/log", "events", "services", "configmaps"]
    verbs: ["get", "list", "watch"]
  - apiGroups: [""]
    resources: ["pods"]
    verbs: ["delete"]  # For restart functionality
  - apiGroups: ["apps"]
    resources: ["deployments", "replicasets", "statefulsets", "daemonsets"]
    verbs: ["get", "list", "watch", "patch", "update"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: opensre
subjects:
  - kind: ServiceAccount
    name: opensre
    namespace: opensre
roleRef:
  kind: ClusterRole
  name: opensre
  apiGroup: rbac.authorization.k8s.io
```

## Actions

### `get_pods`

List pods in a namespace.

```yaml
action: kubernetes.get_pods
params:
  namespace: production
  labels: app=checkout
```

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `namespace` | string | no | Namespace (default: "default", use "all" for all) |
| `labels` | string | no | Label selector |
| `field_selector` | string | no | Field selector |

**Returns:**

```json
{
  "pods": [
    {
      "name": "checkout-abc123",
      "namespace": "production",
      "status": "Running",
      "ready": "2/2",
      "restarts": 0,
      "age": "3d",
      "node": "worker-1"
    }
  ]
}
```

### `get_pod_logs`

Fetch logs from a pod.

```yaml
action: kubernetes.get_pod_logs
params:
  pod: checkout-abc123
  namespace: production
  lines: 100
  container: main
```

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `pod` | string | yes | Pod name |
| `namespace` | string | no | Namespace |
| `lines` | integer | no | Number of lines (default: 100) |
| `container` | string | no | Container name (for multi-container pods) |
| `previous` | boolean | no | Get logs from previous container |
| `since` | string | no | Duration (e.g., "1h", "30m") |

**Returns:**

```json
{
  "logs": "2024-03-15T14:32:05Z INFO Starting checkout service...\n..."
}
```

### `describe_pod`

Get detailed pod information.

```yaml
action: kubernetes.describe_pod
params:
  pod: checkout-abc123
  namespace: production
```

**Returns:**

```json
{
  "name": "checkout-abc123",
  "namespace": "production",
  "node": "worker-1",
  "status": "Running",
  "ip": "10.0.0.45",
  "containers": [
    {
      "name": "main",
      "image": "checkout:v2.4.1",
      "state": "Running",
      "ready": true,
      "restarts": 0,
      "resources": {
        "requests": {"cpu": "100m", "memory": "256Mi"},
        "limits": {"cpu": "500m", "memory": "512Mi"}
      }
    }
  ],
  "conditions": [
    {"type": "Ready", "status": "True"},
    {"type": "PodScheduled", "status": "True"}
  ],
  "events": [
    {"type": "Normal", "reason": "Pulled", "message": "Container image pulled"}
  ]
}
```

### `get_deployments`

List deployments.

```yaml
action: kubernetes.get_deployments
params:
  namespace: production
  labels: team=payments
```

**Returns:**

```json
{
  "deployments": [
    {
      "name": "checkout",
      "namespace": "production",
      "replicas": "3/3",
      "available": 3,
      "updated": 3,
      "age": "30d",
      "image": "checkout:v2.4.1"
    }
  ]
}
```

### `get_events`

Get recent Kubernetes events.

```yaml
action: kubernetes.get_events
params:
  namespace: production
  minutes: 15
  type: Warning
```

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `namespace` | string | no | Namespace |
| `minutes` | integer | no | Look back duration (default: 15) |
| `type` | string | no | Event type (Normal, Warning) |
| `resource` | string | no | Filter by resource (e.g., "pod/checkout-abc") |

**Returns:**

```json
{
  "events": [
    {
      "type": "Warning",
      "reason": "OOMKilled",
      "object": "pod/checkout-abc123",
      "message": "Container main exceeded memory limit",
      "count": 3,
      "lastTimestamp": "2024-03-15T14:30:00Z"
    }
  ]
}
```

### `scale_deployment`

Scale a deployment. **Requires approval.**

```yaml
action: kubernetes.scale_deployment
params:
  name: checkout
  namespace: production
  replicas: 5
```

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `name` | string | yes | Deployment name |
| `namespace` | string | no | Namespace |
| `replicas` | integer | yes | Desired replica count |

**Requires Approval:** Yes (unless in allowlist)

### `rollback_deployment`

Rollback deployment to previous revision. **Requires approval.**

```yaml
action: kubernetes.rollback_deployment
params:
  name: checkout
  namespace: production
  revision: 2  # optional, defaults to previous
```

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `name` | string | yes | Deployment name |
| `namespace` | string | no | Namespace |
| `revision` | integer | no | Target revision (default: previous) |

**Requires Approval:** Yes (always)

### `restart_deployment`

Trigger a rolling restart. **Requires approval.**

```yaml
action: kubernetes.restart_deployment
params:
  name: checkout
  namespace: production
```

**Requires Approval:** Configurable

### `delete_pod`

Delete a pod (triggers restart). **Requires approval.**

```yaml
action: kubernetes.delete_pod
params:
  pod: checkout-abc123
  namespace: production
  grace_period: 30
```

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `pod` | string | yes | Pod name |
| `namespace` | string | no | Namespace |
| `grace_period` | integer | no | Grace period in seconds |

**Requires Approval:** Yes

### `exec_command`

Execute command in a pod. **Requires approval.**

```yaml
action: kubernetes.exec_command
params:
  pod: checkout-abc123
  namespace: production
  command: ["ls", "-la", "/app"]
  container: main
```

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `pod` | string | yes | Pod name |
| `namespace` | string | no | Namespace |
| `command` | array | yes | Command to execute |
| `container` | string | no | Container name |

**Requires Approval:** Yes (always)

### `get_resource_usage`

Get CPU/memory usage for pods.

```yaml
action: kubernetes.get_resource_usage
params:
  namespace: production
  labels: app=checkout
```

**Returns:**

```json
{
  "pods": [
    {
      "name": "checkout-abc123",
      "containers": [
        {
          "name": "main",
          "cpu": "250m",
          "memory": "384Mi"
        }
      ]
    }
  ]
}
```

## Examples

### Pod Crash Handler Agent

```yaml
name: pod-crash-handler
skills:
  - kubernetes
  - slack
  - llm

triggers:
  - type: webhook
    source: kubernetes
    events:
      - Warning.CrashLoopBackOff
      - Warning.OOMKilled

steps:
  - name: get-pod-info
    action: kubernetes.describe_pod
    params:
      pod: "{{ trigger.object.name }}"
      namespace: "{{ trigger.object.namespace }}"
    output: pod

  - name: get-logs
    action: kubernetes.get_pod_logs
    params:
      pod: "{{ trigger.object.name }}"
      namespace: "{{ trigger.object.namespace }}"
      lines: 200
      previous: true
    output: logs

  - name: get-events
    action: kubernetes.get_events
    params:
      namespace: "{{ trigger.object.namespace }}"
      resource: "pod/{{ trigger.object.name }}"
    output: events

  - name: analyze
    action: llm.analyze
    params:
      context:
        pod: "{{ pod }}"
        logs: "{{ logs }}"
        events: "{{ events }}"
      prompt: |
        Analyze this pod crash and identify:
        1. Root cause
        2. Severity (low/medium/high/critical)
        3. Recommended action
    output: analysis

  - name: notify
    action: slack.post_message
    params:
      channel: "#incidents"
      text: |
        🚨 **Pod Crash Detected**
        
        **Pod:** {{ pod.name }}
        **Namespace:** {{ pod.namespace }}
        **Reason:** {{ events.events[0].reason }}
        
        **Analysis:**
        {{ analysis.result }}
```

### Deployment Validation Agent

```yaml
name: deploy-validator
skills:
  - kubernetes
  - prometheus

steps:
  - name: wait-for-rollout
    action: kubernetes.get_deployments
    params:
      namespace: "{{ namespace }}"
      labels: "app={{ service }}"
    output: deployment
    retry:
      max_attempts: 10
      delay: 10
      until: "{{ deployment.deployments[0].available == deployment.deployments[0].replicas }}"

  - name: check-pods
    action: kubernetes.get_pods
    params:
      namespace: "{{ namespace }}"
      labels: "app={{ service }}"
    output: pods

  - name: check-events
    action: kubernetes.get_events
    params:
      namespace: "{{ namespace }}"
      minutes: 5
      type: Warning
    output: events

  - name: fail-on-warnings
    action: core.fail
    params:
      message: "Deployment has warning events: {{ events.events }}"
    condition: "{{ events.events | length > 0 }}"
```

## Troubleshooting

### Connection Refused

```bash
# Test kubectl access
kubectl cluster-info

# Check kubeconfig
kubectl config view

# Verify context
kubectl config current-context
```

### Permission Denied

```bash
# Check current permissions
kubectl auth can-i list pods --all-namespaces

# Check service account permissions
kubectl auth can-i --as=system:serviceaccount:opensre:opensre list pods
```

### In-Cluster Detection Failing

```bash
# Verify service account token exists
ls /var/run/secrets/kubernetes.io/serviceaccount/

# Check token
cat /var/run/secrets/kubernetes.io/serviceaccount/token
```

## See Also

- [Skills Overview](overview.md)
- [Prometheus Skill](prometheus.md)
- [Agent Catalog](../agents/CATALOG.md)
