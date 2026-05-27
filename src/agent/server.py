"""
AutoSRE Investigation Server (LangGraph Mode)

FastAPI server that runs the LangGraph investigation graph.
Streams events via SSE using graph.astream_events().

Usage:
    python -m uvicorn autosre.server:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .config import settings
from .graph import get_graph

logger = logging.getLogger(__name__)
logging.basicConfig(level=getattr(logging, settings.log_level))

# Background task tracking
_background_tasks: Dict[str, asyncio.Task] = {}
_message_queues: Dict[str, asyncio.Queue] = {}
_response_queues: Dict[str, asyncio.Queue] = {}

app = FastAPI(
    title="AutoSRE Investigation Server",
    description="AI SRE agent for incident investigation - LangGraph mode",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request/Response Models
# ---------------------------------------------------------------------------


class InvestigateRequest(BaseModel):
    """Request to start an investigation."""
    prompt: str
    thread_id: Optional[str] = None
    service: Optional[str] = None
    severity: Optional[str] = "high"
    max_iterations: Optional[int] = 3


class InvestigateResponse(BaseModel):
    """Response from investigation start."""
    thread_id: str
    status: str
    message: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    mode: str
    version: str
    active_sessions: int


# ---------------------------------------------------------------------------
# Health Endpoints
# ---------------------------------------------------------------------------


@app.get("/", response_model=HealthResponse)
async def root():
    """Root endpoint with service info."""
    return HealthResponse(
        status="healthy",
        mode="langgraph",
        version="1.0.0",
        active_sessions=len(_background_tasks),
    )


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        mode="langgraph",
        version="1.0.0",
        active_sessions=len(_background_tasks),
    )


@app.get("/ready")
async def ready():
    """Readiness probe."""
    return {"status": "ready"}


@app.get("/live")
async def live():
    """Liveness probe."""
    return {"status": "live"}


# ---------------------------------------------------------------------------
# Investigation Endpoints
# ---------------------------------------------------------------------------


@app.post("/api/v1/investigate", response_model=InvestigateResponse)
async def start_investigation(request: InvestigateRequest):
    """Start a new investigation.
    
    Returns a thread_id that can be used to stream events.
    """
    thread_id = request.thread_id or str(uuid.uuid4())
    
    # Create queues for this thread
    _message_queues[thread_id] = asyncio.Queue()
    _response_queues[thread_id] = asyncio.Queue()
    
    # Parse alert from prompt
    alert = _parse_alert_from_prompt(request.prompt, request.service, request.severity)
    
    # Start background task
    task = asyncio.create_task(
        _run_investigation(thread_id, alert, request.max_iterations or 3)
    )
    _background_tasks[thread_id] = task
    
    logger.info(f"[SERVER] Started investigation {thread_id}")
    
    return InvestigateResponse(
        thread_id=thread_id,
        status="started",
        message="Investigation started. Stream events at /api/v1/investigate/{thread_id}/stream",
    )


@app.get("/api/v1/investigate/{thread_id}/stream")
async def stream_investigation(thread_id: str):
    """Stream investigation events via SSE."""
    if thread_id not in _response_queues:
        raise HTTPException(404, f"Investigation {thread_id} not found")
    
    async def event_generator():
        queue = _response_queues[thread_id]
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=300)
                    if event is None:
                        # End of stream
                        yield f"data: {json.dumps({'type': 'end', 'thread_id': thread_id})}\n\n"
                        break
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield f": keepalive\n\n"
        finally:
            # Cleanup
            _cleanup_thread(thread_id)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/v1/investigate/{thread_id}")
async def get_investigation_status(thread_id: str):
    """Get investigation status."""
    if thread_id not in _background_tasks:
        raise HTTPException(404, f"Investigation {thread_id} not found")
    
    task = _background_tasks[thread_id]
    return {
        "thread_id": thread_id,
        "status": "running" if not task.done() else "completed",
        "done": task.done(),
    }


@app.delete("/api/v1/investigate/{thread_id}")
async def cancel_investigation(thread_id: str):
    """Cancel an ongoing investigation."""
    if thread_id not in _background_tasks:
        raise HTTPException(404, f"Investigation {thread_id} not found")
    
    task = _background_tasks[thread_id]
    if not task.done():
        task.cancel()
    
    _cleanup_thread(thread_id)
    
    return {"thread_id": thread_id, "status": "cancelled"}


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------


def _parse_alert_from_prompt(
    prompt: str,
    service: Optional[str] = None,
    severity: Optional[str] = "high"
) -> dict:
    """Parse an alert dict from the investigation prompt."""
    try:
        alert = json.loads(prompt)
        if isinstance(alert, dict):
            return alert
    except (json.JSONDecodeError, TypeError):
        pass
    
    # Wrap as description-only alert
    return {
        "name": "Investigation",
        "description": prompt,
        "service": service or "",
        "severity": severity or "high",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def _run_investigation(
    thread_id: str,
    alert: dict,
    max_iterations: int = 3
):
    """Run the LangGraph investigation and stream events."""
    queue = _response_queues[thread_id]
    graph = get_graph()
    
    # Initial state
    initial_state = {
        "alert": alert,
        "thread_id": thread_id,
        "max_iterations": max_iterations,
        "iteration": 0,
        "status": "running",
        "messages": [],
        "hypotheses": [],
        "selected_agents": [],
        "agent_states": {},
        "memory_context": {},
        "kg_context": {},
    }
    
    run_config = {
        "configurable": {"thread_id": thread_id},
        "run_name": f"investigation-{thread_id}",
    }
    
    start_time = time.time()
    
    try:
        # Send start event
        await queue.put({
            "type": "start",
            "thread_id": thread_id,
            "alert": alert,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        
        # Stream events from the graph
        async for event in graph.astream_events(initial_state, config=run_config, version="v2"):
            event_type = event.get("event")
            
            if event_type == "on_chain_start":
                node_name = event.get("name", "")
                await queue.put({
                    "type": "node_start",
                    "node": node_name,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            
            elif event_type == "on_chain_end":
                node_name = event.get("name", "")
                output = event.get("data", {}).get("output", {})
                await queue.put({
                    "type": "node_end",
                    "node": node_name,
                    "output_keys": list(output.keys()) if isinstance(output, dict) else [],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            
            elif event_type == "on_tool_start":
                tool_name = event.get("name", "")
                tool_input = event.get("data", {}).get("input", {})
                await queue.put({
                    "type": "tool_start",
                    "tool": tool_name,
                    "input": str(tool_input)[:500],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            
            elif event_type == "on_tool_end":
                tool_name = event.get("name", "")
                tool_output = event.get("data", {}).get("output", "")
                await queue.put({
                    "type": "tool_end",
                    "tool": tool_name,
                    "output_preview": str(tool_output)[:500],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            
            elif event_type == "on_llm_stream":
                # Token streaming
                content = event.get("data", {}).get("chunk", {})
                if hasattr(content, "content") and content.content:
                    await queue.put({
                        "type": "token",
                        "content": content.content,
                    })
        
        # Get final state
        duration = time.time() - start_time
        
        await queue.put({
            "type": "complete",
            "thread_id": thread_id,
            "duration_seconds": duration,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        
    except asyncio.CancelledError:
        await queue.put({
            "type": "cancelled",
            "thread_id": thread_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.error(f"[SERVER] Investigation {thread_id} failed: {e}")
        await queue.put({
            "type": "error",
            "thread_id": thread_id,
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    finally:
        # Signal end of stream
        await queue.put(None)


def _cleanup_thread(thread_id: str):
    """Clean up resources for a thread."""
    _background_tasks.pop(thread_id, None)
    _message_queues.pop(thread_id, None)
    _response_queues.pop(thread_id, None)


# ---------------------------------------------------------------------------
# Startup/Shutdown Events
# ---------------------------------------------------------------------------


@app.on_event("startup")
async def startup_event():
    """Initialize on startup."""
    logger.info("[SERVER] AutoSRE Investigation Server starting...")
    # Pre-warm the graph
    _ = get_graph()
    logger.info("[SERVER] Graph initialized successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("[SERVER] Shutting down, cancelling active tasks...")
    for thread_id, task in _background_tasks.items():
        if not task.done():
            task.cancel()
    logger.info("[SERVER] Shutdown complete")
