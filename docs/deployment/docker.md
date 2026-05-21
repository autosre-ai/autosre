# Docker Deployment Guide

Production-ready Docker configuration for the AutoSRE platform.

## Prerequisites

- Docker 20.10+
- Docker Compose v2+
- 4GB RAM minimum (8GB recommended)

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

## Scaling

### Horizontal Scaling

The SRE agent is stateless and can be scaled horizontally:

```yaml
services:
  sre-agent:
    deploy:
      replicas: 3
```

### Database Scaling

For high-availability PostgreSQL, consider:
- PostgreSQL with streaming replication
- PgBouncer for connection pooling
- Read replicas for analytics queries

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

### Memory issues

If services are OOM-killed, adjust limits in `docker-compose.yml`:

```yaml
services:
  sre-agent:
    deploy:
      resources:
        limits:
          memory: 4G
```

## Health Checks

All services expose health endpoints:

| Service | Health Endpoint |
|---------|-----------------|
| api-gateway | `GET /health` |
| sre-agent | `GET /health` |
| litellm | `GET /health` |

## Backup and Recovery

### Full Backup
```bash
make backup
```

This creates timestamped backups in `./backups/`:
- PostgreSQL dump
- Neo4j database export
- Redis RDB snapshot

### Restore
```bash
# Stop services
make stop

# Restore from backup
./scripts/restore.sh backups/2024-01-15/

# Start services
make dev
```

## Security Considerations

1. **Network Isolation**: Internal services are not exposed to the host
2. **Secrets**: Use Docker secrets or HashiCorp Vault in production
3. **TLS**: Enable TLS for all external connections
4. **Authentication**: API gateway enforces JWT authentication
5. **Rate Limiting**: Configure rate limits in the API gateway
