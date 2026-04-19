# Prometheus Skill

Query Prometheus metrics, manage alerts, and monitor scrape targets.

## Configuration

```yaml
url: http://prometheus:9090    # Prometheus server URL (required)
auth:                          # Optional authentication
  type: basic                  # basic, bearer, or none
  username: admin
  password: secret
timeout: 30                    # Request timeout in seconds
```

## Actions

### `query(promql, time_range)`
Execute an instant PromQL query.

**Parameters:**
- `promql` (str, required): PromQL expression
- `time_range` (str, optional): Time range for rate/increase functions (default: "5m")

**Returns:** List of metric results with labels and values

**Example:**
```python
result = await prometheus.query("up{job='node'}")
# Returns: [{"metric": "up", "labels": {"job": "node"}, "value": 1.0}]
```

### `query_range(promql, start, end, step)`
Execute a range query for time series data.

**Parameters:**
- `promql` (str, required): PromQL expression
- `start` (datetime, optional): Start time (default: 1 hour ago)
- `end` (datetime, optional): End time (default: now)
- `step` (str, optional): Query step (default: "15s")

**Returns:** List of metric results with time series values

### `get_alerts()`
List all active alerts from Prometheus.

**Returns:** List of active alerts with state, labels, and annotations

### `get_alert_rules()`
List all configured alerting rules.

**Returns:** List of alert rules with their expressions and thresholds

### `silence_alert(alert_name, duration, comment)`
Create a silence for an alert.

**Parameters:**
- `alert_name` (str, required): Name of the alert to silence
- `duration` (str, required): Duration (e.g., "2h", "30m")
- `comment` (str, optional): Reason for silencing

**Returns:** Silence ID

**Note:** Requires Alertmanager integration

### `delete_silence(silence_id)`
Remove an active silence.

**Parameters:**
- `silence_id` (str, required): ID of the silence to remove

### `get_targets()`
List all scrape targets and their status.

**Returns:** List of targets with health status, labels, and last scrape time

## Error Handling

All actions return an `ActionResult` with:
- `success`: Boolean indicating success/failure
- `data`: The result data (on success)
- `error`: Error message (on failure)
- `metadata`: Additional context (timing, query info, etc.)

## Dependencies

- `prometheus-api-client>=0.5.0`
- `httpx>=0.24.0`
