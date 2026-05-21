# AutoSRE - Self-Improving AI SRE Agent

## Vision
An open-source, self-improving AI SRE agent that learns from every incident, adapts to your infrastructure, and gets better over time - like Hermes for infrastructure operations.

## Starting Point
**OpenSRE** (Tracer-Cloud/opensre) - 5470 stars, Apache 2.0
- 60+ integrations (Datadog, Grafana, AWS, GCP, Azure, K8s, etc.)
- Multi-LLM support (Anthropic, OpenAI, Gemini, Copilot, Ollama)
- Structured investigation workflow
- FastAPI backend, CLI interface

## What We're Building

### Core Differentiators from OpenSRE

1. **Self-Improving Memory System** (like Hermes)
   - Episodic memory: remembers past incidents and resolutions
   - Procedural memory: learns investigation patterns that work
   - Semantic memory: builds knowledge graph of your infrastructure
   - Auto-generates runbooks from successful investigations

2. **Skill System** (like Hermes skills)
   - Skills are learnable procedures (YAML + scripts)
   - Agent can create new skills from successful investigations
   - Skills can be shared across organizations
   - Version-controlled, auditable

3. **Multi-Agent Architecture**
   - Orchestrator agent: triages and delegates
   - Investigation agents: specialized per domain (K8s, DB, Network)
   - Remediation agents: can take action (with approval gates)
   - Learning agent: analyzes outcomes and improves system

4. **True Vendor/Cloud Agnostic**
   - No cloud-specific assumptions in core
   - Plugin architecture for integrations
   - Works on-prem, multi-cloud, hybrid
   - Bring your own observability stack

5. **Production-Ready Features**
   - Web UI for investigation management
   - Slack/Discord/Teams/Telegram integration
   - PagerDuty/OpsGenie webhook receiver
   - SSO/RBAC for enterprise
   - Audit logging for compliance

## Architecture

```
                                    ┌─────────────────┐
                                    │   Slack/PD/     │
                                    │   Telegram      │
                                    └────────┬────────┘
                                             │
┌─────────────────────────────────────────────────────────────────────┐
│                         AutoSRE Gateway                              │
│  (Webhook receiver, rate limiting, auth, routing)                   │
└────────┬────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Orchestrator Agent                              │
│  - Triage incoming alerts                                           │
│  - Load relevant skills and context                                 │
│  - Delegate to specialized agents                                   │
│  - Synthesize final report                                          │
└────────┬────────────────────────────────────────────────────────────┘
         │
         ├──────────────┬──────────────┬──────────────┐
         ▼              ▼              ▼              ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│ K8s Agent   │  │ DB Agent    │  │ AWS Agent   │  │ Custom      │
│             │  │             │  │             │  │ Agents      │
│ - Pod logs  │  │ - Slow      │  │ - CloudWatch│  │             │
│ - Events    │  │   queries   │  │ - EC2 status│  │ - Plugin    │
│ - Resources │  │ - Locks     │  │ - Lambda    │  │   system    │
│ - Helm      │  │ - Replica   │  │ - S3        │  │             │
└──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘
       │                │                │                │
       └────────────────┴────────────────┴────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        Memory System                                 │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ Episodic     │  │ Procedural   │  │ Semantic     │              │
│  │ Memory       │  │ Memory       │  │ Memory       │              │
│  │              │  │              │  │              │              │
│  │ Past         │  │ Skills &     │  │ Infra        │              │
│  │ incidents    │  │ runbooks     │  │ topology     │              │
│  │ (SQLite/PG)  │  │ (YAML+Git)   │  │ (Neo4j)      │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Learning Agent                                  │
│  - Analyzes successful investigations                               │
│  - Extracts patterns into skills                                    │
│  - Updates runbooks                                                 │
│  - Suggests infrastructure improvements                             │
└─────────────────────────────────────────────────────────────────────┘
```

## Project Structure

