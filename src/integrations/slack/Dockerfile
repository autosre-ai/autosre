# AutoSRE Slack Bot
#
# Multi-stage build for the Slack bot integration

# ============================================
# Stage 1: Builder
# ============================================
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements-slack.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements-slack.txt

# ============================================
# Stage 2: Runtime
# ============================================
FROM python:3.12-slim AS runtime

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --gid 1000 autosre && \
    useradd --uid 1000 --gid 1000 --shell /bin/bash --create-home autosre

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY --chown=autosre:autosre . /app/src/integrations/slack/

# Set Python path
ENV PYTHONPATH="/app"
ENV PYTHONUNBUFFERED=1

# Switch to non-root user
USER autosre

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${HEALTH_PORT:-8080}/health || exit 1

# Default command
CMD ["python", "-m", "src.integrations.slack.bot"]

# Metadata
LABEL org.opencontainers.image.title="AutoSRE Slack Bot" \
      org.opencontainers.image.description="Slack integration for AutoSRE incident investigation" \
      org.opencontainers.image.vendor="AutoSRE" \
      org.opencontainers.image.version="0.1.0"
