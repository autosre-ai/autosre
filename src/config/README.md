# AutoSRE Configuration Service

Configuration management service for AutoSRE agents.

## Features

- **Team Management**: Create and manage teams/organizations
- **Token Management**: Generate and verify API tokens with permissions
- **Agent Configuration**: Configure agent behavior, models, and settings
- **Skill Configuration**: Enable/disable skills with granular controls

## Quick Start

### Development with Docker Compose

```bash
# Start services
docker compose up -d

# Run migrations
docker compose exec config-service alembic upgrade head

# View logs
docker compose logs -f config-service
```

### Local Development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Set up database (requires PostgreSQL)
cp .env.example .env
# Edit .env with your database URL

# Run migrations
alembic upgrade head

# Start server
uvicorn main:app --reload
```

## API Endpoints

### Teams
- `GET /api/v1/teams` - List teams
- `POST /api/v1/teams` - Create team
- `GET /api/v1/teams/{id}` - Get team
- `PUT /api/v1/teams/{id}` - Update team
- `DELETE /api/v1/teams/{id}` - Delete team

### Tokens
- `GET /api/v1/tokens` - List tokens
- `POST /api/v1/tokens` - Create token
- `DELETE /api/v1/tokens/{id}` - Revoke token
- `POST /api/v1/tokens/verify` - Verify token

### Agent Configuration
- `GET /api/v1/agents/config` - List configs
- `POST /api/v1/agents/config` - Create config
- `GET /api/v1/agents/config/{id}` - Get config
- `PUT /api/v1/agents/config/{id}` - Update config
- `DELETE /api/v1/agents/config/{id}` - Delete config

### Skills
- `GET /api/v1/agents/skills` - List skills
- `POST /api/v1/agents/skills` - Create skill
- `GET /api/v1/agents/skills/{id}` - Get skill
- `PUT /api/v1/agents/skills/{id}` - Update skill
- `PUT /api/v1/agents/skills` - Bulk toggle skills
- `DELETE /api/v1/agents/skills/{id}` - Delete skill

## Authentication

Use API tokens in the `X-API-Key` header:

```bash
curl -H "X-API-Key: asre_your_token_here" http://localhost:8000/api/v1/teams
```

### Permissions
- `read` - Read-only access
- `write` - Read and write access
- `admin` - Full access including team management

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection URL | Required |
| `SECRET_KEY` | JWT signing key | Required in production |
| `ENVIRONMENT` | development/staging/production | development |
| `DEBUG` | Enable debug mode | false |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT access token TTL | 30 |

## Database Migrations

```bash
# Create migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

## Testing

```bash
pytest -v
pytest --cov=. --cov-report=html
```
