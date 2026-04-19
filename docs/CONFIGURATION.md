# Configuration

OpenSRE can be configured via environment variables, config files, or command-line arguments.

## Configuration Sources

Configuration is loaded in this order (later sources override earlier):

1. Default values
2. Config file (`config/opensre.yaml`)
3. Environment variables
4. Command-line arguments

## Environment Variables

### Core Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENSRE_LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | `INFO` |
| `OPENSRE_CONFIG_PATH` | Path to config file | `config/opensre.yaml` |
| `OPENSRE_DATA_DIR` | Data storage directory | `~/.opensre` |

### LLM Configuration

#### Ollama (Local)

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENSRE_LLM_PROVIDER` | Set to `ollama` | — |
| `OPENSRE_OLLAMA_HOST` | Ollama server URL | `http://localhost:11434` |
| `OPENSRE_OLLAMA_MODEL` | Model name | `llama3.1:8b` |

#### OpenAI

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENSRE_LLM_PROVIDER` | Set to `openai` | — |
| `OPENSRE_OPENAI_API_KEY` | Your API key | — |
| `OPENSRE_OPENAI_MODEL` | Model name | `gpt-4o` |
| `OPENSRE_OPENAI_BASE_URL` | Custom endpoint | `https://api.openai.com/v1` |

#### Anthropic

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENSRE_LLM_PROVIDER` | Set to `anthropic` | — |
| `OPENSRE_ANTHROPIC_API_KEY` | Your API key | — |
| `OPENSRE_ANTHROPIC_MODEL` | Model name | `claude-3-5-sonnet-20241022` |

### Prometheus

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENSRE_PROMETHEUS_URL` | Prometheus server URL | `http://localhost:9090` |
| `OPENSRE_PROMETHEUS_AUTH` | Authentication type (none, basic, bearer) | `none` |
| `OPENSRE_PROMETHEUS_USERNAME` | Basic auth username | — |
| `OPENSRE_PROMETHEUS_PASSWORD` | Basic auth password | — |
| `OPENSRE_PROMETHEUS_TOKEN` | Bearer token | — |

### Kubernetes

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENSRE_KUBECONFIG` | Path to kubeconfig | `~/.kube/config` |
| `OPENSRE_KUBE_CONTEXT` | Kubernetes context to use | Current context |
| `OPENSRE_KUBE_NAMESPACE` | Default namespace | `default` |

### Slack

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENSRE_SLACK_BOT_TOKEN` | Slack bot OAuth token | — |
| `OPENSRE_SLACK_APP_TOKEN` | Slack app token (for Socket Mode) | — |
| `OPENSRE_SLACK_CHANNEL` | Default notification channel | `#incidents` |
| `OPENSRE_SLACK_SIGNING_SECRET` | For webhook verification | — |

### API Server

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENSRE_HOST` | API server host | `0.0.0.0` |
| `OPENSRE_PORT` | API server port | `8000` |
| `OPENSRE_API_KEY` | API authentication key | — |
| `OPENSRE_CORS_ORIGINS` | Allowed CORS origins | `*` |

### Safety Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENSRE_AUTO_APPROVE_READ` | Auto-approve read operations | `true` |
| `OPENSRE_REQUIRE_APPROVAL` | Actions requiring human approval | `rollback,delete,scale` |
| `OPENSRE_PROTECTED_NAMESPACES` | Namespaces needing extra confirmation | `production,kube-system` |
| `OPENSRE_DRY_RUN` | Execute in dry-run mode | `false` |

## Config File

Create `config/opensre.yaml`:

