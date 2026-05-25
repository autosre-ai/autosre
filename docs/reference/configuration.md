# Configuration Options

AutoSRE is configured via YAML files and environment variables.

## Configuration File

Default location: `.autosre/config.yaml`

```yaml
# Core settings
autosre:
  log_level: info
  autonomy_level: suggest  # observe, suggest, auto

# LLM Configuration
llm:
  provider: anthropic  # openai, anthropic, azure
  model: claude-3-opus-20240229
  temperature: 0.1
  max_tokens: 4096

# Integrations
integrations:
  kubernetes:
    enabled: true
    context: production
    namespace: default
  
  prometheus:
    enabled: true
    url: http://prometheus:9090
  
  slack:
    enabled: false
    webhook_url: ${SLACK_WEBHOOK_URL}
  
  pagerduty:
    enabled: false
    api_key: ${PAGERDUTY_API_KEY}

# Memory System
memory:
  enabled: true
  backend: postgres  # postgres, sqlite, memory
  connection_string: ${DATABASE_URL}

# Knowledge Graph
knowledge_graph:
  enabled: false
  neo4j_uri: bolt://localhost:7687
  neo4j_user: neo4j
  neo4j_password: ${NEO4J_PASSWORD}

# Server
server:
  host: 0.0.0.0
  port: 8000
  cors_origins:
    - http://localhost:3000
```

## Configuration Sections

### autosre

Core agent settings.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `log_level` | string | info | Logging level |
| `autonomy_level` | string | suggest | How autonomous the agent should be |

### llm

LLM provider configuration.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `provider` | string | anthropic | LLM provider to use |
| `model` | string | - | Model identifier |
| `temperature` | float | 0.1 | Response randomness |
| `max_tokens` | int | 4096 | Maximum response length |

### integrations

External service integrations. See individual integration guides for details.

### memory

Episodic memory configuration for learning from past incidents.

### knowledge_graph

Service dependency graph configuration.
