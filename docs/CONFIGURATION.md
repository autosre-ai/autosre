# AutoSRE Configuration Reference

AutoSRE is configured via environment variables, a YAML configuration file, or the CLI.

## Quick Start

```bash
# Initialize configuration interactively
autosre config init

# Set your LLM provider
autosre model use anthropic claude-3-5-sonnet-20241022

# Validate configuration
autosre config validate
```

---

## Configuration Methods

### 1. Environment Variables (Recommended)

All settings can be configured via environment variables with the `OPENSRE_` prefix:

```bash
# .env file or shell export
export OPENSRE_LLM_PROVIDER=anthropic
export OPENSRE_ANTHROPIC_API_KEY=sk-ant-...
export OPENSRE_PROMETHEUS_URL=http://prometheus:9090
```

### 2. Configuration File

Default location: `~/.autosre/config.yaml`

```yaml
llm_provider: anthropic
anthropic_api_key: sk-ant-...
prometheus_url: http://prometheus:9090
```

### 3. CLI Commands

```bash
autosre config set llm_provider anthropic
autosre config show
```

---

## LLM Configuration

### Provider Selection

| Setting | Env Variable | Default | Description |
|---------|-------------|---------|-------------|
| `llm_provider` | `OPENSRE_LLM_PROVIDER` | `ollama` | LLM provider: ollama, openai, anthropic, azure |

### Ollama (Local/Self-hosted)

| Setting | Env Variable | Default | Description |
|---------|-------------|---------|-------------|
| `ollama_host` | `OPENSRE_OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `ollama_model` | `OPENSRE_OLLAMA_MODEL` | `llama3.1:8b` | Model name |

```bash
# Example: Use local Ollama
autosre model use ollama llama3.1:8b
```

### OpenAI

| Setting | Env Variable | Default | Description |
|---------|-------------|---------|-------------|
| `openai_api_key` | `OPENSRE_OPENAI_API_KEY` | None | OpenAI API key |
| `openai_model` | `OPENSRE_OPENAI_MODEL` | `gpt-4o-mini` | Model name |

```bash
# Example: Use OpenAI
export OPENSRE_OPENAI_API_KEY=sk-...
autosre model use openai gpt-4o
```

### Anthropic (Claude)

| Setting | Env Variable | Default | Description |
|---------|-------------|---------|-------------|
| `anthropic_api_key` | `OPENSRE_ANTHROPIC_API_KEY` | None | Anthropic API key |
| `anthropic_model` | `OPENSRE_ANTHROPIC_MODEL` | `claude-3-5-sonnet-20241022` | Model name |

```bash
# Example: Use Anthropic Claude
export OPENSRE_ANTHROPIC_API_KEY=sk-ant-...
autosre model use anthropic claude-3-5-sonnet-20241022
```

### Azure OpenAI

| Setting | Env Variable | Default | Description |
|---------|-------------|---------|-------------|
| `azure_openai_endpoint` | `OPENSRE_AZURE_OPENAI_ENDPOINT` | None | Azure endpoint URL |
| `azure_openai_api_key` | `OPENSRE_AZURE_OPENAI_API_KEY` | None | Azure API key |
| `azure_openai_deployment` | `OPENSRE_AZURE_OPENAI_DEPLOYMENT` | `gpt-4` | Deployment name |
| `azure_openai_api_version` | `OPENSRE_AZURE_OPENAI_API_VERSION` | `2024-02-01` | API version |

```bash
# Example: Use Azure OpenAI
export OPENSRE_AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
export OPENSRE_AZURE_OPENAI_API_KEY=...
autosre model use azure gpt-4
```

### LLM Behavior Settings

| Setting | Env Variable | Default | Description |
|---------|-------------|---------|-------------|
| `llm_retry_max_attempts` | `OPENSRE_LLM_RETRY_MAX_ATTEMPTS` | `3` | Max retry attempts |
| `llm_retry_backoff_factor` | `OPENSRE_LLM_RETRY_BACKOFF_FACTOR` | `2.0` | Backoff multiplier |
| `llm_cache_enabled` | `OPENSRE_LLM_CACHE_ENABLED` | `true` | Enable response caching |
| `llm_cache_ttl_seconds` | `OPENSRE_LLM_CACHE_TTL_SECONDS` | `3600` | Cache TTL in seconds |

---

## Infrastructure Configuration

### Prometheus

| Setting | Env Variable | Default | Description |
|---------|-------------|---------|-------------|
| `prometheus_url` | `OPENSRE_PROMETHEUS_URL` | `http://localhost:9090` | Prometheus server URL |

### Kubernetes

| Setting | Env Variable | Default | Description |
|---------|-------------|---------|-------------|
| `kubeconfig` | `OPENSRE_KUBECONFIG` | None | Path to kubeconfig file |
| `k8s_namespaces` | `OPENSRE_K8S_NAMESPACES` | `default` | Comma-separated namespaces |

```bash
# Example: Configure Kubernetes
export OPENSRE_KUBECONFIG=~/.kube/config
export OPENSRE_K8S_NAMESPACES=production,staging
```

### Loki (Logs)

| Setting | Env Variable | Default | Description |
|---------|-------------|---------|-------------|
| `loki_url` | `OPENSRE_LOKI_URL` | None | Loki server URL |

---

## Integrations

### Slack

