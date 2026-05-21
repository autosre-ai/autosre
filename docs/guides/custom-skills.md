# Custom Skills

Create custom skills to integrate AutoSRE with your internal systems.

## Overview

Skills are Python functions that AutoSRE can call during investigations. They provide:

- **Data gathering** from internal systems
- **Actions** for remediation
- **Custom analysis** logic

---

## Quick Start

### 1. Create a Skill

```python
# skills/my_apm.py
from autosre.skills import skill, ActionResult

@skill("myapm.get_traces")
async def get_traces(
    service: str,
    operation: str = None,
    min_duration_ms: int = None,
    limit: int = 20
) -> ActionResult:
    """
    Fetch traces from internal APM system.
    
    Args:
        service: Service name
        operation: Filter by operation (optional)
        min_duration_ms: Minimum duration filter (optional)
        limit: Max results
        
    Returns:
        List of traces with timing and error info
    """
    try:
        client = MyAPMClient()
        traces = await client.query_traces(
            service=service,
            operation=operation,
            min_duration=min_duration_ms,
            limit=limit
        )
        return ActionResult.ok(traces)
    except Exception as e:
        return ActionResult.fail(f"APM query failed: {e}")
```

### 2. Register the Skill

```python
# skills/__init__.py
from .my_apm import get_traces
```

### 3. Use in Investigations

AutoSRE will automatically discover and use the skill:

```bash
$ autosre investigate "High latency on payment-service"

[...]
🔧 Calling myapm.get_traces(service="payment-service", min_duration_ms=1000)
   Found 15 slow traces
[...]
```

---

## Skill Structure

### Basic Structure

```python
from autosre.skills import skill, ActionResult
from typing import Optional

@skill("namespace.action")
async def my_skill(
    required_param: str,
    optional_param: Optional[int] = None
) -> ActionResult:
    """
    Docstring becomes the skill description for the LLM.
    
    Args:
        required_param: Description shown to LLM
        optional_param: Another description
        
    Returns:
        What the skill returns
    """
    # Implementation
    result = do_something(required_param)
    return ActionResult.ok(result)
```

### ActionResult

Return `ActionResult` to indicate success or failure:

```python
# Success
return ActionResult.ok(data)
return ActionResult.ok(data, cached=True, duration_ms=150)

# Failure
return ActionResult.fail("Error message")
return ActionResult.fail("Connection timeout", retry_after=30)
```

### Async vs Sync

Skills should be async for I/O operations:

```python
# ✅ Good - async for I/O
@skill("db.query")
async def query_database(query: str) -> ActionResult:
    result = await db.execute(query)
    return ActionResult.ok(result)

# ✅ OK - sync for CPU-bound
@skill("analysis.parse")
def parse_logs(logs: str) -> ActionResult:
    parsed = expensive_parsing(logs)
    return ActionResult.ok(parsed)
```

---

## Skill Metadata

### Requiring Approval

```python
@skill("dangerous.delete_pods", requires_approval=True)
async def delete_pods(namespace: str, selector: str) -> ActionResult:
    """Delete pods matching selector. REQUIRES APPROVAL."""
    # Will prompt for approval before executing
    result = await k8s.delete_pods(namespace, selector)
    return ActionResult.ok(result)
```

### Risk Levels

```python
from autosre.skills import skill, RiskLevel

@skill("risky.scale_down", risk_level=RiskLevel.HIGH)
async def scale_down(deployment: str) -> ActionResult:
    ...

# Risk levels: READ, WRITE_SAFE, WRITE_RISKY, DESTRUCTIVE
```

### Tags and Categories

```python
@skill(
    "observability.get_metrics",
    tags=["metrics", "prometheus"],
    category="observability"
)
async def get_metrics(query: str) -> ActionResult:
    ...
```

---

## Input Validation

### Using Pydantic

