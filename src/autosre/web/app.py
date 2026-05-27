"""
AutoSRE Web Application - FastAPI + HTMX + Tailwind

The main web application that provides the dashboard UI.
"""

from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from autosre.web.routes import dashboard, evals, context, agent, feedback
from autosre.api.routes.ws import router as ws_router
from autosre.api.websocket import get_connection_manager


# Get template and static directories
WEB_DIR = Path(__file__).parent
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup/shutdown events."""
    # Startup
    print("🚀 AutoSRE Web Dashboard starting...")
    manager = get_connection_manager()
    await manager.start_heartbeat()
    yield
    # Shutdown
    print("👋 AutoSRE Web Dashboard shutting down...")
    await manager.stop_heartbeat()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="AutoSRE Dashboard",
        description="Web UI for the AutoSRE AI SRE Agent",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )
    
    # Mount static files
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    
    # Set up templates
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    app.state.templates = templates
    
    # Include routers
    app.include_router(dashboard.router, tags=["Dashboard"])
    app.include_router(evals.router, prefix="/evals", tags=["Evals"])
    app.include_router(context.router, prefix="/context", tags=["Context"])
    app.include_router(agent.router, prefix="/agent", tags=["Agent"])
    app.include_router(feedback.router, prefix="/feedback", tags=["Feedback"])
    
    # WebSocket routes
    app.include_router(ws_router, prefix="/api", tags=["WebSocket"])
    
    # Health check
    @app.get("/health")
    async def health():
        """Health check endpoint."""
        return {"status": "healthy", "service": "autosre-web"}
    
    # API info
    @app.get("/api")
    async def api_info():
        """API information."""
        return {
            "name": "AutoSRE Web API",
            "version": "0.1.0",
            "docs": "/api/docs",
        }
    
    return app


# Create default app instance
app = create_app()
