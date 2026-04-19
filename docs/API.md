# OpenSRE API Reference

Complete REST API documentation for OpenSRE.

## Base URL

```
http://localhost:8080/api
```

## Authentication

Authentication is optional but recommended for production.

### API Key (Header)

```bash
curl -H "Authorization: Bearer your-api-key" http://localhost:8080/api/status
```

### Slack Request Verification

For Slack webhooks, OpenSRE verifies the `X-Slack-Signature` header using your signing secret.

---

## Endpoints

### Health & Status

#### GET /api/health

Health check endpoint for load balancers.

**Response:**

```json
{
  "status": "healthy",
  "version": "0.1.0"
}
```

#### GET /api/status

Detailed status including all integration health.

**Response:**

```json
{
  "version": "0.1.0",
  "integrations": {
    "prometheus": {
      "status": "connected",
      "version": "2.45.0",
      "url": "http://prometheus:9090"
    },
    "kubernetes": {
      "status": "connected",
      "version": "v1.28.0",
      "namespaces": ["default", "production"]
    },
    "llm": {
      "status": "connected",
      "provider": "ollama",
      "model": "llama3.1:8b"
    },
    "slack": {
      "status": "connected",
      "bot_user": "opensre",
      "channel": "#incidents"
    }
  }
}
```

---

### Investigations

#### POST /api/investigate

Start a new investigation.

**Request:**

