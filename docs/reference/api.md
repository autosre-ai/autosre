# API Reference

AutoSRE exposes a REST API for integration with external systems.

## Base URL

```
http://localhost:8000/api/v1
```

## Endpoints

### Health Check

```http
GET /health
```

Returns the health status of the AutoSRE service.

### Investigation

```http
POST /investigate
```

Start a new investigation.

**Request Body:**

```json
{
  "alert": {
    "title": "High error rate on checkout-service",
    "severity": "critical",
    "labels": {
      "service": "checkout-service",
      "namespace": "production"
    }
  }
}
```

### Get Investigation Status

```http
GET /investigations/{id}
```

Get the status and results of an investigation.

### List Investigations

```http
GET /investigations
```

List all recent investigations.

## Authentication

AutoSRE supports API key authentication. Set the `X-API-Key` header:

```bash
curl -H "X-API-Key: your-api-key" http://localhost:8000/api/v1/health
```

## Rate Limiting

The API is rate-limited to 100 requests per minute per API key.
