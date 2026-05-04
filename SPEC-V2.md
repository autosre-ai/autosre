# AutoSRE v2 Specification

## Overview

AutoSRE v2 is a world-class, open-source AI SRE agent that investigates production incidents autonomously. It combines the simplicity of our current foundation-first approach with the best ideas from OpenSRE (episodic memory, knowledge graph, multi-agent investigation).

**Design Philosophy:** Simple but world-class. Every feature must earn its place.

## What We're Stealing from OpenSRE

| Feature | OpenSRE Implementation | AutoSRE v2 Approach |
|---------|------------------------|---------------------|
| **Episodic Memory** | PostgreSQL + config-service | SQLite local-first (simpler) |
| **Knowledge Graph** | Neo4j service topology | YAML-based topology (no extra infra) |
| **Multi-Agent** | LangGraph Send() fan-out | Parallel async subagents |
| **Strategy Generation** | LLM from past episodes | Same, but cached in SQLite |
| **Skill System** | 46 skills via config | Modular skill files (Python) |
| **Investigation Loop** | planner → subagents → synthesizer | Same pattern, cleaner code |

## What We're Keeping (Our Advantages)

| Feature | Why It's Better |
|---------|-----------------|
| **Evaluation Suite** | 25+ scenarios - prove accuracy before prod |
| **Safe Remediation** | Approval workflows (enterprise-ready) |
| **Runbook Integration** | Not just RCA, but guided execution |
| **Local-First** | No Neo4j/Postgres required to start |
| **Single Binary** | `pip install autosre` and go |

## Goals

- [ ] Investigation memory that learns from past incidents
- [ ] Multi-agent parallel investigation (K8s, metrics, logs, traces)
- [ ] Strategy generation from similar past incidents
- [ ] Service topology awareness (blast radius)
- [ ] 45 min → 5 min investigation time
- [ ] Zero external dependencies required to start
- [ ] Progressive enhancement (add Neo4j/Postgres later if needed)

## Non-Goals

- Not replacing commercial tools like Rootly or PagerDuty
- Not building a web UI (initially) - CLI-first
- Not supporting every possible integration - focus on top 10

## Architecture

```
                       CLI / API / Slack
                             │
                    ┌────────┴────────┐
                    │    AutoSRE      │
                    │   Orchestrator  │
                    └────────┬────────┘
                             │
        ┌──────────┬────────┴─────────┬──────────┐
        ↓          ↓                  ↓          ↓
   ┌─────────┐ ┌─────────┐      ┌─────────┐ ┌─────────┐
   │ Memory  │ │Topology │      │ Planner │ │  LLM    │
   │ (SQLite)│ │  (YAML) │      │  Agent  │ │ Router  │
   └─────────┘ └─────────┘      └────┬────┘ └─────────┘
                                     │
                    ┌────────┬───────┴───────┬────────┐
                    ↓        ↓               ↓        ↓
              ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
              │   K8s    │ │ Metrics  │ │   Logs   │ │  Traces  │
              │ Subagent │ │ Subagent │ │ Subagent │ │ Subagent │
              └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘
                   └──────┬─────┴────────────┴──────┬─────┘
                          │                         │
                    ┌─────┴────┐              ┌─────┴────┐
                    │Synthesizer│             │  Writeup │
                    └──────────┘              └──────────┘
```

## Core Components

### 1. Episodic Memory (NEW)

Store every investigation for future reference.

**Schema (SQLite):**
```sql
CREATE TABLE episodes (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    alert_type TEXT NOT NULL,
    service_name TEXT,
    severity TEXT,
    root_cause TEXT,
    summary TEXT,
    resolved BOOLEAN,
    effectiveness_score REAL,
    skills_used TEXT,  -- JSON array
    key_findings TEXT,  -- JSON array
    duration_seconds INTEGER
);

CREATE INDEX idx_episodes_alert ON episodes(alert_type);
CREATE INDEX idx_episodes_service ON episodes(service_name);

CREATE TABLE strategies (
    id TEXT PRIMARY KEY,
    alert_type TEXT NOT NULL,
    service_name TEXT,
    strategy_text TEXT NOT NULL,
    source_episode_ids TEXT,  -- JSON array
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**API:**
```python
class EpisodicMemory:
    def search_similar(alert: str, service: str, limit: int = 3) -> List[Episode]
    def store_episode(episode: Episode) -> None
    def get_or_generate_strategy(alert_type: str, service: str) -> Optional[str]
```

### 2. Service Topology (NEW)

YAML-based service dependencies (no Neo4j required).

**topology.yaml:**
```yaml
services:
  checkout-service:
    dependencies:
      - payment-service
      - inventory-service
      - user-service
    owners:
      - team-checkout
    alerts:
      - checkout-5xx
      - checkout-latency
    runbooks:
      - runbooks/checkout-debug.md
      
  payment-service:
    dependencies:
      - stripe-gateway
      - fraud-service
    owners:
      - team-payments
```

**API:**
```python
class ServiceTopology:
    def get_dependencies(service: str) -> List[str]
    def get_blast_radius(service: str) -> List[str]  # Reverse dependencies
    def get_runbooks(service: str) -> List[Path]
    def get_owners(service: str) -> List[str]
