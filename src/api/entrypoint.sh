#!/bin/bash
# =============================================================================
# AutoSRE API Gateway Entrypoint
# =============================================================================
set -e

echo "=== AutoSRE API Gateway Starting ==="
echo "Environment: ${NODE_ENV:-development}"
echo "Workers: ${API_WORKERS:-4}"

# Wait for dependencies
echo "Waiting for dependencies..."

# Wait for PostgreSQL
until python -c "import psycopg2; psycopg2.connect('${DATABASE_URL}')" 2>/dev/null; do
    echo "Waiting for PostgreSQL..."
    sleep 2
done
echo "✓ PostgreSQL connected"

# Wait for Redis
until python -c "import redis; redis.from_url('${REDIS_URL}').ping()" 2>/dev/null; do
    echo "Waiting for Redis..."
    sleep 2
done
echo "✓ Redis connected"

# Wait for SRE Agent
until curl -sf "${AGENT_URL}/health" > /dev/null 2>&1; do
    echo "Waiting for SRE Agent..."
    sleep 2
done
echo "✓ SRE Agent connected"

echo "All dependencies ready!"

# Run database migrations
echo "Running database migrations..."
alembic upgrade head || echo "Migration skipped or failed"

# Start the API server
echo "Starting API Gateway..."
exec uvicorn app.main:app \
    --host "${API_HOST:-0.0.0.0}" \
    --port "${API_PORT:-8000}" \
    --workers "${API_WORKERS:-4}" \
    --log-level "${API_LOG_LEVEL:-info}" \
    --access-log \
    --proxy-headers \
    --forwarded-allow-ips='*'
