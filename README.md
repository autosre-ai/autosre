# OpenSRE

<div align="center">

![OpenSRE Logo](docs/images/logo.png)

**AI-Powered Incident Response for SRE Teams**

[![CI](https://github.com/srisainath/opensre/actions/workflows/ci.yaml/badge.svg)](https://github.com/srisainath/opensre/actions/workflows/ci.yaml)
[![PyPI version](https://badge.fury.io/py/opensre.svg)](https://badge.fury.io/py/opensre)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Discord](https://img.shields.io/discord/1234567890?label=Discord&logo=discord)](https://discord.gg/opensre)

[Documentation](https://opensre.dev/docs) · [Demo](https://opensre.dev/demo) · [Discord](https://discord.gg/opensre) · [Blog](https://opensre.dev/blog)

</div>

---

## 🚨 Stop Debugging at 3 AM

Your phone buzzes. PagerDuty alert. You stumble to your laptop. Query Prometheus. Tail logs. Check deploys. 45 minutes later, you find it: a memory leak.

**OpenSRE investigates incidents automatically while you sleep.**

```
🚨 Alert: checkout-service error rate spike (8.3%)

🔍 OpenSRE analyzed:
  • Deployment v2.4.1 rolled out 12 min ago
  • Memory usage trending up before crashes
  • 3 pods OOMKilled in last 10 min

🎯 Root Cause (94% confidence):
  Memory leak introduced in v2.4.1

[✅ Approve Rollback] [❌ Dismiss] [📝 Details]
```

You tap **Approve**. Go back to sleep.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🧠 **AI Root Cause Analysis** | Multi-agent system correlates metrics, logs, events, and deploys |
| ⚡ **60-Second Investigations** | What took 45 min manually now happens automatically |
| 👤 **Human-in-the-Loop** | AI suggests, humans approve, AI executes |
| 🔌 **Pluggable Skills** | Prometheus, Kubernetes, AWS, Slack, PagerDuty, and more |
| 📚 **Runbook Integration** | Your runbooks inform AI decisions |
| 🔒 **Safe by Default** | Dangerous actions always require approval |
| 🏠 **Local LLM Support** | Works with Ollama — your data never leaves your network |
| 📖 **Open Source** | Apache 2.0 licensed, community-driven |

---

## 🚀 Quick Start

### 1. Install

```bash
pip install opensre
```

### 2. Configure

```bash
# Set your Prometheus URL
export OPENSRE_PROMETHEUS_URL=http://prometheus:9090

# Set your LLM (Ollama, OpenAI, or Anthropic)
export OPENSRE_LLM_PROVIDER=ollama
export OPENSRE_OLLAMA_MODEL=llama3.1:8b

# Optional: Slack notifications
export OPENSRE_SLACK_BOT_TOKEN=xoxb-your-token
```

### 3. Investigate

```bash
opensre investigate "high error rate on checkout service"
```

That's it! OpenSRE queries your Prometheus, checks Kubernetes, and finds the root cause.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         OpenSRE Core                             │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ Observer │  │ Reasoner │  │  Actor   │  │ Notifier │        │
│  │  Agent   │  │  Agent   │  │  Agent   │  │  Agent   │        │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘        │
│       │             │             │             │               │
│  ┌────┴─────────────┴─────────────┴─────────────┴────┐         │
│  │                    Message Bus                      │         │
│  └─────────────────────────┬───────────────────────────┘         │
│                            │                                     │
│  ┌─────────────────────────┴───────────────────────────┐        │
│  │                     Skill Layer                      │        │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │        │
│  │  │Prometheus│ │Kubernetes│ │  Slack   │ │PagerDut│ │        │
│  │  └──────────┘ └──────────┘ └──────────┘ └────────┘ │        │
│  └──────────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         │                    │                    │
         ▼                    ▼                    ▼
   ┌──────────┐         ┌──────────┐        ┌──────────┐
   │Prometheus│         │Kubernetes│        │  Slack   │
   └──────────┘         └──────────┘        └──────────┘
```

### Multi-Agent System

| Agent | Role |
|-------|------|
| **Observer** | Collects metrics, logs, events from your infrastructure |
| **Reasoner** | Correlates signals to find root cause using LLM |
| **Actor** | Executes remediation actions (with approval) |
| **Notifier** | Sends updates to Slack, PagerDuty, etc. |

---

## 🔌 Built-in Skills

| Skill | Description | Actions |
|-------|-------------|---------|
| **prometheus** | Query metrics and alerts | query, alerts, silence |
| **kubernetes** | Manage K8s resources | get_pods, logs, rollback, scale |
| **slack** | Notifications and approvals | post_message, approval_request |
| **pagerduty** | Incident management | acknowledge, resolve |
| **aws** | AWS operations | describe_instances, cloudwatch |
| **gcp** | GCP operations | compute, monitoring |
| **azure** | Azure operations | vms, monitor |
| **http** | HTTP requests | get, post, health_check |
| **github** | Repository operations | issues, deployments |
| **jira** | Ticket management | create_issue, update |
| **argocd** | GitOps deployments | sync, rollback |
| **telegram** | Notifications | send_message |
| **dynatrace** | Observability | query_metrics, problems |

---

## 🤖 Pre-built Agents

| Agent | Trigger | Description |
|-------|---------|-------------|
| **incident-responder** | PagerDuty/Alertmanager webhook | Auto-responds to incidents |
| **pod-crash-handler** | Kubernetes events | Handles pod crashes with analysis |
| **deploy-validator** | ArgoCD/K8s webhook | Validates deployments post-rollout |
| **cert-checker** | Daily schedule | Monitors certificate expiry |
| **cost-anomaly** | Daily schedule | Detects cloud cost anomalies |
| **capacity-planner** | Weekly schedule | Forecasts resource needs |
| **runbook-executor** | Slack/webhook | Executes runbooks with approval |

---

## 📚 Documentation

- **[Getting Started](docs/getting-started.md)** — First investigation in 5 minutes
- **[Installation](docs/installation.md)** — All installation methods
- **[Configuration](docs/CONFIGURATION.md)** — Configuration reference
- **[CLI Reference](docs/cli-reference.md)** — All CLI commands
- **[API Reference](docs/api-reference.md)** — REST API documentation
- **[Skills](docs/skills/overview.md)** — Built-in and custom skills
- **[Agents](docs/agents/overview.md)** — Creating and deploying agents
- **[Architecture](docs/ARCHITECTURE.md)** — System design deep dive
- **[Security](docs/security.md)** — Security model and RBAC
- **[Deployment](docs/DEPLOYMENT.md)** — Production deployment guides
- **[Troubleshooting](docs/troubleshooting.md)** — Common issues and solutions

---

## 🔒 Security

OpenSRE is built with security first:

- **Human-in-the-Loop**: Dangerous actions require approval via Slack
- **RBAC**: Fine-grained permissions for users and agents
- **Audit Logging**: Every action is logged with full context
- **Secret Management**: Integrates with Vault, AWS Secrets Manager
- **Local LLM**: Use Ollama to keep all data on your network

---

## 🗺️ Roadmap

- [x] Core multi-agent architecture
- [x] Prometheus, Kubernetes, Slack skills
- [x] CLI and REST API
- [x] Ollama/OpenAI/Anthropic support
- [x] Slack approval workflows
- [ ] Web UI dashboard
- [ ] Log analysis (Loki, Elasticsearch)
- [ ] Trace analysis (Jaeger, Tempo)
- [ ] Anomaly detection
- [ ] Incident playbooks
- [ ] Multi-cluster support
- [ ] Terraform skill
- [ ] Datadog, New Relic skills
- [ ] Auto-remediation with ML

---

## 🤝 Contributing

We love contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

```bash
# Clone the repo
git clone https://github.com/srisainath/opensre.git
cd opensre

# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linting
ruff check .
mypy .
```

---

## 📄 License

OpenSRE is licensed under the [Apache License 2.0](LICENSE).

---

## 🌟 Star History

[![Star History Chart](https://api.star-history.com/svg?repos=srisainath/opensre&type=Date)](https://star-history.com/#srisainath/opensre&Date)

---

## 💬 Community

- **[GitHub Discussions](https://github.com/srisainath/opensre/discussions)** — Questions and ideas
- **[Discord](https://discord.gg/opensre)** — Real-time chat
- **[Twitter](https://twitter.com/opensre_dev)** — Updates and announcements

---

<div align="center">

**Made with ❤️ by the SRE community**

[⬆ Back to top](#opensre)

</div>
