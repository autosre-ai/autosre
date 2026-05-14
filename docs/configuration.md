# Configuration Reference

AutoSRE V2 can be configured through environment variables and/or a YAML configuration file. Environment variables take precedence over config file settings.

## Configuration Files

### .env File

Environment variables for runtime configuration. Create from the example:

```bash
cp .env.example .env
```

### config.yaml File

YAML-based configuration for detailed settings:

```bash
cp config.example.yaml config.yaml
```

---

## Environment Variables

### Application Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `AUTOSRE_ENV` | `development` | Environment: `development`, `staging`, `production` |
| `AUTOSRE_DEBUG` | `false` | Enable debug mode (verbose logging) |
| `AUTOSRE_LOG_LEVEL` | `INFO` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `AUTOSRE_LOG_FORMAT` | `console` | Log format: `console`, `json` |
| `AUTOSRE_SECRET_KEY` | *required* | Secret key for JWT tokens (generate with `openssl rand -hex 32`) |

### API Server

| Variable | Default | Description |
|----------|---------|-------------|
| `API_PORT` | `8000` | API server port |
| `API_WORKERS` | `4` | Number of uvicorn workers (production) |
| `CORS_ORIGINS` | `http://localhost:3000` | Allowed CORS origins (comma-separated) |
| `RATE_LIMIT_PER_MINUTE` | `100` | API rate limit per user |
| `RATE_LIMIT_BURST` | `20` | Burst limit for rate limiting |

### UI Server

| Variable | Default | Description |
|----------|---------|-------------|
| `UI_PORT` | `3000` | UI server port |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Public API URL for browser requests |

### Database (PostgreSQL)

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_HOST` | `localhost` | PostgreSQL hostname |
| `POSTGRES_PORT` | `5432` | PostgreSQL port |
| `POSTGRES_USER` | `autosre` | Database user |
| `POSTGRES_PASSWORD` | `autosre_local` | Database password |
| `POSTGRES_DB` | `autosre` | Database name |
| `DATABASE_URL` | *derived* | Full connection URL (overrides individual settings) |
| `DB_POOL_SIZE` | `10` | Connection pool size |
| `DB_MAX_OVERFLOW` | `20` | Max overflow connections |
| `DB_POOL_TIMEOUT` | `30` | Pool timeout in seconds |

**DATABASE_URL format:**
```
postgresql+asyncpg://user:password@host:port/database
```

### Redis

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_HOST` | `localhost` | Redis hostname |
| `REDIS_PORT` | `6379` | Redis port |
| `REDIS_DB` | `0` | Redis database number |
| `REDIS_PASSWORD` | *none* | Redis password (optional) |
| `REDIS_URL` | *derived* | Full Redis URL (overrides individual settings) |

**REDIS_URL format:**
```
redis://[:password@]host:port/db
```

### LLM Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `openai` | LLM provider: `openai`, `anthropic`, `ollama`, `litellm` |
| `LLM_TEMPERATURE` | `0.7` | Model temperature (0.0 - 2.0) |
| `LLM_MAX_TOKENS` | `4096` | Max tokens per response |

#### OpenAI

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | *required* | OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o` | Default model |
| `OPENAI_BASE_URL` | *api.openai.com* | Custom base URL (for Azure, proxies) |

#### Anthropic

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | *required* | Anthropic API key |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-20250514` | Default model |

#### Ollama (Local)

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `llama3` | Default model |

#### LiteLLM (Multi-provider)

| Variable | Default | Description |
|----------|---------|-------------|
| `LITELLM_BASE_URL` | *none* | LiteLLM proxy URL |
| `LITELLM_API_KEY` | *none* | LiteLLM API key |

### Kubernetes

| Variable | Default | Description |
|----------|---------|-------------|
| `KUBECONFIG` | `~/.kube/config` | Path to kubeconfig file |
| `K8S_NAMESPACE_DEFAULT` | `default` | Default namespace for operations |
| `K8S_OPERATION_TIMEOUT` | `300` | Operation timeout in seconds |

### Feature Flags

| Variable | Default | Description |
|----------|---------|-------------|
| `FEATURE_K8S_OPERATIONS` | `true` | Enable Kubernetes operations |
| `FEATURE_AUTO_REMEDIATION` | `false` | Enable auto-remediation (⚠️ use with caution) |
| `FEATURE_METRICS_EXPORT` | `true` | Export Prometheus metrics |

### External Integrations

#### Slack

| Variable | Description |
|----------|-------------|
| `SLACK_BOT_TOKEN` | Slack bot OAuth token (`xoxb-...`) |
| `SLACK_APP_TOKEN` | Slack app-level token (`xapp-...`) |
| `SLACK_DEFAULT_CHANNEL` | Default notification channel |

#### PagerDuty

| Variable | Description |
|----------|-------------|
| `PAGERDUTY_API_KEY` | PagerDuty API key |
| `PAGERDUTY_SERVICE_ID` | Default service ID |

#### GitHub

