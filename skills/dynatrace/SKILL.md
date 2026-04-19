# Dynatrace Skill

Query Dynatrace for problems, metrics, and monitored entities.

## Configuration

```yaml
url: https://abc12345.live.dynatrace.com   # Dynatrace environment URL (required)
api_token: ${DYNATRACE_API_TOKEN}           # API token (required)
timeout: 30                                  # Request timeout in seconds
```

## Actions

### `get_problems()`
Get active problems from Dynatrace.

**Returns:** List of active problems with severity, impact, and affected entities

### `get_problem_details(problem_id)`
Get detailed information about a specific problem.

**Parameters:**
- `problem_id` (str, required): Problem ID

**Returns:** Full problem details including root cause analysis

### `get_metrics(metric_key, entity, time_range)`
Query metrics from Dynatrace.

**Parameters:**
- `metric_key` (str, required): Metric key (e.g., "builtin:host.cpu.usage")
- `entity` (str, optional): Entity selector
- `time_range` (str, optional): Time range (default: "now-1h")

**Returns:** Metric data points

### `get_entities(type, filter)`
List monitored entities.

**Parameters:**
- `type` (str, required): Entity type (e.g., "HOST", "SERVICE", "PROCESS_GROUP")
- `filter` (str, optional): Entity selector filter

**Returns:** List of entities with metadata

## API Token Permissions

Required scopes:
- `Read problems` - For problem queries
- `Read metrics` - For metric queries
- `Read entities` - For entity queries
- `Access problem and event feed, metrics, and topology`

## Dependencies

- `httpx>=0.24.0`
