# ==============================================================================
# OpenSRE - AI-Powered Incident Response
# ==============================================================================

# Stage 1: Build dependencies
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY pyproject.toml README.md ./
COPY opensre_core/__init__.py opensre_core/

# Create wheel with all extras
RUN pip wheel --no-cache-dir --wheel-dir /wheels -e ".[all]"

# Stage 2: Runtime image
FROM python:3.11-slim AS runtime

# Security: Run as non-root
RUN groupadd -r opensre && useradd -r -g opensre opensre

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Install kubectl for Kubernetes operations
RUN curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" \
    && install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl \
    && rm kubectl

# Copy wheels and install
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

# Copy application code
COPY opensre_core/ /app/opensre_core/
COPY runbooks/ /app/runbooks/
COPY config/ /app/config/

# Set ownership
RUN chown -R opensre:opensre /app

# Switch to non-root user
USER opensre

# Environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    OPENSRE_LOG_LEVEL=INFO

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Default command
CMD ["uvicorn", "opensre_core.api:app", "--host", "0.0.0.0", "--port", "8000"]
