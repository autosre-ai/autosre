# OpsGenie Skill

Alert and incident management via OpsGenie.

## Configuration

```yaml
opsgenie:
  api_key: ${OPSGENIE_API_KEY}
  api_url: https://api.opsgenie.com  # or https://api.eu.opsgenie.com for EU
```

## Actions

| Action | Description | Parameters |
|--------|-------------|------------|
| `list_alerts` | List alerts | `query`, `status` |
| `get_alert` | Get alert details | `alert_id` |
| `acknowledge_alert` | Acknowledge alert | `alert_id`, `note` |
| `close_alert` | Close alert | `alert_id`, `note` |
| `create_alert` | Create alert | `message`, `priority`, `tags` |
| `get_oncall` | Get on-call schedule | `schedule_id` |

## Example Usage

```python
# List open alerts
result = await opsgenie.list_alerts(status="open")

# Acknowledge an alert
result = await opsgenie.acknowledge_alert(
    alert_id="abc-123",
    note="Investigating issue"
)

# Create a new P1 alert
result = await opsgenie.create_alert(
    message="Production database down",
    priority="P1",
    tags=["database", "production"]
)
```
