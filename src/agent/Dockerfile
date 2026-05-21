# =============================================================================
# AutoSRE Agent - Production Dockerfile
# Multi-stage build for minimal image size and security
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Builder - Install dependencies and build
# -----------------------------------------------------------------------------
FROM python:3.12-slim AS builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy only requirements first for layer caching
WORKDIR /build
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt

# -----------------------------------------------------------------------------
# Stage 2: Production - Minimal runtime image
# -----------------------------------------------------------------------------
FROM python:3.12-slim AS production

# Labels
LABEL org.opencontainers.image.title="AutoSRE Agent" \
      org.opencontainers.image.description="AI-powered SRE agent for autonomous operations" \
      org.opencontainers.image.vendor="AutoSRE" \
      org.opencontainers.image.source="https://github.com/autosre/agent"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random \
    # Application settings
    APP_HOME=/app \
    APP_USER=autosre \
    APP_GROUP=autosre \
    APP_UID=1000 \
    APP_GID=1000

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    ca-certificates \
    tini \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user and group
RUN groupadd --gid ${APP_GID} ${APP_GROUP} && \
    useradd --uid ${APP_UID} --gid ${APP_GID} --shell /bin/bash --create-home ${APP_USER}

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create application directory structure
WORKDIR ${APP_HOME}
RUN mkdir -p data logs config && \
    chown -R ${APP_USER}:${APP_GROUP} ${APP_HOME}

# Copy application code (order optimized for caching)
# 1. Copy configuration files first (least likely to change)
COPY --chown=${APP_USER}:${APP_GROUP} config/ ./config/

# 2. Copy package/module definitions
COPY --chown=${APP_USER}:${APP_GROUP} pyproject.toml setup.py* ./

# 3. Copy source code (most likely to change)
COPY --chown=${APP_USER}:${APP_GROUP} src/ ./src/

# 4. Copy entrypoint and scripts
COPY --chown=${APP_USER}:${APP_GROUP} scripts/ ./scripts/
COPY --chown=${APP_USER}:${APP_GROUP} entrypoint.sh ./

# Make scripts executable
RUN chmod +x entrypoint.sh scripts/*.sh 2>/dev/null || true

# Switch to non-root user
USER ${APP_USER}

# Expose health check port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=15s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Use tini as init system for proper signal handling
ENTRYPOINT ["/usr/bin/tini", "--"]

# Default command
CMD ["./entrypoint.sh"]
