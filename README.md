<p align="center">
  <img src="docs/assets/logo.png" alt="AutoSRE Logo" width="200"/>
</p>

<h1 align="center">AutoSRE</h1>

<p align="center">
  <strong>🤖 The AI SRE that investigates incidents like your best on-call engineer — but faster.</strong>
</p>

<p align="center">
  <a href="https://github.com/opensre/autosre/actions"><img src="https://img.shields.io/github/actions/workflow/status/opensre/autosre/ci.yml?style=flat-square&logo=github" alt="CI Status"></a>
  <a href="https://pypi.org/project/autosre"><img src="https://img.shields.io/pypi/v/autosre?style=flat-square&logo=pypi&logoColor=white" alt="PyPI Version"></a>
  <a href="https://pypi.org/project/autosre"><img src="https://img.shields.io/pypi/pyversions/autosre?style=flat-square&logo=python&logoColor=white" alt="Python Versions"></a>
  <a href="https://github.com/opensre/autosre/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue?style=flat-square" alt="License"></a>
  <a href="https://github.com/opensre/autosre"><img src="https://img.shields.io/github/stars/opensre/autosre?style=flat-square&logo=github" alt="Stars"></a>
</p>

<p align="center">
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-features">Features</a> •
  <a href="#-how-it-works">How It Works</a> •
  <a href="#-integrations">Integrations</a> •
  <a href="docs/">Docs</a>
</p>

---

<p align="center">
  <em>45-minute investigations → 5 minutes. Autonomous triage. Evidence-based RCA. Human-in-the-loop for safety.</em>
</p>

<!-- Demo GIF Placeholder -->
<p align="center">
  <img src="docs/assets/demo.gif" alt="AutoSRE Demo" width="700"/>
</p>

---

## ⚡ Quick Start

```bash
# Install
pip install autosre

# Configure (interactive setup)
autosre config init

# Investigate your first incident
autosre investigate "checkout service 500 errors" --service checkout-service
```

Or with Docker:
```bash
docker run -it --rm -v ~/.autosre:/root/.autosre ghcr.io/opensre/autosre investigate "high latency on api-gateway"
```

**That's it.** No Neo4j. No Postgres. No infrastructure. Just `pip install` and go.

---

## ✨ Features

### 🔍 **Autonomous Investigation**
Multi-agent investigation that works like your best SRE: triage → contain → investigate → resolve → learn.

```bash
$ autosre investigate "payment failures spiking"

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

### 📊 **SLO-Driven Operations**
Error budgets, multi-window burn rates, deployment gating — all built-in.

```bash
$ autosre slo status --service checkout-service

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
git clone https://github.com/opensre/autosre.git
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

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

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
- 📚 Documentation and examples
- 🐛 Bug reports and fixes

---

## 📄 License

Apache 2.0 — See [LICENSE](LICENSE) for details.

---

<p align="center">
  <strong>Built by SREs, for SREs.</strong><br>
  <sub>Tired of 3am pages? Let AutoSRE handle the first 5 minutes.</sub>
</p>

<p align="center">
  <a href="https://github.com/opensre/autosre">⭐ Star us on GitHub</a> •
  <a href="https://discord.gg/opensre">💬 Join Discord</a> •
  <a href="https://twitter.com/opensre">🐦 Follow on Twitter</a>
</p>