| Variable | Description |
|----------|-------------|
| `GITHUB_TOKEN` | GitHub personal access token |
| `GITHUB_APP_ID` | GitHub App ID |
| `GITHUB_PRIVATE_KEY_PATH` | Path to GitHub App private key |
| `GITHUB_WEBHOOK_SECRET` | Webhook signature secret |

### Monitoring & Observability

#### Prometheus & Grafana

| Variable | Description |
|----------|-------------|
| `PROMETHEUS_URL` | Prometheus server URL |
| `GRAFANA_URL` | Grafana server URL |
| `GRAFANA_API_KEY` | Grafana API key |

#### Datadog

| Variable | Description |
|----------|-------------|
| `DATADOG_API_KEY` | Datadog API key |
| `DATADOG_APP_KEY` | Datadog application key |
| `DATADOG_SITE` | Datadog site (`datadoghq.com`, `datadoghq.eu`) |

#### Sentry (Error Tracking)

| Variable | Description |
|----------|-------------|
| `SENTRY_DSN` | Sentry DSN for error tracking |

#### OpenTelemetry

| Variable | Description |
|----------|-------------|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP exporter endpoint |
| `OTEL_SERVICE_NAME` | Service name for traces |

### Logging Backends

| Variable | Description |
|----------|-------------|
| `ELASTICSEARCH_URL` | Elasticsearch URL |
| `ELASTICSEARCH_INDEX` | Index pattern for logs |
| `LOKI_URL` | Grafana Loki URL |
| `CORALOGIX_API_KEY` | Coralogix API key |
| `CORALOGIX_DOMAIN` | Coralogix domain |

### Cloud Providers

#### AWS

| Variable | Description |
|----------|-------------|
| `AWS_ACCESS_KEY_ID` | AWS access key |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key |
| `AWS_REGION` | AWS region |

#### GCP

| Variable | Description |
|----------|-------------|
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to service account JSON |
| `GCP_PROJECT_ID` | GCP project ID |

#### Azure

| Variable | Description |
|----------|-------------|
| `AZURE_TENANT_ID` | Azure tenant ID |
| `AZURE_CLIENT_ID` | Azure client ID |
| `AZURE_CLIENT_SECRET` | Azure client secret |

---

## Config File Format (.autosre.yaml)

The YAML config file supports all settings with structured organization.

### Complete Example

```yaml
# ═══════════════════════════════════════════════════════════════════════
# AutoSRE Configuration
# ═══════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────
# General Settings
# ─────────────────────────────────────────────────────────────────────
debug: false
log_level: INFO

# ─────────────────────────────────────────────────────────────────────
# LLM Configuration
# ─────────────────────────────────────────────────────────────────────
default_provider: openai
default_model: gpt-4o

# Provider-specific settings
openai:
  enabled: true
  default_model: gpt-4o
  max_retries: 3
  timeout: 120.0

anthropic:
  enabled: true
  default_model: claude-sonnet-4-20250514
  max_retries: 3
  timeout: 120.0

ollama:
  enabled: true
  base_url: http://localhost:11434
  default_model: llama3
  timeout: 300.0

azure_openai:
  enabled: false
  # api_version: 2024-02-15-preview
  # base_url: https://your-resource.openai.azure.com
  # deployment_name: your-deployment

together:
  enabled: false
  base_url: https://api.together.xyz/v1
  default_model: meta-llama/Llama-3-70b-chat-hf

# ─────────────────────────────────────────────────────────────────────
# Cache Settings
# ─────────────────────────────────────────────────────────────────────
cache:
  enabled: true
  backend: memory    # memory, disk, or redis
  ttl_seconds: 3600
  max_size: 1000
  # disk_path: .cache/autosre       # For disk backend
  # redis_url: redis://localhost:6379/0  # For redis backend

# ─────────────────────────────────────────────────────────────────────
# Retry Settings
# ─────────────────────────────────────────────────────────────────────
retry:
  max_retries: 3
  base_delay: 1.0       # Initial delay in seconds
  max_delay: 60.0       # Maximum delay between retries
  exponential_base: 2.0 # Exponential backoff multiplier
  jitter: true          # Add randomness to delays

# ─────────────────────────────────────────────────────────────────────
# Token Settings
# ─────────────────────────────────────────────────────────────────────
tokens:
  default_max_tokens: 4096
  default_context_window: 128000
  response_reserve: 1024  # Tokens reserved for response

# ─────────────────────────────────────────────────────────────────────
# Agent Configuration
# ─────────────────────────────────────────────────────────────────────
agents:
  # Coordinator settings
  coordinator:
    max_iterations: 3
    timeout_seconds: 600

  # Triage agent
  triage:
    enabled: true
    temperature: 0.1

  # Investigation agents
  investigation:
    max_iterations: 25
    timeout_seconds: 300
    parallel: true        # Run investigation agents in parallel
    
  # Remediation agent
  remediation:
    enabled: true
    auto_execute: false   # Require approval for actions
    risk_threshold: medium  # low, medium, high

# ─────────────────────────────────────────────────────────────────────
# Integration Configuration
# ─────────────────────────────────────────────────────────────────────
integrations:
  prometheus:
    url: http://prometheus:9090
    timeout: 30
    max_points: 10000

  loki:
    url: http://loki:3100
    timeout: 30
    max_lines: 5000

  kubernetes:
    in_cluster: true      # Use in-cluster config
    namespace_default: production
    timeout: 30

  alertmanager:
    url: http://alertmanager:9093
    timeout: 10

# ─────────────────────────────────────────────────────────────────────
# Feature Flags
# ─────────────────────────────────────────────────────────────────────
features:
  knowledge_base: true
  incident_learning: true
  slack_notifications: true
  pagerduty_integration: false
  auto_remediation: false

# ─────────────────────────────────────────────────────────────────────
# Notification Settings
# ─────────────────────────────────────────────────────────────────────
notifications:
  slack:
    enabled: true
    default_channel: "#sre-alerts"
    mention_on_critical: true
    mention_users: ["@oncall"]
    
  email:
    enabled: false
    smtp_host: smtp.example.com
    smtp_port: 587
    from_address: autosre@example.com
```

