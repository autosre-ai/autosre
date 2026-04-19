# Splunk Skill

Query Splunk for logs, metrics, and alerts.

## Configuration

```yaml
splunk:
  host: splunk.example.com
  port: 8089
  username: ${SPLUNK_USERNAME}
  password: ${SPLUNK_PASSWORD}
  verify_ssl: true
```

## Actions

| Action | Description | Parameters |
|--------|-------------|------------|
| `search` | Execute SPL search | `query`, `earliest_time`, `latest_time`, `max_results` |
| `get_saved_searches` | List saved searches | |
| `run_saved_search` | Run a saved search | `name` |
| `get_alerts` | Get triggered alerts | `severity` |

## Example Usage

```python
# Search for errors in the last hour
result = await splunk.search(
    query='index=main level=ERROR',
    earliest_time="-1h",
    max_results=50
)

# Run a saved search
result = await splunk.run_saved_search(name="Production Errors")

# Get all triggered alerts
result = await splunk.get_alerts()
```

## Required Permissions

- `search` capability for executing searches
- `rest_properties_get` for API access
- Access to relevant indexes
