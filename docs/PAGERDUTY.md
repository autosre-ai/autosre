# PagerDuty Integration

OpenSRE integrates with PagerDuty to:
- **Receive incidents** via webhooks and auto-investigate
- **Post investigation results** as incident notes
- **Manage incidents** (acknowledge, add notes, resolve)

## Setup

### 1. Create PagerDuty API Key

1. Go to **PagerDuty** → **Integrations** → **API Access Keys**
2. Click **Create New API Key**
3. Give it a description like "OpenSRE Integration"
4. Copy the generated key

### 2. Get Your Service ID

1. Go to **Services** → Select your service
2. Copy the **Service ID** from the URL: `https://your-org.pagerduty.com/services/PXXXXXX`

### 3. Configure OpenSRE

Add these environment variables:

```bash
# Required
export OPENSRE_PAGERDUTY_API_KEY="your-api-key"

# Optional - filter incidents to specific service
export OPENSRE_PAGERDUTY_SERVICE_ID="PXXXXXX"

# Optional - email for API "From" header
export OPENSRE_PAGERDUTY_FROM_EMAIL="sre@yourcompany.com"
```

Or in your `.env` file:

```ini
OPENSRE_PAGERDUTY_API_KEY=your-api-key
OPENSRE_PAGERDUTY_SERVICE_ID=PXXXXXX
OPENSRE_PAGERDUTY_FROM_EMAIL=sre@yourcompany.com
```

### 4. Set Up Webhook (for auto-investigation)

To have OpenSRE automatically investigate new incidents:

1. Go to **PagerDuty** → **Services** → Your Service → **Integrations**
2. Click **Add Integration**
3. Search for **Generic Webhook (v3)**
4. Configure:
   - **URL:** `https://your-opensre-domain.com/api/webhook/pagerduty`
   - **Events:** Select `incident.triggered`
   - Optionally add `incident.acknowledged` and `incident.resolved` for logging

### 5. Verify Connection

```bash
opensre status
```

You should see:

```
✓ PagerDuty: connected (user@yourcompany.com)
```

Or via API:

```bash
curl http://localhost:8080/api/pagerduty/health
```

## How It Works

### Automatic Investigation

When PagerDuty sends an `incident.triggered` webhook:

1. OpenSRE starts an investigation using the incident title
2. Collects metrics, logs, and Kubernetes events
3. Uses AI to analyze root cause
4. Posts investigation results as a **note** on the incident
5. Optionally posts to Slack if configured

### Investigation Notes

Investigation results are posted as structured notes:

```
🔍 **OpenSRE Investigation**

**Root Cause:** Pod memory exhaustion caused OOM kills
**Confidence:** 85%

**Key Observations:**
• [prometheus] Memory usage 98% for 15 minutes
• [kubernetes] 3 OOMKilled events in last hour
• [logs] "Out of memory" errors in app logs

**Recommended Actions:**
• Increase memory limit to 2Gi (Risk: low)
• Enable HPA for memory-based scaling (Risk: low)

Investigation ID: abc123
```

## API Endpoints

### Check Health

```bash
GET /api/pagerduty/health
```

Response:
```json
{
  "status": "connected",
  "configured": true,
  "user": "sre@yourcompany.com",
  "service_id": "PXXXXXX"
}
```

### List Incidents

```bash
GET /api/pagerduty/incidents?status=triggered&urgency=high&limit=10
```

Response:
```json
{
  "incidents": [
    {
      "id": "PXXXXXX",
      "title": "High CPU on production",
      "status": "triggered",
      "urgency": "high",
      "service_name": "Production API",
      "created_at": "2024-02-26T10:30:00Z",
      "html_url": "https://your-org.pagerduty.com/incidents/PXXXXXX"
    }
  ]
}
```

### Manually Investigate an Incident

```bash
POST /api/pagerduty/incidents/{incident_id}/investigate
```

This will:
1. Acknowledge the incident
2. Run a full investigation
3. Post results as a note

### Webhook Endpoint

```bash
POST /api/webhook/pagerduty
```

Receives PagerDuty v3 webhook payloads. Configure in PagerDuty service integrations.

## Advanced Usage

### Programmatic Access

```python
from opensre_core.adapters import PagerDutyAdapter

pd = PagerDutyAdapter()

# Get open incidents
incidents = await pd.get_incidents(
    statuses=["triggered", "acknowledged"],
    urgencies=["high"],
)

# Add a note to an incident
await pd.add_note(
    incident_id="PXXXXXX",
    note="Investigation in progress..."
)

# Resolve an incident
await pd.resolve_incident(
    incident_id="PXXXXXX",
    resolution="Root cause was memory leak, deployed fix v1.2.3"
)
```

### Custom Investigation Integration

```python
from opensre_core.adapters import PagerDutyAdapter

pd = PagerDutyAdapter()

# After an investigation completes
note = pd.format_investigation_note(investigation_result)
await pd.add_note(incident.id, note)
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENSRE_PAGERDUTY_API_KEY` | Yes | - | PagerDuty API key |
| `OPENSRE_PAGERDUTY_SERVICE_ID` | No | - | Filter to specific service |
| `OPENSRE_PAGERDUTY_FROM_EMAIL` | No | `opensre@example.com` | Email for API requests |

## Troubleshooting

### "No PagerDuty API key configured"

Set the `OPENSRE_PAGERDUTY_API_KEY` environment variable.

### "HTTP 401" errors

Your API key is invalid or expired. Create a new one in PagerDuty.

### "HTTP 403" errors

Your API key doesn't have permission for the requested operation. Ensure it has:
- Read access to incidents
- Write access to incident notes (for posting investigations)

### Webhook not receiving events

1. Check the webhook URL is publicly accessible
2. Verify the webhook is configured for `incident.triggered` events
3. Check OpenSRE server logs for incoming requests

### Notes not appearing on incidents

1. Verify `OPENSRE_PAGERDUTY_FROM_EMAIL` is a valid PagerDuty user email
2. Check the user has permission to add notes
3. Look for errors in OpenSRE logs

## Security

- Store API keys in environment variables or secrets management
- Use HTTPS for webhook endpoints
- Consider IP allowlisting if PagerDuty supports it
- The `From` email must be a valid PagerDuty user for certain operations