```json
{
  "issue": "High memory usage on payment-service",
  "namespace": "production"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `issue` | string | Yes | Description of the issue to investigate |
| `namespace` | string | No | Kubernetes namespace (default: "default") |

**Response:**

```json
{
  "id": "abc12345",
  "status": "started",
  "message": "Investigation started for: High memory usage on payment-service"
}
```

#### GET /api/investigations

List all investigations.

**Response:**

```json
[
  {
    "id": "abc12345",
    "issue": "High memory usage on payment-service",
    "status": "completed",
    "started_at": "2024-01-15T10:30:00Z"
  },
  {
    "id": "def67890",
    "issue": "Checkout service 500 errors",
    "status": "running",
    "started_at": "2024-01-15T10:45:00Z"
  }
]
```

#### GET /api/investigations/{investigation_id}

Get detailed investigation results.

**Response:**

```json
{
  "id": "abc12345",
  "issue": "High memory usage on payment-service",
  "namespace": "production",
  "started_at": "2024-01-15T10:30:00Z",
  "completed_at": "2024-01-15T10:31:15Z",
  "status": "completed",
  "observations": [
    {
      "source": "prometheus",
      "type": "metric",
      "summary": "Memory at 4.2GB (92% of limit)",
      "severity": "warning"
    },
    {
      "source": "kubernetes",
      "type": "event",
      "summary": "Pod restarted 3 times (OOMKilled)",
      "severity": "critical"
    },
    {
      "source": "kubernetes",
      "type": "deployment",
      "summary": "Deploy payment-v2.3.2 at 08:15:00",
      "severity": "info"
    }
  ],
  "root_cause": "Memory leak introduced in v2.3.2 causing OOM restarts",
  "confidence": 0.87,
  "contributing_factors": [
    "Recent deployment changed memory handling",
    "No memory limit increase"
  ],
  "similar_incidents": [
    "Runbook: Memory Issues",
    "INC-1234: Similar OOM in checkout-service"
  ],
  "actions": [
    {
      "id": "act_001",
      "description": "Rollback deployment to v2.3.1",
      "command": "kubectl rollout undo deployment/payment-service -n production",
      "risk": "medium",
      "status": "pending",
      "requires_approval": true
    },
    {
      "id": "act_002",
      "description": "Get previous pod logs",
      "command": "kubectl logs payment-service-xxx -n production --previous",
      "risk": "low",
      "status": "pending",
      "requires_approval": false
    }
  ],
  "iterations": 2,
  "error": null
}
```

---

### Actions

#### POST /api/actions/approve

Approve and execute a recommended action.

**Request:**

```json
{
  "investigation_id": "abc12345",
  "action_id": "act_001"
}
```

**Response:**

```json
{
  "success": true,
  "action_id": "act_001",
  "stdout": "deployment.apps/payment-service rolled back\n",
  "stderr": "",
  "exit_code": 0
}
```

**Error Response:**

```json
{
  "success": false,
  "error": "Permission denied: Cannot modify resources in kube-system",
  "action_id": "act_001"
}
```

#### POST /api/actions/reject

Reject an action with optional reason.

**Request:**

```json
{
  "investigation_id": "abc12345",
  "action_id": "act_001",
  "reason": "Will investigate further before rolling back"
}
```

**Response:**

```json
{
  "status": "rejected"
}
```

---

### Prometheus Queries

#### GET /api/prometheus/query

Execute instant Prometheus query.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | string | PromQL query |
| `time` | string | Evaluation timestamp (optional) |

**Example:**

```bash
curl "http://localhost:8080/api/prometheus/query?query=up"
```

**Response:**

```json
{
  "status": "success",
  "data": [
    {
      "metric": {"job": "prometheus"},
      "value": 1
    },
    {
      "metric": {"job": "node"},
      "value": 1
    }
  ]
}
```

#### GET /api/prometheus/query_range

Execute range query.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | string | PromQL query |
| `start` | string | Start timestamp |
| `end` | string | End timestamp |
| `step` | string | Query step (default: "15s") |

**Response:**

```json
{
  "status": "success",
  "data": [
    {
      "metric": {"instance": "node-1"},
      "values": [
        [1705312200, "0.85"],
        [1705312215, "0.87"],
        [1705312230, "0.82"]
      ]
    }
  ]
}
```

---

### Kubernetes

#### GET /api/kubernetes/pods

List pods in namespace.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `namespace` | string | Kubernetes namespace (default: "default") |

**Response:**

```json
{
  "pods": [
    {
      "name": "payment-service-abc123",
      "namespace": "production",
      "status": "Running",
      "ready": true,
      "restarts": 0,
      "age": "2d"
    },
    {
      "name": "payment-service-def456",
      "namespace": "production",
      "status": "CrashLoopBackOff",
      "ready": false,
      "restarts": 5,
      "age": "1h"
    }
  ]
}
```

#### GET /api/kubernetes/events

List events in namespace.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `namespace` | string | Kubernetes namespace (default: "default") |

**Response:**

```json
{
  "events": [
    {
      "type": "Warning",
      "reason": "OOMKilled",
      "message": "Container exceeded memory limit",
      "count": 3,
      "object": "pod/payment-service-def456"
    },
    {
      "type": "Normal",
      "reason": "Pulling",
      "message": "Pulling image payment:v2.3.2",
      "count": 1,
      "object": "pod/payment-service-abc123"
    }
  ]
}
```

---

### Slack Integration

#### GET /api/slack/health

Check Slack integration status.

**Response:**

```json
{
  "status": "connected",
  "configured": true,
  "bot_user": "opensre",
  "team": "Your Workspace",
  "channel": "#incidents"
}
```

#### POST /api/slack/events

Handle Slack Events API callbacks. Used internally by Slack.

#### POST /api/slack/interactions

Handle Slack interactive component callbacks. Used internally by Slack.

---

### Webhooks

#### POST /api/webhook/alert

Receive alerts from Alertmanager.

**Request (Alertmanager format):**

```json
{
  "version": "4",
  "status": "firing",
  "alerts": [
    {
      "labels": {
        "alertname": "HighMemoryUsage",
        "namespace": "production",
        "service": "payment-service",
        "severity": "critical"
      },
      "annotations": {
        "summary": "Memory usage above 90%",
        "description": "payment-service pod is using 4.2GB of 4.5GB limit"
      },
      "startsAt": "2024-01-15T10:30:00Z"
    }
  ],
  "commonLabels": {
    "alertname": "HighMemoryUsage",
    "namespace": "production"
  },
  "commonAnnotations": {
    "summary": "Memory usage above 90%"
  }
}
```

**Response:**

```json
{
  "status": "ok",
  "investigation_id": "abc12345",
  "alert_name": "HighMemoryUsage"
}
```

---

### Metrics

#### GET /metrics

Prometheus metrics endpoint (at root, not under /api).

**Response:**

```
# HELP opensre_investigations_total Total number of investigations
# TYPE opensre_investigations_total counter
opensre_investigations_total{namespace="production",status="completed"} 42
opensre_investigations_total{namespace="production",status="failed"} 3

