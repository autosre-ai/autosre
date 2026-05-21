# Cascading Failure Analysis Skill

The Cascading Failure skill detects, analyzes, and helps prevent cascade effects where one service failure triggers failures in dependent services.

## Overview

Cascading failures are one of the most dangerous failure modes in distributed systems. A single point of failure can propagate through the dependency graph, taking down entire systems.

## How Cascading Failures Happen

```
1. Service A becomes slow
   ↓
2. Service B (depends on A) exhausts connection pool waiting for A
   ↓
3. Service C (depends on B) times out, retries aggressively
   ↓
4. Retry storm overwhelms Service A further
   ↓
5. Services D, E, F fail due to B and C unavailability
   ↓
6. Complete system outage
```

## Usage

### Dependency Graph Analysis

```python
from autosre.skills import CascadingFailureSkill

skill = CascadingFailureSkill()

# Build dependency graph from traces
graph = await skill.build_dependency_graph(
    service="payment-service",
    source="distributed_traces",
    window="7d"
)

# Visualize dependencies
print(graph.to_mermaid())
# graph LR
#   payment-service --> user-service
#   payment-service --> inventory-service
#   payment-service --> notification-service
#   user-service --> auth-service
#   user-service --> postgres
```

### Blast Radius Calculation

```python
# Calculate impact if service fails
blast_radius = await skill.calculate_blast_radius(
    failing_service="auth-service"
)

print(blast_radius)
# {
#   "direct_dependents": ["user-service", "api-gateway"],
#   "indirect_dependents": ["payment-service", "order-service", ...],
#   "total_affected_services": 12,
#   "affected_traffic_percentage": 0.85,
#   "severity": "critical"
# }
```

### Cascade Detection

```python
# Detect active cascading failure
cascade = await skill.detect_cascade(
    window="15m"
)

if cascade.detected:
    print(f"Cascade detected!")
    print(f"Origin: {cascade.origin_service}")
    print(f"Propagation path: {cascade.path}")
    print(f"Current scope: {cascade.affected_services}")
    print(f"Recommended actions: {cascade.recommendations}")
```

### Circuit Breaker Recommendations

```python
# Get circuit breaker recommendations
recommendations = await skill.recommend_circuit_breakers(
    service="payment-service"
)

for rec in recommendations:
    print(f"Add circuit breaker: {rec.caller} → {rec.callee}")
    print(f"  Reason: {rec.reason}")
    print(f"  Suggested timeout: {rec.timeout}s")
    print(f"  Failure threshold: {rec.failure_threshold}")
```

### Bulkhead Recommendations

```python
# Get bulkhead/isolation recommendations
bulkheads = await skill.recommend_bulkheads(
    service="payment-service",
    blast_radius_threshold=0.30
)

for bulkhead in bulkheads:
    print(f"Isolate: {bulkhead.resource}")
    print(f"  Pattern: {bulkhead.pattern}")
    print(f"  Rationale: {bulkhead.rationale}")
```

## Configuration

```yaml
# config/autosre.yaml
cascading_failure:
  enabled: true
  
  dependencies:
    auto_discover: true
    definitions_file: "config/dependencies.yaml"
  
  circuit_breaker:
    recommend_on_propagation: true
    default_timeout: 30
  
  bulkhead:
    recommend_on_high_blast_radius: true
    blast_radius_threshold: 0.30
```

### Manual Dependency Definitions

```yaml
# config/dependencies.yaml
services:
  payment-service:
    dependencies:
      - service: user-service
        type: synchronous
        criticality: required
      - service: inventory-service
        type: synchronous
        criticality: required
      - service: notification-service
        type: asynchronous
        criticality: optional
    
  user-service:
    dependencies:
      - service: auth-service
        type: synchronous
        criticality: required
      - service: postgres
        type: database
        criticality: required
```

## Detection Patterns

### 1. Correlated Error Spikes

When multiple services show error spikes within a short time window, and the services are in a dependency chain.

