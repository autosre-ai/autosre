"""
AutoSRE API Application

FastAPI application providing REST API and WebSocket endpoints
for real-time investigation monitoring and dashboard.
"""

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from autosre.api.routes.ws import router as ws_router
from autosre.api.websocket import get_connection_manager
from autosre.dashboard.metrics import get_metrics_aggregator


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    manager = get_connection_manager()
    await manager.start_heartbeat()
    
    yield
    
    # Shutdown
    await manager.stop_heartbeat()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="AutoSRE API",
        description="REST API and WebSocket endpoints for AutoSRE real-time dashboard",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Metrics middleware
    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next):
        """Record metrics for all API requests."""
        start_time = time.time()
        response: Response = await call_next(request)
        duration = time.time() - start_time
        
        # Record metrics
        aggregator = get_metrics_aggregator()
        is_error = response.status_code >= 400
        aggregator.record_request(duration * 1000, is_error)
        
        return response
    
    # Include WebSocket routes
    app.include_router(ws_router, prefix="/api")
    
    # Health check
    @app.get("/health")
    async def health():
        """Health check endpoint."""
        return {"status": "healthy", "service": "autosre-api"}
    
    # API info
    @app.get("/api")
    async def api_info():
        """API information endpoint."""
        manager = get_connection_manager()
        return {
            "name": "AutoSRE API",
            "version": "0.1.0",
            "docs": "/api/docs",
            "websocket_endpoints": [
                "/api/ws",
                "/api/ws/investigations/{investigation_id}",
                "/api/ws/metrics",
                "/api/ws/events",
                "/api/ws/alerts",
            ],
            "active_connections": manager.active_connections,
        }
    
    return app


# Default app instance
app = create_app()
