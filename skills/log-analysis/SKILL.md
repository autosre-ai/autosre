# Log Analysis

Partition-first, sampling-based log analysis for efficient error pattern detection.

## Overview

This skill provides efficient log analysis methodology using statistical sampling and pattern clustering. Never dump all logs - always start with statistics and sample strategically.

## Critical Rules

1. **Statistics First** - Always start with log statistics (volume, error rate, patterns)
2. **Sample, Don't Dump** - Never request all logs (50-100 samples max)
3. **15-30 min windows** - Start narrow, expand if needed
4. **Extract correlation IDs** - trace_id, request_id to follow requests across services

## Workflow

```
Statistics → Sample → Pattern → Temporal → Correlate
```

1. **Statistics** - Volume, error rate, top patterns
2. **Sample** - Representative error subset (50-100)
3. **Signatures** - Cluster into unique error types
4. **Temporal** - When did each pattern start?
5. **Correlate** - Follow trace_ids across services

## Log Level Priority

| Level | Priority | Action |
|-------|----------|--------|
| **FATAL/CRITICAL** | Highest | Immediate attention - service likely down |
| **ERROR** | High | Primary focus - actual failures |
| **WARN** | Medium | Review if errors sparse - may indicate degradation |
| **INFO** | Low | Context only - for tracing specific requests |
| **DEBUG/TRACE** | Ignore | Too noisy for incident investigation |

## Correlation ID Patterns

Look for these fields to trace requests:
- `trace_id`, `traceId`, `x-trace-id` (distributed tracing)
- `request_id`, `requestId`, `x-request-id` (request tracking)
- `correlation_id`, `correlationId` (business correlation)
- `span_id`, `parent_id` (span context)

## Common Error Patterns

| Pattern | Indicates | What to Look For |
|---------|-----------|------------------|
| `connection refused` | Service/DB down | Which host:port? When did it start? |
| `timeout`, `timed out` | Slow dependency | Timeout value? Which service? |
| `OOM`, `OutOfMemory` | Memory exhaustion | Memory trend before crash? |
| `connection pool exhausted` | Pool saturation | Pool size? Concurrent connections? |
| `circuit breaker open` | Dependency failing | Which circuit? Failure threshold? |
| `rate limit`, `429` | Throttling | Which API? Rate vs limit? |
| `deadlock detected` | Concurrency bug | Which locks? Stack traces? |
| `null pointer`, `undefined` | Code bug | Stack trace? Input? |

## Noise Filtering

Ignore these (usually not actionable):
- Health check logs (unless failing)
- Scheduled job completion logs (unless failing)
- Client-side errors (4xx) from bots/scanners
- Deprecated API warnings (unless correlated)
- Log shipping/parsing errors (infrastructure noise)

## Query Patterns by Backend

### Elasticsearch / OpenSearch
```
# Basic error search
level:ERROR AND service:"payment-api"

# Time range with error types
level:(ERROR OR FATAL) AND @timestamp:[now-1h TO now]

# Pattern matching
message:/connection.*refused/
```

### Splunk (SPL)
```spl
index=production level=ERROR
| stats count by source, message
| sort -count

# Error clustering
index=production level=ERROR earliest=-1h
| cluster showcount=t
| table cluster_count, cluster_label
```

### Grafana Loki (LogQL)
```logql
{app="payment-api"} |= "error" | json

# Rate of errors
sum(rate({app="payment-api"} |= "error"[5m]))
```

### Coralogix (DataPrime)
```dataprime
source logs
| filter severity >= 'ERROR'
| filter $d.service == 'payment-api'
| aggregate count() by $d.error_type
```

## Evidence Quoting

Always use this format:
```
[SOURCE] at [TIMESTAMP]: "[EXACT LOG LINE]"
```

Example:
```
[payment-api] at 2024-01-15T10:32:45Z: "Connection refused: database-primary:5432"
```

## Output Template

```markdown
## Log Analysis Summary

### Volume
- Total logs in window: X
- Error count: Y (Z%)
- Top error pattern: "[pattern]" (N occurrences)

### Unique Error Signatures
1. **[Pattern 1]** - N occurrences, first at [time]
   - Sample: "[log line]"
2. **[Pattern 2]** - ...

### Temporal Analysis
- First error: [time]
- Error rate change: [from X to Y at time]
- Correlation with deployment/event: [yes/no]

### Cross-Service Correlation
- Trace ID: [id] shows path: ServiceA → ServiceB → ServiceC
- Failure point: ServiceB at [time]

### Recommendations
1. [Action based on findings]
```

## Configuration

```yaml
# Elasticsearch
elasticsearch:
  url: http://elasticsearch:9200
  index: logs-*

# Splunk
splunk:
  host: splunk.example.com
  port: 8089
  token: ${SPLUNK_TOKEN}

# Loki
loki:
  url: http://loki:3100

# Coralogix
coralogix:
  api_key: ${CORALOGIX_API_KEY}
  domain: ${CORALOGIX_DOMAIN}
```

## Dependencies

- Target logging backend (Elasticsearch, Splunk, Loki, etc.)
