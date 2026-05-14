# AutoSRE V2 API Reference

> Complete API documentation for AutoSRE V2

This document covers all REST API endpoints, WebSocket events, authentication, and error handling.

---

## Table of Contents

- [Overview](#overview)
- [Authentication](#authentication)
- [Endpoints](#endpoints)
  - [Health](#health)
  - [Alerts](#alerts)
  - [Investigations](#investigations)
  - [Webhooks](#webhooks)
  - [Chat](#chat)
  - [Runbooks](#runbooks)
- [WebSocket Events](#websocket-events)
- [Error Codes](#error-codes)
- [Rate Limiting](#rate-limiting)

---

## Overview

### Base URL

```
Production: https://autosre.example.com/api/v1
Development: http://localhost:8000/api/v1
```

### Content Type

All requests and responses use JSON:

```
Content-Type: application/json
Accept: application/json
```

### Common Response Format

```json
{
  "data": { ... },
  "meta": {
    "page": 1,
    "page_size": 20,
    "total": 100,
    "total_pages": 5
  },
  "error": null
}
```

---

## Authentication

### JWT Bearer Token

```http
Authorization: Bearer <jwt_token>
```

### API Key (Webhooks)

```http
X-Webhook-Secret: <api_key>
```

### Obtaining Tokens

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "username": "operator@example.com",
  "password": "secure_password"
}
```

**Response:**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

---

## Endpoints

### Health

#### `GET /health`

Check system health status.

**Response:**

```json
{
  "status": "healthy",
  "version": "2.0.0",
  "components": {
    "database": "healthy",
    "redis": "healthy",
    "prometheus": "healthy",
    "loki": "healthy",
    "kubernetes": "healthy"
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

---

### Alerts

#### `GET /alerts`

List all alerts with optional filtering.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | Filter by status: `firing`, `acknowledged`, `resolved` |
| `severity` | string | Filter by severity: `critical`, `high`, `medium`, `low` |
| `source` | string | Filter by source: `alertmanager`, `pagerduty`, `manual` |
| `page` | integer | Page number (default: 1) |
| `page_size` | integer | Items per page (default: 20, max: 100) |

**Example:**

```bash
curl -X GET "http://localhost:8000/api/v1/alerts?status=firing&severity=critical" \
  -H "Authorization: Bearer $TOKEN"
```

**Response:**

```json
{
  "items": [
    {
      "id": "12345678-1234-1234-1234-123456789abc",
      "name": "HighErrorRate",
      "severity": "critical",
      "status": "firing",
      "source": "alertmanager",
      "service": "payment-service",
      "namespace": "production",
      "labels": {
        "team": "payments",
        "env": "prod"
      },
      "annotations": {
        "summary": "Error rate above 5%",
        "description": "Payment service error rate is 7.2%"
      },
      "fingerprint": "abc123def456",
      "starts_at": "2024-01-15T10:00:00Z",
      "created_at": "2024-01-15T10:00:05Z"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20,
  "total_pages": 1
}
```

---

#### `POST /alerts/{alert_id}/investigate`

Trigger an automated investigation for an alert.

**Request Body:**

```json
{
  "options": {
    "max_iterations": 10,
    "timeout_seconds": 300,
    "agents": ["kubernetes", "metrics", "logs"],
    "auto_remediate": false
  }
}
```

**Response:** `202 Accepted`

```json
{
  "investigation_id": "inv_abc123",
  "alert_id": "12345678-1234-1234-1234-123456789abc",
  "status": "pending",
  "message": "Investigation started",
  "websocket_url": "ws://localhost:8000/api/v1/ws?investigation_id=inv_abc123"
}
```

---

### Investigations

#### `POST /investigate`

Start a new investigation directly (without existing alert).

**Request Body:**

```json
{
  "alert": {
    "name": "HighErrorRate",
    "description": "Error rate above 5% for payment-service",
    "severity": "critical",
    "service": "payment-service",
    "namespace": "production",
    "labels": {
      "team": "payments",
      "env": "prod"
    }
  },
  "options": {
    "max_iterations": 10,
    "timeout_seconds": 300
  }
}
```

**Response:** `202 Accepted`

```json
{
  "id": "inv_abc123",
  "status": "pending",
  "alert": {
    "name": "HighErrorRate",
    "severity": "critical"
  },
  "created_at": "2024-01-15T10:30:00Z",
  "websocket_url": "ws://localhost:8000/api/v1/ws?investigation_id=inv_abc123"
}
```

---

#### `GET /investigations/{investigation_id}`

Get detailed investigation results.

**Response:**

```json
{
  "id": "inv_abc123",
  "status": "completed",
  "alert": {
    "name": "HighErrorRate",
    "severity": "critical",
    "service": "payment-service"
  },
  "started_at": "2024-01-15T10:00:10Z",
  "completed_at": "2024-01-15T10:01:05Z",
  "duration_seconds": 55,
  "iterations": 3,
  "llm_calls": 12,
  "total_tokens": 15420,
  
  "triage": {
    "category": "errors",
    "severity_assessment": "critical",
    "urgency_score": 0.9,
    "recommended_agents": ["kubernetes", "metrics", "logs"]
  },
  
  "hypotheses": [
    {
      "id": "hyp_001",
      "statement": "Database connection pool exhaustion",
      "status": "confirmed",
      "confidence": 0.87,
      "reasoning": "Connection timeout errors correlate with pool saturation metrics"
    }
  ],
  
  "findings": [
    {
      "id": "find_001",
      "title": "High Connection Wait Time",
      "description": "Database connection wait time averaging 2.5s (threshold: 100ms)",
      "severity": "critical",
      "agent_id": "metrics",
      "confidence": 0.92
    }
  ],
  
  "root_cause": "Database connection pool exhaustion due to traffic spike",
  "root_cause_confidence": 0.87,
  
  "summary": "Payment-service experienced elevated error rates due to database connection pool saturation.",
  
  "recommendations": [
    {
      "action_type": "config_change",
      "description": "Increase connection pool size from 10 to 25",
      "command": "kubectl set env deployment/payment-service -n production DB_POOL_SIZE=25",
      "risk_level": "low",
      "expected_impact": "Immediate reduction in connection wait times",
      "rollback_steps": ["kubectl set env deployment/payment-service -n production DB_POOL_SIZE=10"]
    }
  ],
  
  "preventive_measures": [
    "Configure HPA based on connection pool utilization",
    "Add alerting for connection pool saturation > 80%"
  ]
}
```

---

#### `GET /investigations/{investigation_id}/timeline`

Get the chronological timeline of investigation events.

**Response:**

```json
{
  "investigation_id": "inv_abc123",
  "entries": [
    {
      "timestamp": "2024-01-15T10:00:10Z",
      "phase": "pending",
      "event": "Investigation started",
      "agent": null,
      "details": {}
    },
    {
      "timestamp": "2024-01-15T10:00:15Z",
      "phase": "triaging",
      "event": "Triage complete: critical severity",
      "agent": "triage",
      "details": {
        "recommended_agents": ["kubernetes", "metrics", "logs"]
      }
    },
    {
      "timestamp": "2024-01-15T10:01:05Z",
      "phase": "completed",
      "event": "Investigation completed",
      "agent": null,
      "details": {
        "duration_seconds": 55
      }
    }
  ]
}
```

---

#### `POST /investigations/{investigation_id}/action`

Execute an action within an investigation context.

**Request Body:**

```json
{
  "action": "approve",
  "action_id": "rec_001",
  "comment": "Approved by on-call engineer"
}
```

**Actions:**

| Action | Description |
|--------|-------------|
| `approve` | Approve a proposed remediation action |
| `reject` | Reject a proposed remediation action |
| `escalate` | Escalate to human operator |
| `add_note` | Add a note to the investigation |
| `run_command` | Execute a diagnostic command |

**Response:**

```json
{
  "success": true,
  "action": "approve",
  "action_id": "rec_001",
  "executed_at": "2024-01-15T10:05:00Z",
  "executed_by": "operator@example.com"
}
```

---

### Webhooks

#### `POST /webhooks/alertmanager`

Receive alerts from Prometheus Alertmanager.

**Headers:**

```http
X-Alertmanager-Signature: sha256=<hmac_signature>
```

**Request Body (Alertmanager format):**

```json
{
  "version": "4",
  "groupKey": "{}:{alertname=\"HighErrorRate\"}",
  "status": "firing",
  "receiver": "autosre",
  "alerts": [
    {
      "status": "firing",
      "labels": {
        "alertname": "HighErrorRate",
        "severity": "critical",
        "service": "payment-service"
      },
      "annotations": {
        "summary": "Error rate above 5%"
      },
      "startsAt": "2024-01-15T10:00:00Z",
      "fingerprint": "abc123def456"
    }
  ]
}
```

**Response:**

```json
{
  "status": "ok",
  "received": 1,
  "created": 1
}
```

---

#### `POST /webhooks/pagerduty`

Receive events from PagerDuty webhooks (v3).

**Headers:**

```http
X-PagerDuty-Signature: v1=<hmac_signature>
```

**Response:**

```json
{
  "status": "ok",
  "event_type": "incident.triggered",
  "processed": true
}
```

---

#### `POST /webhooks/generic`

Generic webhook endpoint for custom integrations.

**Headers:**

```http
X-Webhook-Secret: <api_key>
```

**Request Body:**

```json
{
  "alertname": "CustomAlert",
  "severity": "high",
  "summary": "Custom alert from monitoring system",
  "description": "Detailed description of the issue",
  "source": "custom-monitor",
  "labels": {
    "service": "api-gateway",
    "team": "platform"
  }
}
```

---

### Chat

#### `POST /chat`

Send a message to the chat interface for investigation assistance.

**Request Body:**

```json
{
  "message": "What's causing the high error rate on payment-service?",
  "investigation_id": "inv_abc123",
  "context": {
    "service": "payment-service",
    "namespace": "production"
  }
}
```

**Response:**

```json
{
  "response": "Based on the current investigation, the high error rate appears to be caused by database connection pool exhaustion...",
  "citations": [
    {
      "finding_id": "find_001",
      "text": "Connection pool utilization at 100%"
    }
  ],
  "suggested_actions": [
    "View detailed metrics",
    "Get remediation recommendations"
  ]
}
```

---

### Runbooks

#### `GET /runbooks`

List available runbooks.

**Response:**

```json
{
  "items": [
    {
      "id": "rb_001",
      "title": "High Error Rate Response",
      "description": "Steps to diagnose and resolve high error rates",
      "service_patterns": ["*-service"],
      "alert_patterns": ["HighErrorRate", "High5xxRate"],
      "tags": ["errors", "availability"],
      "created_at": "2024-01-01T00:00:00Z"
    }
  ],
  "total": 1
}
```

---

#### `POST /runbooks/{runbook_id}/execute`

Execute a runbook in the context of an investigation.

**Request Body:**

```json
{
  "investigation_id": "inv_abc123",
  "parameters": {
    "service": "payment-service",
    "namespace": "production"
  },
  "dry_run": false
}
```

---

## WebSocket Events

### Connection

```javascript
const ws = new WebSocket('ws://localhost:8000/api/v1/ws');

ws.onopen = () => {
  ws.send(JSON.stringify({
    type: 'authenticate',
    token: 'your_jwt_token'
  }));
};

ws.send(JSON.stringify({
  type: 'subscribe',
  investigation_id: 'inv_abc123'
}));
```

### Event Types

| Event | Description |
|-------|-------------|
| `state_changed` | Investigation state transition |
| `triage_started` | Triage phase started |
| `triage_completed` | Triage phase completed |
| `agent_started` | Individual agent started |
| `agent_completed` | Individual agent completed |
| `agent_failed` | Individual agent failed |
| `finding_added` | New finding discovered |
| `completed` | Investigation completed |
| `failed` | Investigation failed |
| `timeout_warning` | Approaching timeout |

### Example Event

```json
{
  "type": "agent_completed",
  "investigation_id": "inv_abc123",
  "source": "kubernetes",
  "timestamp": "2024-01-15T10:00:35Z",
  "data": {
    "agent": "kubernetes",
    "findings_count": 3,
    "duration_seconds": 18
  }
}
```

---

## Error Codes

### HTTP Status Codes

| Code | Meaning |
|------|---------|
| `200` | Success |
| `201` | Created |
| `202` | Accepted (async operation started) |
| `204` | No Content (successful delete) |
| `400` | Bad Request (invalid input) |
| `401` | Unauthorized (invalid/missing auth) |
| `403` | Forbidden (insufficient permissions) |
| `404` | Not Found |
| `409` | Conflict (e.g., investigation already running) |
| `422` | Unprocessable Entity (validation error) |
| `429` | Too Many Requests (rate limited) |
| `500` | Internal Server Error |

### Error Response Format

```json
{
  "error": {
    "code": "INVESTIGATION_NOT_FOUND",
    "message": "Investigation inv_xyz not found",
    "details": {
      "investigation_id": "inv_xyz"
    },
    "request_id": "req_abc123"
  }
}
```

### Error Codes

| Code | Description |
|------|-------------|
| `INVALID_REQUEST` | Request body validation failed |
| `AUTHENTICATION_REQUIRED` | Missing authentication |
| `INVALID_TOKEN` | JWT token is invalid or expired |
| `PERMISSION_DENIED` | User lacks required permissions |
| `ALERT_NOT_FOUND` | Alert ID does not exist |
| `INVESTIGATION_NOT_FOUND` | Investigation ID does not exist |
| `INVESTIGATION_ALREADY_RUNNING` | Cannot start duplicate investigation |
| `WEBHOOK_SIGNATURE_INVALID` | Webhook signature verification failed |
| `RATE_LIMIT_EXCEEDED` | Too many requests |
| `LLM_ERROR` | Error communicating with LLM provider |
| `INTEGRATION_ERROR` | Error with external integration |

---

## Rate Limiting

### Limits

| Endpoint Category | Limit |
|-------------------|-------|
| General API | 100 requests/minute |
| Investigation start | 10 requests/minute |
| Webhooks | 1000 requests/minute |
| WebSocket messages | 60 messages/minute |

### Headers

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1705316400
```

### Rate Limit Response

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 30

{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded. Try again in 30 seconds.",
    "details": {
      "limit": 100,
      "window_seconds": 60,
      "retry_after": 30
    }
  }
}
```

---

## OpenAPI Specification

Full OpenAPI 3.0 spec available at:

```
GET /openapi.json
GET /docs          # Swagger UI
GET /redoc         # ReDoc
```

---

## SDK Examples

### Python

```python
import httpx

client = httpx.AsyncClient(
    base_url="http://localhost:8000/api/v1",
    headers={"Authorization": f"Bearer {token}"}
)

# Start investigation
response = await client.post("/investigate", json={
    "alert": {
        "name": "HighErrorRate",
        "severity": "critical",
        "service": "payment-service"
    }
})
investigation = response.json()
print(f"Started: {investigation['id']}")
```

### cURL

```bash
curl -X POST http://localhost:8000/api/v1/investigate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "alert": {
      "name": "HighErrorRate",
      "severity": "critical",
      "service": "payment-service"
    }
  }'
```
