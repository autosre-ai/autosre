<p align="center">
  <img src="docs/assets/logo.png" alt="AutoSRE Logo" width="200"/>
</p>

<h1 align="center">AutoSRE</h1>

<p align="center">
  <strong>🤖 The AI SRE that investigates incidents like your best on-call engineer — but faster.</strong>
</p>

<p align="center">
  <a href="https://github.com/autosre-ai/autosre/actions"><img src="https://img.shields.io/github/actions/workflow/status/autosre-ai/autosre/ci.yml?style=flat-square&logo=github" alt="CI Status"></a>
  <a href="https://pypi.org/project/autosre-ai"><img src="https://img.shields.io/pypi/v/autosre-ai?style=flat-square&logo=pypi&logoColor=white" alt="PyPI Version"></a>
  <a href="https://pypi.org/project/autosre-ai"><img src="https://img.shields.io/pypi/pyversions/autosre-ai?style=flat-square&logo=python&logoColor=white" alt="Python Versions"></a>
  <a href="https://github.com/autosre-ai/autosre/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue?style=flat-square" alt="License"></a>
  <a href="https://github.com/autosre-ai/autosre"><img src="https://img.shields.io/github/stars/autosre-ai/autosre?style=flat-square&logo=github" alt="Stars"></a>
</p>

<p align="center">
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-features">Features</a> •
  <a href="#-how-it-works">How It Works</a> •
  <a href="#-integrations">Integrations</a> •
  <a href="#-cli-reference">CLI Reference</a> •
  <a href="docs/">Docs</a>
</p>

---

<p align="center">
  <em>45-minute investigations → 5 minutes. Autonomous triage. Evidence-based RCA. Human-in-the-loop for safety.</em>
</p>

## 🎬 See It In Action

<p align="center">
  <img src="docs/assets/demo.gif" alt="AutoSRE Demo - AI-powered incident investigation" width="700"/>
</p>

<p align="center">
  <sub>
    ▲ AutoSRE automatically triages alerts, gathers evidence from Kubernetes, Prometheus, and logs,
    <br>tests hypotheses, identifies root cause, and recommends remediation — all in under 5 minutes.
  </sub>
</p>

<details>
<summary><strong>📹 What the demo shows</strong></summary>

1. **Alert Triage** — Receives "payment service 500 errors" alert
2. **Evidence Gathering** — Queries K8s pods, Prometheus metrics, recent deployments
3. **Hypothesis Testing** — Tests deployment bug vs DB issues vs resource exhaustion
4. **Root Cause** — Identifies null pointer in v2.3.1 with 92% confidence
5. **Human Approval** — Requests confirmation before rollback action
6. **Memory Recall** — Shows similar past incidents for context

Try it yourself:
```bash
# Mock mode (no external dependencies)
python examples/demo_simple.py

# With your LLM configured
autosre investigate run "payment service 500 errors" --service payment-service
```

</details>

---

## ⚡ Quick Start

```bash
# Install
pip install autosre-ai

# Configure (interactive setup)
autosre config init

# Investigate your first incident
autosre investigate run "checkout service 500 errors" --service checkout-service
```

Or with Docker:
```bash
docker run -it --rm -v ~/.autosre:/root/.autosre ghcr.io/autosre-ai/autosre investigate run "high latency on api-gateway"
```

**That's it.** No Neo4j. No Postgres. No infrastructure. Just `pip install` and go.

---

## ✨ Features

### 🔍 **Autonomous Investigation**
Multi-agent investigation that works like your best SRE: triage → contain → investigate → resolve → learn.

```bash
$ autosre investigate run "payment failures spiking"

[Triage] Confirmed: payment-service 5xx rate at 12% (normally <0.1%)
[Scope] Affected: checkout-service, order-service (downstream)
[Hypothesis] Testing: Recent deployment of payment-service v2.3.1
[Evidence] Deployment at 14:02, errors started 14:05 ✓
[Root Cause] payment-service v2.3.1 introduced null pointer in retry logic
[Recommendation] Rollback to v2.3.0 (requires approval)
```

### 🧠 **Episodic Memory**
Learns from every investigation. Recalls similar incidents. Gets smarter over time.

```bash
$ autosre memory search "database timeout"

Found 3 similar incidents:
├── inv_abc123: PostgreSQL connection pool exhaustion (resolved in 8m)
├── inv_def456: Slow query blocking connections (resolved in 12m)
└── inv_ghi789: Network partition to RDS (resolved in 23m)
```

### 📊 **SLO-Driven Operations** *(Coming Soon)*
Error budgets, multi-window burn rates, deployment gating — all built-in.

