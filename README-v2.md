# AutoSRE v2

> AI-Powered SRE Agent for Autonomous Incident Investigation

AutoSRE is an open-source agent that investigates production incidents autonomously using:
- 🧠 **Episodic Memory** — Learns from past investigations
- 🤖 **Multi-Agent Architecture** — Specialized subagents for Kubernetes, metrics, logs
- 🗺️ **Service Topology** — Blast radius and dependency awareness
- 📊 **Structured Reports** — Professional incident reports with root cause analysis

## Quick Start

```bash
# Install
pip install autosre

# Set API key
export ANTHROPIC_API_KEY=sk-...

# Investigate!
python -c "
import asyncio
from autosre import investigate

async def main():
    report = await investigate('checkout-service 5xx spike')
    print(f'Root cause: {report.root_cause}')

asyncio.run(main())
"
```

## Installation

```bash
# From PyPI (once published)
pip install autosre

# From source
git clone https://github.com/yourorg/autosre
cd autosre
pip install -e .
```

## Usage

### Basic Investigation

```python
import asyncio
from autosre import Orchestrator

async def main():
    orch = Orchestrator()
    
    # String description
    report = await orch.investigate("payment-service timeout errors")
    
    # Or full alert dict
    report = await orch.investigate({
        "name": "HighErrorRate",
        "service": "checkout-service",
        "severity": "critical",
        "description": "Error rate above 5% for 10 minutes",
    })
    
    print(f"Root cause: {report.root_cause}")
    print(f"Confidence: {report.confidence:.0%}")
    print(f"Summary: {report.summary}")

asyncio.run(main())
```

### With Service Topology

Create `topology.yaml`:

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
    
  payment-service:
    dependencies:
      - stripe-gateway
      - payment-db
    tier: critical

tiers:
  critical:
    sla_minutes: 15
```

Then:

```python
from autosre import Orchestrator, load_topology

load_topology("topology.yaml")
orch = Orchestrator()
report = await orch.investigate("checkout-service errors")
```

### Memory System

AutoSRE learns from past investigations:

```python
from autosre import EpisodicMemory

memory = EpisodicMemory()

# Get stats
stats = memory.get_stats()
print(f"Total episodes: {stats['total_episodes']}")
print(f"Resolution rate: {stats['resolution_rate']:.0%}")

# Search similar past investigations
episodes = memory.search_similar(
    alert_type="http_500",
    service_name="checkout-service",
)
for ep in episodes:
    print(f"- {ep.root_cause}")
```

## Configuration

Environment variables:
```bash
ANTHROPIC_API_KEY=sk-...          # Required (or OPENAI_API_KEY)
AUTOSRE_LLM_MODEL=claude-sonnet-4-20250514  # Model to use
AUTOSRE_MEMORY_DB_PATH=.autosre/memory.db   # Memory database
AUTOSRE_INVESTIGATION_MAX_ITERATIONS=3      # Max investigation loops
```

Or via Python:
```python
from autosre import Settings, configure

configure(
    llm={"provider": "anthropic", "model": "claude-sonnet-4-20250514"},
    investigation={"max_iterations": 5},
)
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Orchestrator                         │
│  ┌─────────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐  │
│  │   Memory    │  │ Topology │  │ Planner  │  │Synthesizer│ │
│  │  (SQLite)   │  │  (YAML)  │  │  Agent   │  │  Agent  │  │
│  └─────────────┘  └──────────┘  └──────────┘  └─────────┘  │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                  Subagents (parallel)                │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐          │   │
│  │  │Kubernetes│  │ Metrics  │  │   Logs   │  ...     │   │
│  │  └──────────┘  └──────────┘  └──────────┘          │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                    Writeup Agent                     │   │
│  │            (Generates final report)                  │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Investigation Flow

1. **Init Context** — Extract service name, classify alert type
2. **Memory Lookup** — Find similar past investigations
3. **Topology Context** — Load service dependencies and blast radius
4. **Planner** — Generate hypotheses about root cause
5. **Subagents** — Gather evidence (Kubernetes, metrics, logs)
6. **Synthesizer** — Combine findings, decide if more investigation needed
7. **Loop** — Back to planner if insufficient evidence
8. **Writeup** — Generate final report
9. **Store Episode** — Save to memory for future learning

## Extending AutoSRE

### Custom Subagents

```python
from autosre.agents.subagents import BaseSubagent

class MySubagent(BaseSubagent):
    agent_id = "custom"
    agent_name = "Custom Investigation Agent"
    capabilities_description = "My custom capabilities"
    
    async def _run_investigation(self, alert, hypotheses, service_context, llm_client):
        # Your investigation logic
        self.add_evidence(
            skill="my_check",
            query="my query",
            result="my result",
        )
        return "Investigation findings summary"
```

### Custom Skills

Create `skills/myskill/SKILL.md`:

```yaml
---
name: my-skill
description: My custom skill
category: observability
tags: [monitoring, custom]
---

# My Skill

Instructions for using this skill...
```

## Comparison to OpenSRE

AutoSRE v2 is inspired by [OpenSRE](https://github.com/swapnildahiphale/OpenSRE) but simplified:

| Feature | OpenSRE | AutoSRE v2 |
|---------|---------|------------|
| Orchestration | LangGraph | Plain async Python |
| Memory | PostgreSQL | SQLite |
| Knowledge Graph | Neo4j | YAML topology |
| Configuration | HTTP config service | Local YAML/env |
| LLM Routing | LiteLLM proxy | Direct Anthropic/OpenAI |

## Development

```bash
# Clone
git clone https://github.com/yourorg/autosre
cd autosre

# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/

# Run example
python examples/investigate.py
```

## License

Apache 2.0

## Acknowledgments

- Inspired by [OpenSRE](https://github.com/swapnildahiphale/OpenSRE)
- Built with [Anthropic Claude](https://anthropic.com) and [OpenAI GPT](https://openai.com)
