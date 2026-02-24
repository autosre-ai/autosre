# OpenSRE

**AI-Powered Incident Response — Because 3 AM pages shouldn't require 3 hours of debugging.**

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

---

## 🌙 The 3 AM Scenario

You're asleep. Your phone buzzes:

> **🚨 ALERT: Checkout service error rate > 5%**

Two minutes later, Slack pings:

```
┌─────────────────────────────────────────────────────────────┐
│  🔍 OpenSRE Analysis                                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Alert: checkout-service error rate spike (8.3%)            │
│  Time: 3:02 AM                                              │
│                                                             │
│  📊 What I found:                                           │
│  • Deployment checkout-v2.4.1 rolled out 12 min ago         │
│  • Error rate was 0.1% before, now 8.3%                     │
│  • Affected: /api/v1/checkout/payment endpoint              │
│  • 3 pods showing OOMKilled restarts                        │
│                                                             │
│  🎯 Root Cause (High Confidence):                           │
│  Memory leak in v2.4.1 causing OOM crashes                  │
│                                                             │
│  ✅ Recommended Action:                                     │
│  Rollback to checkout-v2.4.0                                │
│                                                             │
│  [ ✅ Approve Rollback ]  [ 🔍 Investigate More ]  [ ❌ Dismiss ]  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

You tap **Approve Rollback**. OpenSRE executes. You go back to sleep.

**That's OpenSRE.**

---

## ✨ Features

- **🤖 AI-Powered Analysis** — Connects the dots between metrics, logs, events, and recent changes
- **📊 Multi-Signal Correlation** — Prometheus metrics + K8s events + deployment history
- **🎯 Root Cause Detection** — Not just "what's broken" but "why it broke"
- **💬 Slack-Native Workflow** — Analysis delivered to Slack with interactive buttons
- **👤 Human-in-the-Loop** — AI suggests, humans approve, AI executes
- **📚 Runbook Integration** — Your existing runbooks inform the AI's decisions
- **🔒 Safe by Default** — Dangerous actions always require approval
- **🏠 Local LLM Support** — Works with Ollama, no data leaves your network

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Kubernetes cluster (or kubeconfig access)
- Prometheus instance
- Slack workspace (for notifications)
- Ollama (optional, for local LLM)

### Installation

```bash
# Clone the repo
git clone https://github.com/srisainath/opensre.git
cd opensre

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install
pip install -e .

# Copy environment template
cp .env.example .env
```

### Configuration

Edit `.env`:

```bash
# LLM (pick one)
OPENSRE_LLM_PROVIDER=ollama
OPENSRE_OLLAMA_MODEL=llama3.1:8b
# Or: OPENSRE_LLM_PROVIDER=openai / anthropic

# Infrastructure
OPENSRE_PROMETHEUS_URL=http://prometheus:9090
OPENSRE_KUBECONFIG=~/.kube/config

# Slack
OPENSRE_SLACK_BOT_TOKEN=xoxb-your-token
OPENSRE_SLACK_CHANNEL=#incidents
```

### Run

```bash
# Start the daemon (listens for alerts)
opensre start

# Or investigate manually
opensre investigate "checkout service high error rate"

# Check system status
opensre status
```

---

## 🏗️ Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Alertmanager│────▶│   OpenSRE   │────▶│    Slack    │
│ (webhook)   │     │   Daemon    │     │ (analysis)  │
└─────────────┘     └──────┬──────┘     └──────┬──────┘
                           │                   │
                    ┌──────▼──────┐     ┌──────▼──────┐
                    │   Agents    │     │   Human     │
                    │             │     │  Approval   │
                    │ • Observer  │     └──────┬──────┘
                    │ • Reasoner  │            │
                    │ • Actor     │◀───────────┘
                    └──────┬──────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
    ┌────▼────┐      ┌─────▼─────┐     ┌─────▼─────┐
    │Prometheus│     │ Kubernetes │     │  Runbooks  │
    │ (metrics)│     │(logs/events)│    │ (context)  │
    └──────────┘     └───────────┘     └───────────┘
```

### Multi-Agent System

| Agent | Role |
|-------|------|
| **Observer** | Gathers metrics, logs, events, deployment history |
| **Reasoner** | Correlates signals, identifies root cause |
| **Actor** | Suggests and executes remediation actions |
| **Orchestrator** | Coordinates agents, manages workflow |

---

## 💬 Slack Integration

### Setup

1. Create a Slack app at [api.slack.com](https://api.slack.com/apps)
2. Add Bot Token Scopes: `chat:write`, `reactions:write`, `files:write`
3. Enable Interactivity, point to `https://your-server/slack/events`
4. Install to workspace, copy Bot Token to `.env`

### Commands

```
/opensre investigate <description>  — Manually trigger investigation
/opensre status                     — Check OpenSRE health
/opensre runbooks                   — List available runbooks
```

---

## 📚 Runbooks

Drop markdown runbooks in `runbooks/`:

```markdown
# Redis Connection Issues

## Symptoms
- High latency on cache-dependent services
- Redis connection timeouts in logs

## Investigation Steps
1. Check Redis pod health: `kubectl get pods -l app=redis`
2. Check memory usage: `redis-cli INFO memory`
3. Check slow log: `redis-cli SLOWLOG GET 10`

## Remediation
- If OOM: Scale Redis memory or clear cache
- If connection pool exhausted: Restart dependent services
```

OpenSRE uses these runbooks to inform its analysis and suggest actions.

---

## 🔒 Safety & Permissions

Actions are categorized by risk:

| Risk Level | Examples | Approval |
|------------|----------|----------|
| 🟢 **Low** | Get logs, describe pods, query metrics | Auto-approved |
| 🟡 **Medium** | Restart single pod, scale replicas | Requires approval |
| 🔴 **High** | Rollback deployment, delete resources | Requires approval + confirmation |

Configure in `config/agents.yaml`:

```yaml
safety:
  auto_approve_low_risk: true
  require_confirmation_high_risk: true
  
  # Actions that always require human approval
  protected_namespaces:
    - production
    - kube-system
```

---

## 🛠️ Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check .

# Type check
mypy opensre_core
```

---

## 🗺️ Roadmap

- [x] Core multi-agent architecture
- [x] Prometheus integration
- [x] Kubernetes integration  
- [x] Slack notifications with interactive buttons
- [ ] PagerDuty integration
- [ ] OpsGenie integration
- [ ] Grafana dashboard
- [ ] Custom alert routing rules
- [ ] Multi-cluster support
- [ ] Incident timeline generation
- [ ] Post-mortem draft generation

---

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

Areas we need help:
- Additional integrations (Datadog, New Relic, Splunk)
- More runbook templates
- Testing and feedback
- Documentation

---

## 📄 License

Apache 2.0 — See [LICENSE](LICENSE)

---

## 🙏 Acknowledgments

Built with:
- [Ollama](https://ollama.ai) — Local LLM inference
- [FastAPI](https://fastapi.tiangolo.com) — API framework
- [Typer](https://typer.tiangolo.com) — CLI framework
- [Prometheus](https://prometheus.io) — Metrics
- [Kubernetes Python Client](https://github.com/kubernetes-client/python)

---

<p align="center">
  <strong>Stop debugging at 3 AM. Let OpenSRE handle it.</strong>
</p>
