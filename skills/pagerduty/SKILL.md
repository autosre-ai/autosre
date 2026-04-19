# PagerDuty Skill

Integration with PagerDuty for incident management and on-call schedules.

## Actions

| Action | Description |
|--------|-------------|
| `list_incidents` | Get incidents by status |
| `get_incident` | Get incident details |
| `acknowledge_incident` | Acknowledge an incident |
| `resolve_incident` | Resolve an incident |
| `add_note` | Add note to incident |
| `get_oncall` | Get current on-call responders |
| `create_incident` | Trigger a new incident |

## Configuration

Required environment variables:
- `PAGERDUTY_API_KEY` — REST API key
- `PAGERDUTY_FROM_EMAIL` — Email for API requests

## Usage

```python
from skills.pagerduty import PagerDutySkill

skill = PagerDutySkill()

# List triggered incidents
incidents = await skill.list_incidents(status="triggered")

# Acknowledge incident
await skill.acknowledge_incident("P123ABC")

# Get on-call
oncall = await skill.get_oncall(schedule_id="SCHEDULE123")
print(f"On-call: {oncall.user.name}")

# Create incident
incident = await skill.create_incident(
    service_id="SERVICE123",
    title="High error rate in payments",
    body="Error rate exceeded 5% threshold"
)
```

## Rate Limiting

Built-in rate limiting: 960 requests/minute (default PagerDuty limit).

## Dependencies

- `aiohttp>=3.8.0`
- `pydantic>=2.0.0`
