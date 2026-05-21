# AutoSRE Config Service Dockerfile
# Multi-stage build for production

# ============ Builder Stage ============
FROM python:3.12-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install pip and build tools
RUN pip install --no-cache-dir --upgrade pip hatch

# Copy project files
COPY pyproject.toml .
COPY . .

# Build wheel
RUN pip wheel --no-cache-dir --wheel-dir /wheels -e .


# ============ Production Stage ============
FROM python:3.12-slim as production

# Create non-root user
RUN groupadd -r autosre && useradd -r -g autosre autosre

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy wheels from builder and install
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index /wheels/*.whl && rm -rf /wheels

# Copy application code
COPY --chown=autosre:autosre . .

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=production

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Switch to non-root user
USER autosre

# Expose port
EXPOSE 8000

# Run with uvicorn
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
