# Trace Analysis

Distributed tracing analysis for request flow debugging and latency investigation.

## Overview

This skill provides distributed tracing analysis methodology for debugging request flows, identifying latency bottlenecks, and correlating errors across services.

## Quick Reference

**Your Role:** Analyze request flow, find latency bottlenecks, correlate failures across services
**Start With:** Find traces for errors/slow requests, examine spans
**Key Output:** Request flow, latency breakdown, failure point identification

## When to Use Traces

| Scenario | Traces Help With |
|----------|------------------|
| High latency | Which service/operation is slow? |
| 5xx errors | Where in the request chain did it fail? |
| Timeout | Which downstream call timed out? |
| Intermittent failures | Pattern in failed vs successful requests? |
| Cross-service issues | Which services are involved? |

## Trace Concepts

- **Trace**: Complete request journey from entry to completion
- **Span**: Single operation within a trace (e.g., HTTP call, DB query)
- **Parent/Child**: Spans have hierarchy showing call relationships
- **Duration**: Time taken by each span
- **Tags/Attributes**: Metadata (service name, status code, error)

## Analysis Workflow

```
1. Find relevant traces (by time, service, error)
2. Examine trace overview (total duration, span count)
3. Identify critical path (longest chain of dependent spans)
4. Find bottleneck (span with highest duration or error)
5. Correlate with logs (using trace_id)
```

## Key Metrics from Traces

| Metric | What It Shows |
|--------|---------------|
| Trace duration | End-to-end request time |
| Span duration | Time in each operation |
| Span count | Request complexity |
| Error spans | Failure points |
| Service latency contribution | Which service adds most latency |

## Common Patterns

### Latency Issues

```
Total trace: 2.5s
├─ ServiceA: 50ms
├─ ServiceB: 100ms
├─ Database: 2.3s  ← Bottleneck!
└─ ServiceC: 50ms
```

→ Root cause: Slow database query

### Cascading Failure

```
Span: ServiceA → ServiceB
  Status: Error
  Error: "Connection refused"
  
Span: ServiceB → ServiceC
  Status: Error  
  Error: "Timeout waiting for ServiceB"
```

→ Root cause: ServiceB is down, causing upstream failures

### N+1 Problem

```
Span count by type:
├─ HTTP calls: 3
├─ Database queries: 150  ← Suspicious!
```

→ Root cause: N+1 query pattern in code

## Query Examples

### By Jaeger/Tempo
```
# Find slow traces
service="payment-api" AND duration>1s

# Find errors
service="checkout" AND status.code=error

# Find specific operation
service="order-service" AND operation="ProcessOrder"
```

### By Trace ID
```
# Get full trace by ID
traceID=abc123def456...

# Find related logs
trace_id=abc123def456... in log search
```

## Output Template

```markdown
## Trace Analysis Summary

### Trace Overview
- Trace ID: [id]
- Duration: [total_ms] ms
- Span count: [count]
- Services involved: [list]
- Status: [success/error]

### Request Flow
```
→ api-gateway (15ms)
  → auth-service (25ms)
  → order-service (150ms)
    → inventory-db (120ms) ← Slowest
    → payment-api (45ms)
      → stripe-api (40ms)
  → notification-service (20ms)
```

### Latency Breakdown
| Service | Duration | % of Total |
|---------|----------|------------|
| inventory-db | 120ms | 48% |
| payment-api | 45ms | 18% |
| ... | ... | ... |

### Critical Path
[service1] → [service2] → [service3]
Total: [duration]ms

### Bottleneck
- Service: [name]
- Operation: [operation]
- Duration: [ms] (X% of total)
- Root cause: [analysis]

### Recommendations
1. [Action based on findings]
```

## Configuration

```yaml
# Jaeger
jaeger:
  url: http://jaeger:16686
  
# Tempo (Grafana)
tempo:
  url: http://tempo:3200
  
# Zipkin
zipkin:
  url: http://zipkin:9411

# X-Ray
xray:
  region: us-west-2
```

## Actions

### `find_traces`
Find traces by service, operation, time range, or error status.

**Parameters:**
- `service` (str): Service name
- `operation` (str, optional): Operation/endpoint name
- `time_range` (str): Time range (e.g., 1h, 15m)
- `status` (str, optional): Filter by status (error, ok)
- `min_duration` (str, optional): Minimum duration (e.g., 1s)
- `limit` (int): Maximum traces to return (default: 20)

### `get_trace`
Get full trace details by trace ID.

**Parameters:**
- `trace_id` (str): Trace ID

**Returns:** Complete trace with all spans

### `analyze_trace`
Analyze a trace for bottlenecks and issues.

**Parameters:**
- `trace_id` (str): Trace ID

**Returns:** Analysis including critical path, bottlenecks, recommendations

### `compare_traces`
Compare traces to find differences (e.g., slow vs fast).

**Parameters:**
- `trace_ids` (list[str]): List of trace IDs to compare

**Returns:** Comparison showing differences in duration, spans

### `get_service_latency`
Get latency contribution by service.

**Parameters:**
- `service` (str): Service name
- `time_range` (str): Time range

**Returns:** Latency percentiles and breakdown

## Dependencies

- Tracing backend (Jaeger, Tempo, Zipkin, X-Ray)
