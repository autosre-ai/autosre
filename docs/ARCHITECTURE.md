# AutoSRE Architecture

This document explains how AutoSRE works internally.

## Overview

AutoSRE follows a **foundation-first** architecture:

```
┌────────────────────────────────────────────────────────────────┐
│                        User Interface                          │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐           │
│  │   CLI   │  │   API   │  │  Slack  │  │ PagerD. │           │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘           │
└───────┴────────────┴────────────┴────────────┴────────────────┘
                              │
┌─────────────────────────────┴──────────────────────────────────┐
│                          Agent                                  │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   Observer   │  │   Reasoner   │  │    Actor     │         │
│  │              │  │              │  │              │         │
│  │ • Alerts     │──│ • Analysis   │──│ • Execute    │         │
│  │ • Metrics    │  │ • Correlation│  │ • Verify     │         │
│  │ • Logs       │  │ • Runbooks   │  │ • Guardrails │         │
│  │ • Changes    │  │ • LLM        │  │ • Audit      │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│                              │                                  │
└──────────────────────────────┴──────────────────────────────────┘
                               │
┌──────────────────────────────┴──────────────────────────────────┐
│                       Context Store                             │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Services  │  Ownership  │  Changes  │  Runbooks  │ Alerts │ │
│  └────────────────────────────────────────────────────────────┘ │
│                              │                                   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                       Connectors                             ││
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌──────────┐ ││
│  │  │Kubernetes │  │Prometheus │  │  GitHub   │  │  Slack   │ ││
│  │  └───────────┘  └───────────┘  └───────────┘  └──────────┘ ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

## Core Principles

### 1. Foundation First

The **Context Store** is the foundation. Without accurate context, LLMs produce unreliable recommendations.

**Before AutoSRE makes any decision, it:**
1. Knows what services exist
2. Understands their dependencies
3. Tracks recent changes
4. Has relevant runbooks loaded
5. Correlates with past incidents

### 2. Observer-Reasoner-Actor Pattern

Based on the OODA loop (Observe, Orient, Decide, Act), adapted for SRE:

| Component | Role | Outputs |
|-----------|------|---------|
| **Observer** | Watch for signals | Alerts, anomalies, changes |
| **Reasoner** | Analyze and correlate | Root cause, confidence, recommendations |
| **Actor** | Execute safely | Actions, verifications, rollbacks |

### 3. Guardrails Everywhere

Every automated action passes through guardrails:
- **Approval workflows** for risky operations
- **Blast radius checks** before execution
- **Automatic rollback** on failures
- **Audit logging** for compliance

---

## Components

### Context Store

The single source of truth for infrastructure state.

**Data Model:**

```python
# Services and topology
class Service:
    name: str
    namespace: str
    cluster: str
    dependencies: list[str]
    status: ServiceStatus
    replicas: int

# Ownership and on-call
class Ownership:
    service_name: str
    team: str
    slack_channel: str
    oncall_email: str

# Changes and deployments
class ChangeEvent:
    service_name: str
    change_type: ChangeType
    description: str
    author: str
    timestamp: datetime

# Runbooks
class Runbook:
    id: str
    title: str
    alert_names: list[str]
    steps: list[dict]
    automated: bool

# Alerts and incidents
class Alert:
    name: str
    severity: Severity
    service_name: str
    summary: str
```

**Storage:** SQLite database at `~/.autosre/context.db`

**Sync Sources:**
- Kubernetes (services, pods, deployments)
- Prometheus (alerts, metrics)
- GitHub (PRs, deployments, commits)
- Manual entry via CLI

### Connectors

Adapters for external systems:

```
┌─────────────────┐
│ Base Connector  │
├─────────────────┤
│ + connect()     │
│ + disconnect()  │
│ + sync()        │
│ + health()      │
└─────────────────┘
        △
        │
┌───────┴────────┬──────────────┬─────────────┐
│                │              │             │
┌──────────────┐ ┌────────────┐ ┌───────────┐ ┌──────────┐
│  Kubernetes  │ │ Prometheus │ │  GitHub   │ │  Slack   │
└──────────────┘ └────────────┘ └───────────┘ └──────────┘
```

Each connector:
1. Connects to its external system
2. Syncs data into the Context Store
3. Handles failures gracefully
4. Supports health checks

### Observer

Watches for signals that require attention:

**Alert Watcher:**
- Polls Prometheus/Alertmanager for firing alerts
- Deduplicates and prioritizes
- Triggers analysis when thresholds exceeded

**Metric Analyzer:**
- Detects anomalies in time series
- Identifies correlations across services
- Tracks SLO/SLI violations

**Log Correlator:**
- Searches logs for error patterns
- Correlates across services
- Extracts relevant context

**Change Detector:**
- Monitors for recent deployments
- Tracks config changes
- Identifies potentially risky changes

### Reasoner

The LLM-powered analysis engine:

```python
class Reasoner:
    async def analyze(self, alert: Alert) -> Analysis:
        # 1. Gather context
        context = self.gather_context(alert)
        
        # 2. Find relevant runbooks
        runbooks = self.find_runbooks(alert)
        
        # 3. Check recent changes
        changes = self.get_recent_changes(alert.service_name)
        
        # 4. Build prompt with context
        prompt = self.build_prompt(alert, context, runbooks, changes)
        
        # 5. Call LLM
        response = await self.llm.generate(prompt)
        
        # 6. Parse and validate
        analysis = self.parse_response(response)
        
        return analysis
```

**Analysis Output:**

```python
class Analysis:
    root_cause: str
    confidence: float  # 0.0 - 1.0
    affected_services: list[str]
    related_changes: list[ChangeEvent]
    recommended_runbook: Optional[Runbook]
    suggested_actions: list[Action]
    reasoning: str
