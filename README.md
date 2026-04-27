# AutoSRE

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

**Open-source AI SRE agent** for incident investigation, root cause analysis, and auto-remediation.

Built **foundation-first**: context awareness before AI reasoning, for reliable and accurate incident response.

<p align="center">
  <img src="docs/images/autosre-demo.gif" alt="AutoSRE Demo" width="700">
</p>

---

## 🚀 Quick Start

Get running in 5 minutes:

```bash
# Install
pip install autosre

# Initialize in your project
autosre init

# Start a local sandbox (optional, requires Docker)
autosre sandbox start

# Sync context from Kubernetes
autosre context sync --kubernetes

# Run the agent
autosre agent run
```

---

## ✨ Features

### 🔍 **Context-Aware Analysis**
- Correlates alerts with recent deployments, config changes, and dependencies
- Maintains service topology and ownership mappings
- Tracks historical incidents for pattern recognition

### 🤖 **Intelligent Root Cause Analysis**
- Multi-LLM support (Ollama, OpenAI, Anthropic, Azure)
- Structured reasoning with confidence scores
- Learns from feedback to improve over time

### 📖 **Runbook Integration**
- Matches alerts to relevant runbooks
- Step-by-step execution guidance
- Automated execution with guardrails

### 🛡️ **Safe Remediation**
- Approval workflows for risky actions
- Auto-approve low-risk operations
- Audit logging for compliance

### 🧪 **Built-in Evaluation**
- 25+ synthetic incident scenarios
- Measure accuracy before production
- Track improvements over time

---

## 📦 Installation

### From PyPI (Recommended)

```bash
pip install autosre

# With LLM support
pip install autosre[llm]

# With sandbox support
pip install autosre[sandbox]

# Everything
pip install autosre[all]
```

### From Source

```bash
git clone https://github.com/opensre/autosre.git
cd autosre
pip install -e ".[all,dev]"
```

### Requirements

- **Python 3.11+**
- **Docker** (for sandbox environments)
- **kubectl** (for Kubernetes integration)
- **kind** (for local sandbox clusters)

---

## ⚙️ Configuration

Create a `.env` file or set environment variables:

```bash
# Copy the example
cp .env.example .env
```

### Essential Settings

```bash
# LLM Provider (ollama is default, runs locally)
OPENSRE_LLM_PROVIDER=ollama
OPENSRE_OLLAMA_HOST=http://localhost:11434
OPENSRE_OLLAMA_MODEL=llama3.1:8b

# Or use OpenAI
# OPENSRE_LLM_PROVIDER=openai
# OPENSRE_OPENAI_API_KEY=sk-...
# OPENSRE_OPENAI_MODEL=gpt-4o-mini

# Infrastructure
OPENSRE_PROMETHEUS_URL=http://localhost:9090
OPENSRE_K8S_NAMESPACES=default,production
```

See [Configuration Guide](docs/CONFIGURATION.md) for all options.

---

## 📖 Usage

### Initialize AutoSRE

```bash
autosre init
```

Creates:
- `.autosre/` - Configuration and databases
- `runbooks/` - Runbook YAML files
- `.env.example` - Configuration template

### Check Status

```bash
autosre status
```

Shows:
- Configuration status
- Context store summary
- LLM provider health
- Connected integrations

### Manage Context

```bash
# View context summary
autosre context show

# View specific data
autosre context show --services
autosre context show --changes
autosre context show --alerts
autosre context show --runbooks

# Sync from external sources
autosre context sync --kubernetes
autosre context sync --prometheus
autosre context sync --all

# Add items manually
autosre context add service --name api --namespace prod --team platform
autosre context add runbook --file runbooks/high-cpu.yaml
```

### Run Evaluations

```bash
# List available scenarios
autosre eval list

# Run a scenario
autosre eval run --scenario high_cpu

# View results
autosre eval report

# Create custom scenario
autosre eval create --template
```

### Manage Sandbox

```bash
# Create local Kind cluster
autosre sandbox start

# Check status
autosre sandbox status

# Inject chaos for testing
autosre sandbox inject cpu-hog
autosre sandbox inject pod-kill --target frontend

# Tear down
autosre sandbox stop
```

