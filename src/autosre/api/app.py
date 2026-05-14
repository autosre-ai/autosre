"""FastAPI Application Factory.

Main application entry point with middleware, routers, and lifecycle management.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from autosre.api.middleware.logging import RequestLoggingMiddleware
from autosre.api.routes import (
    alerts,
    chat,
    health,
    investigations,
    runbooks,
    webhooks,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager for startup/shutdown events."""
    # Startup
    # TODO: Initialize database connections, message queues, etc.
    yield
    # Shutdown
    # TODO: Clean up resources


app = FastAPI(
    title="AutoSRE API",
    description="Automated Site Reliability Engineering platform for incident investigation and remediation",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# Middleware (order matters - first added = outermost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure via settings in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(RequestLoggingMiddleware)

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(alerts.router, prefix="/api/v1/alerts", tags=["Alerts"])
app.include_router(
    investigations.router, prefix="/api/v1/investigations", tags=["Investigations"]
)
app.include_router(chat.router, prefix="/api/v1/chat", tags=["Chat"])
app.include_router(runbooks.router, prefix="/api/v1/runbooks", tags=["Runbooks"])
app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["Webhooks"])
