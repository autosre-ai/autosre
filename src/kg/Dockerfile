# syntax=docker/dockerfile:1.7

# ============================================================================
# AutoSRE Knowledge Graph Service - Production Container
# ============================================================================
#
# Multi-stage build for minimal, secure production image.
# Follows AutoSRE security hardening guidelines from SPEC.md.
#

# --- Builder stage ---
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# Using pip directly since this is a service module
COPY requirements.txt ./
RUN pip install --no-cache-dir --target=/build/deps -r requirements.txt

# Copy application
COPY . ./src/kg/

# --- Production image ---
FROM python:3.12-slim AS runtime

# Security: Create non-root user
RUN groupadd -r autosre && useradd -r -g autosre autosre

# Security: Install only runtime deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    tini \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

WORKDIR /app

# Copy dependencies from builder
COPY --from=builder /build/deps /usr/local/lib/python3.12/site-packages

# Copy application
COPY --from=builder /build/src/kg ./kg

# Security: Set ownership
RUN chown -R autosre:autosre /app

# Security: Switch to non-root
USER autosre

# Security: Read-only filesystem compatible
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Neo4j connection defaults (override via environment)
ENV NEO4J_URI=bolt://neo4j:7687
ENV NEO4J_USERNAME=neo4j
ENV NEO4J_PASSWORD=""
ENV NEO4J_DATABASE=neo4j
ENV NEO4J_MAX_POOL_SIZE=50

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import asyncio; from kg import get_client; asyncio.run(get_client().health_check())" || exit 1

# Graceful shutdown via tini
ENTRYPOINT ["/usr/bin/tini", "--"]

# Default: run health check (override for actual service)
CMD ["python", "-c", "import asyncio; from kg import get_client; print(asyncio.run(get_client().health_check()))"]
