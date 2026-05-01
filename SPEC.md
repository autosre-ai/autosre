# AutoSRE - Specification Document

**Version:** 1.0.0
**Last Updated:** 2026-05-01
**Status:** Production Ready (MVP)

## Overview

AutoSRE is an open-source AI-powered SRE (Site Reliability Engineering) automation toolkit. It provides both CLI and Web UI interfaces for incident response, runbook execution, health checks, and alerting.

## Core Features

### 1. CLI Interface (`autosre`)
- **init**: Initialize AutoSRE in a project directory
- **status**: Show system health and configuration
- **context**: Manage context store (services, ownership, changes)
- **eval**: Run evaluation scenarios
- **agent**: Run the AI SRE agent
- **sandbox**: Manage Kubernetes sandbox environments
- **feedback**: Collect and manage feedback
- **web**: Start the web dashboard

### 2. Web Dashboard
- Real-time system status
- Evaluation scenario management
- Context store browsing
- Agent activity monitoring
- Feedback submission

### 3. Context Store
A centralized repository tracking:
- **Services**: Names, namespaces, teams, dependencies
- **Ownership**: Team mappings, on-call schedules
- **Changes**: Deployments, config changes, PRs
- **Alerts**: Active and historical alerts
- **Runbooks**: Incident response procedures

### 4. AI Agent
- **Observer**: Watches for alerts and anomalies
- **Reasoner**: LLM-powered root cause analysis
- **Actor**: Execute remediation with guardrails

### 5. Integrations
| Integration | Status | Purpose |
|-------------|--------|---------|
| Kubernetes | ✅ Ready | Service discovery, pod status, events |
| Prometheus | ✅ Ready | Metrics, alerts, Alertmanager |
| GitHub | ✅ Ready | Deployments, PRs, commits |
| PagerDuty | ✅ Ready | Incident management |
| Slack | ✅ Ready | Notifications, approvals |

### 6. Evaluation Framework
- 35+ built-in incident scenarios
- Difficulty levels: Easy, Medium, Hard
- Categories: CPU, Memory, Network, Database, Kubernetes

## Technical Stack

### Backend
- **Language**: Python 3.11+
- **CLI Framework**: Click + Rich
- **Web Framework**: FastAPI + Jinja2
- **Async HTTP**: HTTPX
- **Validation**: Pydantic v2
- **Config**: pydantic-settings + python-dotenv

### Frontend (Web UI)
- **Framework**: HTMX (hypermedia-driven)
- **Styling**: Tailwind CSS
- **No heavy JS frameworks** - server-rendered HTML

### Data Storage
- SQLite for context store
- JSON files for configuration
- YAML for runbooks

### LLM Support
- Ollama (local, default)
- OpenAI (cloud)
- Anthropic (cloud)
- Azure OpenAI (enterprise)

## Installation Methods

### PyPI (Recommended)
```bash
pip install autosre
# With extras
pip install autosre[all]  # Full installation
pip install autosre[llm]  # LLM providers
pip install autosre[sandbox]  # Docker/Kind support
```

### From Source
```bash
git clone https://github.com/opensre/autosre.git
cd autosre
pip install -e ".[all,dev]"
```

### Docker
```bash
docker pull opensre/autosre:latest
docker run -p 8080:8080 opensre/autosre web start
```

## Demo Mode

For demonstration without real infrastructure:

```bash
# Initialize with demo data
autosre init --demo

# Run evaluation scenarios
autosre eval run --scenario high_cpu

# Start web UI with mock data
autosre web start --demo
```

## API Endpoints (Web)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Dashboard |
| `/health` | GET | Health check |
| `/api/docs` | GET | OpenAPI docs |
| `/evals` | GET | Evaluation page |
| `/evals/run` | POST | Run a scenario |
| `/context` | GET | Context store |
| `/agent` | GET | Agent status |
| `/feedback` | GET/POST | Feedback form |

## Security Features

- **Guardrails**: Approval workflows for risky actions
- **Sanitization**: PII removal from logs
- **Audit Logging**: All actions tracked
- **RBAC**: Role-based access (API keys)

## Success Criteria

1. ✅ CLI installs via `pip install autosre`
2. ✅ Web UI accessible at `http://localhost:8080`
3. ✅ Demo mode works without external dependencies
4. ✅ 35+ evaluation scenarios runnable
5. ✅ All 842 unit tests passing
6. ✅ Documentation complete
7. ⏳ Test coverage >80%
8. ⏳ E2E browser tests for Web UI

## Non-Goals (v1.0)

- Multi-tenant SaaS deployment
- Production incident management (this is a toolkit, not a platform)
- Real-time collaboration features
- Native mobile apps

## Future Roadmap (v1.1+)

- [ ] Datadog integration
- [ ] Grafana Loki integration
- [ ] OpsGenie integration
- [ ] Multi-cluster support
- [ ] Custom scenario builder UI
