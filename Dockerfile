# ═══════════════════════════════════════════════════════════════════════════════
# AutoSRE — Multi-stage Docker Build
# ═══════════════════════════════════════════════════════════════════════════════
#
# Usage:
#   docker build -t autosre .
#   docker run -p 8000:8000 --env-file .env autosre
#
# ═══════════════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────────────
# Base stage
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# ─────────────────────────────────────────────────────────────────────────────
# Builder stage - install dependencies
# ─────────────────────────────────────────────────────────────────────────────
FROM base AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock* ./

# Create virtual environment and install dependencies
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN uv pip install --no-cache -e ".[all]"

# ─────────────────────────────────────────────────────────────────────────────
# Production stage
# ─────────────────────────────────────────────────────────────────────────────
FROM base AS production

# Install runtime dependencies only
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    tini \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Install kubectl for K8s operations (optional, comment out if not needed)
ARG KUBECTL_VERSION=v1.29.0
RUN curl -fsSL "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl" -o /usr/local/bin/kubectl \
    && chmod +x /usr/local/bin/kubectl

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create non-root user
RUN groupadd -r autosre && useradd -r -g autosre -d /app -s /sbin/nologin autosre \
    && mkdir -p /app /data \
    && chown -R autosre:autosre /app /data

# Copy application code
COPY --chown=autosre:autosre src/ /app/src/
COPY --chown=autosre:autosre pyproject.toml /app/

ENV PYTHONPATH=/app/src

USER autosre

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Use tini as init system
ENTRYPOINT ["/usr/bin/tini", "--"]

# Default command: run the API server
CMD ["python", "-m", "uvicorn", "autosre.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ─────────────────────────────────────────────────────────────────────────────
# Development stage (for local development with hot reload)
# ─────────────────────────────────────────────────────────────────────────────
FROM production AS development

USER root

# Install development dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
RUN /opt/venv/bin/pip install -e ".[dev]" 2>/dev/null || true

USER autosre

CMD ["python", "-m", "uvicorn", "autosre.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