---

## Common Configuration Examples

### Development Environment

```bash
# .env
AUTOSRE_ENV=development
AUTOSRE_DEBUG=true
AUTOSRE_LOG_LEVEL=DEBUG

LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-dev-key

DATABASE_URL=postgresql+asyncpg://autosre:autosre_local@localhost:5432/autosre
REDIS_URL=redis://localhost:6379/0

AUTOSRE_SECRET_KEY=dev-secret-not-for-production
```

### Production Environment

```bash
# .env
AUTOSRE_ENV=production
AUTOSRE_DEBUG=false
AUTOSRE_LOG_LEVEL=INFO
AUTOSRE_LOG_FORMAT=json

LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-prod-key

DATABASE_URL=postgresql+asyncpg://autosre:secure-password@postgres.internal:5432/autosre
REDIS_URL=redis://:redis-password@redis.internal:6379/0

AUTOSRE_SECRET_KEY=your-secure-random-secret

# Observability
PROMETHEUS_URL=http://prometheus:9090
LOKI_URL=http://loki:3100
SENTRY_DSN=https://key@sentry.io/project

# Notifications
SLACK_BOT_TOKEN=xoxb-your-token
SLACK_DEFAULT_CHANNEL=#sre-alerts
```

### Using Multiple LLM Providers

```yaml
# config.yaml - Use different models for different tasks
default_provider: openai
default_model: gpt-4o

openai:
  enabled: true
  default_model: gpt-4o

anthropic:
  enabled: true
  default_model: claude-sonnet-4-20250514

# Agent-specific overrides
agents:
  triage:
    provider: anthropic    # Use Claude for triage
    model: claude-sonnet-4-20250514
    
  investigation:
    provider: openai       # Use GPT-4 for investigation
    model: gpt-4o
    
  remediation:
    provider: anthropic    # Use Claude for remediation
    model: claude-sonnet-4-20250514
```

### Local LLM with Ollama

```bash
# .env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3
```

```yaml
# config.yaml
default_provider: ollama

ollama:
  enabled: true
  base_url: http://localhost:11434
  default_model: llama3
  timeout: 300.0  # Longer timeout for local inference
```

### Air-Gapped Environment

For environments without internet access:

```yaml
# config.yaml
default_provider: ollama

# Disable external integrations
integrations:
  slack:
    enabled: false
  pagerduty:
    enabled: false

# Use local models only
ollama:
  enabled: true
  base_url: http://ollama.internal:11434
  default_model: llama3

# Disable telemetry
features:
  telemetry: false
  auto_update_check: false
```

---

## Configuration Precedence

Settings are applied in this order (later overrides earlier):

1. **Default values** (built into application)
2. **config.yaml** file
3. **Environment variables**
4. **Command-line arguments** (where applicable)

Example:
```bash
# config.yaml sets log_level: INFO
# Environment variable overrides:
AUTOSRE_LOG_LEVEL=DEBUG

# Result: log_level is DEBUG
```

---

## Validation

Check your configuration:

```bash
# Verify environment
make env-check

# Test configuration loading
autosre config validate

# Show effective configuration
autosre config show
```

---

## Secrets Management

### Development

Use `.env` file (gitignored):

```bash
# .env (never commit!)
OPENAI_API_KEY=sk-...
AUTOSRE_SECRET_KEY=...
```

### Production

Use your secrets manager:

**Kubernetes Secrets:**
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: autosre-secrets
type: Opaque
stringData:
  OPENAI_API_KEY: sk-...
  AUTOSRE_SECRET_KEY: ...
```

**AWS Secrets Manager:**
```bash
aws secretsmanager create-secret \
  --name autosre/production \
  --secret-string '{"OPENAI_API_KEY":"sk-..."}'
```

**HashiCorp Vault:**
```bash
vault kv put secret/autosre/production \
  OPENAI_API_KEY=sk-... \
  AUTOSRE_SECRET_KEY=...
```