```yaml
# config/opensre.yaml

# Logging
log_level: INFO

# LLM Configuration
llm:
  provider: ollama
  ollama:
    host: http://localhost:11434
    model: llama3.1:8b
  # openai:
  #   api_key: ${OPENSRE_OPENAI_API_KEY}
  #   model: gpt-4o
  # anthropic:
  #   api_key: ${OPENSRE_ANTHROPIC_API_KEY}
  #   model: claude-3-5-sonnet-20241022

# Prometheus Configuration
prometheus:
  url: http://prometheus:9090
  auth:
    type: none  # none, basic, bearer
    # username: admin
    # password: secret
    # token: my-token

# Kubernetes Configuration
kubernetes:
  kubeconfig: ~/.kube/config
  context: null  # Use current context
  default_namespace: default

# Slack Configuration
slack:
  bot_token: ${OPENSRE_SLACK_BOT_TOKEN}
  app_token: ${OPENSRE_SLACK_APP_TOKEN}
  channel: "#incidents"

# API Server
server:
  host: 0.0.0.0
  port: 8000
  api_key: ${OPENSRE_API_KEY}
  cors_origins:
    - "*"

# Safety Configuration
safety:
  # Actions that auto-approve
  auto_approve:
    - "*.get_*"
    - "*.list_*"
    - "*.describe_*"
    - "prometheus.query"
    - "slack.post_message"
  
  # Actions requiring human approval
  require_approval:
    - "kubernetes.rollback"
    - "kubernetes.delete_*"
    - "kubernetes.scale"
    - "aws.terminate_*"
  
  # Protected namespaces
  protected_namespaces:
    - production
    - kube-system
    - monitoring
  
  # Dry-run mode
  dry_run: false
  
  # Require confirmation for high-risk actions
  require_confirmation: true

# Knowledge Configuration
knowledge:
  # Runbooks directory
  runbooks_path: runbooks/
  
  # Past incidents storage
  incidents_db: data/incidents.db
  
  # Vector store for semantic search
  vector_store:
    type: chroma
    path: data/vectors

# Agent Configuration
agents:
  # Default agent timeout
  timeout: 300  # 5 minutes
  
  # Maximum concurrent investigations
  max_concurrent: 3
  
  # Retry configuration
  retry:
    max_attempts: 3
    backoff: exponential
```

## Agent-Specific Config

Each agent can have its own configuration:

```yaml
# agents/incident-responder.yaml

name: incident-responder
description: Responds to PagerDuty incidents

# Agent-specific settings
config:
  timeout: 600  # Override default
  notify_on_complete: true
  
# Triggers
triggers:
  - type: webhook
    source: pagerduty
  - type: prometheus_alert
    match: "severity=critical"

# Skills to use
skills:
  - prometheus
  - kubernetes
  - slack

# Runbook
runbook: |
  1. Acknowledge the incident
  2. Query Prometheus for affected metrics
  3. Check Kubernetes pod health
  4. Identify root cause
  5. Suggest remediation
  6. Post findings to Slack

# Safety overrides
safety:
  require_approval:
    - kubernetes.rollback
```

## Secrets Management

### Environment Variables

The simplest approach — set secrets as environment variables:

```bash
export OPENSRE_OPENAI_API_KEY=sk-your-key
export OPENSRE_SLACK_BOT_TOKEN=xoxb-your-token
```

### .env File

For local development, use a `.env` file:

```bash
# .env
OPENSRE_OPENAI_API_KEY=sk-your-key
OPENSRE_SLACK_BOT_TOKEN=xoxb-your-token
```

**Important:** Never commit `.env` to version control!

### Kubernetes Secrets

For Kubernetes deployments:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: opensre-secrets
type: Opaque
stringData:
  openai-api-key: sk-your-key
  slack-bot-token: xoxb-your-token
```

Reference in deployment:

```yaml
env:
  - name: OPENSRE_OPENAI_API_KEY
    valueFrom:
      secretKeyRef:
        name: opensre-secrets
        key: openai-api-key
```

### HashiCorp Vault

For enterprise deployments, integrate with Vault:

```yaml
# config/opensre.yaml
secrets:
  provider: vault
  vault:
    address: https://vault.example.com
    path: secret/data/opensre
    auth:
      method: kubernetes
      role: opensre
```

## Validation

Validate your configuration:

```bash
# Check configuration
opensre config validate

# Show resolved configuration
opensre config show

# Test connections
opensre test all
```

## Next Steps

- **[Skills Overview](skills/overview.md)** — Configure skills
- **[Agent Configuration](agents/overview.md)** — Configure agents
- **[Deployment](deployment.md)** — Production deployment
