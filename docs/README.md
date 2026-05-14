# AutoSRE V2 Documentation

> **AI-Powered Site Reliability Engineering Assistant**

AutoSRE V2 is an intelligent multi-agent system that automatically investigates production incidents, identifies root causes, and generates actionable remediation recommendations. It integrates with your existing observability stack and uses LLMs to reason through complex failure scenarios.

---

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Features](#features)
- [Architecture](#architecture)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage Examples](#usage-examples)
- [API Reference](#api-reference)
- [Contributing](#contributing)

---

## Overview

AutoSRE V2 combines the power of Large Language Models with deep observability integrations to automate incident investigation. When an alert fires, AutoSRE:

1. **Triages** the alert to assess severity and scope
2. **Investigates** using specialized agents (Kubernetes, Metrics, Logs, Traces)
3. **Synthesizes** findings to identify root cause
4. **Recommends** safe, reversible remediation actions

### Why AutoSRE?

| Traditional Approach | With AutoSRE |
|---------------------|--------------|
| Manual log searching | Automated log correlation |
| Dashboard hopping | Single investigation view |
| Tribal knowledge required | AI-powered reasoning |
| 30+ minutes MTTR | Minutes to root cause |
| Reactive firefighting | Proactive recommendations |

---

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose (optional)
- An LLM API key (OpenAI, Anthropic, or local Ollama)

### 5-Minute Setup

```bash
# 1. Clone and enter directory
git clone https://github.com/autosre/autosre-v2.git
cd autosre-v2

# 2. Create virtual environment and install
make setup

# 3. Configure your environment
cp .env.example .env
# Edit .env with your API keys and infrastructure URLs

# 4. Start the development server
make dev
```

### Your First Investigation

```bash
# Via CLI
autosre investigate start --alert-id abc123

# Via API
curl -X POST http://localhost:8000/api/v1/investigate \
  -H "Content-Type: application/json" \
  -d '{
    "alert": {
      "name": "HighErrorRate",
      "severity": "critical",
      "service": "payment-service"
    }
  }'
```

### Using Docker

```bash
# Start everything
docker compose up -d

# View logs
docker compose logs -f autosre-api

# Open UI at http://localhost:3000
# Open API docs at http://localhost:8000/docs
```

---

## Features

### 🤖 Multi-Agent Investigation System

Specialized AI agents work together to investigate incidents:

| Agent | Responsibility |
|-------|----------------|
| **Triage Agent** | Classifies alerts, assesses severity, generates hypotheses |
| **Kubernetes Agent** | Analyzes pod status, events, deployments, logs |
| **Metrics Agent** | Queries Prometheus, identifies anomalies |
| **Logs Agent** | Searches Loki, correlates error patterns |
| **Remediation Agent** | Generates safe, reversible fixes |

### 🔄 ReAct Pattern Investigation

Uses the Reasoning + Acting pattern for thorough investigation:

```
🔍 Observe → 🤔 Think → 🛠️ Act → 🔁 Repeat
```

- Forms and tests hypotheses systematically
- Gathers evidence from multiple sources
- Refines conclusions based on findings
- Explains reasoning at every step

### 🔌 Deep Integrations

- **Prometheus** — PromQL queries, alerting, anomaly detection
- **Loki** — Log search, pattern matching, correlation
- **Kubernetes** — Native cluster access, pod inspection, events
- **Alertmanager** — Alert ingestion via webhooks
- **PagerDuty** — Incident synchronization

### 🧠 Knowledge Base

- Stores runbooks and procedures
- Records incident history for learning
- Suggests relevant past incidents
- Improves recommendations over time

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              AutoSRE V2                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        🎯 Coordinator                                │   │
│  │   Orchestrates investigation flow, manages agent handoffs            │   │
│  │   State machine lifecycle • Event emission • Retry handling          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                    ┌───────────────┼───────────────┐                       │
│                    ▼               ▼               ▼                       │
│  ┌─────────────────────┐ ┌─────────────────┐ ┌─────────────────────┐      │
│  │   🚦 Triage Agent   │ │ 🔍 Investigation │ │  🔧 Remediation    │      │
│  │                     │ │     Agents       │ │      Agent         │      │
│  │ • Classify alert    │ │                  │ │                    │      │
│  │ • Assess severity   │ │ ┌──────────────┐ │ │ • Analyze findings │      │
│  │ • Form hypotheses   │ │ │ ☸️  Kubernetes │ │ │ • Generate fixes   │      │
│  │ • Route to agents   │ │ └──────────────┘ │ │ • Provide rollback │      │
│  │                     │ │ ┌──────────────┐ │ │                    │      │
│  └─────────────────────┘ │ │ 📊 Metrics    │ │ └─────────────────────┘      │
│                          │ └──────────────┘ │                               │
│                          │ ┌──────────────┐ │                               │
│                          │ │ 📜 Logs       │ │                               │
│                          │ └──────────────┘ │                               │
│                          │ ┌──────────────┐ │                               │
│                          │ │ 🔗 Traces     │ │                               │
│                          │ └──────────────┘ │                               │
│                          └─────────────────┘                               │
│                                    │                                        │
│         ┌──────────────────────────┼──────────────────────────┐            │
│         ▼                          ▼                          ▼            │
│  ┌─────────────┐           ┌─────────────┐           ┌─────────────┐       │
│  │ Prometheus  │           │    Loki     │           │ Kubernetes  │       │
│  │   📈        │           │    📋       │           │ API  ☸️     │       │
│  └─────────────┘           └─────────────┘           └─────────────┘       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Investigation Flow

```
Alert Received
      │
      ▼
┌──────────────┐
│   Triage     │ ── Classify, assess severity, generate hypotheses
│   Agent      │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Investigation│ ── Run specialized agents in parallel
│   Phase      │    (Kubernetes, Metrics, Logs, Traces)
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  Analysis    │ ── Synthesize findings, identify root cause
│   Phase      │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Remediation  │ ── Generate recommendations, assess risk
│   Agent      │
└──────┬───────┘
       │
       ▼
┌───────────────────────┐
│  Investigation Report │
│  + Recommendations    │
└───────────────────────┘
```

For detailed architecture documentation, see [ARCHITECTURE.md](./ARCHITECTURE.md).

---

## Installation

### Option 1: pip/uv (Recommended for Development)

```bash
# Using uv (recommended)
uv venv
source .venv/bin/activate
uv pip install -e ".[all,dev]"

# Or using pip
python -m venv .venv
source .venv/bin/activate
pip install -e ".[all,dev]"
```

### Option 2: Docker

```bash
# Build images
docker compose build

# Start services
docker compose up -d
```

### Option 3: Helm (Kubernetes)

```bash
helm install autosre deploy/helm \
  --namespace autosre \
  --create-namespace \
  -f deploy/helm/values.yaml
```

### Verify Installation

```bash
# Check CLI
autosre --version

# Check API health
curl http://localhost:8000/api/v1/health
```

---

## Configuration

### Environment Variables

Create a `.env` file from the example:

```bash
cp .env.example .env
```

Key configuration options:

```bash
# Core settings
AUTOSRE_ENV=production
AUTOSRE_DEBUG=false
AUTOSRE_SECRET_KEY=your-secret-key

# LLM Provider (choose one)
LLM_PROVIDER=openai              # openai, anthropic, or ollama
OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
# OLLAMA_BASE_URL=http://localhost:11434

# Infrastructure connections
PROMETHEUS_URL=http://prometheus:9090
LOKI_URL=http://loki:3100
# KUBECONFIG=~/.kube/config      # For out-of-cluster access

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/autosre

# Redis (caching)
REDIS_URL=redis://localhost:6379/0
```

### Configuration File

For detailed settings, create `config.yaml`:

```yaml
environment: production

llm:
  provider: openai
  model: gpt-4o
  temperature: 0.1
  max_tokens: 4096

agents:
  triage:
    enabled: true
  investigation:
    max_iterations: 25
    timeout_seconds: 300
    parallel: true
  remediation:
    enabled: true
    auto_execute: false  # Always require approval

integrations:
  prometheus:
    url: http://prometheus:9090
    timeout: 30
  loki:
    url: http://loki:3100
    timeout: 30
  kubernetes:
    in_cluster: true
    namespace_default: production

features:
  knowledge_base: true
  incident_learning: true
  slack_notifications: true
```

---

## Usage Examples

### CLI Investigation

```bash
# Start investigation from alert ID
autosre investigate start abc123

# Watch investigation progress
autosre investigate status abc123 --watch

# View timeline
autosre investigate timeline abc123

# Generate report
autosre investigate report abc123 --format markdown

# List all investigations
autosre investigate list --status in_progress
```

### Python SDK

```python
import asyncio
from autosre.core.alert import Alert
from autosre.agents.coordinator import AgentCoordinator

async def investigate():
    # Create an alert
    alert = Alert(
        name="HighErrorRate",
        description="Error rate > 5% for payment-service",
        severity="critical",
        service="payment-service",
        namespace="production",
        labels={"team": "payments", "env": "prod"},
    )

    # Run investigation
    coordinator = AgentCoordinator()
    result = await coordinator.start_investigation(alert.to_dict())

    # Access results
    print(f"🎯 Root Cause: {result.result.root_cause}")
    print(f"📊 Confidence: {result.result.root_cause_confidence:.0%}")
    
    for rec in result.result.recommendations:
        print(f"💡 {rec}")

asyncio.run(investigate())
```

### Webhook Integration (Alertmanager)

```yaml
# alertmanager.yml
receivers:
  - name: autosre
    webhook_configs:
      - url: http://autosre:8000/api/v1/webhooks/alertmanager
        send_resolved: true
```

---

## API Reference

### Quick Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/investigate` | POST | Start investigation |
| `/api/v1/investigations` | GET | List investigations |
| `/api/v1/investigations/{id}` | GET | Get investigation details |
| `/api/v1/investigations/{id}/timeline` | GET | Get investigation timeline |
| `/api/v1/alerts` | GET | List alerts |
| `/api/v1/webhooks/alertmanager` | POST | Alertmanager webhook |
| `/api/v1/health` | GET | Health check |

### Start Investigation

```bash
curl -X POST http://localhost:8000/api/v1/investigate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "alert": {
      "name": "HighErrorRate",
      "severity": "critical",
      "service": "payment-service",
      "namespace": "production"
    },
    "options": {
      "max_iterations": 10,
      "timeout_seconds": 300
    }
  }'
```

For complete API documentation, see [API.md](./API.md).

---

## Contributing

We welcome contributions! Here's how to get started:

### Development Setup

```bash
# Clone and setup
git clone https://github.com/autosre/autosre-v2.git
cd autosre-v2
make setup

# Run tests
make test

# Run linters
make lint

# Format code
make format
```

### Pull Request Process

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes and add tests
4. Ensure all checks pass: `make check`
5. Commit with conventional commits: `git commit -m "feat: add amazing feature"`
6. Push and open a PR

### Code Style

- Python: Ruff + Black formatting, strict mypy types
- Tests: pytest with asyncio support
- Commits: Conventional Commits format

---

## Additional Documentation

- **[ARCHITECTURE.md](./ARCHITECTURE.md)** — Detailed technical architecture
- **[API.md](./API.md)** — Complete API documentation
- **[CLI.md](./CLI.md)** — CLI reference guide
- **[AGENTS.md](./AGENTS.md)** — Agent system documentation

---

## License

MIT License - see [LICENSE](../LICENSE) for details.

---

<p align="center">
  Built with ❤️ by the AutoSRE Team
</p>
