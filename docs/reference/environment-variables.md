# Environment Variables

AutoSRE configuration via environment variables.

## Core Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `AUTOSRE_CONFIG` | No | Path to configuration file |
| `AUTOSRE_LOG_LEVEL` | No | Logging level (debug, info, warning, error) |
| `AUTOSRE_AUTONOMY_LEVEL` | No | Autonomy level (observe, suggest, auto) |

## LLM Provider

### Anthropic (default)

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key |

### OpenAI

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | OpenAI API key |
| `OPENAI_ORG_ID` | No | OpenAI organization ID |

### Azure OpenAI

| Variable | Required | Description |
|----------|----------|-------------|
| `AZURE_OPENAI_API_KEY` | Yes | Azure OpenAI API key |
| `AZURE_OPENAI_ENDPOINT` | Yes | Azure OpenAI endpoint URL |
| `AZURE_OPENAI_DEPLOYMENT` | Yes | Deployment name |

## Integrations

### Kubernetes

| Variable | Required | Description |
|----------|----------|-------------|
| `KUBECONFIG` | No | Path to kubeconfig file |
| `KUBERNETES_SERVICE_HOST` | No | In-cluster service host |

### Prometheus

| Variable | Required | Description |
|----------|----------|-------------|
| `PROMETHEUS_URL` | Yes | Prometheus server URL |

### Slack

| Variable | Required | Description |
|----------|----------|-------------|
| `SLACK_BOT_TOKEN` | Yes | Slack bot OAuth token |
| `SLACK_SIGNING_SECRET` | Yes | Slack signing secret |
| `SLACK_WEBHOOK_URL` | No | Webhook URL for notifications |

### PagerDuty

| Variable | Required | Description |
|----------|----------|-------------|
| `PAGERDUTY_API_KEY` | Yes | PagerDuty API key |
| `PAGERDUTY_SERVICE_ID` | No | Default service ID |

### Datadog

| Variable | Required | Description |
|----------|----------|-------------|
| `DD_API_KEY` | Yes | Datadog API key |
| `DD_APP_KEY` | Yes | Datadog application key |
| `DD_SITE` | No | Datadog site (datadoghq.com, datadoghq.eu) |

## Database

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | No | PostgreSQL connection string |
| `NEO4J_URI` | No | Neo4j connection URI |
| `NEO4J_USER` | No | Neo4j username |
| `NEO4J_PASSWORD` | No | Neo4j password |

## Server

| Variable | Required | Description |
|----------|----------|-------------|
| `AUTOSRE_HOST` | No | API server bind host |
| `AUTOSRE_PORT` | No | API server bind port |
| `AUTOSRE_API_KEY` | No | API key for authentication |
