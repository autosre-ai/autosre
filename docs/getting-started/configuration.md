# Configuration

AutoSRE is configured via YAML files and environment variables. This guide covers all configuration options.

## Configuration Files

AutoSRE looks for configuration in this order:

1. `./autosre.yaml` (current directory)
2. `./.autosre/config.yaml` (project-specific)
3. `~/.autosre/config.yaml` (user default)
4. Environment variables (override all)

## Minimal Configuration

```yaml
# ~/.autosre/config.yaml
llm:
  provider: anthropic
  model: claude-3-5-sonnet-20241022

agent:
  autonomy: suggest
```

## Full Configuration Reference

```yaml
# AutoSRE Configuration
# =====================

# LLM Provider Settings
# ---------------------
llm:
  # Provider: anthropic | openai | azure | ollama | litellm
  provider: anthropic
  
  # Model name (provider-specific)
  model: claude-3-5-sonnet-20241022
  
  # API endpoint (optional, for self-hosted or Azure)
  base_url: null
  
  # Max tokens for responses
  max_tokens: 4096
  
  # Temperature (0.0-1.0, lower = more deterministic)
  temperature: 0.1
  
  # Request timeout in seconds
  timeout: 120
  
  # Retry configuration
  retry:
    max_attempts: 3
    backoff_factor: 2
    max_wait: 60

# Agent Behavior
# --------------
agent:
  # Autonomy level:
  # - observe: Only report findings, never execute
  # - suggest: Recommend actions, require approval
  # - auto_safe: Auto-execute low-risk actions
  # - auto_all: Auto-execute all actions (dangerous!)
  autonomy: suggest
  
  # Maximum investigation duration
  max_duration_seconds: 600
  
  # Maximum number of tool calls per investigation
  max_tool_calls: 50
  
  # Confidence threshold for auto-remediation (0.0-1.0)
  auto_threshold: 0.85
  
  # Enable learning from past incidents
  learning:
    enabled: true
    min_similarity: 0.75
    max_results: 5

# Context Store
# -------------
context:
  # Database path (SQLite)
  database: ~/.autosre/context.db
  
  # Sync interval for connectors (seconds)
  sync_interval: 300
  
  # Data retention (days)
  retention:
    investigations: 90
    changes: 30
    alerts: 7

# Integrations
# ------------
integrations:
  # Kubernetes
  kubernetes:
    enabled: true
    # Use current kubectl context, or specify one
    context: null
    # Namespaces to monitor (empty = all)
    namespaces: []
    # Resource types to track
    resources:
      - deployments
      - pods
      - services
      - configmaps
      - secrets  # names only, not contents
    # Timeout for API calls
    timeout: 30
  
  # Prometheus / Alertmanager
  prometheus:
    enabled: true
    url: http://prometheus:9090
    # Optional: Alertmanager for active alerts
    alertmanager_url: http://alertmanager:9093
    # Default query range
    default_range: 1h
    # Maximum series per query
    max_series: 1000
  
  # Datadog
  datadog:
    enabled: false
    # API and APP keys set via env vars:
    # DATADOG_API_KEY, DATADOG_APP_KEY
    site: datadoghq.com  # or datadoghq.eu
    
  # Slack
  slack:
    enabled: false
    # Token set via SLACK_BOT_TOKEN env var
    default_channel: "#incidents"
    # Enable interactive buttons
    interactive: true
    # Thread replies for updates
    thread_updates: true
  
  # PagerDuty
  pagerduty:
    enabled: false
    # API key set via PAGERDUTY_API_KEY env var
    # Service IDs to monitor (empty = all)
    service_ids: []
    # Auto-acknowledge when investigating
    auto_ack: false
  
  # GitHub (for recent changes)
  github:
    enabled: false
    # Token set via GITHUB_TOKEN env var
    # Organizations to monitor
    orgs: []
    # Repositories to monitor (format: org/repo)
    repos: []
    # Track deployments, commits, PRs
    track:
      - deployments
      - commits
      - pull_requests
  
  # Elasticsearch / OpenSearch
  elasticsearch:
    enabled: false
    hosts:
      - http://elasticsearch:9200
    # Index pattern for logs
    index_pattern: "logs-*"
    # Default time range for queries
    default_range: 1h
    # Maximum documents per query
    max_docs: 1000
  
  # AWS
  aws:
    enabled: false
    # Region (uses AWS_REGION env var if not set)
    region: null
    # Profile (uses AWS_PROFILE env var if not set)
    profile: null
    # Services to integrate
    services:
      - cloudwatch
      - ec2
      - rds
      - lambda
      - ecs
  
  # GCP
  gcp:
    enabled: false
    # Project ID
    project: null
    # Services to integrate
    services:
      - monitoring
      - logging
      - compute
      - gke

# Knowledge Graph (Neo4j)
# ----------------------
graph:
  enabled: false
  uri: bolt://neo4j:7687
  # Credentials via NEO4J_USER, NEO4J_PASSWORD env vars
  
  # Auto-discovery settings
  discovery:
    enabled: true
    # Sources for topology discovery
    sources:
      - kubernetes
      - prometheus
      - github

# Memory / Learning
# ----------------
memory:
  # PostgreSQL for investigation history
  database:
    enabled: true
    # Connection string via DATABASE_URL env var
    # or individual settings:
    host: localhost
    port: 5432
    database: autosre
    # Credentials via POSTGRES_USER, POSTGRES_PASSWORD
  
  # Vector embeddings for similarity search
  embeddings:
    enabled: true
    provider: openai  # or local
    model: text-embedding-3-small
    dimensions: 1536

# API Server
# ----------
api:
  # Server host/port
  host: 0.0.0.0
  port: 8000
  
  # CORS settings
  cors:
    origins:
      - http://localhost:3000
    allow_credentials: true
  
  # Rate limiting
  rate_limit:
    enabled: true
    requests_per_minute: 60
    burst: 10
  
  # Authentication
  auth:
    # API key auth
    api_keys:
      enabled: true
    # JWT auth
    jwt:
      enabled: true
      # Secret via JWT_SECRET_KEY env var
      algorithm: HS256
      expire_minutes: 60

# Notifications
# -------------
notifications:
  # Channels to notify for different events
  on_investigation_start:
    - slack
  on_investigation_complete:
    - slack
    - pagerduty
  on_action_required:
    - slack
  on_error:
    - slack

# Logging
# -------
logging:
  # Log level: DEBUG, INFO, WARNING, ERROR
  level: INFO
  # Format: json | text
  format: json
  # Output file (null = stdout)
  file: null

# Metrics
# -------
metrics:
  # Enable Prometheus metrics
  enabled: true
  # Metrics endpoint path
  path: /metrics
  # Port (if separate from API)
  port: null

# Tracing
# -------
tracing:
  # Enable OpenTelemetry tracing
  enabled: false
  # OTLP endpoint
  endpoint: http://otel-collector:4317
  # Service name
  service_name: autosre
```

