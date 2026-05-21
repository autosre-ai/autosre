"""AutoSRE API Gateway - FastAPI Application."""

import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog

from .routes import (
    investigate_router,
    memory_router,
    config_router,
    health_router,
)
from .models.common import ErrorResponse
from .services import AgentService

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Application metadata
APP_TITLE = "AutoSRE API"
APP_DESCRIPTION = """
## AutoSRE - Intelligent SRE Investigation Platform

AutoSRE is an agentic system that automates incident investigation and response.

### Key Features

- **Automated Investigation**: AI agents analyze alerts and diagnose root causes
- **Episodic Memory**: Learn from past incidents to improve future responses
- **Skill-based Architecture**: Modular capabilities for metrics, logs, and remediation
- **Human-in-the-Loop**: Feedback system for continuous improvement

### API Overview

- **Investigations** (`/api/v1/investigate`): Start, monitor, and manage investigations
- **Memory** (`/api/v1/memory`): Access episodic memory and learned strategies
- **Configuration** (`/api/v1/config`): Manage teams, skills, and settings
- **Health** (`/health`, `/ready`, `/live`): Service health endpoints

### Authentication

All endpoints (except health checks) require JWT authentication.
Include the token in the `Authorization` header:

```
Authorization: Bearer <your-token>
```

### Real-time Updates

For real-time investigation updates, use the SSE stream endpoint:

```
GET /api/v1/investigate/{id}/stream
```
"""

APP_VERSION = "0.1.0"


# Service instances
_agent_service = AgentService()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    # Startup
    logger.info("autosre_api_starting", version=APP_VERSION)
    await _agent_service.connect()
    logger.info("autosre_api_started")

    yield

    # Shutdown
    logger.info("autosre_api_stopping")
    await _agent_service.disconnect()
    logger.info("autosre_api_stopped")


# Create FastAPI application
app = FastAPI(
    title=APP_TITLE,
    description=APP_DESCRIPTION,
    version=APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)


# CORS middleware
allowed_origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next) -> Response:
    """Log all requests with timing and correlation ID."""
    # Generate correlation ID
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

    # Bind request context to logger
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        method=request.method,
        path=request.url.path,
    )

    start_time = time.perf_counter()

    try:
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start_time) * 1000

        logger.info(
            "request_completed",
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
        )

        # Add correlation ID to response
        response.headers["X-Request-ID"] = request_id
        return response

    except Exception as e:
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.error(
            "request_failed",
            error=str(e),
            duration_ms=round(duration_ms, 2),
            exc_info=True,
        )
        raise


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler for unhandled errors."""
    request_id = request.headers.get("X-Request-ID", "unknown")

    logger.error(
        "unhandled_exception",
        error=str(exc),
        request_id=request_id,
        exc_info=True,
    )

    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="internal_error",
            message="An unexpected error occurred",
            request_id=request_id,
        ).model_dump(),
    )


# Include routers
app.include_router(health_router)
app.include_router(investigate_router)
app.include_router(memory_router)
app.include_router(config_router)


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    """Root endpoint - redirect to docs."""
    return {
        "name": APP_TITLE,
        "version": APP_VERSION,
        "docs": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("ENV", "development") == "development",
        log_level="info",
    )