```

**LLM Providers:**

| Provider | Model | Use Case |
|----------|-------|----------|
| Ollama | llama3.1:8b | Local, privacy-focused |
| OpenAI | gpt-4o-mini | High accuracy, cloud |
| Anthropic | claude-3.5-sonnet | Reasoning tasks |
| Azure | gpt-4 | Enterprise, compliance |

### Actor

Executes remediation with safety:

```python
class Actor:
    async def execute(self, action: Action) -> ActionResult:
        # 1. Check guardrails
        if not self.guardrails.approve(action):
            return ActionResult(status="blocked", reason="Guardrail violation")
        
        # 2. Request approval if needed
        if action.requires_approval:
            approved = await self.request_approval(action)
            if not approved:
                return ActionResult(status="rejected")
        
        # 3. Execute with rollback support
        try:
            result = await self.execute_with_rollback(action)
        except Exception as e:
            await self.rollback(action)
            raise
        
        # 4. Verify success
        if not await self.verify(action):
            await self.rollback(action)
            return ActionResult(status="failed", reason="Verification failed")
        
        # 5. Log for audit
        self.audit_log.record(action, result)
        
        return result
```

**Guardrails:**

| Check | Description |
|-------|-------------|
| **Blast Radius** | Limits how many pods/services affected |
| **Tier Protection** | Higher tiers require approval |
| **Time Windows** | Blocks actions during sensitive periods |
| **Rate Limiting** | Prevents runaway automation |
| **Dry Run** | Simulates before executing |

---

## Data Flow

### Alert Analysis Flow

```
Alert Fires
     │
     ▼
┌─────────────┐
│  Observer   │ ← Polls Alertmanager
└─────────────┘
     │
     ▼
┌─────────────┐
│ Context     │ ← Enriches with topology, ownership, changes
│ Gathering   │
└─────────────┘
     │
     ▼
┌─────────────┐
│  Reasoner   │ ← LLM analysis with context
└─────────────┘
     │
     ▼
┌─────────────┐
│  Analysis   │ → Root cause, confidence, recommendations
│  Output     │
└─────────────┘
     │
     ▼
┌─────────────┐
│  Actor      │ → Execute remediation (with approval)
└─────────────┘
     │
     ▼
┌─────────────┐
│  Feedback   │ ← Human confirms correctness
│  Loop       │
└─────────────┘
```

### Context Sync Flow

```
External System
     │
     ▼
┌─────────────┐
│ Connector   │ ← Adapts to system API
└─────────────┘
     │
     ▼
┌─────────────┐
│ Transform   │ ← Normalizes to AutoSRE models
└─────────────┘
     │
     ▼
┌─────────────┐
│ Context     │ ← Upserts into SQLite
│ Store       │
└─────────────┘
```

---

## Evaluation Framework

The eval framework measures agent accuracy against synthetic incidents:

```
┌────────────────────────────────────────────────────────┐
│                   Scenario YAML                        │
│  ┌───────────────────────────────────────────────────┐ │
│  │ - alert: {...}                                    │ │
│  │ - services: [...]                                 │ │
│  │ - changes: [...]                                  │ │
│  │ - expected_root_cause: "..."                      │ │
│  │ - expected_service: "..."                         │ │
│  └───────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────┐
│                  Evaluation Runner                      │
│  1. Load scenario                                       │
│  2. Inject context into store                           │
│  3. Run agent analysis                                  │
│  4. Compare output to expected                          │
│  5. Calculate metrics                                   │
└────────────────────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────┐
│                  Metrics Output                         │
│  - time_to_root_cause: 12.3s                           │
│  - root_cause_correct: true                            │
│  - service_correct: true                               │
│  - accuracy: 85%                                       │
└────────────────────────────────────────────────────────┘
```

---

## Directory Structure

```
autosre/
├── agent/               # Observer, Reasoner, Actor
│   ├── observer.py
│   ├── reasoner.py
│   ├── actor.py
│   └── guardrails.py
├── cli/                 # CLI commands
│   ├── main.py
│   └── commands/
├── evals/               # Evaluation framework
│   ├── framework.py
│   ├── metrics.py
│   └── scenarios/       # YAML scenario files
├── feedback/            # Feedback loop
├── foundation/          # Core data layer
│   ├── context_store.py
│   ├── models.py
│   └── connectors/
├── sandbox/             # Test environment
│   ├── cluster.py
│   ├── chaos.py
│   └── observability.py
└── config.py            # Configuration
```

---

## Extension Points

### Adding a New Connector

1. Create connector in `autosre/foundation/connectors/`
2. Implement `BaseConnector` interface
3. Register in connector factory
4. Add CLI sync option

### Adding a New LLM Provider

1. Create adapter in `autosre/agent/llm/`
2. Implement `LLMProvider` interface
3. Add to config options
4. Update CLI model selection

### Adding a New Scenario

1. Create YAML in `autosre/evals/scenarios/`
2. Define alert, services, changes
3. Specify expected outcomes
4. Run with `autosre eval run`

---

## Security Considerations

### Data Protection
- Context store is local SQLite (no cloud)
- API keys stored in environment variables
- Sensitive data can be excluded from context

### Action Safety
- All remediation requires approval by default
- Guardrails prevent dangerous operations
- Audit logging for compliance

### LLM Privacy
- Ollama option for fully local inference
- No training on customer data
- Prompts don't include secrets

---

## Performance

### Context Store
- SQLite handles millions of records
- Indexes on common queries
- Incremental sync for efficiency

### LLM Calls
- Response caching (configurable TTL)
- Retry with exponential backoff
- Timeout handling

### Connectors
- Async I/O for parallel sync
- Rate limiting per external API
- Graceful degradation
