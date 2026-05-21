# AutoSRE API

FastAPI-based API Gateway for the AutoSRE intelligent incident investigation platform.

## Quick Start

```bash
# Install dependencies
pip install -e .

# Run development server
python main.py

# Or with uvicorn directly
uvicorn main:app --reload
```

## API Documentation

Once running, access the interactive docs at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/openapi.json

## Endpoints

### Health
- `GET /health` - Comprehensive health check
- `GET /ready` - Kubernetes readiness probe
- `GET /live` - Kubernetes liveness probe

### Investigations
- `POST /api/v1/investigate` - Start new investigation
- `GET /api/v1/investigate` - List investigations
- `GET /api/v1/investigate/{id}` - Get investigation details
- `GET /api/v1/investigate/{id}/stream` - SSE event stream
- `POST /api/v1/investigate/{id}/feedback` - Submit feedback
- `DELETE /api/v1/investigate/{id}` - Cancel investigation

### Memory
- `GET /api/v1/memory/episodes` - List episodes
- `GET /api/v1/memory/episodes/{id}` - Get episode
- `POST /api/v1/memory/search` - Search similar episodes
- `GET /api/v1/memory/strategies` - List learned strategies
- `GET /api/v1/memory/stats` - Memory statistics

### Configuration
- `GET /api/v1/config/teams` - List teams
- `GET /api/v1/config/teams/{id}` - Get team
- `PUT /api/v1/config/teams/{id}` - Update team
- `GET /api/v1/config/skills` - List skills

## Authentication

All endpoints (except health) require JWT authentication:

```bash
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/v1/investigate
```

## Docker

```bash
# Build image
docker build -t autosre-api .

# Run container
docker run -p 8000:8000 -e JWT_SECRET=your-secret autosre-api
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | 8000 | Server port |
| `ENV` | development | Environment (development/production) |
| `JWT_SECRET` | dev-secret-* | JWT signing secret |
| `CORS_ORIGINS` | * | Allowed CORS origins (comma-separated) |