```
autosre/
├── README.md
├── LICENSE                    # Apache 2.0
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── Makefile
│
├── autosre/                   # Core Python package
│   ├── __init__.py
│   ├── cli/                   # CLI interface
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── investigate.py
│   │   └── onboard.py
│   │
│   ├── gateway/               # Webhook gateway
│   │   ├── __init__.py
│   │   ├── server.py
│   │   └── routes/
│   │       ├── pagerduty.py
│   │       ├── opsgenie.py
│   │       ├── datadog.py
│   │       └── generic.py
│   │
│   ├── agents/                # Multi-agent system
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── orchestrator.py
│   │   ├── investigator.py
│   │   ├── remediator.py
│   │   └── learner.py
│   │
│   ├── memory/                # Self-improving memory
│   │   ├── __init__.py
│   │   ├── episodic.py       # Past incidents
│   │   ├── procedural.py     # Skills & runbooks
│   │   └── semantic.py       # Knowledge graph
│   │
│   ├── skills/                # Built-in skills
│   │   ├── kubernetes/
│   │   ├── databases/
│   │   ├── aws/
│   │   ├── gcp/
│   │   ├── azure/
│   │   └── observability/
│   │
│   ├── integrations/          # Platform integrations (from OpenSRE)
│   │   ├── __init__.py
│   │   ├── registry.py
│   │   ├── datadog/
│   │   ├── grafana/
│   │   ├── prometheus/
│   │   ├── cloudwatch/
│   │   ├── kubernetes/
│   │   └── ...
│   │
│   ├── tools/                 # Agent tools
│   │   ├── __init__.py
│   │   ├── registry.py
│   │   └── ... (from OpenSRE)
│   │
│   ├── llm/                   # LLM providers
│   │   ├── __init__.py
│   │   ├── provider.py
│   │   ├── anthropic.py
│   │   ├── openai.py
│   │   ├── gemini.py
│   │   └── ollama.py
│   │
│   ├── delivery/              # Alert delivery
│   │   ├── __init__.py
│   │   ├── slack.py
│   │   ├── discord.py
│   │   ├── telegram.py
│   │   └── pagerduty.py
│   │
│   └── web/                   # Web UI API
│       ├── __init__.py
│       ├── app.py
│       └── routes/
│
├── web/                       # Web UI (Next.js)
│   ├── package.json
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx
│   │   │   ├── investigations/
│   │   │   ├── skills/
│   │   │   ├── memory/
│   │   │   └── settings/
│   │   └── components/
│   └── ...
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── docs/
│   ├── quickstart.md
│   ├── architecture.md
│   ├── integrations.md
│   └── skills.md
│
├── charts/                    # Helm chart
│   └── autosre/
│
└── examples/
    ├── alerts/
    └── skills/
```

## Phase 1 - MVP (Launch Tomorrow)

### What's included:
1. **CLI that works** (`autosre investigate`, `autosre onboard`)
2. **Core integrations** (Datadog, Grafana, Prometheus, K8s, AWS)
3. **Single agent** investigation flow
4. **Basic memory** (SQLite episodic)
5. **Slack/Telegram** delivery
6. **Docker Compose** deployment
7. **README** with quickstart

### What's NOT in MVP:
- Web UI (CLI only)
- Multi-agent system (single agent)
- Skill learning (manual skills only)
- Neo4j knowledge graph (SQLite only)
- SSO/RBAC

## Phase 2 - Self-Improvement (Week 2)

1. Skill extraction from investigations
2. Memory-based context loading
3. Runbook generation
4. Investigation pattern learning

## Phase 3 - Production (Week 3-4)

1. Web UI
2. Multi-agent architecture
3. Neo4j integration
4. Enterprise features

## Technical Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Language | Python 3.12+ | OpenSRE base, LLM ecosystem |
| Framework | FastAPI | OpenSRE base, async, fast |
| CLI | Click + Rich | OpenSRE base, great DX |
| DB | SQLite -> Postgres | Start simple, scale later |
| LLM | Multi-provider | Copilot default (free), fall back to others |
| Deployment | Docker Compose | Simple, portable |
| License | Apache 2.0 | Commercial-friendly |

## Success Criteria for MVP

1. [ ] `autosre onboard` sets up in < 5 minutes
2. [ ] `autosre investigate "pod crashlooping"` produces useful RCA
3. [ ] Works with Datadog OR Grafana OR Prometheus
4. [ ] Sends summary to Slack/Telegram
5. [ ] README is clear and complete
6. [ ] Docker Compose works out of the box
7. [ ] GitHub repo is public and star-worthy
