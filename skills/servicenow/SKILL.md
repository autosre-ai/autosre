# ServiceNow Skill

Incident and change management via ServiceNow.

## Configuration

```yaml
servicenow:
  instance: mycompany.service-now.com
  username: ${SNOW_USERNAME}
  password: ${SNOW_PASSWORD}
```

## Actions

| Action | Description | Parameters |
|--------|-------------|------------|
| `get_incidents` | Query incidents | `query`, `state`, `limit` |
| `get_incident` | Get incident details | `sys_id` |
| `create_incident` | Create incident | `short_description`, `description`, `urgency`, `impact` |
| `update_incident` | Update incident | `sys_id`, `fields` |
| `add_work_note` | Add work note | `sys_id`, `note` |
| `get_change_requests` | Query change requests | `query`, `state` |

## Example Usage

```python
# Get open incidents
result = await servicenow.get_incidents(state="new")

# Create a P1 incident
result = await servicenow.create_incident(
    short_description="Production database unresponsive",
    description="Database server db-prod-01 not responding to queries",
    urgency=1,
    impact=1,
)

# Add a work note
result = await servicenow.add_work_note(
    sys_id="abc123",
    note="Restarted database service, monitoring recovery"
)
```

## Required Permissions

- `incident` table read/write access
- `change_request` table read access
- API access enabled for user
