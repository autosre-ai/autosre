# Creating Skills

This guide walks you through creating a custom skill for OpenSRE.

## Quick Start

### Generate Skill Scaffold

```bash
opensre skill create my-custom-skill

# Creates:
# skills/my-custom-skill/
# ├── SKILL.md
# ├── skill.yaml
# ├── actions.py
# ├── schemas.py
# └── tests/
#     └── test_skill.py
```

## Skill Structure

### skill.yaml

Metadata and configuration:

```yaml
# skills/my-tool/skill.yaml
name: my-tool
version: 1.0.0
description: Integration with My Tool monitoring platform

# Author information
author: Your Name
repository: https://github.com/yourname/opensre-skill-mytool

# Required configuration
config:
  - name: api_key
    description: My Tool API key
    required: true
    env: OPENSRE_MYTOOL_API_KEY
  - name: endpoint
    description: My Tool API endpoint
    required: false
    default: https://api.mytool.com
    env: OPENSRE_MYTOOL_ENDPOINT

# Dependencies
dependencies:
  - httpx>=0.26

# Permission levels for actions
permissions:
  read:
    - query
    - get_alerts
    - list_dashboards
  write:
    - create_annotation
    - update_dashboard
  destructive:
    - delete_alert
```

### actions.py

Implement the skill actions:

```python
# skills/my-tool/actions.py
"""My Tool skill actions."""

from typing import Any
from pydantic import BaseModel, Field
from opensre.skills import Skill, action


class QueryInput(BaseModel):
    """Input for query action."""
    query: str = Field(..., description="Query string")
    start: str = Field(default="1h", description="Time range start")
    end: str = Field(default="now", description="Time range end")


class QueryResult(BaseModel):
    """Result from query action."""
    data: list[dict[str, Any]]
    query: str
    time_range: str


class MyToolSkill(Skill):
    """My Tool monitoring integration."""
    
    name = "my-tool"
    
    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.api_key = config["api_key"]
        self.endpoint = config.get("endpoint", "https://api.mytool.com")
        self._client = None
    
    async def initialize(self):
        """Initialize the HTTP client."""
        import httpx
        self._client = httpx.AsyncClient(
            base_url=self.endpoint,
            headers={"Authorization": f"Bearer {self.api_key}"}
        )
    
    async def cleanup(self):
        """Cleanup resources."""
        if self._client:
            await self._client.aclose()
    
    async def health_check(self) -> bool:
        """Check if My Tool is accessible."""
        try:
            response = await self._client.get("/health")
            return response.status_code == 200
        except Exception:
            return False
    
    @action(
        name="query",
        description="Execute a query against My Tool",
        input_schema=QueryInput,
        output_schema=QueryResult,
        permission="read"
    )
    async def query(self, query: str, start: str = "1h", end: str = "now") -> QueryResult:
        """Execute a query and return results.
        
        Args:
            query: The query string to execute
            start: Start of time range (e.g., "1h", "2024-01-01")
            end: End of time range (e.g., "now", "2024-01-02")
            
        Returns:
            QueryResult with data points
        """
        response = await self._client.post("/query", json={
            "query": query,
            "start": start,
            "end": end
        })
        response.raise_for_status()
        
        data = response.json()
        return QueryResult(
            data=data["results"],
            query=query,
            time_range=f"{start} to {end}"
        )
    
    @action(
        name="get_alerts",
        description="Get active alerts from My Tool",
        permission="read"
    )
    async def get_alerts(self, severity: str = None) -> list[dict]:
        """Get active alerts.
        
        Args:
            severity: Filter by severity (critical, warning, info)
            
        Returns:
            List of active alerts
        """
        params = {}
        if severity:
            params["severity"] = severity
            
        response = await self._client.get("/alerts", params=params)
        response.raise_for_status()
        return response.json()["alerts"]
    
    @action(
        name="create_annotation",
        description="Create an annotation on a dashboard",
        permission="write"
    )
    async def create_annotation(
        self, 
        dashboard_id: str, 
        text: str, 
        time: str = "now"
    ) -> dict:
        """Create an annotation.
        
        Args:
            dashboard_id: ID of the dashboard
            text: Annotation text
            time: Timestamp for annotation
            
        Returns:
            Created annotation details
        """
        response = await self._client.post(
            f"/dashboards/{dashboard_id}/annotations",
            json={"text": text, "time": time}
        )
        response.raise_for_status()
        return response.json()
```

### schemas.py

Define input/output schemas (optional, can be inline):

```python
# skills/my-tool/schemas.py
"""Pydantic schemas for My Tool skill."""

from typing import Any, Optional
from pydantic import BaseModel, Field


class QueryInput(BaseModel):
    """Input for query action."""
    query: str = Field(..., description="Query string in MyTool Query Language")
    start: str = Field(default="1h", description="Time range start (relative or absolute)")
    end: str = Field(default="now", description="Time range end")
    step: Optional[str] = Field(default=None, description="Resolution step")


class DataPoint(BaseModel):
    """A single data point."""
    timestamp: float
    value: float
    labels: dict[str, str] = {}


class QueryResult(BaseModel):
    """Result from a query."""
    data: list[DataPoint]
    query: str
    time_range: str
    execution_time_ms: float


class Alert(BaseModel):
    """An alert from My Tool."""
    id: str
    name: str
    severity: str
    status: str
    message: str
    started_at: str
    labels: dict[str, str] = {}
```

### SKILL.md

Document your skill:

```markdown
# My Tool Skill

Integration with My Tool monitoring platform.

## Installation

\`\`\`bash
opensre skill install my-tool
\`\`\`

## Configuration

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENSRE_MYTOOL_API_KEY` | API key | Yes |
| `OPENSRE_MYTOOL_ENDPOINT` | API endpoint | No |

