# AutoSRE Slack Integration

Slack bot integration for AutoSRE, enabling incident investigation directly from Slack.

## Features

- **@mention investigations**: Mention the bot to start an investigation
- **Slash commands**: Use `/investigate` for structured queries
- **Real-time updates**: SSE streaming of investigation progress
- **Reaction feedback**: 👍/👎 reactions for investigation feedback
- **Thread follow-ups**: Ask follow-up questions in investigation threads

## Quick Start

### 1. Create a Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps)
2. Create a new app "From scratch"
3. Name it "AutoSRE" and select your workspace

### 2. Configure OAuth & Permissions

Add these **Bot Token Scopes**:
- `app_mentions:read` - Receive @mentions
- `chat:write` - Send messages
- `commands` - Slash commands
- `reactions:read` - Read reactions for feedback

### 3. Enable Socket Mode

1. Go to **Socket Mode** in the sidebar
2. Enable Socket Mode
3. Create an App-Level Token with `connections:write` scope
4. Save the token (starts with `xapp-`)

### 4. Add Event Subscriptions

Enable these events:
- `app_mention` - Bot @mentions
- `message.channels` - Channel messages (for thread replies)
- `reaction_added` - Reaction feedback

### 5. Create Slash Commands

Add these commands:
- `/investigate` - Start an investigation
- `/autosre` - Alias for `/investigate`

### 6. Install to Workspace

1. Go to **Install App**
2. Click "Install to Workspace"
3. Authorize the app
4. Copy the **Bot User OAuth Token** (starts with `xoxb-`)

### 7. Configure Environment

```bash
# Copy the example env file
cp .env.example .env

# Edit with your values
vim .env
```

Required variables:
- `SLACK_BOT_TOKEN` - Bot User OAuth Token (xoxb-...)
- `SLACK_APP_TOKEN` - App-Level Token (xapp-...)
- `SLACK_SIGNING_SECRET` - From Basic Information page
- `AUTOSRE_API_URL` - AutoSRE API endpoint

### 8. Run the Bot

#### Local Development

```bash
# Install dependencies
pip install -r requirements-slack.txt

# Run the bot
python -m src.integrations.slack.bot
```

#### Docker

```bash
# Build and run with docker-compose
docker-compose -f docker-compose.slack.yml up --build
```

## Usage

### @Mention

```
@AutoSRE investigate payment-service high error rate
@AutoSRE service=auth-api severity=critical
@AutoSRE check the database connection issues
```

### Slash Command

```
/investigate service=payment-api severity=critical description="Error rate spike"
/investigate checkout-service latency issues
/autosre service=auth severity=high
```

### Thread Follow-ups

In an investigation thread:
- `status` - Get current investigation status
- `cancel` - Get instructions to cancel
- Any text - Logged as follow-up context

### Reaction Feedback

React to the final investigation message:
- 👍 - Positive feedback (accurate results)
- 👎 - Negative feedback (needs improvement)
- ❓ - Unclear/needs more information

## Message Formats

The bot uses Slack Block Kit for rich formatting:

### Investigation Start
```
🔍 Investigation Started
━━━━━━━━━━━━━━━━━━━━━
Investigation ID: inv-abc123
Requested by: @user
Service: payment-service
Severity: 🔴 Critical

Alert Description:
Error rate above 5% for 10 minutes

⏱️ Started at 2024-01-15 10:30:00 UTC
```

### Evidence Found
```
📊 Evidence Found: Metric
Error rate increased from 0.1% to 5.2%

• Metric: payment_errors_total
• Window: 10 minutes
• Threshold: 1%

Confidence: ████████░░ 80%
```

### Investigation Complete
```
✅ Investigation Complete

🎯 Root Cause:
Database connection pool exhaustion

📋 Summary:
The payment service experienced high error rates due to...

💡 Recommendations:
1. Increase connection pool size
2. Add connection timeout monitoring
3. Implement circuit breaker pattern

⏱️ Duration: 2m 34s | React with 👍/👎 for feedback
```

## Architecture

```
┌─────────────┐     ┌─────────────────┐     ┌─────────────┐
│   Slack     │◄───►│  Slack Bot      │◄───►│ AutoSRE API │
│  (Socket)   │     │  (slack-bolt)   │     │  (FastAPI)  │
└─────────────┘     └─────────────────┘     └─────────────┘
                           │
                           │ SSE Stream
                           ▼
                    ┌─────────────────┐
                    │  Investigation  │
                    │    Updates      │
                    └─────────────────┘
```

## API Endpoints Used

- `POST /api/v1/investigate` - Start investigation
- `GET /api/v1/investigate/{id}/status` - Get status
- `GET /api/v1/investigate/{id}/stream` - SSE updates
- `POST /api/v1/investigate/{id}/feedback` - Submit feedback

## Error Handling

The bot handles errors gracefully:
- API connection failures → User-friendly error message
- Invalid commands → Help text with usage examples
- Investigation failures → Error details in thread

## Monitoring

Health check endpoint available at `/health` (configurable port).

Metrics available (if prometheus-client enabled):
- `slack_bot_investigations_started_total`
- `slack_bot_messages_sent_total`
- `slack_bot_errors_total`

## Development

### Project Structure

```
src/integrations/slack/
├── __init__.py          # Package exports
├── bot.py               # Main bot class
├── handlers.py          # Event handlers
├── messages.py          # Block Kit formatters
├── Dockerfile           # Container definition
├── requirements-slack.txt
├── .env.example
└── README.md
```

### Testing

```bash
# Run tests
pytest tests/integrations/slack/

# Test message formatting
python -c "from src.integrations.slack.messages import *; print(format_investigation_start('inv-123', {'service': 'test'}, '<@U123>'))"
```

## Troubleshooting

### Bot not responding to mentions
- Check Socket Mode is enabled
- Verify `app_mentions:read` scope
- Ensure bot is invited to the channel

### "Invalid token" errors
- Verify SLACK_BOT_TOKEN is correct
- Check token hasn't been regenerated

### No updates appearing
- Verify AUTOSRE_API_URL is reachable
- Check SSE stream endpoint is working
- Look for errors in bot logs

## License

Part of the AutoSRE project.
