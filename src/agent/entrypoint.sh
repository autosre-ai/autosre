#!/bin/bash
# =============================================================================
# AutoSRE Agent Entrypoint
# =============================================================================
set -e

echo "=== AutoSRE Agent Starting ==="
echo "Environment: ${ENVIRONMENT:-development}"
echo "Log Level: ${AGENT_LOG_LEVEL:-INFO}"

# Wait for dependencies
echo "Waiting for database connections..."

# Wait for PostgreSQL
until python -c "import psycopg2; psycopg2.connect('${DATABASE_URL}')" 2>/dev/null; do
    echo "Waiting for PostgreSQL..."
    sleep 2
done
echo "✓ PostgreSQL connected"

# Wait for Neo4j
until python -c "from neo4j import GraphDatabase; GraphDatabase.driver('${NEO4J_URI}', auth=('${NEO4J_USER}', '${NEO4J_PASSWORD}')).verify_connectivity()" 2>/dev/null; do
    echo "Waiting for Neo4j..."
    sleep 2
done
echo "✓ Neo4j connected"

# Wait for Redis
until python -c "import redis; redis.from_url('${REDIS_URL}').ping()" 2>/dev/null; do
    echo "Waiting for Redis..."
    sleep 2
done
echo "✓ Redis connected"

echo "All dependencies ready!"

# Run database migrations if needed
if [ -f "scripts/migrate.sh" ]; then
    echo "Running migrations..."
    ./scripts/migrate.sh
fi

# Start the agent
echo "Starting SRE Agent..."
exec python -m src.agent.main \
    --host 0.0.0.0 \
    --port 8080 \
    --log-level "${AGENT_LOG_LEVEL:-INFO}"
