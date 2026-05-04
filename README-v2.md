# AutoSRE v2 — AI-Powered SRE Agent

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-green.svg)](LICENSE)

AutoSRE is an open-source AI SRE agent that investigates production incidents autonomously.

## Features

- **Episodic Memory** — Learns from past investigations, suggests strategies
- **Multi-Agent Investigation** — Parallel subagents for Kubernetes, Metrics, Logs
- **Service Topology** — YAML-based dependency graph for blast radius analysis
- **Local-First** — SQLite for memory, no external databases required
- **Simple API** — Just `pip install autosre` and investigate

## Quick Start

```python
import asyncio
from autosre import Orchestrator

async def main():
    orch = Orchestrator()
    
    report = await orch.investigate({
        "name": "High5xxRate",
        "service": "checkout-service",
        "severity": "critical",
        "description": "checkout-service 5xx rate above 5% for 10 minutes",
    })
    
    print(f"Root Cause: {report.root_cause}")
    print(f"Confidence: {report.confidence:.0%}")

asyncio.run(main())
```

## Installation

```bash
pip install autosre

# Set your LLM API key
export ANTHROPIC_API_KEY=sk-...
# or
export OPENAI_API_KEY=sk-...
```

## Configuration

AutoSRE uses Pydantic settings with environment variables:

```bash
# LLM settings
export AUTOSRE_LLM__PROVIDER=anthropic  # or openai
export AUTOSRE_LLM__MODEL=claude-sonnet-4-20250514

# Investigation settings
export AUTOSRE_INVESTIGATION__MAX_ITERATIONS=3
export AUTOSRE_INVESTIGATION__PARALLEL_SUBAGENTS=true

# Paths
export AUTOSRE_TOPOLOGY_PATH=topology.yaml
export AUTOSRE_MEMORY__DB_PATH=.autosre/memory.db
```

Or use a config file (`config.yaml`):

```yaml
llm:
  provider: anthropic
  model: claude-sonnet-4-20250514
  temperature: 0.0

investigation:
  max_iterations: 3
  parallel_subagents: true
  timeout_seconds: 300

memory:
  db_path: .autosre/memory.db

topology_path: topology.yaml
```

## Service Topology

Define your services and dependencies in `topology.yaml`:

```yaml
services:
  checkout-service:
    description: "Main checkout flow"
    dependencies:
      - payment-service
      - inventory-service
    owners:
      - team-checkout
    tier: critical
    alerts:
      - checkout-5xx
      - checkout-latency
      
  payment-service:
    dependencies:
      - stripe-gateway
      - payment-db
    tier: critical
    
alert_mappings:
  checkout-5xx: checkout-service
  payment-failure: payment-service

tiers:
  critical:
    sla_minutes: 15
    notify_slack: "#incidents-critical"
```

## Investigation Flow

```
┌─────────────────────────────────────────────────────────────┐
│                      Alert Received                          │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│ 1. init_context     - Parse alert, load topology             │
│ 2. memory_lookup    - Find similar past incidents            │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│ 3. planner          - Generate hypotheses, select agents     │
└─────────────────────┬───────────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        │             │             │
┌───────▼───┐  ┌──────▼────┐  ┌─────▼────┐
│kubernetes │  │  metrics  │  │   logs   │
│ subagent  │  │ subagent  │  │ subagent │
└───────┬───┘  └──────┬────┘  └─────┬────┘
        │             │             │
        └─────────────┼─────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│ 5. synthesizer      - Combine evidence, decide loop/done     │
└─────────────────────┬───────────────────────────────────────┘
                      │
        ┌─────────────┴─────────────┐
        │                           │
  Need more evidence          Sufficient evidence
        │                           │
        │                  ┌────────▼─────────┐
        └─────→ Loop       │  6. writeup      │
                           │  Generate report │
                           └────────┬─────────┘
                                    │
                           ┌────────▼─────────┐
                           │  7. memory_store │
                           │  Save for future │
                           └──────────────────┘
```

## Subagents

### Kubernetes
- `pod_logs` — Get logs from pods
- `describe` — Describe resources
- `events` — Get cluster events
- `get_pods` — Pod status overview
- `top_pods` — Resource usage

### Metrics (Prometheus)
- `query_prometheus` — PromQL instant queries
- `query_range` — Range queries for trends
- `error_rate` — Calculate error rates
- `latency` — Get p50/p95/p99 latency

### Logs
- `search_logs` — Grep log files
- `tail_logs` — Tail recent entries
- `grep_errors` — Find error patterns
- `journalctl` — Systemd journal
- `loki_search` — Grafana Loki queries

## Episodic Memory

AutoSRE remembers past investigations:

```python
from autosre.memory import EpisodicMemory, Episode

memory = EpisodicMemory()

# Store an investigation
memory.store(Episode(
    alert_type="http_500",
    service_name="checkout-service",
    root_cause="Database connection pool exhausted",
    resolved=True,
    skills_used=["pod_logs", "query_prometheus"],
))

# Search similar incidents
similar = memory.search_similar(
    alert_type="http_500",
    service_name="checkout-service",
)

# Get stats
stats = memory.get_stats()
print(f"Episodes: {stats['total_episodes']}")
print(f"Resolution rate: {stats['resolution_rate']:.0%}")
```

## Python API

```python
from autosre import Orchestrator, Settings, investigate

# Quick investigation
report = await investigate({
    "name": "HighLatency",
    "service": "api-gateway",
    "description": "p99 latency above 500ms",
})

# With custom settings
settings = Settings(
    investigation={"max_iterations": 5},
    memory={"db_path": "my_memory.db"},
)
orch = Orchestrator(settings=settings)
report = await orch.investigate(alert)

# Access results
print(report.root_cause)
print(report.confidence)
print(report.summary)
for h in report.hypotheses:
    print(f"- {h.hypothesis}: {h.confirmed}")
```

## Architecture

```
autosre/
├── __init__.py          # Public API
├── orchestrator.py      # Main investigation flow
├── config.py            # Pydantic settings
├── memory/
│   ├── episodic.py      # SQLite episode storage
│   └── strategy.py      # Strategy generation
├── topology/
│   └── service.py       # YAML service graph
├── agents/
│   ├── state.py         # Investigation state models
│   ├── planner.py       # Hypothesis generation
│   ├── synthesizer.py   # Evidence combination
│   ├── writeup.py       # Report generation
│   └── subagents/
│       ├── base.py
│       ├── kubernetes.py
│       ├── metrics.py
│       └── logs.py
├── skills/
│   └── registry.py      # Skill loader
└── llm/
    └── client.py        # Anthropic/OpenAI client
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

Apache 2.0 — see [LICENSE](LICENSE).

---

Built with ❤️ by Sainath + Clawd