```python
from pydantic import BaseModel, Field
from autosre.skills import skill, ActionResult

class MetricsQuery(BaseModel):
    query: str = Field(..., description="PromQL query")
    start: str = Field(default="-1h", description="Start time")
    end: str = Field(default="now", description="End time")
    step: str = Field(default="1m", description="Step interval")

@skill("prometheus.query_range")
async def query_range(params: MetricsQuery) -> ActionResult:
    """Query Prometheus with range."""
    result = await prom.query_range(
        query=params.query,
        start=params.start,
        end=params.end,
        step=params.step
    )
    return ActionResult.ok(result)
```

### Type Hints

Type hints are used to generate tool schemas for the LLM:

```python
@skill("search.logs")
async def search_logs(
    query: str,                    # Required string
    index: str = "logs-*",         # Optional with default
    limit: int = 100,              # Integer
    fields: list[str] = None,      # Optional list
    time_range: dict = None        # Optional dict
) -> ActionResult:
    ...
```

---

## Examples

### Database Health Check

```python
@skill("db.health_check")
async def database_health(
    database: str,
    include_slow_queries: bool = False
) -> ActionResult:
    """
    Check database health including connections, replication, and optionally slow queries.
    
    Args:
        database: Database identifier
        include_slow_queries: Include slow query analysis
    """
    try:
        conn = await get_db_connection(database)
        
        health = {
            "status": "healthy",
            "connections": {
                "active": await conn.get_active_connections(),
                "max": await conn.get_max_connections(),
                "waiting": await conn.get_waiting_connections()
            },
            "replication": await conn.get_replication_status(),
            "disk_usage": await conn.get_disk_usage()
        }
        
        if include_slow_queries:
            health["slow_queries"] = await conn.get_slow_queries(limit=10)
        
        # Determine health status
        if health["connections"]["waiting"] > 10:
            health["status"] = "degraded"
            health["issues"] = ["High connection wait queue"]
            
        return ActionResult.ok(health)
        
    except Exception as e:
        return ActionResult.fail(f"Database health check failed: {e}")
```

### Internal API Check

```python
@skill("internal.call_api")
async def call_internal_api(
    service: str,
    endpoint: str,
    method: str = "GET",
    body: dict = None
) -> ActionResult:
    """
    Call internal service API for health/status checks.
    
    Args:
        service: Service name (resolves to internal URL)
        endpoint: API endpoint path
        method: HTTP method
        body: Request body for POST/PUT
    """
    try:
        base_url = await service_discovery.resolve(service)
        url = f"{base_url}{endpoint}"
        
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=method,
                url=url,
                json=body,
                timeout=30.0
            )
            
            return ActionResult.ok({
                "status_code": response.status_code,
                "body": response.json() if response.is_success else None,
                "error": response.text if not response.is_success else None,
                "latency_ms": response.elapsed.total_seconds() * 1000
            })
            
    except httpx.TimeoutException:
        return ActionResult.fail(f"Request to {service} timed out")
    except Exception as e:
        return ActionResult.fail(f"API call failed: {e}")
```

### Feature Flag Check

```python
@skill("features.check_flags")
async def check_feature_flags(
    service: str,
    user_segment: str = None
) -> ActionResult:
    """
    Check feature flag status for a service.
    
    Args:
        service: Service name
        user_segment: Optional user segment filter
    """
    try:
        client = LaunchDarklyClient()
        
        flags = await client.get_flags_for_service(service)
        
        if user_segment:
            flags = [f for f in flags if user_segment in f.get("segments", [])]
        
        # Find recently changed flags
        recent_changes = [
            f for f in flags 
            if f["last_modified"] > datetime.now() - timedelta(hours=24)
        ]
        
        return ActionResult.ok({
            "total_flags": len(flags),
            "enabled": len([f for f in flags if f["enabled"]]),
            "recently_changed": recent_changes
        })
        
    except Exception as e:
        return ActionResult.fail(f"Feature flag check failed: {e}")
```

---

## Guardrails

### Custom Guardrails

