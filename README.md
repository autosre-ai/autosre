# AutoSRE Docker Infrastructure

Production-ready Docker configuration for the AutoSRE platform.

## 🚀 New in v0.2.0: SRE Best Practices

AutoSRE now implements core SRE principles from Google's SRE book:

### AI Safety Features
- **Hypothesis-driven investigation**: All AI reasoning follows structured format with evidence and falsifiable criteria
- **Confidence scoring**: Every AI decision includes explicit confidence (0.0-1.0)
- **Human-in-the-loop**: Critical actions require human approval
- **AI error budgets**: Track AI accuracy with internal SLOs (80% high-severity accuracy, 99% safe action rate)
- **Telemetry**: Full decision audit trail for calibration and improvement

### SLO-Driven Operations
- **Error budget tracking**: Know exactly how much unreliability you can afford
- **Multi-window burn rates**: 1h, 6h, 24h, 7d burn rate calculations
- **Deployment gating**: Automatically block deploys when error budget exhausted
- **Budget policies**: Configurable thresholds for freeze, caution, and normal operation

### Investigation Phases
- **Triage-first approach**: Understand scope and impact before acting
- **Structured phases**: TRIAGE → MITIGATE → DIAGNOSE → RESOLVE
- **Phase discipline**: Prevents jumping to conclusions or missing scope

### Postmortem Automation
- **Auto-triggered**: User impact, data loss, long resolution time, repeat incidents
- **Auto-generated content**: Timeline, metrics snapshots, AI decision audit
- **Action item tracking**: Reminders and escalation for incomplete items
- **Blameless enforcement**: Automated scanning for blame language

### Toil Tracking
- **50% budget**: Track toil vs. project work
- **Auto-classification**: Identify repetitive manual work
- **Automation recommendations**: Suggest automation after N occurrences

📚 **Documentation**: See `docs/` for detailed guides on each feature.

---

## Quick Start

```bash
# Initial setup
make setup

# Edit .env with your configuration
vim .env

# Start all services
make dev

# View logs
make logs
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| web-ui | 3000 | Next.js web interface |
| api-gateway | 8000 | FastAPI REST API |
| litellm | 4000 | LLM proxy |
| sre-agent | 8080 (internal) | AI agent service |
| postgres | 5432 | PostgreSQL database |
| neo4j | 7474, 7687 | Graph database |
| redis | 6379 | Cache & pub/sub |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      External Network                        │
│  ┌──────────┐    ┌─────────────┐                            │
│  │  Web UI  │───▶│ API Gateway │                            │
│  │  :3000   │    │    :8000    │                            │
│  └──────────┘    └──────┬──────┘                            │
└─────────────────────────┼───────────────────────────────────┘
                          │
┌─────────────────────────┼───────────────────────────────────┐
│                         │        Internal Network           │
│  ┌──────────────────────▼──────────────────────┐            │
│  │              SRE Agent :8080                 │            │
│  └────┬─────────────────┬─────────────────┬────┘            │
│       │                 │                 │                  │
│  ┌────▼────┐      ┌────▼────┐      ┌────▼────┐             │
│  │ LiteLLM │      │PostgreSQL│      │  Neo4j  │             │
│  │  :4000  │      │  :5432   │      │  :7687  │             │
│  └────┬────┘      └─────────┘      └─────────┘             │
│       │                                                      │
│  ┌────▼────┐                                                │
│  │  Redis  │                                                │
│  │  :6379  │                                                │
│  └─────────┘                                                │
└─────────────────────────────────────────────────────────────┘
```

## Commands

### Development
- `make dev` - Start all services
- `make stop` - Stop all services
- `make restart` - Restart all services
- `make logs` - View all logs
- `make status` - Service status
- `make health` - Health check

### Building
- `make build` - Build all images
- `make build-no-cache` - Build without cache

### Testing
- `make test` - Run all tests
- `make lint` - Run linters
- `make format` - Format code

### Database
- `make db-shell` - PostgreSQL shell
- `make redis-cli` - Redis CLI
- `make neo4j-shell` - Neo4j Cypher shell
- `make db-migrate` - Run migrations

### Cleanup
- `make clean` - Stop and remove containers
- `make clean-volumes` - Remove all data (destructive)
- `make backup` - Backup all volumes

## Configuration

### Required Environment Variables

Generate secrets:
```bash
openssl rand -hex 32
```

Edit `.env`:
```env
POSTGRES_PASSWORD=<secure-password>
NEO4J_PASSWORD=<secure-password>
REDIS_PASSWORD=<secure-password>
LITELLM_MASTER_KEY=<your-key>
API_SECRET_KEY=<generated-hex>
JWT_SECRET_KEY=<generated-hex>
NEXTAUTH_SECRET=<generated-hex>
OPENAI_API_KEY=<your-key>
ANTHROPIC_API_KEY=<your-key>
```

### LiteLLM Configuration

Edit `config/litellm_config.yaml` to add/modify LLM models.

## Production Deployment

1. Set `ENVIRONMENT=production` in `.env`
2. Use proper secrets management (not .env files)
3. Set up reverse proxy (nginx/traefik)
4. Enable SSL/TLS
5. Set restrictive CORS origins
6. Run `make backup` regularly

## Troubleshooting

### Services not starting
```bash
make health
make logs
```

### Database connection issues
```bash
make db-shell
# Then: \conninfo
```

### Reset everything
```bash
make clean-all
make setup
make dev
```