```

### 3. Multi-Agent Investigation (NEW)

Parallel subagents for different investigation domains.

**Subagents:**
| Agent | Skills | Data Sources |
|-------|--------|--------------|
| `kubernetes` | pod_logs, describe, events, exec | kubectl |
| `metrics` | query_prometheus, anomaly_detect | Prometheus/VictoriaMetrics |
| `logs` | search_logs, tail_logs, grep | Loki/Elasticsearch/Datadog |
| `traces` | find_traces, latency_breakdown | Jaeger/Tempo/Datadog |
| `changes` | recent_deploys, config_diffs | Git/ArgoCD/Flux |

**Investigation Flow:**
1. `init_context` - Parse alert, load topology, check memory
2. `memory_lookup` - Find similar past incidents
3. `planner` - Generate hypotheses, select subagents
4. `subagents` (parallel) - Execute skills, gather evidence
5. `synthesizer` - Combine findings, decide if complete
6. `writeup` - Generate final report
7. `memory_store` - Save episode for future

### 4. Skill System (ENHANCED)

Modular, composable skills.

**Skill Structure:**
```
skills/
├── kubernetes/
│   ├── __init__.py
│   ├── skill.yaml        # Metadata
│   ├── pod_logs.py
│   ├── describe.py
│   └── events.py
├── metrics/
│   ├── skill.yaml
│   ├── query.py
│   └── anomaly.py
└── logs/
    ├── skill.yaml
    └── search.py
```

**skill.yaml:**
```yaml
name: kubernetes
description: Kubernetes cluster investigation
requires:
  - kubectl
skills:
  - name: pod_logs
    description: Get logs from a pod
    parameters:
      - name: pod
        type: string
        required: true
      - name: namespace
        type: string
        default: default
      - name: lines
        type: int
        default: 100
  - name: describe
    description: Describe a Kubernetes resource
    parameters:
      - name: resource
        type: string
        required: true
```

### 5. LLM Router (ENHANCED)

Support multiple LLM providers with fallback.

**Config:**
```yaml
llm:
  primary:
    provider: anthropic
    model: claude-sonnet-4-20250514
  fallback:
    provider: openai
    model: gpt-4o
  local:
    provider: ollama
    model: llama3.1:8b
```

## CLI Interface

```bash
# Investigate an alert
autosre investigate "checkout-service 5xx spike"

# With service hint
autosre investigate "5xx spike" --service checkout-service

# Interactive mode
autosre investigate --interactive

# Show investigation history
autosre history
autosre history --service checkout-service

# Show memory stats
autosre memory stats

# Search past investigations
autosre memory search "payment timeout"

# Manage topology
autosre topology show
autosre topology validate
autosre topology add-service --name new-service

# Run in server mode (for Slack/API)
autosre serve --port 8001

# Evaluate against test scenarios
autosre eval --scenarios tests/scenarios/
```

## Directory Structure

```
autosre/
├── src/
│   └── autosre/
│       ├── __init__.py
│       ├── cli.py              # Typer CLI
│       ├── config.py           # Settings
│       ├── orchestrator.py     # Main investigation flow
│       ├── memory/
│       │   ├── __init__.py
│       │   ├── episodic.py     # Episode storage
│       │   └── strategy.py     # Strategy generation
│       ├── topology/
│       │   ├── __init__.py
│       │   └── service.py      # Service graph
│       ├── agents/
│       │   ├── __init__.py
│       │   ├── planner.py
│       │   ├── synthesizer.py
│       │   ├── writeup.py
│       │   └── subagents/
│       │       ├── kubernetes.py
│       │       ├── metrics.py
│       │       ├── logs.py
│       │       └── traces.py
│       ├── skills/
│       │   ├── __init__.py
│       │   ├── loader.py
│       │   └── registry.py
│       ├── llm/
│       │   ├── __init__.py
│       │   └── router.py
│       └── reporters/
│           ├── __init__.py
│           ├── terminal.py
│           └── slack.py
├── skills/                     # Built-in skills
│   ├── kubernetes/
│   ├── metrics/
│   ├── logs/
│   └── traces/
├── tests/
│   ├── scenarios/              # Evaluation scenarios
│   ├── unit/
│   └── integration/
├── examples/
│   ├── topology.yaml
│   └── config.yaml
├── docs/
├── pyproject.toml
├── README.md
└── Makefile
```

## Acceptance Criteria

### Phase 1: Core (Week 1)
- [ ] SQLite episodic memory working
- [ ] YAML topology loading
- [ ] Basic CLI investigate command
- [ ] Single-agent investigation (no parallelism yet)

### Phase 2: Multi-Agent (Week 2)
- [ ] Planner agent with hypothesis generation
- [ ] Parallel subagent execution
- [ ] Synthesizer combining evidence
- [ ] Memory storage after investigation

### Phase 3: Skills (Week 3)
- [ ] Skill loader from YAML
- [ ] Kubernetes skills (pod_logs, describe, events)
- [ ] Metrics skills (query_prometheus)
- [ ] Logs skills (search_logs)

### Phase 4: Polish (Week 4)
- [ ] Strategy generation from past episodes
- [ ] Evaluation framework
- [ ] Documentation
- [ ] PyPI publish

## Open Questions

1. **LangGraph vs Plain AsyncIO?**
   - LangGraph: More structure, checkpointing, studio support
   - AsyncIO: Simpler, fewer dependencies
   - Decision: Start with AsyncIO, migrate to LangGraph if needed

2. **SQLite vs PostgreSQL for memory?**
   - SQLite: Zero config, local-first
   - PostgreSQL: Better for multi-instance, production
   - Decision: SQLite default, PostgreSQL optional

3. **How to handle rate limits on LLM?**
   - Implement backoff and retry
   - Support local LLM fallback (Ollama)

## Timeline

| Week | Focus | Deliverable |
|------|-------|-------------|
| 1 | Core architecture | Memory + Topology + Basic CLI |
| 2 | Multi-agent | Planner → Subagents → Synthesizer |
| 3 | Skills | K8s/Metrics/Logs skills |
| 4 | Polish | Eval + Docs + Publish |

---

*Spec Version: 1.0*
*Author: Sainath + Clawd*
*Date: 2026-05-03*
