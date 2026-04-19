# API Reference

Complete REST API and WebSocket documentation for OpenSRE.

## Base URL

```
http://localhost:8000
```

## Authentication

### API Key

Include your API key in the `Authorization` header:

```bash
curl -H "Authorization: Bearer <your-api-key>" \
  http://localhost:8000/api/v1/status
```

## REST API

### Health & Status

#### GET /health

Health check endpoint.

```bash
curl http://localhost:8000/health
```

**Response:**
```json
{
  "status": "healthy",
  "version": "0.1.0"
}
```

#### GET /api/v1/status

Detailed system status.

```bash
curl http://localhost:8000/api/v1/status
```

**Response:**
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "components": {
    "prometheus": {
      "status": "connected",
      "url": "http://prometheus:9090"
    },
    "kubernetes": {
      "status": "connected",
      "nodes": 3
    },
    "llm": {
      "status": "ready",
      "provider": "ollama",
      "model": "llama3.1:8b"
    },
    "slack": {
      "status": "connected",
      "channel": "#incidents"
    }
  },
  "agents": {
    "active": 3,
    "running_investigations": 0
  }
}
```

### Investigations

#### POST /api/v1/investigate

Trigger a manual investigation.

```bash
curl -X POST http://localhost:8000/api/v1/investigate \
  -H "Content-Type: application/json" \
  -d '{
    "description": "high error rate on checkout service",
    "context": {
      "namespace": "production",
      "service": "checkout"
    }
  }'
```

**Request Body:**
```json
{
  "description": "string, required - What to investigate",
  "context": {
    "namespace": "string, optional - Kubernetes namespace",
    "service": "string, optional - Service name",
    "labels": "object, optional - Additional labels"
  },
  "agent": "string, optional - Specific agent to use",
  "async": "boolean, optional - Return immediately (default: false)"
}
```

**Response (sync):**
```json
{
  "investigation_id": "inv-abc123",
  "status": "completed",
  "started_at": "2024-01-15T10:30:00Z",
  "completed_at": "2024-01-15T10:30:47Z",
  "observations": {
    "metrics": {
      "error_rate": 0.083,
      "latency_p99": 2.5
    },
    "pods": [
      {"name": "checkout-abc", "status": "Running"},
      {"name": "checkout-def", "status": "OOMKilled"}
    ],
    "recent_deployments": [
      {"name": "checkout-v2.4.1", "timestamp": "2024-01-15T10:15:00Z"}
    ]
  },
  "analysis": {
    "root_cause": "Memory leak in checkout-v2.4.1",
    "confidence": 0.94,
    "evidence": [
      "Error rate increased 82x after deployment",
      "3 pods showing OOMKilled",
      "Memory usage trending up before crashes"
    ],
    "recommendation": "Rollback to checkout-v2.4.0"
  },
  "actions": [
    {
      "action": "kubernetes.rollback",
      "status": "pending_approval",
      "params": {
        "deployment": "checkout",
        "namespace": "production"
      }
    }
  ]
}
```

**Response (async):**
```json
{
  "investigation_id": "inv-abc123",
  "status": "running",
  "started_at": "2024-01-15T10:30:00Z"
}
```

#### GET /api/v1/investigations

List investigations.

```bash
curl http://localhost:8000/api/v1/investigations?limit=10
```

**Query Parameters:**
- `limit` - Number of results (default: 20, max: 100)
- `offset` - Pagination offset
- `status` - Filter by status (running, completed, failed)
- `since` - Filter by start time (ISO 8601)
- `agent` - Filter by agent name

**Response:**
```json
{
  "investigations": [
    {
      "investigation_id": "inv-abc123",
      "status": "completed",
      "description": "high error rate on checkout service",
      "started_at": "2024-01-15T10:30:00Z",
      "completed_at": "2024-01-15T10:30:47Z",
      "agent": "incident-responder"
    }
  ],
  "total": 47,
  "limit": 10,
  "offset": 0
}
```

#### GET /api/v1/investigations/{id}

Get investigation details.

```bash
curl http://localhost:8000/api/v1/investigations/inv-abc123
```

**Response:** Same as POST /api/v1/investigate response.

### Actions

#### POST /api/v1/actions/{action_id}/approve

Approve a pending action.

```bash
curl -X POST http://localhost:8000/api/v1/actions/act-xyz789/approve \
  -H "Content-Type: application/json" \
  -d '{"user": "alice", "comment": "Approved based on analysis"}'