## Environment Variables

All configuration can be overridden via environment variables:

### Required

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `OPENAI_API_KEY` | OpenAI API key (if using OpenAI) |
| `AUTOSRE_LLM_PROVIDER` | LLM provider override |
| `AUTOSRE_LLM_MODEL` | Model override |

### Database

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `POSTGRES_HOST` | PostgreSQL host |
| `POSTGRES_PORT` | PostgreSQL port |
| `POSTGRES_USER` | PostgreSQL username |
| `POSTGRES_PASSWORD` | PostgreSQL password |
| `POSTGRES_DB` | PostgreSQL database name |

### Integrations

| Variable | Description |
|----------|-------------|
| `SLACK_BOT_TOKEN` | Slack bot token (xoxb-...) |
| `SLACK_SIGNING_SECRET` | Slack signing secret |
| `PAGERDUTY_API_KEY` | PagerDuty API key |
| `DATADOG_API_KEY` | Datadog API key |
| `DATADOG_APP_KEY` | Datadog application key |
| `GITHUB_TOKEN` | GitHub personal access token |
| `AWS_ACCESS_KEY_ID` | AWS access key |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key |
| `AWS_REGION` | AWS region |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to GCP service account JSON |

### Security

| Variable | Description |
|----------|-------------|
| `API_SECRET_KEY` | API encryption key |
| `JWT_SECRET_KEY` | JWT signing key |
| `NEO4J_USER` | Neo4j username |
| `NEO4J_PASSWORD` | Neo4j password |

### Agent

| Variable | Description |
|----------|-------------|
| `AUTOSRE_AUTONOMY` | Autonomy level override |
| `AUTOSRE_MAX_DURATION` | Max investigation duration |
| `AUTOSRE_LOG_LEVEL` | Logging level |

## Configuration Patterns

### Development

```yaml
# dev.yaml
llm:
  provider: ollama
  model: llama3.1:8b
  base_url: http://localhost:11434

agent:
  autonomy: observe
  max_duration_seconds: 60

logging:
  level: DEBUG
  format: text

integrations:
  kubernetes:
    enabled: true
    context: minikube
```

### Production

```yaml
# prod.yaml
llm:
  provider: anthropic
  model: claude-3-5-sonnet-20241022
  temperature: 0.1
  retry:
    max_attempts: 5

agent:
  autonomy: suggest
  max_duration_seconds: 600
  auto_threshold: 0.90

api:
  cors:
    origins:
      - https://autosre.example.com
  rate_limit:
    enabled: true
    requests_per_minute: 100

logging:
  level: INFO
  format: json

metrics:
  enabled: true

tracing:
  enabled: true
  endpoint: http://otel-collector:4317
```

### High Security

```yaml
# secure.yaml
agent:
  autonomy: observe  # Never auto-execute
  learning:
    enabled: false  # Don't store investigation data

integrations:
  kubernetes:
    enabled: true
    resources:
      - deployments
      - pods
      # No secrets access

api:
  auth:
    api_keys:
      enabled: true
    jwt:
      enabled: true
      expire_minutes: 15  # Short-lived tokens

logging:
  # Don't log sensitive data
  level: WARNING
```

## Validating Configuration

Check your configuration:

```bash
autosre config validate

# Or specify a file
autosre config validate -f ./autosre.yaml
```

View effective configuration:

```bash
autosre config show

# With secrets masked
autosre config show --mask-secrets
```

## Dynamic Configuration

Some settings can be changed at runtime via the API:

```bash
# Update autonomy level
curl -X PATCH http://localhost:8000/api/v1/config \
  -H "Content-Type: application/json" \
  -d '{"agent": {"autonomy": "auto_safe"}}'
```

Dynamic settings:
- `agent.autonomy`
- `agent.max_duration_seconds`
- `notifications.*`

Static settings (require restart):
- `llm.*`
- `integrations.*`
- `api.*`

---

## Next Steps

- [Set up Slack integration →](../guides/slack-integration.md)
- [Connect PagerDuty →](../guides/pagerduty-integration.md)
- [Deploy to Kubernetes →](../guides/kubernetes-deployment.md)
