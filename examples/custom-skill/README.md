# Custom Skill Example

Learn how to create your own OpenSRE skill.

## What This Demonstrates

Creating a skill that integrates with a custom monitoring system called "MyMonitor".

## Skill Structure

```
custom-skill/
├── SKILL.md           # Documentation
├── skill.yaml         # Metadata
├── actions.py         # Implementation
├── schemas.py         # Data schemas
└── tests/
    └── test_skill.py  # Tests
```

## Setup

### 1. Create Skill Directory

```bash
mkdir -p skills/my-monitor
```

### 2. Define Metadata

Create `skill.yaml`:

```yaml
name: my-monitor
version: 1.0.0
description: Integration with MyMonitor platform

config:
  - name: api_key
    description: MyMonitor API key
    required: true
    env: MYMONITOR_API_KEY
  - name: endpoint
    description: MyMonitor API endpoint
    required: true
    env: MYMONITOR_ENDPOINT

dependencies:
  - httpx>=0.26

permissions:
  read:
    - query
    - get_alerts
  write:
    - create_annotation
  destructive:
    - delete_alert
```

### 3. Implement Actions

Create `actions.py`:

```python
from opensre.skills import Skill, action
import httpx

class MyMonitorSkill(Skill):
    name = "my-monitor"
    
    def __init__(self, config):
        self.api_key = config["api_key"]
        self.endpoint = config["endpoint"]
        self._client = None
    
    async def initialize(self):
        self._client = httpx.AsyncClient(
            base_url=self.endpoint,
            headers={"Authorization": f"Bearer {self.api_key}"}
        )
    
    async def health_check(self) -> bool:
        try:
            r = await self._client.get("/health")
            return r.status_code == 200
        except Exception:
            return False
    
    @action(name="query", description="Query metrics")
    async def query(self, query: str, start: str = "-1h") -> dict:
        response = await self._client.post("/query", json={
            "query": query,
            "start": start
        })
        return response.json()
    
    @action(name="get_alerts", description="Get active alerts")
    async def get_alerts(self, severity: str = None) -> list:
        params = {"severity": severity} if severity else {}
        response = await self._client.get("/alerts", params=params)
        return response.json()["alerts"]
```

### 4. Write Tests

Create `tests/test_skill.py`:

```python
import pytest
from skills.my_monitor.actions import MyMonitorSkill

@pytest.fixture
def skill():
    return MyMonitorSkill({
        "api_key": "test-key",
        "endpoint": "https://api.test"
    })

@pytest.mark.asyncio
async def test_query(skill, mock_client):
    mock_client.post.return_value.json.return_value = {"data": []}
    
    await skill.initialize()
    result = await skill.query("test_metric")
    
    assert "data" in result
```

### 5. Install Skill

```bash
opensre skill install ./skills/my-monitor
```

### 6. Use in Agent

```yaml
# agent.yaml
name: my-agent
skills:
  - my-monitor
  - slack

runbook: |
  1. Query MyMonitor for metrics
  2. Post to Slack
```

## Files

- `skill.yaml` — Skill metadata
- `actions.py` — Skill implementation
- `schemas.py` — Pydantic schemas
- `SKILL.md` — Documentation
- `tests/` — Unit tests