# HELP opensre_investigation_duration_seconds Investigation duration in seconds
# TYPE opensre_investigation_duration_seconds histogram
opensre_investigation_duration_seconds_bucket{namespace="production",le="10"} 15
opensre_investigation_duration_seconds_bucket{namespace="production",le="30"} 35

# HELP opensre_actions_suggested_total Actions suggested by risk level
# TYPE opensre_actions_suggested_total counter
opensre_actions_suggested_total{risk="low"} 120
opensre_actions_suggested_total{risk="medium"} 45
opensre_actions_suggested_total{risk="high"} 12

# HELP opensre_websocket_connections Current WebSocket connections
# TYPE opensre_websocket_connections gauge
opensre_websocket_connections 3
```

---

## WebSocket API

### Connect

```javascript
const ws = new WebSocket('ws://localhost:8080/api/ws');
```

### Messages

#### Ping/Pong

Keep connection alive:

```json
// Send
{"type": "ping"}

// Receive
{"type": "pong"}
```

#### Start Investigation

```json
// Send
{
  "type": "investigate",
  "issue": "High latency on checkout",
  "namespace": "production"
}

// Receive
{
  "type": "investigation_started",
  "id": "abc12345"
}
```

#### Real-time Updates

Broadcast messages you'll receive:

```json
// Investigation started
{
  "type": "investigation_started",
  "id": "abc12345",
  "issue": "High latency on checkout"
}

// Action executed
{
  "type": "action_executed",
  "investigation_id": "abc12345",
  "action_id": "act_001",
  "result": {
    "success": true,
    "stdout": "..."
  }
}

// Alert received
{
  "type": "alert_received",
  "alert_name": "HighMemoryUsage",
  "investigation_id": "def67890",
  "status": "running"
}
```

---

## Error Responses

All endpoints return consistent error format:

```json
{
  "detail": "Investigation not found"
}
```

### HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Bad Request - Invalid input |
| 401 | Unauthorized - Invalid/missing auth |
| 404 | Not Found - Resource doesn't exist |
| 500 | Internal Error - Server error |

---

## Rate Limiting

Currently no rate limiting. Planned for future releases.

---

## Examples

### Python

```python
import requests

# Start investigation
response = requests.post(
    "http://localhost:8080/api/investigate",
    json={"issue": "High latency", "namespace": "production"}
)
investigation_id = response.json()["id"]

# Poll for results
import time
while True:
    result = requests.get(
        f"http://localhost:8080/api/investigations/{investigation_id}"
    ).json()
    
    if result["status"] in ["completed", "failed"]:
        break
    time.sleep(2)

# Approve action
if result["actions"]:
    requests.post(
        "http://localhost:8080/api/actions/approve",
        json={
            "investigation_id": investigation_id,
            "action_id": result["actions"][0]["id"]
        }
    )
```

### JavaScript

```javascript
// WebSocket for real-time updates
const ws = new WebSocket('ws://localhost:8080/api/ws');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  if (data.type === 'investigation_started') {
    console.log('Started:', data.id);
  } else if (data.type === 'action_executed') {
    console.log('Executed:', data.result);
  }
};

// Start investigation
ws.send(JSON.stringify({
  type: 'investigate',
  issue: 'High latency',
  namespace: 'production'
}));
```

### cURL

```bash
# Start investigation
curl -X POST http://localhost:8080/api/investigate \
  -H "Content-Type: application/json" \
  -d '{"issue": "Pod crashloop", "namespace": "default"}'

# Get results
curl http://localhost:8080/api/investigations/abc12345

# Approve action
curl -X POST http://localhost:8080/api/actions/approve \
  -H "Content-Type: application/json" \
  -d '{"investigation_id": "abc12345", "action_id": "act_001"}'
```
