# OpenSRE Slack Integration Setup

This guide walks you through setting up the Slack integration for OpenSRE, enabling:
- 🔔 Automated alert notifications with investigation results
- ✅ Interactive buttons to approve/reject remediation actions
- 🔍 On-demand investigations via @mentions
- 🎯 Human-in-the-loop approval workflow

## Prerequisites

- A Slack workspace where you have admin permissions
- OpenSRE server running and accessible (for webhook endpoints)
- (Optional) A public URL or tunnel like ngrok for local development

## Step 1: Create a Slack App

1. Go to [Slack API Apps](https://api.slack.com/apps)
2. Click **Create New App** → **From scratch**
3. Name your app (e.g., "OpenSRE") and select your workspace
4. Click **Create App**

## Step 2: Configure Bot Token Scopes

1. In your app settings, go to **OAuth & Permissions**
2. Scroll to **Scopes** → **Bot Token Scopes**
3. Add these scopes:

| Scope | Purpose |
|-------|---------|
| `chat:write` | Post messages to channels |
| `chat:write.customize` | Customize bot appearance |
| `commands` | (Optional) Slash commands |
| `app_mentions:read` | Respond to @mentions |
| `channels:history` | Read channel messages |
| `channels:read` | List channels |
| `groups:history` | Read private channel messages |
| `groups:read` | List private channels |
| `im:history` | Read DMs |
| `im:read` | Access DM info |
| `im:write` | Send DMs |

## Step 3: Enable Event Subscriptions

1. Go to **Event Subscriptions**
2. Toggle **Enable Events** to ON
3. Set **Request URL** to: `https://your-domain.com/api/slack/events`
   - For local dev: use ngrok (`ngrok http 8080`) and use the ngrok URL
   - Slack will send a verification challenge; OpenSRE handles this automatically

4. Under **Subscribe to bot events**, add:
   - `app_mention` — Respond when users mention the bot
   - `message.channels` — (Optional) Listen to channel messages
   - `message.im` — (Optional) Respond to DMs

5. Click **Save Changes**

## Step 4: Enable Interactivity

1. Go to **Interactivity & Shortcuts**
2. Toggle **Interactivity** to ON
3. Set **Request URL** to: `https://your-domain.com/api/slack/interactions`
4. Click **Save Changes**

This enables the interactive buttons (Approve, Reject, Investigate More).

## Step 5: Install App to Workspace

1. Go to **Install App**
2. Click **Install to Workspace**
3. Review permissions and click **Allow**
4. Copy the **Bot User OAuth Token** (starts with `xoxb-`)

## Step 6: Configure OpenSRE

Set these environment variables:

```bash
# Required
export OPENSRE_SLACK_BOT_TOKEN="xoxb-your-bot-token"
export OPENSRE_SLACK_CHANNEL="#incidents"  # Default channel for alerts

# Optional (recommended for production)
export OPENSRE_SLACK_SIGNING_SECRET="your-signing-secret"  # From Basic Information page
```

Or add to your `.env` file:

```env
OPENSRE_SLACK_BOT_TOKEN=xoxb-your-bot-token
OPENSRE_SLACK_CHANNEL=#incidents
OPENSRE_SLACK_SIGNING_SECRET=your-signing-secret
```

### Finding Your Signing Secret

1. Go to **Basic Information** in your Slack app settings
2. Under **App Credentials**, find **Signing Secret**
3. Click **Show** and copy it

## Step 7: Invite Bot to Channel

1. In Slack, go to the channel where you want alerts (e.g., #incidents)
2. Type `/invite @OpenSRE` (or whatever you named your bot)

## Step 8: Configure Alertmanager (Optional)

To automatically receive alerts from Prometheus Alertmanager:

```yaml
# alertmanager.yml
receivers:
  - name: 'opensre'
    webhook_configs:
      - url: 'http://opensre:8080/api/webhook/alert'
        send_resolved: true

route:
  receiver: 'opensre'
  # Or route specific alerts
  routes:
    - match:
        severity: critical
      receiver: 'opensre'
```

## Testing the Integration

### 1. Health Check

```bash
curl http://localhost:8080/api/slack/health
```

Expected response:
```json
{
  "status": "connected",
  "configured": true,
  "bot_user": "opensre",
  "team": "Your Workspace",
  "channel": "#incidents"
}
```

### 2. Test Investigation via API

```bash
curl -X POST http://localhost:8080/api/investigate \
  -H "Content-Type: application/json" \
  -d '{"issue": "High memory usage on payment-service", "namespace": "production"}'
```

This will post results to Slack if configured.

### 3. Test via @Mention

In Slack, type:
```
@OpenSRE investigate high latency on checkout-service
```

The bot will start an investigation and post results.

### 4. Simulate Alertmanager Webhook

```bash
curl -X POST http://localhost:8080/api/webhook/alert \
  -H "Content-Type: application/json" \
  -d '{
    "status": "firing",
    "alerts": [{
      "labels": {
        "alertname": "HighMemoryUsage",
        "namespace": "production",
        "service": "payment-api"
      },
      "annotations": {
        "summary": "Memory usage above 90%",
        "description": "payment-api pod is using 4.2GB of memory"
      }
    }],
    "commonLabels": {
      "alertname": "HighMemoryUsage",
      "namespace": "production"
    },
    "commonAnnotations": {
      "summary": "Memory usage above 90%",
      "description": "payment-api pod is using 4.2GB of memory"
    }
  }'
```

## Slack Message Format

OpenSRE posts investigation results in a rich format:

```
┌─────────────────────────────────────────────────────────┐
│ 🔍 OpenSRE Analysis                                     │
├─────────────────────────────────────────────────────────┤
│ Alert: HighMemoryUsage                                  │
│ Time: 2024-01-15 14:30:00                              │
├─────────────────────────────────────────────────────────┤
│ 📊 What I found:                                        │
│ • Memory at 4.2GB (92% of limit)                       │
│ • Pod restarted 3 times in last hour                   │
│ • Recent deployment: v2.3.1 → v2.3.2                   │
├─────────────────────────────────────────────────────────┤
│ 🎯 Root Cause (confidence: 85%)                        │
│ ████████░░                                             │
│ Memory leak in v2.3.2 causing gradual OOM              │
├─────────────────────────────────────────────────────────┤
│ ✅ Recommended Action:                                  │
│ 🟡 kubectl rollout undo deployment/payment-api         │
│                                                         │
│ [✅ Approve] [🔍 Investigate More] [❌ Dismiss]        │
└─────────────────────────────────────────────────────────┘
```

## Interactive Actions

| Button | Action |
|--------|--------|
| ✅ Approve | Executes the recommended kubectl command |
| 🔍 Investigate More | Triggers deeper analysis with more data sources |
| ❌ Dismiss | Marks alert as handled, no action needed |

## Security Considerations

1. **Signing Secret**: Always configure `OPENSRE_SLACK_SIGNING_SECRET` in production to verify requests from Slack

2. **Network Security**: 
   - Keep OpenSRE behind a firewall
   - Use HTTPS with valid certificates
   - Restrict Alertmanager webhook to internal network

3. **Action Approval**: 
   - By default, all destructive actions require human approval
   - Review the `OPENSRE_AUTO_APPROVE_LOW_RISK` setting carefully

4. **Audit Trail**: All approved/rejected actions are logged with user attribution

## Troubleshooting

### Bot not responding to mentions

1. Check the bot is invited to the channel
2. Verify Event Subscriptions are enabled
3. Check the Request URL is correct and accessible
4. Look at OpenSRE logs for errors

### Buttons not working

1. Verify Interactivity is enabled
2. Check the Interactivity Request URL
3. Ensure signing secret matches (if configured)

### No messages appearing

1. Check `OPENSRE_SLACK_BOT_TOKEN` is set correctly
2. Verify the token starts with `xoxb-`
3. Check the bot has `chat:write` scope
4. Test with `/api/slack/health` endpoint

### "Invalid signature" errors

1. Double-check `OPENSRE_SLACK_SIGNING_SECRET` value
2. Ensure you're using the Signing Secret (not the Client Secret)
3. Check for time sync issues (requests expire after 5 minutes)

## Local Development with ngrok

For testing webhooks locally:

```bash
# Terminal 1: Start OpenSRE
cd ~/clawd/projects/opensre
source venv/bin/activate
uvicorn opensre_core.api:create_app --factory --reload --port 8080

# Terminal 2: Start ngrok tunnel
ngrok http 8080
```

Use the ngrok URL (e.g., `https://abc123.ngrok.io`) for:
- Event Subscriptions Request URL: `https://abc123.ngrok.io/api/slack/events`
- Interactivity Request URL: `https://abc123.ngrok.io/api/slack/interactions`

Remember to update these URLs when your ngrok session changes.

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/slack/health` | GET | Check Slack integration health |
| `/api/slack/events` | POST | Slack Events API webhook |
| `/api/slack/interactions` | POST | Slack interactivity webhook |
| `/api/webhook/alert` | POST | Alertmanager webhook |

## Next Steps

- Configure [PagerDuty integration](./PAGERDUTY_SETUP.md) for escalation
- Set up [Runbooks](./RUNBOOKS.md) for guided remediation
- Review [Security Best Practices](./SECURITY.md)