```
# Example output (planned feature):
checkout-service SLO Status
├── Availability: 99.92% (target: 99.9%) ✓
├── Latency p99: 245ms (target: 300ms) ✓
├── Error Budget: 72% remaining
│   ├── 1h burn rate: 0.8x
│   ├── 6h burn rate: 1.2x
│   └── 24h burn rate: 0.9x
└── Deploys: ALLOWED
```

### 🛡️ **AI Safety Built-In**
Every decision has confidence scores. Critical actions require human approval. Full audit trails.

- **Hypothesis-driven reasoning** with falsifiable criteria
- **Confidence scoring** (0.0-1.0) on every decision
- **Human-in-the-loop** for remediation actions
- **AI error budgets** tracking accuracy over time

### 🔧 **Extensible Skills System**
Modular investigation skills: Kubernetes, metrics, logs, traces, infrastructure.

```
skills/
├── kubernetes/         # Pod states, deployments, events
├── metrics-analysis/   # Prometheus, Datadog, Grafana
├── log-analysis/       # Pattern matching, anomaly detection
├── traces/             # Distributed tracing analysis
├── infrastructure/     # AWS, GCP resource checks
└── investigation/      # Methodology and hypothesis testing
```

### 📝 **Automated Postmortems**
Blameless postmortems with auto-generated timelines, metrics snapshots, and action items.

---

## 🎯 How It Works

```
┌────────────────────────────────────────────────────────────────┐
│                     autosre investigate                         │
└────────────────────────────┬───────────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │   Orchestrator   │
                    │   (LangGraph)    │
                    └────────┬────────┘
                             │
         ┌───────────┬───────┴───────┬───────────┐
         │           │               │           │
    ┌────▼────┐ ┌────▼────┐   ┌─────▼────┐ ┌────▼────┐
    │ Memory  │ │Topology │   │ Planner  │ │  LLM    │
    │(SQLite) │ │ (YAML)  │   │  Agent   │ │ Router  │
    └─────────┘ └─────────┘   └────┬─────┘ └─────────┘
                                   │
               ┌─────────┬─────────┼─────────┬─────────┐
               │         │         │         │         │
          ┌────▼───┐┌────▼───┐┌────▼───┐┌────▼───┐┌────▼───┐
          │  K8s   ││Metrics ││  Logs  ││ Traces ││ Infra  │
          │Subagent││Subagent││Subagent││Subagent││Subagent│
          └────┬───┘└────┬───┘└────┬───┘└────┬───┘└────┬───┘
               └─────────┴─────────┴─────────┴─────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │         Synthesizer         │
                    │   (Evidence → Root Cause)   │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │     Writeup & Actions       │
                    │  (Postmortem, Remediation)  │
                    └─────────────────────────────┘
```

**Key Concepts:**

| Component | What It Does |
|-----------|--------------|
| **Orchestrator** | Coordinates investigation phases (Triage → Mitigate → Diagnose → Resolve) |
| **Episodic Memory** | SQLite-based learning from past investigations with FTS5 search |
| **Service Topology** | YAML-defined service dependencies for blast radius analysis |
| **Subagents** | Parallel specialists (Kubernetes, metrics, logs, traces) |
| **Synthesizer** | Merges evidence, tests hypotheses, identifies root cause |

---

## 🔌 Integrations

| Category | Supported |
|----------|-----------|
| **Observability** | Prometheus, Grafana, Datadog |
| **Incident Management** | PagerDuty, Slack, OpsGenie |
| **Infrastructure** | Kubernetes, AWS, GCP |
| **Source Control** | GitHub, GitLab |
| **Issue Tracking** | Jira, Linear |

---

## 💻 CLI Reference

AutoSRE provides a powerful CLI for investigations and management.

### Quick Commands

```bash
# Start an investigation (shortcut for 'investigate run')
autosre run "High error rate on checkout" --service checkout

# Check system status
autosre status

# Interactive chat session
autosre chat

# Run health check
autosre doctor
```

### Investigation Commands

```bash
# Full investigation with real infrastructure
autosre investigate run "API latency spike" --service api-gateway

# Demo mode (no infrastructure required)
autosre investigate run "Memory leak detected" --demo

# Continuous monitoring (re-runs every N seconds)
autosre investigate run "High error rate" --watch --watch-interval 120

# Save report to HTML
autosre investigate run "DB connection errors" --format html --save report.html

# Stream output in real-time (default behavior)
autosre investigate run "Redis connection timeout" --service cache-service
```

### Memory & Learning