```python
# Detected pattern:
# t=0:00 - auth-service errors spike to 50%
# t=0:02 - user-service errors spike to 45%
# t=0:03 - payment-service errors spike to 40%
# t=0:05 - api-gateway errors spike to 35%
```

### 2. Latency Propagation

When latency increases propagate through the dependency graph.

```python
# Detected pattern:
# t=0:00 - database p99 latency: 50ms → 2000ms
# t=0:01 - user-service p99 latency: 100ms → 2100ms
# t=0:02 - payment-service p99 latency: 200ms → 4500ms (includes retries)
```

### 3. Connection Pool Exhaustion

When downstream slowness causes connection pool exhaustion in upstream services.

```python
# Detected pattern:
# t=0:00 - auth-service response time increases
# t=0:05 - user-service connection pool utilization: 50% → 100%
# t=0:06 - user-service starts rejecting requests
```

## Prevention Strategies

### 1. Circuit Breakers

Automatically stop calling failing services:

```python
# Example circuit breaker configuration
circuit_breaker_config = {
    "failure_threshold": 5,      # Open after 5 failures
    "success_threshold": 3,      # Close after 3 successes
    "timeout": 30,               # Half-open after 30 seconds
    "failure_rate_threshold": 0.5  # Or 50% failure rate
}
```

### 2. Bulkheads

Isolate resources to prevent one failure from consuming all capacity:

```python
# Example bulkhead patterns
bulkhead_patterns = [
    "Separate thread pools per downstream service",
    "Separate connection pools per service",
    "Rate limiting per tenant",
    "Queue isolation per workload type"
]
```

### 3. Timeouts and Deadlines

Set appropriate timeouts to prevent indefinite waiting:

```python
# Timeout strategy
timeout_config = {
    "connect_timeout": 1.0,      # Fast fail on connection
    "read_timeout": 5.0,         # Reasonable read timeout
    "total_timeout": 10.0,       # Overall request deadline
    "retry_timeout": 0.5         # Short timeout for retries
}
```

### 4. Graceful Degradation

Design services to degrade gracefully when dependencies fail:

```python
# Graceful degradation examples
degradation_strategies = [
    "Return cached data when database is slow",
    "Skip non-critical features when dependent service is down",
    "Use default values instead of failing",
    "Queue requests for later processing"
]
```

## Metrics Exported

```promql
# Cascade detection metrics
autosre_cascade_detected_total{origin_service="auth-service"}
autosre_cascade_affected_services{cascade_id="abc123"}
autosre_cascade_duration_seconds{cascade_id="abc123"}

# Blast radius metrics
autosre_blast_radius_services{service="auth-service"}
autosre_blast_radius_traffic_percentage{service="auth-service"}

# Circuit breaker metrics
autosre_circuit_breaker_state{caller="user-service", callee="auth-service"}
autosre_circuit_breaker_trips_total{caller="user-service", callee="auth-service"}
```

## Best Practices

### 1. Map Dependencies Before Incidents

Don't discover your dependency graph during an outage. Map it proactively.

### 2. Test Cascading Failures

Use chaos engineering to intentionally trigger cascading failures in non-production:

```python
# Example chaos test
await chaos.inject_failure(
    service="auth-service",
    failure_type="latency",
    latency_ms=5000,
    percentage=50
)

# Observe: Does the cascade propagate? Do circuit breakers trip?
```

### 3. Monitor Dependency Health

Don't just monitor your service—monitor your dependencies:

```python
# Dependency health check
for dep in service.dependencies:
    health = await dep.health_check()
    if not health.healthy:
        log.warning(f"Dependency {dep.name} unhealthy: {health.reason}")
```

### 4. Design for Failure

Assume dependencies will fail. Design accordingly:

- What's the fallback?
- Can you cache?
- Can you queue?
- What's the degraded experience?

## See Also

- [Golden Signals Monitoring](./golden_signals.md)
- [Error Budget Tracking](./error_budget.md)
- [AI Safety Features](./ai_safety.md)
