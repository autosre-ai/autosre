<p align="center">
  <img src="docs/assets/logo.svg" alt="AutoSRE Logo" width="120">
</p>

<h1 align="center">AutoSRE</h1>

<p align="center">
  <strong>AI-Powered Site Reliability Engineering Assistant</strong>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#deployment">Deployment</a> •
  <a href="#api-reference">API</a> •
  <a href="#contributing">Contributing</a>
</p>

<p align="center">
  <a href="https://github.com/autosre-ai/autosre/actions/workflows/ci.yaml">
    <img src="https://github.com/autosre-ai/autosre/actions/workflows/ci.yaml/badge.svg" alt="CI Status">
  </a>
  <a href="https://pypi.org/project/autosre/">
    <img src="https://img.shields.io/pypi/v/autosre.svg" alt="PyPI">
  </a>
  <a href="https://github.com/autosre-ai/autosre/releases">
    <img src="https://img.shields.io/github/v/release/autosre-ai/autosre" alt="Release">
  </a>
  <a href="https://github.com/autosre-ai/autosre/blob/main/LICENSE">
    <img src="https://img.shields.io/badge/license-Apache%202.0-blue.svg" alt="License">
  </a>
  <a href="https://python.org">
    <img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python">
  </a>
</p>

---

**AutoSRE** is an intelligent multi-agent system that automatically investigates production incidents, identifies root causes, and generates actionable remediation recommendations. It integrates with your existing observability stack (Prometheus, Loki, Kubernetes) and uses LLMs to reason through complex failure scenarios.

## ✨ Features

<table>
<tr>
<td width="50%">

### 🤖 Multi-Agent Investigation

Specialized AI agents work together to investigate incidents:

- **Triage Agent** — Classifies alerts, assesses severity
- **Kubernetes Agent** — Analyzes pod status, events, deployments
- **Metrics Agent** — Queries Prometheus, identifies anomalies
- **Logs Agent** — Searches Loki, correlates error patterns
- **Remediation Agent** — Generates safe, reversible fixes

</td>
<td width="50%">

### 🔄 Iterative Reasoning

Uses the ReAct pattern for thorough investigation:

```
🔍 Observe → 🤔 Think → 🛠️ Act → 🔁 Repeat
```

- Forms and tests hypotheses
- Gathers evidence from multiple sources
- Refines conclusions based on findings
- Explains reasoning at every step

</td>
</tr>
<tr>
<td width="50%">

### 🔌 Deep Integrations

Works with your existing infrastructure:

- **Prometheus** — PromQL queries, alerting
- **Loki** — Log search and correlation
- **Kubernetes** — Native cluster access
- **Alertmanager** — Alert ingestion
- **Slack/PagerDuty** — Notifications

</td>
<td width="50%">

### 🧠 Knowledge Base

Learns from past incidents:

- Stores runbooks and procedures
- Records incident history
- Suggests relevant past incidents
- Improves recommendations over time

</td>
</tr>
</table>

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              AutoSRE V2                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        🎯 Coordinator                                │   │
│  │   Orchestrates investigation flow, manages agent handoffs           │   │
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
                    ┌──────────────┐
                    │    Alert     │
                    │  Received    │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │   Triage     │
                    │   Agent      │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │   K8s    │ │ Metrics  │ │   Logs   │
        │  Agent   │ │  Agent   │ │  Agent   │
        └────┬─────┘ └────┬─────┘ └────┬─────┘
              │            │            │
              └────────────┼────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │ Remediation  │
                    │    Agent     │
                    └──────┬───────┘
                           │
                           ▼
               ┌───────────────────────┐
               │  Investigation Report │
               │  + Recommendations    │
               └───────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- An LLM API key (OpenAI, Anthropic, or local Ollama)

### Installation

```bash
# Install from PyPI
pip install autosre[all]

# Or clone the repository
git clone https://github.com/autosre-ai/autosre.git
cd autosre

# Run setup
make setup

# Edit configuration
vi .env  # Add your API keys

# Install dependencies
make install

# Start development servers
make dev
```

