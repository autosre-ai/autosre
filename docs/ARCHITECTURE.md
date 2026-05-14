# AutoSRE V2 Architecture

> Technical architecture documentation for AutoSRE V2

This document describes the system architecture, component design, data flow, and key implementation decisions.

---

## Table of Contents

- [System Overview](#system-overview)
- [Multi-Agent System](#multi-agent-system)
- [Integration Layer](#integration-layer)
- [Database Schema](#database-schema)
- [API Design](#api-design)
- [Security Model](#security-model)
- [Scalability Considerations](#scalability-considerations)

---

## System Overview

AutoSRE V2 is built as a modular, event-driven system with three main layers:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            PRESENTATION LAYER                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   Web UI     │  │   REST API   │  │   WebSocket  │  │     CLI      │    │
│  │   (React)    │  │   (FastAPI)  │  │   (Events)   │  │   (Typer)    │    │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
├─────────────────────────────────────────────────────────────────────────────┤
│                             BUSINESS LAYER                                   │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │                       Agent Coordinator                             │    │
│  │   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐             │    │
│  │   │  Triage  │ │  K8s     │ │ Metrics  │ │  Logs    │ ... Agents  │    │
│  │   │  Agent   │ │  Agent   │ │  Agent   │ │  Agent   │             │    │
│  │   └──────────┘ └──────────┘ └──────────┘ └──────────┘             │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐               │
│  │  LLM Client    │  │ Knowledge Base │  │  Event System  │               │
│  └────────────────┘  └────────────────┘  └────────────────┘               │
├─────────────────────────────────────────────────────────────────────────────┤
│                           INTEGRATION LAYER                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │  Prometheus  │  │     Loki     │  │  Kubernetes  │  │  Alertmanager│    │
│  │   Client     │  │    Client    │  │    Client    │  │    Webhook   │    │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
├─────────────────────────────────────────────────────────────────────────────┤
│                             DATA LAYER                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                      │
│  │  PostgreSQL  │  │    Redis     │  │  File Store  │                      │
│  │  (Primary)   │  │   (Cache)    │  │  (Reports)   │                      │
│  └──────────────┘  └──────────────┘  └──────────────┘                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Core Components

| Component | Technology | Purpose |
|-----------|------------|---------|
| API Server | FastAPI | REST/WebSocket endpoints, request handling |
| Web UI | React + TypeScript | User interface for investigations |
| CLI | Typer + Rich | Command-line interface |
| Agent Coordinator | Python async | Orchestrates multi-agent workflow |
| LLM Client | OpenAI/Anthropic SDK | Interfaces with language models |
| Database | PostgreSQL + SQLAlchemy | Persistent storage |
| Cache | Redis | Session state, rate limiting |

---

## Multi-Agent System

### Agent Architecture

All agents inherit from `BaseAgent`, which provides:

```python
class BaseAgent(ABC):
    """Abstract base class for investigation agents."""
    
    agent_id: str           # Unique identifier
    agent_name: str         # Human-readable name
    description: str        # What this agent does
    
    # Core capabilities
    tools: ToolRegistry     # Available tools for this agent
    config: AgentConfig     # Runtime configuration
    
    # Abstract methods
    def get_system_prompt(self, investigation: Investigation) -> str: ...
    async def execute(self, investigation: Investigation) -> AgentResult: ...
    
    # Shared implementation
    async def run_react_loop(
        self,
        investigation: Investigation,
        initial_message: str,
        max_iterations: int | None = None,
    ) -> AgentResult:
        """Run the ReAct (Reasoning + Acting) loop."""
```

### Agent Types

#### 1. Triage Agent

**Purpose**: Initial alert classification and routing

```
Input:  Alert (name, severity, labels, annotations)
Output: TriageResult (category, assessed severity, hypotheses, recommended agents)
```

**Process**:
1. Receives alert with raw labels
2. Queries knowledge base for similar incidents
3. Classifies alert category (latency, errors, resources, availability)
4. Assesses true severity (may differ from alert severity)
5. Generates initial hypotheses
6. Recommends which investigation agents to involve

#### 2. Investigation Agents

**Domain-specific agents** that use tools to gather evidence:

| Agent | Domain | Key Tools |
|-------|--------|-----------|
| Kubernetes | Cluster state | `get_pod_status`, `get_pod_events`, `get_deployment_status`, `get_pod_logs`, `get_warning_events` |
| Metrics | Prometheus | `query_metrics`, `query_range`, `get_error_rate`, `get_latency`, `get_resource_usage` |
| Logs | Loki | `query_logs`, `search_errors`, `search_pattern` |
| Traces | Tracing | `search_traces`, `get_trace_details` |

**ReAct Loop**:

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Observe   │────▶│    Think    │────▶│     Act     │
│  (context)  │     │  (reason)   │     │ (use tools) │
└─────────────┘     └─────────────┘     └──────┬──────┘
       ▲                                        │
       │                                        │
       └────────────────────────────────────────┘
                    (iterate until done)
```

#### 3. Remediation Agent

**Purpose**: Generate safe, actionable recommendations

```
Input:  Investigation with findings and confirmed hypotheses
Output: RemediationPlan (immediate actions, follow-ups, preventive measures)
```

**Safety Constraints**:
- NEVER executes actions automatically
- All recommendations require human approval
- Includes rollback procedures for every action
- Risk-levels all recommendations (low/medium/high)

### Coordinator

The `AgentCoordinator` orchestrates the investigation workflow:

```python
class AgentCoordinator:
    """Orchestrates the multi-agent investigation workflow."""
    
    async def start_investigation(
        self,
        alert: dict[str, Any],
        investigation_id: str | None = None,
    ) -> Investigation:
        """
        Main entry point. Orchestrates:
        1. Triage phase
        2. Investigation phase (may iterate)
        3. Analysis/synthesis phase
        4. Remediation recommendation phase
        5. Conclusion generation
        """
```

**State Machine**:

```
                                ┌──────────────────────┐
                                │       PENDING        │
                                └──────────┬───────────┘
                                           │ start
                                           ▼
                                ┌──────────────────────┐
                                │      TRIAGING        │
                                └──────────┬───────────┘
                                           │ triage_complete
                                           ▼
                    ┌──────────────────────────────────────────────┐
                    │                INVESTIGATING                  │
                    │   (agents run in parallel with semaphore)     │
                    └──────────┬───────────────────────┬───────────┘
                               │                       │
                   observations_collected        agent_failed
                               │                       │
                               ▼                       ▼
                    ┌──────────────────────┐   ┌─────────────┐
                    │      ANALYZING       │   │   FAILED    │
                    └──────────┬───────────┘   └─────────────┘
                               │
              ┌────────────────┼────────────────┐
              │ analysis_complete        need_more_data
              │                                 │
              ▼                                 │
    ┌──────────────────────┐                    │
    │    RECOMMENDING      │                    │
    └──────────┬───────────┘                    │
               │                                │
               ▼                                │
    ┌──────────────────────┐                    │
    │      COMPLETED       │◀───────────────────┘
    └──────────────────────┘       (after max iterations)
```

### Tool System

Tools are registered with JSON Schema definitions:

```python
self.tools.register(
    name="get_pod_status",
    description="Get status of pods for a service",
    parameters={
        "type": "object",
        "properties": {
            "service": {"type": "string", "description": "Service/app name"},
            "namespace": {"type": "string", "description": "Kubernetes namespace"},
        },
        "required": ["service", "namespace"],
    },
    handler=self._tool_get_pod_status,
)
```

**Tool Execution Flow**:

1. LLM generates tool call with arguments
2. `ToolRegistry` validates and routes to handler
3. Handler executes (async or sync)
4. Result returned to LLM as tool response
5. Duplicate detection prevents repeated identical calls

---

## Integration Layer

### Client Architecture

All integration clients follow a consistent pattern:

```python
class PrometheusClient:
    """Prometheus integration client."""
    
    def __init__(
        self,
        url: str | None = None,
        timeout: int = 30,
    ):
        self.url = url or get_config().integrations.prometheus.url
        self.timeout = timeout
        self._session: aiohttp.ClientSession | None = None
    
    async def query(self, query: str) -> list[MetricResult]:
        """Execute instant query."""
        ...
    
    async def query_range(
        self,
        query: str,
        duration: timedelta,
        step: str = "1m",
    ) -> RangeQueryResult:
        """Execute range query."""
        ...
```

### Integration Map

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                             AutoSRE V2                                       │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     Integration Layer                                │   │
│  │                                                                      │   │
│  │  ┌──────────────────┐                    ┌──────────────────┐       │   │
│  │  │ PrometheusClient │─────PromQL────────▶│   Prometheus     │       │   │
│  │  │                  │◀────Metrics────────│     Server       │       │   │
│  │  └──────────────────┘                    └──────────────────┘       │   │
│  │                                                                      │   │
│  │  ┌──────────────────┐                    ┌──────────────────┐       │   │
│  │  │   LokiClient     │─────LogQL─────────▶│      Loki        │       │   │
│  │  │                  │◀────Logs───────────│     Server       │       │   │
│  │  └──────────────────┘                    └──────────────────┘       │   │
│  │                                                                      │   │
│  │  ┌──────────────────┐                    ┌──────────────────┐       │   │
│  │  │KubernetesClient  │─────K8s API───────▶│   Kubernetes     │       │   │
│  │  │                  │◀────Resources──────│     Cluster      │       │   │
│  │  └──────────────────┘                    └──────────────────┘       │   │
│  │                                                                      │   │
│  │  ┌──────────────────┐                    ┌──────────────────┐       │   │
│  │  │ AlertWebhook     │◀────Webhook────────│  Alertmanager    │       │   │
│  │  │                  │                    │    PagerDuty     │       │   │
│  │  └──────────────────┘                    └──────────────────┘       │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Prometheus Integration

```python
# Core capabilities
await client.query("up{job='api-server'}")
await client.query_range("rate(http_requests_total[5m])", duration=timedelta(hours=1))
await client.get_error_rate("payment-service", "5m")
await client.get_latency_percentile("payment-service", 0.99, "5m")
await client.get_resource_usage(pod_pattern="api-.*", namespace="production")
```

### Kubernetes Integration

```python
# Pod operations
pods = await client.list_pods(namespace="production", label_selector="app=api")
events = await client.get_pod_events("api-pod-xyz", "production")
logs = await client.get_pod_logs("api-pod-xyz", "production", tail_lines=100)

# Deployment operations
deploy = await client.get_deployment("api-gateway", "production")
events = await client.get_events(namespace="production", warning_only=True)
```

### Loki Integration

```python
# Log queries
result = await client.query('{app="payment-service"} |= "error"', duration="1h")
errors = await client.search_errors(service="payment-service", duration="1h")
matches = await client.query_service(service="api", pattern="timeout", duration="30m")
```

---

## Database Schema

### Core Entities

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                               DATABASE SCHEMA                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────┐         ┌─────────────────┐                            │
│  │     alerts      │         │ investigations  │                            │
│  ├─────────────────┤         ├─────────────────┤                            │
│  │ id (PK)         │────────▶│ id (PK)         │                            │
│  │ name            │         │ alert_id (FK)   │                            │
│  │ severity        │         │ status          │                            │
│  │ source          │         │ title           │                            │
│  │ fingerprint     │         │ objective       │                            │
│  │ labels (JSON)   │         │ started_at      │                            │
│  │ annotations     │         │ completed_at    │                            │
│  │ status          │         │ llm_calls       │                            │
│  │ created_at      │         │ total_tokens    │                            │
│  │ resolved_at     │         │ result (JSON)   │                            │
│  └─────────────────┘         └────────┬────────┘                            │
│                                       │                                      │
│                    ┌──────────────────┼──────────────────┐                  │
│                    │                  │                  │                  │
│                    ▼                  ▼                  ▼                  │
│         ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐        │
│         │  observations   │ │   hypotheses    │ │    findings     │        │
│         ├─────────────────┤ ├─────────────────┤ ├─────────────────┤        │
│         │ id (PK)         │ │ id (PK)         │ │ id (PK)         │        │
│         │ investigation_id│ │ investigation_id│ │ investigation_id│        │
│         │ type            │ │ status          │ │ title           │        │
│         │ source          │ │ statement       │ │ description     │        │
│         │ query           │ │ reasoning       │ │ severity        │        │
│         │ data (JSON)     │ │ confidence      │ │ confidence      │        │
│         │ is_anomalous    │ │ tested_by       │ │ agent_id        │        │
│         │ observed_at     │ │ proposed_at     │ │ evidence (JSON) │        │
│         └─────────────────┘ └─────────────────┘ └─────────────────┘        │
│                                                                              │
│         ┌─────────────────┐ ┌─────────────────┐                             │
│         │    actions      │ │ knowledge_base  │                             │
│         ├─────────────────┤ ├─────────────────┤                             │
│         │ id (PK)         │ │ id (PK)         │                             │
│         │ investigation_id│ │ type            │                             │
│         │ type            │ │ title           │                             │
│         │ description     │ │ content         │                             │
│         │ command         │ │ service         │                             │
│         │ risk_level      │ │ alert_pattern   │                             │
│         │ status          │ │ tags (JSON)     │                             │
│         │ approved_by     │ │ embedding       │                             │
│         │ executed_at     │ │ created_at      │                             │
│         └─────────────────┘ └─────────────────┘                             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Models

```python
class Investigation(Base):
    __tablename__ = "investigations"
    
    id: Mapped[UUID] = mapped_column(primary_key=True)
    alert_id: Mapped[UUID] = mapped_column(ForeignKey("alerts.id"))
    status: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(500))
    objective: Mapped[str | None] = mapped_column(Text)
    
    # Timing
    started_at: Mapped[datetime] = mapped_column(default=func.now())
    completed_at: Mapped[datetime | None]
    
    # Metrics
    llm_calls: Mapped[int] = mapped_column(default=0)
    total_tokens: Mapped[int] = mapped_column(default=0)
    
    # Result (JSON blob)
    result: Mapped[dict | None] = mapped_column(JSON)
    
    # Relationships
    alert: Mapped["Alert"] = relationship(back_populates="investigations")
    observations: Mapped[list["Observation"]] = relationship()
    hypotheses: Mapped[list["Hypothesis"]] = relationship()
    findings: Mapped[list["Finding"]] = relationship()
    actions: Mapped[list["Action"]] = relationship()
```

### Migrations

Using Alembic for database migrations:

```bash
# Create new migration
alembic revision --autogenerate -m "Add actions table"

# Run migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

---

## API Design

### REST API Structure

```
/api/v1/
├── /alerts                    # Alert management
│   ├── GET /                  # List alerts
│   ├── POST /                 # Create alert
│   ├── GET /{id}              # Get alert
│   ├── PATCH /{id}            # Update alert
│   ├── DELETE /{id}           # Delete alert
│   ├── POST /{id}/investigate # Trigger investigation
│   ├── POST /{id}/acknowledge # Acknowledge alert
│   └── POST /{id}/resolve     # Resolve alert
│
├── /investigations            # Investigation management
│   ├── GET /                  # List investigations
│   ├── GET /{id}              # Get investigation
│   ├── GET /{id}/timeline     # Get timeline
│   ├── GET /{id}/steps        # Get execution steps
│   ├── GET /{id}/logs         # Stream logs (SSE)
│   ├── POST /{id}/action      # Execute action
│   ├── POST /{id}/cancel      # Cancel investigation
│   └── POST /{id}/retry       # Retry failed investigation
│
├── /webhooks                  # External webhooks
│   ├── POST /alertmanager     # Alertmanager webhook
│   ├── POST /pagerduty        # PagerDuty webhook
│   └── POST /generic          # Generic webhook
│
├── /chat                      # Chat interface
│   ├── POST /                 # Send message
│   └── GET /history/{id}      # Get chat history
│
├── /runbooks                  # Runbook management
│   ├── GET /                  # List runbooks
│   ├── POST /                 # Create runbook
│   ├── GET /{id}              # Get runbook
│   └── POST /{id}/execute     # Execute runbook
│
└── /health                    # Health check
    └── GET /                  # System health
```

### WebSocket Events

Real-time updates via WebSocket:

```javascript
const ws = new WebSocket('ws://localhost:8000/api/v1/ws');

// Event types
{
  type: 'state_changed',
  investigation_id: 'inv_abc123',
  data: {
    from_state: 'triaging',
    to_state: 'investigating',
    event: 'triage_complete'
  }
}
```

### Event Types

| Event | Description |
|-------|-------------|
| `state_changed` | Investigation state transition |
| `triage_started` | Triage phase started |
| `triage_completed` | Triage phase completed |
| `investigation_started` | Investigation phase started |
| `agent_started` | Individual agent started |
| `agent_completed` | Individual agent completed |
| `agent_failed` | Individual agent failed |
| `investigation_completed` | Investigation phase completed |
| `analysis_started` | Analysis/synthesis started |
| `analysis_completed` | Analysis completed |
| `remediation_started` | Remediation planning started |
| `remediation_completed` | Remediation planning completed |
| `action_approved` | Remediation action approved |
| `action_executed` | Remediation action executed |
| `completed` | Investigation completed |
| `failed` | Investigation failed |
| `timeout_warning` | Approaching timeout |
| `retry_attempted` | Retry attempt |
| `error_occurred` | Error during execution |

---

## Security Model

### Authentication

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           AUTHENTICATION FLOW                                │
│                                                                              │
│   ┌────────┐    ┌────────────┐    ┌────────────┐    ┌────────────┐         │
│   │ Client │───▶│  API GW    │───▶│   Auth     │───▶│  AutoSRE   │         │
│   │        │    │            │    │  Middleware │   │    API     │         │
│   └────────┘    └────────────┘    └────────────┘    └────────────┘         │
│       │                                 │                                    │
│       │         JWT Token               │                                    │
│       └─────────────────────────────────┘                                    │
│                                                                              │
│   Supported Methods:                                                         │
│   • JWT Bearer tokens                                                        │
│   • API keys (for webhooks)                                                  │
│   • OAuth2 (optional)                                                        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Authorization

Role-based access control (RBAC):

| Role | Permissions |
|------|-------------|
| `viewer` | Read investigations, alerts |
| `operator` | + Acknowledge alerts, approve actions |
| `admin` | + Create/delete alerts, manage runbooks |
| `system` | + Webhook access, system configuration |

### Secret Management

```yaml
# Kubernetes secrets
apiVersion: v1
kind: Secret
metadata:
  name: autosre-secrets
type: Opaque
data:
  OPENAI_API_KEY: <base64>
  DATABASE_URL: <base64>
  SECRET_KEY: <base64>
```

### Webhook Security

```python
def verify_alertmanager_signature(
    payload: bytes,
    signature: str,
    secret: str,
) -> bool:
    """Verify HMAC-SHA256 signature."""
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)
```

---

## Scalability Considerations

### Horizontal Scaling

```
                    ┌─────────────────┐
                    │  Load Balancer  │
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│   API Server    │ │   API Server    │ │   API Server    │
│   (Replica 1)   │ │   (Replica 2)   │ │   (Replica N)   │
└────────┬────────┘ └────────┬────────┘ └────────┬────────┘
         │                   │                   │
         └───────────────────┼───────────────────┘
                             │
                    ┌────────▼────────┐
                    │     Redis       │
                    │ (Session Store) │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │   PostgreSQL    │
                    │   (Primary)     │
                    └─────────────────┘
```

### Bottleneck Mitigation

| Bottleneck | Mitigation |
|------------|------------|
| LLM API rate limits | Request queuing, caching, multiple API keys |
| Database connections | Connection pooling, read replicas |
| Agent execution | Parallel execution with semaphore |
| Large investigations | Pagination, streaming results |

### Caching Strategy

```python
# Redis caching for:
# - Investigation state (during execution)
# - LLM response caching (for identical queries)
# - Knowledge base embeddings
# - Rate limit counters

CACHE_TTL = {
    "investigation_state": 3600,      # 1 hour
    "llm_response": 300,              # 5 minutes  
    "knowledge_embedding": 86400,     # 1 day
    "rate_limit": 60,                 # 1 minute
}
```

### Monitoring

Key metrics to monitor:

```yaml
# Prometheus metrics exposed at /metrics
autosre_investigations_total{status="completed|failed|timeout"}
autosre_investigation_duration_seconds{quantile="0.5|0.9|0.99"}
autosre_agent_duration_seconds{agent="triage|kubernetes|metrics|logs"}
autosre_llm_calls_total{provider="openai|anthropic"}
autosre_llm_tokens_total{type="input|output"}
autosre_tool_calls_total{tool="query_metrics|get_pod_status|..."}
autosre_tool_errors_total{tool="..."}
```

---

## Directory Structure

```
autosre-v2/
├── src/autosre/                # Main Python package
│   ├── agents/                 # Agent implementations
│   │   ├── base_agent.py       # Base class
│   │   ├── coordinator.py      # Orchestration
│   │   ├── triage_agent.py     # Triage
│   │   ├── investigation_agent.py  # Investigation
│   │   ├── remediation_agent.py    # Remediation
│   │   ├── state.py            # State machine
│   │   └── prompts.py          # LLM prompts
│   │
│   ├── api/                    # FastAPI application
│   │   ├── app.py              # Application factory
│   │   ├── routes/             # API routes
│   │   ├── schemas/            # Pydantic schemas
│   │   └── middleware/         # Auth, logging
│   │
│   ├── cli/                    # Typer CLI
│   │   ├── main.py             # Entry point
│   │   ├── investigate.py      # Investigation commands
│   │   ├── alerts.py           # Alert commands
│   │   ├── chat.py             # Chat interface
│   │   └── config.py           # Configuration
│   │
│   ├── core/                   # Core types
│   │   ├── alert.py            # Alert models
│   │   ├── investigation.py    # Investigation models
│   │   ├── llm_client.py       # LLM abstraction
│   │   └── knowledge_base.py   # Knowledge base
│   │
│   ├── integrations/           # External integrations
│   │   ├── prometheus.py       # Prometheus client
│   │   ├── loki.py             # Loki client
│   │   └── kubernetes.py       # Kubernetes client
│   │
│   └── utils/                  # Utilities
│       ├── config.py           # Configuration
│       ├── logging.py          # Structured logging
│       └── cache.py            # Redis caching
│
├── web-ui/                     # React frontend
│   └── src/
│       ├── components/         # UI components
│       ├── hooks/              # React hooks
│       ├── pages/              # Page components
│       └── store/              # Redux store
│
├── tests/                      # Test suite
│   ├── unit/                   # Unit tests
│   ├── integration/            # Integration tests
│   └── e2e/                    # End-to-end tests
│
├── deploy/                     # Deployment configs
│   ├── kubernetes/             # K8s manifests
│   └── helm/                   # Helm chart
│
└── docs/                       # Documentation
```

---

## Next Steps

- [API.md](./API.md) — Complete API documentation
- [CLI.md](./CLI.md) — CLI reference
- [AGENTS.md](./AGENTS.md) — Agent system deep dive