```

**Response:**
```json
{
  "action_id": "act-xyz789",
  "status": "executing",
  "approved_by": "alice",
  "approved_at": "2024-01-15T10:35:00Z"
}
```

#### POST /api/v1/actions/{action_id}/reject

Reject a pending action.

```bash
curl -X POST http://localhost:8000/api/v1/actions/act-xyz789/reject \
  -H "Content-Type: application/json" \
  -d '{"user": "alice", "reason": "Want to investigate more first"}'
```

### Agents

#### GET /api/v1/agents

List configured agents.

```bash
curl http://localhost:8000/api/v1/agents
```

**Response:**
```json
{
  "agents": [
    {
      "name": "incident-responder",
      "description": "Responds to PagerDuty incidents",
      "status": "active",
      "skills": ["prometheus", "kubernetes", "slack"],
      "investigations_total": 47,
      "last_run": "2024-01-15T10:30:00Z"
    }
  ]
}
```

#### GET /api/v1/agents/{name}

Get agent details.

#### POST /api/v1/agents/{name}/run

Manually trigger an agent.

```bash
curl -X POST http://localhost:8000/api/v1/agents/incident-responder/run \
  -H "Content-Type: application/json" \
  -d '{
    "trigger": {
      "alertname": "HighErrorRate",
      "labels": {"service": "checkout"}
    }
  }'
```

### Skills

#### GET /api/v1/skills

List installed skills.

```bash
curl http://localhost:8000/api/v1/skills
```

**Response:**
```json
{
  "skills": [
    {
      "name": "prometheus",
      "version": "1.0.0",
      "status": "healthy",
      "actions": ["query", "query_range", "alerts", "silence"]
    },
    {
      "name": "kubernetes",
      "version": "1.0.0",
      "status": "healthy",
      "actions": ["get_pods", "get_deployments", "rollback", "scale"]
    }
  ]
}
```

#### POST /api/v1/skills/{name}/invoke

Invoke a skill action directly.

```bash
curl -X POST http://localhost:8000/api/v1/skills/prometheus/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "action": "query",
    "params": {
      "query": "rate(http_requests_total[5m])"
    }
  }'
```

### Webhooks

#### POST /webhook/alertmanager

Receive Alertmanager webhooks.

```bash
curl -X POST http://localhost:8000/webhook/alertmanager \
  -H "Content-Type: application/json" \
  -d '{
    "receiver": "opensre",
    "status": "firing",
    "alerts": [
      {
        "status": "firing",
        "labels": {
          "alertname": "HighErrorRate",
          "service": "checkout",
          "severity": "critical"
        },
        "annotations": {
          "summary": "High error rate on checkout service"
        },
        "startsAt": "2024-01-15T10:30:00Z"
      }
    ]
  }'
```

#### POST /webhook/pagerduty

Receive PagerDuty webhooks.

#### POST /webhook/{source}

Receive generic webhooks.

### Runbooks

#### GET /api/v1/runbooks

List runbooks.

```bash
curl http://localhost:8000/api/v1/runbooks
```

#### GET /api/v1/runbooks/{name}

Get runbook content.

#### POST /api/v1/runbooks

Upload a new runbook.

```bash
curl -X POST http://localhost:8000/api/v1/runbooks \
  -H "Content-Type: application/json" \
  -d '{
    "name": "memory-leak-remediation",
    "content": "# Memory Leak Remediation\n\n..."
  }'