### Run the Agent

```bash
# Watch mode (continuous)
autosre agent run

# Single analysis
autosre agent analyze --alert alert.json
autosre agent analyze --service frontend

# View configuration
autosre agent config

# View history
autosre agent history
```

### Submit Feedback

```bash
# Mark analysis as correct
autosre feedback submit -i INC-123 --correct

# Mark as incorrect with correction
autosre feedback submit -i INC-123 --incorrect --actual-cause "DNS timeout"

# View feedback stats
autosre feedback report
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        AutoSRE Agent                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  Observer   │  │  Reasoner   │  │   Actor     │         │
│  │             │  │             │  │             │         │
│  │ • Alerts    │  │ • LLM       │  │ • Execute   │         │
│  │ • Metrics   │  │ • Context   │  │ • Verify    │         │
│  │ • Logs      │  │ • Runbooks  │  │ • Rollback  │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│         │                │                │                 │
│         └────────────────┼────────────────┘                 │
│                          │                                  │
│  ┌───────────────────────┴───────────────────────┐         │
│  │              Context Store                     │         │
│  │  • Services & Dependencies                     │         │
│  │  • Ownership & On-call                         │         │
│  │  • Changes & Deployments                       │         │
│  │  • Runbooks & Playbooks                        │         │
│  │  • Alerts & Incidents                          │         │
│  └───────────────────────────────────────────────┘         │
│                          │                                  │
├──────────────────────────┼──────────────────────────────────┤
│                          │                                  │
│  ┌──────────┐  ┌─────────┴─────────┐  ┌─────────────┐      │
│  │Kubernetes│  │    Prometheus     │  │   GitHub    │      │
│  └──────────┘  └───────────────────┘  └─────────────┘      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Foundation-First Philosophy:**
1. **Context Store** - Single source of truth for all infrastructure state
2. **Connectors** - Sync from Kubernetes, Prometheus, GitHub, etc.
3. **Observer** - Watch for alerts and anomalies
4. **Reasoner** - LLM-powered root cause analysis with rich context
5. **Actor** - Execute remediation with guardrails

See [Architecture Guide](docs/ARCHITECTURE.md) for details.

---

## 🧪 Evaluation Framework

AutoSRE includes 25+ synthetic incident scenarios for testing:

| Scenario | Difficulty | Description |
|----------|------------|-------------|
| `high_cpu` | Easy | CPU spike causing latency |
| `memory_leak` | Medium | Gradual memory exhaustion |
| `cascading_failure` | Hard | Multi-service outage |
| `deployment_rollback` | Medium | Failed deployment |
| `database_connection_pool_exhaustion` | Medium | DB connection issues |

Run evaluations before production to ensure accuracy:

```bash
autosre eval run --scenario cascading_failure --verbose
```

---

## 🔌 Integrations

### Supported

- **Kubernetes** - Service discovery, pod status, events
- **Prometheus** - Metrics, alerts, Alertmanager
- **GitHub** - Deployments, PRs, commits
- **Slack** - Alert notifications, approval workflows
- **PagerDuty** - Incident management

### Coming Soon

- Datadog
- New Relic
- Grafana Loki
- OpsGenie
- VictorOps

---

## 📚 Documentation

- [Getting Started](docs/getting-started.md)
- [CLI Reference](docs/cli-reference.md)
- [Configuration](docs/CONFIGURATION.md)
- [Architecture](docs/ARCHITECTURE.md)
- [API Reference](docs/api-reference.md)
- [Contributing](CONTRIBUTING.md)

---

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

```bash
# Setup development environment
git clone https://github.com/opensre/autosre.git
cd autosre
pip install -e ".[all,dev]"

# Run tests
pytest

# Run linting
ruff check .
```

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

Built with:
- [Click](https://click.palletsprojects.com/) - CLI framework
- [Rich](https://rich.readthedocs.io/) - Beautiful terminal output
- [Pydantic](https://pydantic.dev/) - Data validation
- [HTTPX](https://www.python-httpx.org/) - HTTP client

Inspired by the SRE practices at Google, Netflix, and the broader DevOps community.

---

<p align="center">
  <b>Built with ❤️ by the OpenSRE Community</b>
</p>
