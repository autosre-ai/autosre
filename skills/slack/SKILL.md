# Slack Skill

Integration with Slack for messaging, channel management, and incident response.

## Actions

| Action | Description |
|--------|-------------|
| `send_message` | Post a message to a channel |
| `send_thread_reply` | Reply in a thread |
| `add_reaction` | Add emoji reaction to a message |
| `upload_file` | Upload a file to a channel |
| `get_channel_history` | Fetch recent messages |
| `create_incident_channel` | Create a new incident channel |
| `archive_channel` | Archive a channel |

## Configuration

Required environment variables:
- `SLACK_BOT_TOKEN` — Bot OAuth token (xoxb-...)
- `SLACK_SIGNING_SECRET` — (optional) For webhook verification

## Usage

```python
from skills.slack import SlackSkill

skill = SlackSkill()

# Send a message
await skill.send_message(
    channel="#alerts",
    text="🚨 High CPU usage detected",
    blocks=[{"type": "section", "text": {"type": "mrkdwn", "text": "*Alert*: CPU > 90%"}}]
)

# Create incident channel
channel = await skill.create_incident_channel(
    name="inc-2024-001-db-outage",
    users=["U123", "U456"]
)

# React to a message
await skill.add_reaction(
    channel="C123",
    timestamp="1234567890.123456",
    emoji="eyes"
)
```

## Rate Limiting

Built-in rate limiting respects Slack's API limits:
- Tier 1: 1 req/sec
- Tier 2: 20 req/min
- Tier 3: 50 req/min

## Dependencies

- `slack_sdk>=3.0.0`
- `aiohttp`