```

## WebSocket API

### Connection

```javascript
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onopen = () => {
  // Authenticate
  ws.send(JSON.stringify({
    type: 'auth',
    token: 'your-api-key'
  }));
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log(message);
};
```

### Subscribe to Investigation

```javascript
ws.send(JSON.stringify({
  type: 'subscribe',
  channel: 'investigation',
  investigation_id: 'inv-abc123'
}));
```

### Event Types

#### investigation.started

```json
{
  "type": "investigation.started",
  "investigation_id": "inv-abc123",
  "description": "high error rate on checkout service",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

#### investigation.observation

```json
{
  "type": "investigation.observation",
  "investigation_id": "inv-abc123",
  "phase": "observe",
  "observation": {
    "source": "prometheus",
    "data": {...}
  }
}
```

#### investigation.analysis

```json
{
  "type": "investigation.analysis",
  "investigation_id": "inv-abc123",
  "analysis": {
    "root_cause": "Memory leak in checkout-v2.4.1",
    "confidence": 0.94
  }
}
```

#### investigation.action

```json
{
  "type": "investigation.action",
  "investigation_id": "inv-abc123",
  "action": {
    "action_id": "act-xyz789",
    "type": "kubernetes.rollback",
    "status": "pending_approval"
  }
}
```

#### investigation.completed

```json
{
  "type": "investigation.completed",
  "investigation_id": "inv-abc123",
  "status": "completed",
  "duration_ms": 47000
}
```

## MCP Server

OpenSRE can run as an MCP (Model Context Protocol) server for integration with AI assistants.

### Starting MCP Server

```bash
opensre mcp
```

### Claude Desktop Configuration

```json
{
  "mcpServers": {
    "opensre": {
      "command": "opensre",
      "args": ["mcp"]
    }
  }
}
```

### Available Tools

| Tool | Description |
|------|-------------|
| `investigate` | Investigate an incident |
| `query_prometheus` | Query Prometheus metrics |
| `get_pods` | Get Kubernetes pods |
| `get_logs` | Get pod logs |
| `rollback` | Rollback a deployment |
| `scale` | Scale a deployment |
| `silence_alert` | Silence an alert |

### Example Prompts

Once configured, you can ask Claude:

- "Investigate why pods are crashing in production"
- "What's the error rate for the checkout service?"
- "Get logs from the failing pod"
- "Rollback the checkout deployment to the previous version"

## Error Codes

| Code | Description |
|------|-------------|
| 400 | Bad request - Invalid parameters |
| 401 | Unauthorized - Invalid or missing API key |
| 403 | Forbidden - Action not allowed |
| 404 | Not found - Resource doesn't exist |
| 409 | Conflict - Resource state conflict |
| 429 | Too many requests - Rate limit exceeded |
| 500 | Internal server error |
| 503 | Service unavailable - Dependency down |

## Rate Limits

| Endpoint | Limit |
|----------|-------|
| `/api/v1/investigate` | 10/minute |
| `/api/v1/skills/*/invoke` | 60/minute |
| `/webhook/*` | 100/minute |
| Other endpoints | 120/minute |

## Metrics

OpenSRE exposes Prometheus metrics at `/metrics`:

| Metric | Type | Description |
|--------|------|-------------|
| `opensre_investigations_total` | Counter | Total investigations |
| `opensre_investigation_duration_seconds` | Histogram | Investigation duration |
| `opensre_actions_total` | Counter | Total actions taken |
| `opensre_skill_invocations_total` | Counter | Skill invocations |
| `opensre_llm_tokens_total` | Counter | LLM tokens used |
| `opensre_errors_total` | Counter | Error count |

## Next Steps

- **[Architecture](architecture.md)** — System design
- **[Configuration](configuration.md)** — Configuration options
- **[Skills Reference](skills/skill-reference.md)** — Available skills