```bash
# Search past incidents
autosre memory search "database timeout"

# List recent investigations
autosre memory list --limit 10

# Show memory statistics
autosre memory stats
```

### Model Configuration

```bash
# List available models
autosre model list

# Switch providers
autosre model use anthropic claude-3-5-sonnet-20241022
autosre model use openai gpt-4o
autosre model use ollama llama3.1:8b

# Test connection
autosre model test
```

### Webhook Server

```bash
# Start alert webhook server
autosre serve start --port 8080

# With Slack notifications
autosre serve start --notification-webhook https://hooks.slack.com/...

# Check server status
autosre serve status
```

### Additional Commands

```bash
# Interactive tutorial for new users
autosre tutorial

# Manage runbooks
autosre runbook list

# Use investigation templates
autosre template list

# Manage plugins
autosre plugin list

# Team collaboration
autosre team list

# Compare investigations
autosre diff INV_ID_1 INV_ID_2

# Autonomous agent mode
autosre agent run
```

📚 **Full CLI documentation:** [docs/COMMANDS.md](docs/COMMANDS.md)

---

## ⚙️ Configuration

AutoSRE is configured via environment variables or YAML:

```bash
# Set LLM provider
export OPENSRE_LLM_PROVIDER=anthropic
export OPENSRE_ANTHROPIC_API_KEY=sk-ant-...

# Or for OpenAI
export OPENSRE_LLM_PROVIDER=openai
export OPENSRE_OPENAI_API_KEY=sk-...

# Configure infrastructure
export OPENSRE_PROMETHEUS_URL=http://prometheus:9090
export OPENSRE_K8S_NAMESPACES=production,staging

# Or use the CLI
autosre config init
autosre config set llm_provider openai
```

📚 **Full configuration reference:** [docs/CONFIGURATION.md](docs/CONFIGURATION.md)

---

## 📈 Why AutoSRE?

| Before AutoSRE | After AutoSRE |
|----------------|---------------|
| 45+ min incident investigations | 5 min AI-assisted triage |
| Lost context between incidents | Episodic memory recalls similar issues |
| Tribal knowledge in runbooks | AI executes and learns from runbooks |
| Manual toil tracking | Auto-classified, automation suggested |
| Blame-filled postmortems | Auto-generated blameless documentation |

**Test Results:** 1,053 tests passing | 25+ investigation scenarios validated

---

## 🏗️ Production Deployment

For production deployments with persistent storage and multiple services, see the [Docker Deployment Guide](docs/deployment/docker.md).

<details>
<summary><strong>Quick Docker Compose Setup</strong></summary>

```bash
# Clone and setup
git clone https://github.com/autosre-ai/autosre.git
cd autosre
make setup

# Configure secrets
cp .env.example .env
vim .env  # Add your API keys

# Start all services
make dev

# Verify health
make health
```

**Services:**
| Service | Port | Description |
|---------|------|-------------|
| web-ui | 3000 | Next.js web interface |
| api-gateway | 8000 | FastAPI REST API |
| sre-agent | 8080 | AI agent service |
| postgres | 5432 | PostgreSQL database |
| neo4j | 7474 | Graph database (optional) |
| redis | 6379 | Cache & pub/sub |

</details>

---

## 🤝 Contributing

We welcome contributions! See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for the full development guide.

```bash
# Development setup
git clone https://github.com/opensre/autosre.git
cd autosre
pip install -e ".[dev]"
pytest  # Run the test suite
```

**Areas we need help:**
- 🔌 New integrations (Elastic, Splunk, New Relic)
- 📊 Investigation scenarios for evaluation
- 📚 Documentation and examples — see [examples/](examples/)
- 🐛 Bug reports and fixes

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [CLI Commands](docs/COMMANDS.md) | Complete CLI reference with all commands and options |
| [Configuration](docs/CONFIGURATION.md) | All configuration options and environment variables |
| [Development](docs/DEVELOPMENT.md) | Development setup, testing, and contribution guide |
| [Examples](examples/) | Example scripts and integrations |

---

## 📄 License

Apache 2.0 — See [LICENSE](LICENSE) for details.

---

<p align="center">
  <strong>Built by SREs, for SREs.</strong><br>
  <sub>Tired of 3am pages? Let AutoSRE handle the first 5 minutes.</sub>
</p>

<p align="center">
  <a href="https://github.com/autosre-ai/autosre">⭐ Star us on GitHub</a> •
  <a href="https://discord.gg/autosre">💬 Join Discord</a> •
  <a href="https://twitter.com/autosre_ai">🐦 Follow on Twitter</a>
</p>
