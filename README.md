# OpenSRE

<div align="center">

![OpenSRE Logo](docs/images/logo.png)

**AI-Powered Incident Response for SRE Teams**

[![CI](https://github.com/srisainath/opensre/actions/workflows/ci.yaml/badge.svg)](https://github.com/srisainath/opensre/actions/workflows/ci.yaml)
[![Tests](https://img.shields.io/badge/tests-384%20passed-brightgreen)](https://github.com/srisainath/opensre/actions)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

[Documentation](https://opensre.dev/docs) · [Demo](#-try-the-demo) · [Discord](https://discord.gg/opensre) · [Blog](https://opensre.dev/blog)

</div>

---

## 🎬 Demo Video

<!-- TODO: Replace with actual demo video -->
[![OpenSRE Demo](https://img.shields.io/badge/▶_Watch_Demo-4285F4?style=for-the-badge&logo=youtube&logoColor=white)](https://github.com/srisainath/opensre)

> *See OpenSRE investigate a memory leak, identify the root cause, and suggest a rollback — in under 60 seconds.*

---

## 🚨 Stop Debugging at 3 AM

Your phone buzzes. PagerDuty alert. You stumble to your laptop. Query Prometheus. Tail logs. Check deploys. 45 minutes later, you find it: a memory leak.

**OpenSRE investigates incidents automatically while you sleep.**

```
🚨 ALERT: checkout-service Memory Alert
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Error Rate:     8.3%        (threshold: 1%)
• Memory:         1.8GB       (baseline: 500MB)
• OOMKilled:      3 pods      (last 10 min)
• Recent Deploy:  v2.4.1      (12 min ago)

🔍 OBSERVER AGENT — Collecting signals...
  ✓ prometheus: memory_working_set_bytes trending +15% over 10m
  ✓ kubernetes: 3x OOMKilled events in checkout-service namespace
  ✓ deploy: v2.4.1 rolled out 12 minutes ago by deploy-bot
  ✓ baseline: Normal memory ~500MB, current 1.8GB (+260%)

🧠 AI ANALYSIS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 ROOT CAUSE:
Memory leak introduced in deployment v2.4.1

📊 CONFIDENCE: 94%

⚡ IMMEDIATE ACTION:
Rollback to v2.4.0

🔍 FOLLOW-UP:
Profile memory usage, check for unclosed connections
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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

## 🎯 Try the Demo

Experience OpenSRE without any infrastructure setup:

```bash
# Clone and setup
git clone https://github.com/srisainath/opensre.git
cd opensre
python -m venv .venv && source .venv/bin/activate
pip install -e .

# Start Ollama (if not running)
ollama serve &
ollama pull llama3:8b

# Run the interactive demo
python demo.py
```

The demo includes five real-world scenarios:
1. **Memory Leak** - Post-deployment OOMKill cascade
2. **Database Exhaustion** - Connection pool saturation
3. **Certificate Expiry** - SSL handshake failures
4. **Crash Loop** - Dependency failure causing restarts
5. **CPU Spike** - Traffic surge overwhelming capacity

---

## 🚀 Quick Start (With Real Infrastructure)

### 1. Install

```bash
pip install opensre
```

### 2. Configure

```bash
# Prometheus connection
export OPENSRE_PROMETHEUS_URL=http://prometheus:9090

# LLM provider (choose one)
# Option A: Local with Ollama (recommended for privacy)
export OPENSRE_LLM_PROVIDER=ollama
export OPENSRE_OLLAMA_MODEL=llama3:8b

# Option B: OpenAI
export OPENSRE_LLM_PROVIDER=openai
export OPENSRE_OPENAI_API_KEY=sk-...
export OPENSRE_OPENAI_MODEL=gpt-4o

# Option C: Anthropic
export OPENSRE_LLM_PROVIDER=anthropic
export OPENSRE_ANTHROPIC_API_KEY=sk-ant-...
export OPENSRE_ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
```

### 3. Investigate

```bash
opensre investigate "high error rate on checkout service"
```

---

## 📊 Real Integration Examples

### Prometheus Queries

OpenSRE generates and executes PromQL queries automatically:

```python
from opensre_core.skills.prometheus import PrometheusSkill

prometheus = PrometheusSkill(url="http://prometheus:9090")

# Query error rate
result = await prometheus.query(
    'sum(rate(http_requests_total{status=~"5.."}[5m])) / '
    'sum(rate(http_requests_total[5m])) * 100'
)
print(f"Error rate: {result['value']}%")

# Get firing alerts
alerts = await prometheus.get_alerts()
for alert in alerts:
    print(f"🚨 {alert['labels']['alertname']}: {alert['annotations']['summary']}")
```

### Kubernetes Operations

Inspect and remediate cluster issues:

```python
from opensre_core.skills.kubernetes import KubernetesSkill

k8s = KubernetesSkill()

# Get pods in CrashLoopBackOff
pods = await k8s.get_pods(
    namespace="production",
    field_selector="status.phase!=Running"
)

# Get recent events for a troubled pod
events = await k8s.get_events(
    namespace="production",
    field_selector=f"involvedObject.name={pod_name}"
)

# Rollback a deployment
await k8s.rollback_deployment(
    namespace="production",
    name="checkout-service",
    revision=None  # Previous revision
)
```

### LLM Analysis

Generate root cause analysis with multiple LLM backends:

```python
from opensre_core.adapters.llm import create_llm_adapter

# Create adapter (auto-detects from environment)
llm = create_llm_adapter()

# Or specify provider explicitly
llm = create_llm_adapter(provider="openai")

# Generate analysis
response = await llm.generate(
    prompt="""
    Analyze this incident:
    - checkout-service error rate: 8.3%
    - memory_working_set_bytes: 1.8GB (baseline: 500MB)
    - 3 OOMKilled events in last 10 minutes
    - Deployment v2.4.1 rolled out 12 minutes ago
    
    What is the root cause and recommended action?
    """,
    temperature=0.3,
    max_tokens=1024
)

print(response.content)
print(f"Tokens used: {response.input_tokens} in, {response.output_tokens} out")
print(f"Latency: {response.latency_ms}ms")
```

### Slack Notifications

Send alerts and get approval for actions:

```python
from opensre_core.skills.slack import SlackSkill

slack = SlackSkill(bot_token="xoxb-...")

# Send an alert
await slack.post_message(
    channel="#incidents",
    text="🚨 checkout-service error rate spike detected"
)

# Request approval for action
approval = await slack.request_approval(
    channel="#sre-oncall",
    title="Rollback checkout-service",
    description="Memory leak detected in v2.4.1. Recommend rollback to v2.4.0.",
    actions=["approve", "reject", "investigate"]
)

if approval.action == "approve":
    await k8s.rollback_deployment(...)
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         OpenSRE Core                             │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ Observer │  │ Reasoner │  │  Actor   │  │ Notifier │        │
│  │  Agent   │──│  Agent   │──│  Agent   │──│  Agent   │        │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │
│       │             │             │             │               │
│  ┌────┴─────────────┴─────────────┴─────────────┴────┐         │
│  │                    Skill Layer                     │         │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────┐ │         │
│  │  │Prometheus│ │Kubernetes│ │   LLM    │ │ Slack │ │         │
│  │  └──────────┘ └──────────┘ └──────────┘ └───────┘ │         │
│  └────────────────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
   │Prometheus│   │Kubernetes│   │ Ollama/  │   │  Slack   │
   │          │   │          │   │ OpenAI   │   │          │
   └──────────┘   └──────────┘   └──────────┘   └──────────┘
```

### Multi-Agent Flow

1. **Observer Agent** — Collects signals from Prometheus, Kubernetes, logs
2. **Reasoner Agent** — Analyzes signals with LLM, determines root cause
3. **Actor Agent** — Proposes and executes remediation (with approval)
4. **Notifier Agent** — Sends updates to Slack, PagerDuty, email

---

## 🔌 Built-in Skills

| Skill | Description | Actions |
|-------|-------------|---------|
| **prometheus** | Query metrics and alerts | `query`, `alerts`, `silence` |
| **kubernetes** | Manage K8s resources | `get_pods`, `logs`, `rollback`, `scale` |
| **slack** | Notifications and approvals | `post_message`, `approval_request` |
| **pagerduty** | Incident management | `acknowledge`, `resolve` |
| **aws** | AWS operations | `describe_instances`, `cloudwatch` |
| **http** | HTTP requests | `get`, `post`, `health_check` |
| **github** | Repository operations | `issues`, `deployments` |

See [docs/skills](docs/skills) for the complete list and configuration options.

---

## 📚 Documentation

| Topic | Description |
|-------|-------------|
| [Getting Started](docs/getting-started.md) | First investigation in 5 minutes |
| [Configuration](docs/CONFIGURATION.md) | Environment variables and settings |
| [Skills Reference](docs/skills/overview.md) | Built-in and custom skills |
| [Architecture](docs/ARCHITECTURE.md) | System design deep dive |
| [Deployment](docs/DEPLOYMENT.md) | Kubernetes, Docker, bare metal |
| [Security](docs/security.md) | RBAC, audit logging, secrets |

---

## 🛠️ Development

```bash
# Clone the repo
git clone https://github.com/srisainath/opensre.git
cd opensre

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install with dev dependencies
pip install -e ".[dev]"

# Run tests (384 tests, all passing)
pytest

# Run linting
ruff check .
mypy .

# Run the demo
python demo.py
```

---

## 🔒 Security

- **Human-in-the-Loop**: All remediation actions require explicit approval
- **Local LLM**: Use Ollama to keep sensitive data on-premises
- **Audit Logging**: Every action is logged with full context
- **RBAC**: Fine-grained permissions for users and service accounts
- **Secret Management**: Integrates with Vault, AWS Secrets Manager

---

## 🗺️ Roadmap

- [x] Multi-agent architecture (Observer → Reasoner → Actor)
- [x] Prometheus, Kubernetes, Slack skills
- [x] Ollama, OpenAI, Anthropic LLM support
- [x] Interactive demo with 5 scenarios
- [x] 384 passing tests
- [ ] Web UI dashboard
- [ ] Log analysis (Loki, Elasticsearch)
- [ ] Trace analysis (Jaeger, Tempo)
- [ ] Anomaly detection with ML
- [ ] Multi-cluster support

---

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

Quick start:
```bash
git clone https://github.com/srisainath/opensre.git
cd opensre
pip install -e ".[dev]"
pytest  # Make sure tests pass
# Make your changes
# Submit a PR!
```

---

## 📄 License

OpenSRE is licensed under the [Apache License 2.0](LICENSE).

---

## 💬 Community

- **[GitHub Discussions](https://github.com/srisainath/opensre/discussions)** — Questions and ideas
- **[Discord](https://discord.gg/opensre)** — Real-time chat
- **[Twitter](https://twitter.com/opensre_dev)** — Updates and announcements

---

<div align="center">

**Made with ❤️ by SREs, for SREs**

[⬆ Back to top](#opensre)

</div>