Open [http://localhost:3000](http://localhost:3000) for the UI and [http://localhost:8000/docs](http://localhost:8000/docs) for the API documentation.

### Docker Quick Start

```bash
# Copy environment file
cp .env.example .env
vi .env  # Add your API keys

# Start everything with Docker
make docker-up

# View logs
make docker-logs
```

### Example Investigation

```python
import asyncio
from autosre.core.alert import Alert
from autosre.agents.coordinator import Coordinator

async def investigate():
    # Create an alert from your monitoring system
    alert = Alert(
        name="HighErrorRate",
        description="Error rate > 5% for payment-service",
        severity="critical",
        service="payment-service",
        namespace="production",
        labels={"team": "payments", "env": "prod"},
    )

    # Run investigation
    coordinator = Coordinator()
    result = await coordinator.investigate(alert)

    # Print findings
    print(f"🎯 Root Cause: {result.root_cause}")
    print(f"📊 Confidence: {result.root_cause_confidence:.0%}")
    print(f"📝 Summary: {result.summary}")
    print("\n💡 Recommendations:")
    for rec in result.recommendations:
        print(f"   • {rec}")

asyncio.run(investigate())
```

**Example Output:**
```
🎯 Root Cause: Database connection pool exhaustion
📊 Confidence: 87%
📝 Summary: Payment-service is experiencing elevated error rates due to 
   database connection timeouts. The connection pool is saturated following 
   a recent traffic spike from a marketing campaign.

💡 Recommendations:
   • Increase connection pool size from 10 to 25
   • Add connection timeout monitoring
   • Configure connection pool metrics in Prometheus
   • Consider implementing connection pooling with PgBouncer
```

## ⚙️ Configuration

### Environment Variables

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

Create `config.yaml` for detailed settings:

```yaml
# config.yaml
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

## 🛠️ Development

### Project Structure

```
autosre-v2/
├── src/autosre/           # Python backend
│   ├── agents/            # AI agents (triage, investigation, remediation)
│   ├── api/               # FastAPI endpoints
│   ├── cli/               # Command-line interface
│   ├── core/              # Core types and utilities
│   ├── integrations/      # Prometheus, Loki, K8s clients
│   └── utils/             # Helpers and config
├── web-ui/                # React frontend
│   └── src/
│       ├── components/    # UI components
│       ├── hooks/         # React hooks
│       └── pages/         # Page components
├── tests/                 # Test suite
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── deploy/                # Deployment configs
│   ├── kubernetes/        # K8s manifests
│   └── helm/              # Helm chart
├── docker/                # Dockerfiles
└── docs/                  # Documentation
```

### Make Commands

```bash
# Development
make install        # Install all dependencies
make dev            # Start API + UI with hot reload
make dev-api        # Start API only
make dev-ui         # Start UI only

# Testing
make test           # Run all tests
make test-cov       # Run with coverage report
make test-unit      # Unit tests only
make lint           # Run linters
make format         # Format code

# Docker
make docker-up      # Start Docker Compose stack
make docker-down    # Stop stack
make docker-logs    # Follow logs
make docker-build   # Build images

# Kubernetes
make k8s-apply      # Apply manifests
make k8s-status     # Check deployment status
make helm-install   # Install with Helm

# Database
make db-migrate     # Run migrations
make db-reset       # Reset database (destructive!)

# See all commands
make help
```

### Running Tests

```bash
# All tests
make test

# With coverage
make test-cov

# Specific test file
uv run pytest tests/unit/test_triage_agent.py -v

# Integration tests (requires running services)
make docker-up
make test-integration
```

### Code Quality

```bash
# Run all checks
make check

# Format code
make format

# Fix linting issues
make lint-fix

# Type checking
uv run mypy src/
```

## 🚢 Deployment

### Docker Compose (Development/Staging)

```bash
# Start the full stack
docker compose up -d

# With custom environment
docker compose --env-file .env.staging up -d

# Scale workers
docker compose up -d --scale autosre-api=3
```

### Kubernetes

```bash
# Using kubectl
make k8s-apply

# Using Helm
make helm-install

# With custom values
helm upgrade --install autosre deploy/helm \
  --namespace autosre \
  --create-namespace \
  -f deploy/helm/values-production.yaml
```

### Helm Chart Values

```yaml
# values-production.yaml
replicaCount:
  api: 3
  ui: 2

image:
  registry: ghcr.io/autosre
  tag: v2.0.0

ingress:
  enabled: true
  className: nginx
  hosts:
    - host: autosre.example.com
      paths:
        - path: /
          pathType: Prefix

resources:
  api:
    requests:
      cpu: 500m
      memory: 512Mi
    limits:
      cpu: 2000m
      memory: 2Gi

autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70
```

## 📡 API Reference

### REST Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/investigate` | Start a new investigation |
| `GET` | `/api/v1/investigations` | List investigations |
| `GET` | `/api/v1/investigations/{id}` | Get investigation details |
| `POST` | `/api/v1/alerts/webhook` | Receive alerts (Alertmanager) |
| `GET` | `/api/v1/health` | Health check |
| `GET` | `/docs` | OpenAPI documentation |

### Start Investigation

```bash
curl -X POST http://localhost:8000/api/v1/investigate \
  -H "Content-Type: application/json" \
  -d '{
    "alert": {
      "name": "HighErrorRate",
      "description": "Error rate above 5%",
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

### Response

```json
{
  "id": "inv_abc123",
  "status": "completed",
  "alert": {
    "name": "HighErrorRate",
    "severity": "critical"
  },
  "root_cause": "Database connection pool exhaustion",
  "root_cause_confidence": 0.87,
  "summary": "Investigation identified connection pool...",
  "findings": [
    {
      "agent": "kubernetes",
      "finding": "Pod restarts detected: 5 in last hour",
      "evidence": ["kubectl get pods output..."]
    }
  ],
  "recommendations": [
    {
      "action": "Increase connection pool size",
      "priority": "high",
      "command": "kubectl set env deployment/payment-service DB_POOL_SIZE=25",
      "rollback": "kubectl set env deployment/payment-service DB_POOL_SIZE=10"
    }
  ],
  "timeline": [
    {"timestamp": "2024-01-15T10:30:00Z", "event": "Investigation started"},
    {"timestamp": "2024-01-15T10:30:05Z", "event": "Triage completed"}
  ]
}
```

### WebSocket (Real-time Updates)

```javascript
const ws = new WebSocket('ws://localhost:8000/api/v1/ws');

ws.onmessage = (event) => {
  const update = JSON.parse(event.data);
  console.log('Investigation update:', update);
};

// Start investigation via WebSocket
ws.send(JSON.stringify({
  type: 'investigate',
  alert: { name: 'HighErrorRate', ... }
}));
```

## 🔧 Extending

### Custom Investigation Agent

```python
from autosre.agents.base_agent import BaseAgent, AgentResult
from autosre.core.investigation import Investigation

class CloudWatchAgent(BaseAgent):
    """Custom agent for AWS CloudWatch integration."""
    
    agent_id = "cloudwatch"
    agent_name = "CloudWatch Investigation Agent"
    
    def __init__(self):
        super().__init__()
        self._register_tools()
    
    def _register_tools(self):
        self.tools.register(
            name="query_cloudwatch_logs",
            description="Query CloudWatch Logs Insights",
            parameters={
                "type": "object",
                "properties": {
                    "log_group": {"type": "string"},
                    "query": {"type": "string"},
                    "duration": {"type": "string", "default": "1h"}
                },
                "required": ["log_group", "query"]
            },
            handler=self._query_logs
        )
    
    async def _query_logs(self, log_group: str, query: str, duration: str = "1h"):
        # Implementation here
        pass
    
    def get_system_prompt(self, investigation: Investigation) -> str:
        return """You are a CloudWatch investigation agent.
        Analyze AWS CloudWatch logs and metrics to identify issues."""
    
    async def execute(self, investigation: Investigation) -> AgentResult:
        return await self.run_react_loop(
            investigation=investigation,
            initial_message="Analyzing CloudWatch logs and metrics..."
        )
```

### Custom Integration

```python
from autosre.integrations.base import BaseIntegration

class DatadogIntegration(BaseIntegration):
    """Datadog metrics and logs integration."""
    
    def __init__(self, api_key: str, app_key: str):
        self.api_key = api_key
        self.app_key = app_key
    
    async def query_metrics(self, query: str, duration: str) -> dict:
        # Implementation
        pass
    
    async def search_logs(self, query: str, duration: str) -> list:
        # Implementation
        pass
```

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

```bash
# Fork and clone
git clone https://github.com/YOUR_USERNAME/autosre-v2.git

# Create a branch
git checkout -b feature/amazing-feature

# Make changes and test
make check

# Commit and push
git commit -m "Add amazing feature"
git push origin feature/amazing-feature

# Open a Pull Request
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  Built with ❤️ by the AutoSRE Team
</p>

<p align="center">
  <a href="https://github.com/autosre/autosre-v2/issues">Report Bug</a> •
  <a href="https://github.com/autosre/autosre-v2/issues">Request Feature</a> •
  <a href="https://autosre.dev">Documentation</a>
</p>
