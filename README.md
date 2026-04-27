# AutoSRE

**Open-source AI SRE Agent — Built Foundation-First**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://github.com/opensre/autosre/actions/workflows/tests.yml/badge.svg)](https://github.com/opensre/autosre/actions)

AutoSRE is the open-source equivalent to [Azure SRE Agent](https://azure.microsoft.com/en-us/products/sre-agent). Unlike other tools that connect an LLM directly to alerts (and get garbage results), AutoSRE is **built foundation-first**.

## 🎯 The Problem

Most internal AI SRE tools fail because they skip the foundation:

```
┌─────────────────────────────────────────────────┐
│  🏠 ROOF: Connect LLM to Alerts                 │  ← Most teams START and STOP here
│     (Where 90% of teams begin)                  │
├─────────────────────────────────────────────────┤
│  🔄 Feedback Loop                               │  ← SKIPPED
│     (Real incidents feeding agent back)         │
├─────────────────────────────────────────────────┤
│  🎭 Realistic Eval Scenarios                    │  ← SKIPPED  
│     (Actual alert payloads, real env setup)     │
├─────────────────────────────────────────────────┤
│  📊 Evals and Baselines                         │  ← SKIPPED
│     (How do you know it's getting better?)      │
├─────────────────────────────────────────────────┤
│  🏗️ FOUNDATION                                  │  ← NEVER BUILT
│     (Context, topology, ownership, history)     │
└─────────────────────────────────────────────────┘
```

**Result:** Teams dump alerts into LLM → garbage results → "AI isn't ready" → abandon project.

## ✨ The Solution

AutoSRE builds the foundation first:

1. **Context Store** — Service topology, ownership, change history
2. **Eval Framework** — Synthetic incidents, replay attacks, baseline metrics
3. **Sandbox Environment** — Kind cluster with chaos injection
4. **Agent Core** — Observer/Reasoner/Actor with guardrails
5. **Feedback Loop** — Learn from outcomes, continuous improvement

## 🚀 Quick Start

### Installation

```bash
# Install with pip
pip install autosre

# Or with uv (recommended)
uv add autosre
```

### Basic Usage

```bash
# Show context summary
autosre context show

# Sync from Kubernetes
autosre context sync --kubernetes

# List evaluation scenarios
autosre eval list

# Run an evaluation
autosre eval run --scenario memory_leak

# Create sandbox cluster
autosre sandbox create

# Analyze an alert
autosre agent analyze --alert alert.json
```

### Python API

```python
from autosre.foundation import ContextStore, Service
from autosre.agent import Reasoner, ReasonerConfig

# Initialize context store
store = ContextStore()

# Add services
store.add_service(Service(
    name="payment-service",
    namespace="production",
    dependencies=["database", "redis-cache"],
))

# Configure reasoner with Ollama
config = ReasonerConfig(
    model="qwen3:14b",
    provider="ollama",
)

# Analyze an alert
reasoner = Reasoner(store, config)
result = await reasoner.analyze(alert)

print(f"Root Cause: {result.root_cause}")
print(f"Confidence: {result.confidence}")
print(f"Actions: {result.immediate_actions}")
```

## 📊 Evaluation Scenarios

AutoSRE includes 10 built-in scenarios:

| Scenario | Difficulty | Description |
|----------|------------|-------------|
| `memory_leak` | Medium | Gradual memory leak causing OOM kills |
| `high_cpu` | Easy | High CPU usage causing latency spikes |
| `cert_expiry` | Easy | TLS certificate about to expire |
| `cascading_failure` | Hard | Database failure causing cascading outages |
| `deployment_rollback` | Medium | Bad deployment needs rollback |
| `disk_full` | Easy | Disk space exhausted |
| `network_latency` | Medium | Network latency spike between services |
| `external_dependency_down` | Medium | Third-party API is down |
| `alert_storm` | Hard | Multiple alerts, find root cause |
| `silent_failure` | Hard | Service healthy but processing broken |

Run evaluations:

```bash
autosre eval run --scenario cascading_failure --verbose
autosre eval report
```

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     AutoSRE Agent                            │
├─────────────────────────────────────────────────────────────┤
│  Observer          │  Reasoner         │  Actor              │
│  ─────────────     │  ──────────       │  ─────              │
│  • Alert Watcher   │  • LLM Analysis   │  • Runbook Exec     │
│  • Metric Analyzer │  • Context Inject │  • Notifications    │
│  • Log Correlator  │  • Chain of Thought│ • Ticket Creation  │
│  • Change Detector │  • Confidence     │  • Rollbacks        │
├─────────────────────────────────────────────────────────────┤
│                     Guardrails                               │
│  • Human Approval  • Blast Radius Limits  • Audit Logging   │
├─────────────────────────────────────────────────────────────┤
│                     Foundation                               │
│  ┌──────────┐  ┌───────────┐  ┌─────────┐  ┌──────────┐     │
│  │ Context  │  │ Connectors│  │ Topology│  │ Runbooks │     │
│  │ Store    │  │ K8s/Prom  │  │ Graph   │  │ Index    │     │
│  └──────────┘  └───────────┘  └─────────┘  └──────────┘     │
├─────────────────────────────────────────────────────────────┤
│                     Data Sources                             │
│  Kubernetes  │  Prometheus  │  GitHub  │  PagerDuty         │
└─────────────────────────────────────────────────────────────┘
```

## 📈 Comparison

| Feature | AutoSRE | Azure SRE Agent | HolmesGPT |
|---------|---------|-----------------|-----------|
| **Open Source** | ✅ | ❌ | ✅ |
| **Cloud Agnostic** | ✅ | ❌ (Azure only) | ✅ |
| **Local LLM** | ✅ (Ollama) | ❌ | ✅ |
| **Foundation Layer** | ✅ | ✅ | ❌ |
| **Eval Framework** | ✅ | Internal | ❌ |
| **Sandbox Testing** | ✅ | ❌ | ❌ |
| **Feedback Loop** | ✅ | ✅ | ❌ |
| **Guardrails** | ✅ | ✅ | ❌ |

## 🔧 Configuration

AutoSRE uses a simple YAML config:

```yaml
# ~/.autosre/config.yaml

# LLM Configuration
llm:
  provider: ollama  # ollama, openai, anthropic
  model: qwen3:14b
  host: http://localhost:11434

# Connectors
connectors:
  kubernetes:
    enabled: true
    kubeconfig: ~/.kube/config
    
  prometheus:
    enabled: true
    url: http://localhost:9090
    
  github:
    enabled: true
    token: ${GITHUB_TOKEN}
    repositories:
      - myorg/service-a
      - myorg/service-b

# Guardrails
guardrails:
  dry_run: true
  auto_approve_low_risk: true
  max_blast_radius: 5
  require_approval:
    - rollback
    - scale
    - script
```

## 📚 Documentation

- [Getting Started](docs/getting-started.md)
- [Architecture](docs/architecture.md)
- [Connectors](docs/connectors.md)
- [Evaluation Framework](docs/evals.md)
- [Sandbox Setup](docs/sandbox.md)
- [API Reference](docs/api.md)

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

```bash
# Clone the repo
git clone https://github.com/opensre/autosre.git
cd autosre

# Install with dev dependencies
uv sync --all-extras

# Run tests
uv run pytest

# Run linting
uv run ruff check .
```

## 🛣️ Roadmap

- [x] Foundation layer (context store, connectors)
- [x] Evaluation framework with synthetic scenarios
- [x] Sandbox environment with chaos injection
- [x] Agent core (observer/reasoner/actor)
- [x] Guardrails and approval workflow
- [x] Feedback loop and learning pipeline
- [ ] Web UI for incident management
- [ ] Slack/Teams integration
- [ ] Custom scenario builder
- [ ] Multi-cluster support
- [ ] Anomaly detection ML models

## 📜 License

MIT License - see [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

- Inspired by [Azure SRE Agent](https://azure.microsoft.com/en-us/products/sre-agent)
- Built on insights from [HolmesGPT](https://github.com/robusta-dev/holmesgpt)
- Thanks to the CNCF observability ecosystem

---

<p align="center">
  <strong>Built by the OpenSRE Community</strong><br>
  <a href="https://github.com/opensre/autosre">GitHub</a> •
  <a href="https://github.com/opensre/autosre/issues">Issues</a> •
  <a href="https://github.com/opensre/autosre/discussions">Discussions</a>
</p>