```python
from autosre.skills import skill, ActionResult
from autosre.guardrails import Guardrail

class TierGuardrail(Guardrail):
    """Block actions on Tier-0 services."""
    
    async def check(self, action: str, params: dict) -> bool:
        service = params.get("service")
        if service and await is_tier_0(service):
            raise GuardrailViolation(
                f"Cannot execute {action} on Tier-0 service {service}"
            )
        return True

@skill(
    "dangerous.restart_service",
    requires_approval=True,
    guardrails=[TierGuardrail()]
)
async def restart_service(service: str, namespace: str) -> ActionResult:
    ...
```

### Built-in Guardrails

```python
from autosre.guardrails import (
    BlastRadiusGuardrail,
    TimeWindowGuardrail,
    RateLimitGuardrail
)

@skill(
    "k8s.scale",
    guardrails=[
        BlastRadiusGuardrail(max_pods=10),
        TimeWindowGuardrail(blocked_hours=[(2, 6)]),  # Block 2-6 AM
        RateLimitGuardrail(max_per_hour=5)
    ]
)
async def scale_deployment(...):
    ...
```

---

## Testing Skills

### Unit Tests

```python
# tests/test_my_skill.py
import pytest
from skills.my_apm import get_traces

@pytest.mark.asyncio
async def test_get_traces_success():
    result = await get_traces(
        service="test-service",
        limit=5
    )
    
    assert result.success
    assert len(result.data) <= 5

@pytest.mark.asyncio
async def test_get_traces_invalid_service():
    result = await get_traces(
        service="nonexistent"
    )
    
    assert not result.success
    assert "not found" in result.error.lower()
```

### Integration Tests

```python
@pytest.mark.integration
async def test_get_traces_real_apm():
    """Test against real APM (requires credentials)."""
    result = await get_traces(
        service="checkout-service",
        min_duration_ms=100
    )
    
    assert result.success
    # Verify structure
    for trace in result.data:
        assert "trace_id" in trace
        assert "duration_ms" in trace
```

---

## Skill Discovery

AutoSRE discovers skills from:

1. **Built-in skills**: `autosre.skills.*`
2. **Plugin packages**: `autosre_skills_*`
3. **Custom directory**: `~/.autosre/skills/`
4. **Project directory**: `./skills/`

### Plugin Package

Create a pip-installable skill package:

```
autosre-skills-mycompany/
├── autosre_skills_mycompany/
│   ├── __init__.py
│   └── internal_api.py
├── pyproject.toml
└── README.md
```

```toml
# pyproject.toml
[project]
name = "autosre-skills-mycompany"
version = "0.1.0"

[project.entry-points."autosre.skills"]
mycompany = "autosre_skills_mycompany"
```

---

## Best Practices

### 1. Good Descriptions

```python
# ❌ Bad - vague description
@skill("api.call")
async def call(url: str):
    """Call an API."""

# ✅ Good - clear, specific
@skill("internal.health_check")
async def health_check(service: str):
    """
    Check health of an internal service via its /health endpoint.
    Returns status, latency, and any health issues.
    
    Args:
        service: Service name (e.g., "checkout-service", "payments-api")
    """
```

### 2. Structured Returns

```python
# ❌ Bad - unstructured
return ActionResult.ok("Service is healthy")

# ✅ Good - structured data
return ActionResult.ok({
    "status": "healthy",
    "latency_ms": 45,
    "checks": {
        "database": "ok",
        "cache": "ok",
        "dependencies": "ok"
    }
})
```

### 3. Error Context

```python
# ❌ Bad - generic error
return ActionResult.fail("Failed")

# ✅ Good - actionable error
return ActionResult.fail(
    f"Connection to {service} timed out after 30s. "
    f"Service may be overloaded or network issues present."
)
```

### 4. Timeouts

```python
# Always set timeouts for external calls
async with httpx.AsyncClient(timeout=30.0) as client:
    response = await client.get(url)
```

---

## Next Steps

- [Skills Reference →](../concepts/skills.md)
- [Investigation Flow →](../concepts/investigation-flow.md)
- [API Reference →](../reference/api.md)
