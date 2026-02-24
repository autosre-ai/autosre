"""
FastAPI Application - REST API and WebSocket server
"""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import asyncio
import json
from pathlib import Path

from opensre_core import __version__
from opensre_core.config import settings
from opensre_core.agents.orchestrator import InvestigationManager


# Global investigation manager
investigation_manager: InvestigationManager | None = None

# WebSocket connections for real-time updates
websocket_connections: list[WebSocket] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    global investigation_manager
    investigation_manager = InvestigationManager()
    yield
    # Cleanup


def create_app() -> FastAPI:
    """Create FastAPI application."""
    app = FastAPI(
        title="SRE-Agent",
        description="AI-Powered SRE Copilot — Autonomous troubleshooting with human-in-the-loop",
        version=__version__,
        lifespan=lifespan,
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Register routes
    app.include_router(api_router)
    
    # Serve static files (UI)
    ui_path = Path(__file__).parent.parent / "ui" / "dist"
    if ui_path.exists():
        app.mount("/assets", StaticFiles(directory=ui_path / "assets"), name="assets")
        
        @app.get("/")
        async def serve_ui():
            return FileResponse(ui_path / "index.html")
    
    return app


# =============================================================================
# API Routes
# =============================================================================

from fastapi import APIRouter

api_router = APIRouter(prefix="/api")


class InvestigateRequest(BaseModel):
    """Request to start an investigation."""
    issue: str
    namespace: str = "default"


class ApproveActionRequest(BaseModel):
    """Request to approve an action."""
    investigation_id: str
    action_id: str


class RejectActionRequest(BaseModel):
    """Request to reject an action."""
    investigation_id: str
    action_id: str
    reason: str = ""


@api_router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": __version__}


@api_router.get("/status")
async def get_status():
    """Get system status including integration health."""
    from opensre_core.adapters import PrometheusAdapter, KubernetesAdapter, LLMAdapter
    
    checks = {}
    
    # Check Prometheus
    try:
        result = await PrometheusAdapter().health_check()
        checks["prometheus"] = {"status": "connected", **result}
    except Exception as e:
        checks["prometheus"] = {"status": "error", "error": str(e)}
    
    # Check Kubernetes
    try:
        result = await KubernetesAdapter().health_check()
        checks["kubernetes"] = {"status": "connected", **result}
    except Exception as e:
        checks["kubernetes"] = {"status": "error", "error": str(e)}
    
    # Check LLM
    try:
        result = await LLMAdapter().health_check()
        checks["llm"] = {"status": "connected", **result}
    except Exception as e:
        checks["llm"] = {"status": "error", "error": str(e)}
    
    return {
        "version": __version__,
        "integrations": checks,
    }


@api_router.post("/investigate")
async def start_investigation(request: InvestigateRequest):
    """Start a new investigation."""
    if not investigation_manager:
        raise HTTPException(status_code=500, detail="Server not initialized")
    
    investigation_id = await investigation_manager.start_investigation(
        issue=request.issue,
        namespace=request.namespace,
    )
    
    # Notify WebSocket clients
    await broadcast_update({
        "type": "investigation_started",
        "id": investigation_id,
        "issue": request.issue,
    })
    
    return {
        "id": investigation_id,
        "status": "started",
        "message": f"Investigation started for: {request.issue}",
    }


@api_router.get("/investigations")
async def list_investigations():
    """List all investigations."""
    if not investigation_manager:
        raise HTTPException(status_code=500, detail="Server not initialized")
    
    return await investigation_manager.list_investigations()


@api_router.get("/investigations/{investigation_id}")
async def get_investigation(investigation_id: str):
    """Get investigation details."""
    if not investigation_manager:
        raise HTTPException(status_code=500, detail="Server not initialized")
    
    investigation = await investigation_manager.get_investigation(investigation_id)
    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found")
    
    return investigation.to_dict()


@api_router.post("/actions/approve")
async def approve_action(request: ApproveActionRequest):
    """Approve and execute an action."""
    if not investigation_manager:
        raise HTTPException(status_code=500, detail="Server not initialized")
    
    result = await investigation_manager.approve_action(
        investigation_id=request.investigation_id,
        action_id=request.action_id,
    )
    
    # Notify WebSocket clients
    await broadcast_update({
        "type": "action_executed",
        "investigation_id": request.investigation_id,
        "action_id": request.action_id,
        "result": result,
    })
    
    return result


@api_router.post("/actions/reject")
async def reject_action(request: RejectActionRequest):
    """Reject an action."""
    if not investigation_manager:
        raise HTTPException(status_code=500, detail="Server not initialized")
    
    result = await investigation_manager.reject_action(
        investigation_id=request.investigation_id,
        action_id=request.action_id,
        reason=request.reason,
    )
    
    return result


# =============================================================================
# WebSocket for Real-time Updates
# =============================================================================

@api_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await websocket.accept()
    websocket_connections.append(websocket)
    
    try:
        while True:
            # Keep connection alive, handle incoming messages
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Handle different message types
            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
            
            elif message.get("type") == "investigate":
                # Start investigation from WebSocket
                if investigation_manager:
                    inv_id = await investigation_manager.start_investigation(
                        issue=message.get("issue", ""),
                        namespace=message.get("namespace", "default"),
                    )
                    await websocket.send_json({
                        "type": "investigation_started",
                        "id": inv_id,
                    })
    
    except WebSocketDisconnect:
        websocket_connections.remove(websocket)
    except Exception:
        if websocket in websocket_connections:
            websocket_connections.remove(websocket)


async def broadcast_update(message: dict[str, Any]):
    """Broadcast update to all connected WebSocket clients."""
    disconnected = []
    
    for ws in websocket_connections:
        try:
            await ws.send_json(message)
        except Exception:
            disconnected.append(ws)
    
    # Remove disconnected clients
    for ws in disconnected:
        if ws in websocket_connections:
            websocket_connections.remove(ws)


# =============================================================================
# Prometheus Queries (for UI graphs)
# =============================================================================

@api_router.get("/prometheus/query")
async def prometheus_query(query: str, time: str | None = None):
    """Execute a Prometheus query."""
    from opensre_core.adapters import PrometheusAdapter
    
    adapter = PrometheusAdapter()
    try:
        result = await adapter.query(query)
        return {
            "status": "success",
            "data": [
                {
                    "metric": r.labels,
                    "value": r.current_value,
                }
                for r in result
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/prometheus/query_range")
async def prometheus_query_range(
    query: str,
    start: str | None = None,
    end: str | None = None,
    step: str = "15s",
):
    """Execute a Prometheus range query."""
    from opensre_core.adapters import PrometheusAdapter
    from datetime import datetime, timedelta
    
    adapter = PrometheusAdapter()
    
    # Parse times
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=1)
    
    try:
        result = await adapter.query_range(query, start_time, end_time, step)
        return {
            "status": "success",
            "data": [
                {
                    "metric": r.labels,
                    "values": [[v[0].timestamp(), v[1]] for v in r.values],
                }
                for r in result
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Kubernetes (for UI)
# =============================================================================

@api_router.get("/kubernetes/pods")
async def get_pods(namespace: str = "default"):
    """Get pods in namespace."""
    from opensre_core.adapters import KubernetesAdapter
    
    adapter = KubernetesAdapter()
    try:
        pods = await adapter.get_pods(namespace)
        return {
            "pods": [
                {
                    "name": p.name,
                    "namespace": p.namespace,
                    "status": p.status,
                    "ready": p.ready,
                    "restarts": p.restarts,
                    "age": p.age,
                }
                for p in pods
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/kubernetes/events")
async def get_events(namespace: str = "default"):
    """Get events in namespace."""
    from opensre_core.adapters import KubernetesAdapter
    
    adapter = KubernetesAdapter()
    try:
        events = await adapter.get_events(namespace)
        return {
            "events": [
                {
                    "type": e.type,
                    "reason": e.reason,
                    "message": e.message,
                    "count": e.count,
                    "object": e.involved_object,
                }
                for e in events[-50:]  # Last 50 events
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