## Actions

### query

Execute a query against My Tool.

**Input:**
- `query` (string, required): Query string
- `start` (string): Time range start (default: "1h")
- `end` (string): Time range end (default: "now")

**Output:**
- `data`: List of data points
- `query`: Executed query
- `time_range`: Time range string

**Example:**
\`\`\`python
result = await my_tool.query(
    query="avg(cpu_usage)",
    start="1h",
    end="now"
)
\`\`\`

### get_alerts

Get active alerts.

**Input:**
- `severity` (string, optional): Filter by severity

**Output:**
List of alert objects.

### create_annotation

Create a dashboard annotation.

**Input:**
- `dashboard_id` (string, required): Dashboard ID
- `text` (string, required): Annotation text
- `time` (string): Timestamp (default: "now")

**Output:**
Created annotation details.
```

### tests/test_skill.py

Write tests for your skill:

```python
# skills/my-tool/tests/test_skill.py
"""Tests for My Tool skill."""

import pytest
from unittest.mock import AsyncMock, patch

from skills.my_tool.actions import MyToolSkill


@pytest.fixture
def skill():
    """Create skill instance for testing."""
    return MyToolSkill({
        "api_key": "test-key",
        "endpoint": "https://api.mytool.test"
    })


@pytest.fixture
def mock_client():
    """Mock HTTP client."""
    with patch("httpx.AsyncClient") as mock:
        yield mock.return_value


@pytest.mark.asyncio
async def test_query(skill, mock_client):
    """Test query action."""
    mock_client.post.return_value = AsyncMock(
        status_code=200,
        json=lambda: {"results": [{"timestamp": 1234, "value": 42}]}
    )
    
    await skill.initialize()
    result = await skill.query("avg(cpu)")
    
    assert len(result.data) == 1
    assert result.query == "avg(cpu)"


@pytest.mark.asyncio
async def test_get_alerts(skill, mock_client):
    """Test get_alerts action."""
    mock_client.get.return_value = AsyncMock(
        status_code=200,
        json=lambda: {"alerts": [{"id": "1", "severity": "critical"}]}
    )
    
    await skill.initialize()
    alerts = await skill.get_alerts(severity="critical")
    
    assert len(alerts) == 1
    assert alerts[0]["severity"] == "critical"


@pytest.mark.asyncio
async def test_health_check_success(skill, mock_client):
    """Test health check when service is up."""
    mock_client.get.return_value = AsyncMock(status_code=200)
    
    await skill.initialize()
    assert await skill.health_check() is True


@pytest.mark.asyncio
async def test_health_check_failure(skill, mock_client):
    """Test health check when service is down."""
    mock_client.get.side_effect = Exception("Connection refused")
    
    await skill.initialize()
    assert await skill.health_check() is False
```

## Advanced Topics

### Error Handling

```python
from opensre.skills import SkillError, RetryableError

@action(name="query", ...)
async def query(self, query: str) -> QueryResult:
    try:
        response = await self._client.post("/query", json={"query": query})
        response.raise_for_status()
        return QueryResult(...)
    except httpx.TimeoutException as e:
        # Will be retried
        raise RetryableError(f"Timeout querying My Tool: {e}")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            raise SkillError("Invalid API key")
        elif e.response.status_code >= 500:
            raise RetryableError(f"My Tool server error: {e}")
        raise SkillError(f"Query failed: {e}")
```

### Caching

```python
from opensre.skills import cached

class MyToolSkill(Skill):
    @action(name="get_dashboards", ...)
    @cached(ttl=300)  # Cache for 5 minutes
    async def get_dashboards(self) -> list[dict]:
        response = await self._client.get("/dashboards")
        return response.json()
```

### Rate Limiting

```python
from opensre.skills import rate_limit

class MyToolSkill(Skill):
    @action(name="query", ...)
    @rate_limit(calls=10, period=60)  # 10 calls per minute
    async def query(self, query: str) -> QueryResult:
        ...
```

### Streaming Results

```python
from typing import AsyncIterator
from opensre.skills import streaming_action

class MyToolSkill(Skill):
    @streaming_action(name="tail_logs", ...)
    async def tail_logs(self, source: str) -> AsyncIterator[str]:
        """Stream logs from a source."""
        async with self._client.stream("GET", f"/logs/{source}/tail") as response:
            async for line in response.aiter_lines():
                yield line
```

## Publishing Your Skill

### 1. Prepare for Publication

```yaml
# skill.yaml
name: my-tool
version: 1.0.0
description: Integration with My Tool
author: Your Name <you@example.com>
license: Apache-2.0
repository: https://github.com/yourname/opensre-skill-mytool
keywords:
  - monitoring
  - observability
  - my-tool
```

### 2. Publish to Registry

```bash
# Login to registry
opensre registry login

# Publish
opensre skill publish ./skills/my-tool
```

### 3. Users Install Via

```bash
opensre skill install my-tool
```

## Best Practices

1. **Atomic Actions** — Each action should do one thing well
2. **Idempotent** — Actions should be safe to retry
3. **Descriptive Names** — Use clear action names (get_pods, not gp)
4. **Good Defaults** — Provide sensible defaults for optional parameters
5. **Error Messages** — Include helpful context in error messages
6. **Documentation** — Document every action with examples
7. **Tests** — Write tests for all actions
8. **Health Check** — Implement health_check() for connectivity testing

## Next Steps

- **[Skill Reference](skill-reference.md)** — Core skill documentation
- **[Agent Configuration](../agents/overview.md)** — Use skills in agents