| Setting | Env Variable | Default | Description |
|---------|-------------|---------|-------------|
| `slack_bot_token` | `OPENSRE_SLACK_BOT_TOKEN` | None | Slack bot token |
| `slack_signing_secret` | `OPENSRE_SLACK_SIGNING_SECRET` | None | Slack signing secret |
| `slack_channel` | `OPENSRE_SLACK_CHANNEL` | `#incidents` | Default channel |

### PagerDuty

| Setting | Env Variable | Default | Description |
|---------|-------------|---------|-------------|
| `pagerduty_api_key` | `OPENSRE_PAGERDUTY_API_KEY` | None | PagerDuty API key |

---

## Server Configuration

### Webhook Server

| Setting | Env Variable | Default | Description |
|---------|-------------|---------|-------------|
| `ui_host` | `OPENSRE_UI_HOST` | `0.0.0.0` | Server bind host |
| `ui_port` | `OPENSRE_UI_PORT` | `8080` | Server bind port |
| `ui_reload` | `OPENSRE_UI_RELOAD` | `false` | Enable auto-reload |
| `alertmanager_webhook_path` | `OPENSRE_ALERTMANAGER_WEBHOOK_PATH` | `/webhook/alert` | Webhook endpoint |

---

## Agent Behavior

| Setting | Env Variable | Default | Description |
|---------|-------------|---------|-------------|
| `require_approval` | `OPENSRE_REQUIRE_APPROVAL` | `true` | Require human approval for actions |
| `auto_approve_low_risk` | `OPENSRE_AUTO_APPROVE_LOW_RISK` | `false` | Auto-approve low-risk actions |
| `confidence_threshold` | `OPENSRE_CONFIDENCE_THRESHOLD` | `0.7` | Minimum confidence for decisions |
| `max_iterations` | `OPENSRE_MAX_ITERATIONS` | `10` | Max investigation iterations |
| `timeout_seconds` | `OPENSRE_TIMEOUT_SECONDS` | `300` | Investigation timeout |

---

## Runbooks

| Setting | Env Variable | Default | Description |
|---------|-------------|---------|-------------|
| `runbooks_path` | `OPENSRE_RUNBOOKS_PATH` | `./runbooks` | Directory containing runbooks |

---

## MCP (Model Context Protocol)

| Setting | Env Variable | Default | Description |
|---------|-------------|---------|-------------|
| `mcp_enabled` | `OPENSRE_MCP_ENABLED` | `false` | Enable MCP client |
| `mcp_config_path` | `OPENSRE_MCP_CONFIG_PATH` | `./mcp-clients.json` | MCP config file |
| `mcp_kubernetes` | `OPENSRE_MCP_KUBERNETES` | `true` | Use kubernetes-mcp |
| `mcp_prometheus` | `OPENSRE_MCP_PROMETHEUS` | `true` | Use prometheus-mcp |

---

## Logging

| Setting | Env Variable | Default | Description |
|---------|-------------|---------|-------------|
| `log_level` | `OPENSRE_LOG_LEVEL` | `INFO` | Log level: DEBUG, INFO, WARNING, ERROR |
| `log_format` | `OPENSRE_LOG_FORMAT` | `json` | Log format: json or text |

---

## Example Configurations

### Minimal Setup (Local Ollama)

```bash
# .env
OPENSRE_LLM_PROVIDER=ollama
OPENSRE_OLLAMA_HOST=http://localhost:11434
OPENSRE_OLLAMA_MODEL=llama3.1:8b
```

### Production Setup (Anthropic + Full Stack)

```bash
# .env
OPENSRE_LLM_PROVIDER=anthropic
OPENSRE_ANTHROPIC_API_KEY=sk-ant-...

# Infrastructure
OPENSRE_PROMETHEUS_URL=http://prometheus.monitoring:9090
OPENSRE_KUBECONFIG=/home/sre/.kube/config
OPENSRE_K8S_NAMESPACES=production,staging
OPENSRE_LOKI_URL=http://loki.monitoring:3100

# Integrations
OPENSRE_SLACK_BOT_TOKEN=xoxb-...
OPENSRE_SLACK_CHANNEL=#sre-alerts
OPENSRE_PAGERDUTY_API_KEY=...

# Server
OPENSRE_UI_HOST=0.0.0.0
OPENSRE_UI_PORT=8080

# Behavior
OPENSRE_REQUIRE_APPROVAL=true
OPENSRE_CONFIDENCE_THRESHOLD=0.8
OPENSRE_MAX_ITERATIONS=15
OPENSRE_TIMEOUT_SECONDS=600
```

### Docker Compose Environment

```yaml
# docker-compose.yml
services:
  autosre:
    image: ghcr.io/autosre-ai/autosre:latest
    environment:
      - OPENSRE_LLM_PROVIDER=anthropic
      - OPENSRE_ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - OPENSRE_PROMETHEUS_URL=http://prometheus:9090
      - OPENSRE_LOKI_URL=http://loki:3100
    volumes:
      - ~/.kube:/root/.kube:ro
      - ~/.autosre:/root/.autosre
```

---

## Configuration Validation

```bash
# Check current configuration
autosre config show

# Validate and test connections
autosre config validate

# Run diagnostics
autosre doctor -v
```

---

## See Also

- [CLI Commands Reference](COMMANDS.md)
- [Development Guide](DEVELOPMENT.md)
- [Main README](../README.md)
