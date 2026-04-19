# Telegram Skill

Integration with Telegram for messaging and file sharing.

## Actions

| Action | Description |
|--------|-------------|
| `send_message` | Send a text message |
| `send_photo` | Send an image |
| `send_document` | Send a file |

## Configuration

Required environment variables:
- `TELEGRAM_BOT_TOKEN` — Bot token from @BotFather

## Usage

```python
from skills.telegram import TelegramSkill

skill = TelegramSkill()

# Send a message
await skill.send_message(
    chat_id="-100123456789",
    text="🚨 *Alert*: CPU usage exceeded 90%",
    parse_mode="Markdown"
)

# Send a photo
await skill.send_photo(
    chat_id="-100123456789",
    photo_url="https://example.com/graph.png",
    caption="CPU usage over time"
)

# Send a document
await skill.send_document(
    chat_id="-100123456789",
    file_path="/tmp/report.pdf"
)
```

## Rate Limiting

Built-in rate limiting respects Telegram's API limits:
- 30 messages/second to same group
- 1 message/second to same user

## Dependencies

- `aiohttp>=3.8.0`
- `pydantic>=2.0.0`
