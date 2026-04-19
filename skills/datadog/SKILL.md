# Datadog Skill

Query Datadog for metrics, monitors, events, and manage incidents.

## Configuration

```yaml
datadog:
  api_key: ${DD_API_KEY}
  app_key: ${DD_APP_KEY}
  site: datadoghq.com  # or datadoghq.eu, us3.datadoghq.com, etc.
```

## Actions

| Action | Description | Parameters |
|--------|-------------|------------|
| `query_metrics` | Query metrics using DQL | `query`, `from_ts`, `to_ts` |
| `get_monitors` | List monitors | `tags`, `monitor_states` |
| `mute_monitor` | Mute a monitor | `monitor_id`, `end`, `scope` |
| `get_events` | Query events | `start`, `end`, `tags` |
| `get_incidents` | List incidents | `status` |
| `create_incident` | Create incident | `title`, `severity` |

## Example Usage

```python
# Query CPU metrics
result = await datadog.query_metrics(
    query="avg:system.cpu.user{*}",
    from_ts=int(time.time()) - 3600,
    to_ts=int(time.time())
)

# Get alerting monitors
result = await datadog.get_monitors(
    monitor_states=["Alert", "Warn"]
)

# Mute a monitor for 1 hour
result = await datadog.mute_monitor(
    monitor_id=123456,
    end=int(time.time()) + 3600
)
```

## Required API Permissions

- `monitors_read` - For listing monitors
- `monitors_write` - For muting monitors
- `events_read` - For querying events
- `timeseries_query` - For querying metrics
- `incidents_read` - For listing incidents
- `incidents_write` - For creating incidents
