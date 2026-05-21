# Slack Integration

Set up the Slack integration for real-time notifications, interactive approvals, and on-demand investigations.

## Features

- 🔔 **Automated notifications** with investigation results
- ✅ **Interactive buttons** to approve/reject remediation actions
- 🔍 **On-demand investigations** via @mentions
- 📊 **Rich formatting** with investigation details

## Prerequisites

- Slack workspace with admin permissions
- AutoSRE server running and accessible
- (Optional) Public URL or ngrok for local development

---

## Step 1: Create a Slack App

1. Go to [Slack API Apps](https://api.slack.com/apps)
2. Click **Create New App** → **From scratch**
3. Name your app (e.g., "AutoSRE") and select your workspace
4. Click **Create App**

---

## Step 2: Configure Bot Scopes

1. Go to **OAuth & Permissions** in your app settings
2. Under **Bot Token Scopes**, add:

| Scope | Purpose |
|-------|---------|
| `chat:write` | Post messages |
| `chat:write.customize` | Custom bot appearance |
| `app_mentions:read` | Respond to @mentions |
| `channels:history` | Read channel messages |
| `channels:read` | List channels |
| `im:write` | Send DMs |
| `reactions:write` | Add reactions |

---

## Step 3: Enable Event Subscriptions

1. Go to **Event Subscriptions**
2. Toggle **Enable Events** to ON
3. Set **Request URL**:
   ```
   https://your-domain.com/api/v1/slack/events
   ```
   
   !!! tip "Local Development"
       Use ngrok: `ngrok http 8000` and use the ngrok URL

4. Under **Subscribe to bot events**, add:
   - `app_mention`
   - `message.im` (optional, for DMs)

5. Click **Save Changes**

---

## Step 4: Enable Interactivity

1. Go to **Interactivity & Shortcuts**
2. Toggle **Interactivity** to ON
3. Set **Request URL**:
   ```
   https://your-domain.com/api/v1/slack/interactions
   ```
4. Click **Save Changes**

---

## Step 5: Install App to Workspace

1. Go to **Install App**
2. Click **Install to Workspace**
3. Review permissions and click **Allow**
4. Copy the **Bot User OAuth Token** (starts with `xoxb-`)

---

## Step 6: Configure AutoSRE

### Environment Variables

```bash
export SLACK_BOT_TOKEN="xoxb-your-bot-token"
export SLACK_SIGNING_SECRET="your-signing-secret"  # From Basic Information
```

### Configuration File

```yaml
# autosre.yaml
integrations:
  slack:
    enabled: true
    default_channel: "#incidents"
    interactive: true
    thread_updates: true
    
    # Message formatting
    format:
      include_evidence: true
      include_reasoning: true
      max_evidence_items: 5
    
    # Notification settings
    notifications:
      on_investigation_start: true
      on_investigation_complete: true
      on_action_required: true
      on_error: true
```

---

## Step 7: Invite Bot to Channel

In Slack:
```
/invite @AutoSRE
```

---

## Usage

### Automated Notifications

When an investigation completes, AutoSRE posts:

```
┌─────────────────────────────────────────────────────────────┐
│ 🔍 AutoSRE Investigation                                    │
├─────────────────────────────────────────────────────────────┤
│ Alert: HighErrorRate on checkout-service                    │
│ Time: 2025-01-27 10:30:00 UTC                              │
├─────────────────────────────────────────────────────────────┤
│ 🎯 Root Cause (confidence: 92%)                             │
│ Database connection pool exhaustion caused by a new query   │
│ introduced in deployment v2.3.1.                            │
├─────────────────────────────────────────────────────────────┤
│ 📊 Evidence:                                                │
│ • P99 latency: 4.2s (baseline: 120ms)                      │
│ • DB connections: 50/50 (pool exhausted)                   │
│ • Recent deployment: v2.3.0 → v2.3.1 (23 min ago)         │
├─────────────────────────────────────────────────────────────┤
│ ✅ Recommended Action:                                       │
│ kubectl rollout undo deployment/checkout-service           │
│                                                             │
│ [✅ Approve] [🔍 Investigate More] [❌ Dismiss]              │
└─────────────────────────────────────────────────────────────┘
```

### Interactive Buttons

| Button | Action |
|--------|--------|
| ✅ **Approve** | Execute the recommended action |
| 🔍 **Investigate More** | Trigger deeper analysis |
| ❌ **Dismiss** | Mark as handled |

### On-Demand Investigation

Mention the bot to start an investigation:

```
@AutoSRE investigate high latency on payment-service
```

Response:
```
🔍 Starting investigation for "high latency on payment-service"...
Investigation ID: inv_01HQ7X9A2B3C4D5E6F
```

Results are posted when complete.

---

## Alertmanager Integration

Route alerts from Prometheus Alertmanager to AutoSRE:

```yaml
# alertmanager.yml
receivers:
  - name: 'autosre'
    webhook_configs:
      - url: 'http://autosre:8000/api/v1/webhook/alertmanager'
        send_resolved: true

route:
  receiver: 'autosre'
  routes:
    - match:
        severity: critical
      receiver: 'autosre'
```

---

## Testing

### Health Check

```bash
curl http://localhost:8000/api/v1/slack/health
```

Response:
```json
{
  "status": "connected",
  "bot_user": "autosre",
  "team": "Your Workspace"
}
```

### Test Message

```bash
curl -X POST http://localhost:8000/api/v1/slack/test \
  -H "Content-Type: application/json" \
  -d '{"channel": "#incidents", "message": "Test from AutoSRE"}'
```

---

## Troubleshooting

### Bot Not Responding to Mentions

1. Verify bot is invited to channel (`/invite @AutoSRE`)
2. Check Event Subscriptions are enabled
3. Verify Request URL is accessible
4. Check AutoSRE logs for errors

### Buttons Not Working

1. Verify Interactivity is enabled
2. Check Interactivity Request URL
3. Verify signing secret matches

### "Invalid Signature" Errors

1. Double-check `SLACK_SIGNING_SECRET`
2. Use Signing Secret (not Client Secret)
3. Check time sync (requests expire after 5 min)

### No Messages Appearing

1. Verify `SLACK_BOT_TOKEN` starts with `xoxb-`
2. Check bot has `chat:write` scope
3. Test with `/api/v1/slack/health`

---

## Security Best Practices

1. **Always set signing secret** in production
2. **Use HTTPS** for webhook URLs
3. **Restrict channels** the bot can post to
4. **Audit action approvals** via logs
5. **Rotate tokens** periodically

---

## Next Steps

- [PagerDuty Integration →](pagerduty-integration.md)
- [Configuration Reference →](../reference/configuration.md)
