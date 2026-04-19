# OpenSRE

AI-powered incident response for Kubernetes. Get a root cause analysis at 3 AM, click approve, go back to sleep.

## What It Does

OpenSRE is your AI SRE teammate that:
- Automatically investigates Kubernetes incidents
- Correlates metrics, logs, and events
- Identifies root causes with confidence scores
- Suggests safe remediation actions
- Integrates with Slack, PagerDuty, and alerting systems

## Quick Start

### Prerequisites
- Python 3.11+
- Access to a Kubernetes cluster (minikube works)
- Prometheus (with kube-state-metrics)
- Ollama running locally OR Anthropic/OpenAI API key

### Installation

```bash
# Clone and install
git clone https://github.com/srisainath/opensre.git
cd opensre
pip install -e .

# Configure
cp .env.example .env
# Edit .env with your Prometheus URL and LLM settings

# Verify setup
opensre status
```

### First Investigation

```bash
# Check cluster health
opensre investigate "check health of default namespace"

# Investigate a specific issue
opensre investigate "high memory usage on payment-service" --namespace production

# Watch mode - monitor and auto-investigate
opensre watch --namespace production
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENSRE_PROMETHEUS_URL` | Prometheus server URL | `http://localhost:9090` |
| `OPENSRE_LLM_PROVIDER` | LLM provider (ollama/anthropic/openai) | `ollama` |
| `OPENSRE_OLLAMA_HOST` | Ollama server URL | `http://localhost:11434` |
| `OPENSRE_OLLAMA_MODEL` | Ollama model to use | `llama3:8b` |
| `OPENSRE_ANTHROPIC_API_KEY` | Anthropic API key | - |
| `OPENSRE_SLACK_BOT_TOKEN` | Slack bot token | - |
| `OPENSRE_SLACK_CHANNEL` | Slack channel for alerts | `#incidents` |

### Kubernetes RBAC

OpenSRE needs read access to pods, events, logs, and deployments. Apply the provided RBAC:

```bash
kubectl apply -f charts/opensre/templates/clusterrole.yaml
kubectl apply -f charts/opensre/templates/clusterrolebinding.yaml
```

## Commands

### CLI

```bash
# Investigate an issue
opensre investigate "<issue description>" [--namespace <ns>] [--verbose]

# Check connection status
opensre status

# Run as API server
opensre serve --port 8000

# Run as MCP server
opensre mcp

# Manage runbooks
opensre runbooks list
opensre runbooks show <name>
opensre runbooks search "<query>"

# Watch mode
opensre watch --namespace <ns> [--interval 60]
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/investigate` | POST | Run investigation |
| `/api/health` | GET | Health check |
| `/api/status` | GET | Connection status |
| `/api/runbooks` | GET | List runbooks |
| `/webhook/alert` | POST | Alertmanager webhook |

## Integrations

### Slack
Configure a Slack app with the `chat:write` scope. Set `OPENSRE_SLACK_BOT_TOKEN` and `OPENSRE_SLACK_CHANNEL`. Investigations will be posted with interactive approve/reject buttons.

### Alertmanager
Configure Alertmanager to send alerts to OpenSRE:

```yaml
receivers:
  - name: opensre
    webhook_configs:
      - url: http://opensre:8000/webhook/alert
```

### MCP (Model Context Protocol)
Run OpenSRE as an MCP server for Claude Desktop or VS Code:

```bash
opensre mcp
```

## Example Scenarios

### Memory Issue
```bash
opensre investigate "high memory usage on checkout-service"
```

Output:
```
🔍 Investigation: high memory usage on checkout-service

Root Cause: Memory leak in checkout-service caused by unclosed database connections
Confidence: 78%

Key Observations:
- [prometheus] checkout-service memory: 480MB / 512MB (94%)
- [kubernetes] Pod checkout-service-abc123: Running but approaching OOM
- [logs] ERROR: Connection pool exhausted

Recommended Actions:
[1] Restart checkout-service pods       (LOW risk)
[2] Scale checkout-service to 3 replicas (MEDIUM risk)
```

### Crashloop
```bash
opensre investigate "payment-service is crashlooping"
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Orchestrator                          │
│                                                               │
│   ┌───────────┐    ┌───────────┐    ┌───────────┐           │
│   │  Observer │ →  │  Reasoner │ →  │   Actor   │           │
│   └───────────┘    └───────────┘    └───────────┘           │
│         │                │                │                  │
│         ▼                ▼                ▼                  │
│   ┌───────────┐    ┌───────────┐    ┌───────────┐           │
│   │Prometheus │    │    LLM    │    │ Kubernetes│           │
│   │Kubernetes │    │  (Ollama/ │    │  Actions  │           │
│   │  Runbooks │    │ Anthropic)│    │           │           │
│   └───────────┘    └───────────┘    └───────────┘           │
└─────────────────────────────────────────────────────────────┘
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## License

Apache 2.0
