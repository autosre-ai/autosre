"""
FastAPI Application - REST API and WebSocket server
"""

import asyncio
import json
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

from fastapi import (
    FastAPI,
    Header,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from opensre_core import __version__
from opensre_core.agents.orchestrator import InvestigationManager
from opensre_core.config import settings
from opensre_core.metrics import (
    WEBSOCKET_CONNECTIONS,
    get_content_type,
    get_metrics,
    record_api_request,
    set_version_info,
)
from opensre_core.security.audit import EventType, get_audit_logger
from opensre_core.security.auth import get_auth_manager
from opensre_core.security.rbac import Permission, check_permission

# Global investigation manager
investigation_manager: InvestigationManager | None = None

# Global Slack adapter
slack_adapter = None

# Global PagerDuty adapter
pagerduty_adapter = None

# WebSocket connections for real-time updates
websocket_connections: list[WebSocket] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    global investigation_manager, slack_adapter, pagerduty_adapter
    investigation_manager = InvestigationManager()

    # Initialize Slack adapter
    from opensre_core.adapters.slack import SlackAdapter
    slack_adapter = SlackAdapter()

    # Initialize PagerDuty adapter
    from opensre_core.adapters.pagerduty import PagerDutyAdapter
    pagerduty_adapter = PagerDutyAdapter()

    # Set version info for metrics
    set_version_info(__version__, settings.llm_provider)

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

    # Add metrics middleware
    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next):
        """Record metrics for all API requests."""
        start_time = time.time()
        response = await call_next(request)
        duration = time.time() - start_time

        # Don't record metrics for the /metrics endpoint itself
        if request.url.path != "/metrics":
            record_api_request(
                method=request.method,
                endpoint=request.url.path,
                status_code=response.status_code,
                latency=duration
            )

        return response

    # Register routes
    app.include_router(api_router)

    # Prometheus metrics endpoint (at root level, not under /api)
    @app.get("/metrics")
    async def metrics():
        """Prometheus metrics endpoint."""
        return Response(
            content=get_metrics(),
            media_type=get_content_type()
        )

    # Serve static files (UI) - Next.js static export uses _next/ folder
    ui_path = Path(__file__).parent.parent / "ui" / "dist"
    if ui_path.exists():
        # Mount _next static assets
        next_path = ui_path / "_next"
        if next_path.exists():
            app.mount("/_next", StaticFiles(directory=next_path), name="next_static")

        @app.get("/")
        async def serve_ui():
            return FileResponse(ui_path / "index.html")

    return app


# =============================================================================
# API Routes
# =============================================================================

from fastapi import APIRouter

api_router = APIRouter(prefix="/api")


# =============================================================================
# Authentication Dependency
# =============================================================================

async def get_current_user(
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    authorization: str | None = Header(None),
) -> dict:
    """
    Dependency to get the current authenticated user.

    Checks:
    1. X-API-Key header
    2. Authorization: Bearer <token> header
    3. OPENSRE_API_KEY environment variable
    """
    import os

    auth_manager = get_auth_manager()
    audit = get_audit_logger()

    # Try X-API-Key header
    if x_api_key:
        user_info = auth_manager.validate_api_key(x_api_key)
        if user_info:
            return user_info
        audit.log(EventType.AUTH_FAILURE, user="unknown", action="Invalid API key")
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Try Authorization header (Bearer token)
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        auth_token = auth_manager.validate_token(token)
        if auth_token:
            return {"user": auth_token.user, "roles": auth_token.roles}
        audit.log(EventType.AUTH_FAILURE, user="unknown", action="Invalid token")
        raise HTTPException(status_code=401, detail="Invalid token")

    # Try environment variable (for CLI/background jobs)
    env_key = os.environ.get("OPENSRE_API_KEY")
    if env_key:
        user_info = auth_manager.validate_api_key(env_key)
        if user_info:
            return user_info

    # Check if auth is required
    if settings.require_approval:  # Use this as proxy for require_auth for now
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Default to system user if auth not required
    return {"user": "anonymous", "roles": ["viewer"]}


async def require_permission_dep(required: Permission):
    """Factory for permission-checking dependencies."""
    async def check(current_user: dict = Depends(get_current_user)) -> dict:
        if not check_permission(current_user.get("roles", []), required):
            audit = get_audit_logger()
            audit.log_permission_denied(
                user=current_user.get("user", "unknown"),
                action="API access",
                required_permission=required.value,
            )
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: requires {required.value}",
            )
        return current_user
    return check


# Make get_current_user importable as a dependency
from fastapi import Depends


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
    from opensre_core.adapters import (
        KubernetesAdapter,
        LLMAdapter,
        PagerDutyAdapter,
        PrometheusAdapter,
        SlackAdapter,
    )

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

    # Check Slack
    try:
        result = await SlackAdapter().health_check()
        checks["slack"] = result
    except Exception as e:
        checks["slack"] = {"status": "error", "error": str(e)}

    # Check PagerDuty
    try:
        result = await PagerDutyAdapter().health_check()
        checks["pagerduty"] = result
    except Exception as e:
        checks["pagerduty"] = {"status": "error", "error": str(e)}

    return {
        "version": __version__,
        "integrations": checks,
    }


@api_router.post("/investigate")
async def start_investigation(
    request: InvestigateRequest,
    current_user: dict = Depends(get_current_user),
):
    """Start a new investigation."""
    if not investigation_manager:
        raise HTTPException(status_code=500, detail="Server not initialized")

    # Check read permission (anyone who can read can start investigation)
    if not check_permission(current_user.get("roles", []), Permission.READ_INVESTIGATIONS):
        raise HTTPException(status_code=403, detail="Permission denied")

    # Audit log
    audit = get_audit_logger()
    audit.log_investigation(
        user=current_user.get("user", "unknown"),
        issue=request.issue,
        namespace=request.namespace,
    )

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
async def approve_action(
    request: ApproveActionRequest,
    current_user: dict = Depends(get_current_user),
):
    """Approve and execute an action."""
    if not investigation_manager:
        raise HTTPException(status_code=500, detail="Server not initialized")

    # Check APPROVE_ACTIONS permission
    if not check_permission(current_user.get("roles", []), Permission.APPROVE_ACTIONS):
        audit = get_audit_logger()
        audit.log_permission_denied(
            user=current_user.get("user", "unknown"),
            action=f"approve action {request.action_id}",
            required_permission=Permission.APPROVE_ACTIONS.value,
        )
        raise HTTPException(status_code=403, detail="Permission denied: requires approve:actions")

    result = await investigation_manager.approve_action(
        investigation_id=request.investigation_id,
        action_id=request.action_id,
        approved_by=current_user.get("user", "unknown"),
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
async def reject_action(
    request: RejectActionRequest,
    current_user: dict = Depends(get_current_user),
):
    """Reject an action."""
    if not investigation_manager:
        raise HTTPException(status_code=500, detail="Server not initialized")

    # Any authenticated user can reject (it's safer than approving)
    result = await investigation_manager.reject_action(
        investigation_id=request.investigation_id,
        action_id=request.action_id,
        reason=request.reason,
        rejected_by=current_user.get("user", "unknown"),
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
    WEBSOCKET_CONNECTIONS.inc()

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
        WEBSOCKET_CONNECTIONS.dec()
    except Exception:
        if websocket in websocket_connections:
            websocket_connections.remove(websocket)
            WEBSOCKET_CONNECTIONS.dec()


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


@api_router.websocket("/ws/investigate")
async def websocket_investigate(websocket: WebSocket):
    """
    WebSocket endpoint for real-time investigation streaming.

    Connect, send a JSON message with issue and namespace,
    then receive real-time events as the investigation progresses.

    Message format:
        {"issue": "high CPU on api-service", "namespace": "production"}

    Event types:
        - started: Investigation started
        - progress: Progress update (step, current, total)
        - observation: Single observation collected
        - observation_complete: All observations collected
        - thinking: Analysis in progress
        - hypothesis: Generated hypothesis
        - root_cause: Root cause identified
        - action: Remediation action suggested
        - completed: Investigation finished (includes full result)
        - error: Error occurred
    """
    await websocket.accept()
    WEBSOCKET_CONNECTIONS.inc()

    try:
        # Receive issue to investigate
        data = await websocket.receive_json()
        issue = data.get("issue")
        namespace = data.get("namespace", "default")

        if not issue:
            await websocket.send_json({
                "type": "error",
                "data": {"error": "Missing 'issue' field"},
                "timestamp": datetime.now().isoformat(),
            })
            await websocket.close()
            return

        if not investigation_manager:
            await websocket.send_json({
                "type": "error",
                "data": {"error": "Server not initialized"},
                "timestamp": datetime.now().isoformat(),
            })
            await websocket.close()
            return

        # Stream investigation events
        async for event in investigation_manager.start_investigation_streaming(issue, namespace):
            await websocket.send_json(event.to_dict())

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({
                "type": "error",
                "data": {"error": str(e)},
                "timestamp": datetime.now().isoformat(),
            })
        except Exception:
            pass
    finally:
        WEBSOCKET_CONNECTIONS.dec()
        try:
            await websocket.close()
        except Exception:
            pass


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
    from datetime import datetime, timedelta

    from opensre_core.adapters import PrometheusAdapter

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


# =============================================================================
# Slack Integration & Webhooks
# =============================================================================

class AlertPayload(BaseModel):
    """Alertmanager webhook payload."""
    version: str = "4"
    groupKey: str = ""
    status: str = "firing"  # firing or resolved
    receiver: str = ""
    groupLabels: dict[str, str] = {}
    commonLabels: dict[str, str] = {}
    commonAnnotations: dict[str, str] = {}
    externalURL: str = ""
    alerts: list[dict[str, Any]] = []


@api_router.post("/webhook/alert")
async def receive_alertmanager_webhook(alert: AlertPayload):
    """
    Receive alerts from Alertmanager and trigger investigation.

    Configure Alertmanager to send webhooks here:
    ```yaml
    receivers:
      - name: opensre
        webhook_configs:
          - url: 'http://opensre:8080/api/webhook/alert'
            send_resolved: true
    ```
    """
    if not investigation_manager:
        raise HTTPException(status_code=500, detail="Server not initialized")

    # Only process firing alerts
    if alert.status != "firing":
        return {"status": "ok", "message": "Resolved alert, no action needed"}

    # Extract issue summary from alert
    alert_name = alert.commonLabels.get("alertname", "Unknown Alert")
    namespace = alert.commonLabels.get("namespace", "default")
    summary = alert.commonAnnotations.get("summary", alert_name)
    description = alert.commonAnnotations.get("description", "")

    issue = f"{summary}. {description}".strip(". ")

    # Start investigation
    investigation_id = await investigation_manager.start_investigation(
        issue=issue,
        namespace=namespace,
    )

    # Wait for investigation to complete (with timeout)
    max_wait = 60  # seconds
    waited = 0
    investigation = None

    while waited < max_wait:
        investigation = await investigation_manager.get_investigation(investigation_id)
        if investigation and investigation.status in ["completed", "failed", "timeout"]:
            break
        await asyncio.sleep(2)
        waited += 2

    # Post to Slack if configured
    if slack_adapter and investigation:
        investigation.alert_name = alert_name
        await slack_adapter.send_investigation(investigation)

    # Notify WebSocket clients
    await broadcast_update({
        "type": "alert_received",
        "alert_name": alert_name,
        "investigation_id": investigation_id,
        "status": investigation.status if investigation else "running",
    })

    return {
        "status": "ok",
        "investigation_id": investigation_id,
        "alert_name": alert_name,
    }


@api_router.post("/slack/events")
async def slack_events(request: Request):
    """
    Handle Slack Events API callbacks.

    This endpoint handles:
    - URL verification challenge
    - App mentions
    - Direct messages
    """
    body = await request.body()
    data = await request.json()

    # URL verification challenge (Slack sends this during app setup)
    if data.get("type") == "url_verification":
        return {"challenge": data.get("challenge")}

    # Verify signature if signing secret is configured
    if slack_adapter and slack_adapter.signing_secret:
        timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
        signature = request.headers.get("X-Slack-Signature", "")

        if not slack_adapter.verify_signature(body, timestamp, signature):
            raise HTTPException(status_code=401, detail="Invalid signature")

    # Handle events
    event = data.get("event", {})
    event_type = event.get("type")

    # Respond to app mentions
    if event_type == "app_mention":
        text = event.get("text", "")
        channel = event.get("channel")

        # Extract issue from mention (remove bot mention)
        issue = " ".join(text.split()[1:]) if " " in text else "general health check"

        if investigation_manager and issue:
            inv_id = await investigation_manager.start_investigation(issue=issue)

            # Acknowledge the request
            if slack_adapter and slack_adapter.client:
                slack_adapter.client.chat_postMessage(
                    channel=channel,
                    text=f"🔍 Starting investigation: {issue}\nInvestigation ID: {inv_id}",
                )

    return {"ok": True}


@api_router.post("/slack/interactions")
async def slack_interactions(request: Request):
    """
    Handle Slack interactive component callbacks.

    Called when user clicks buttons in Slack messages.

    Configure your Slack app's Interactivity URL to point here:
    https://your-domain.com/api/slack/interactions
    """
    body = await request.body()

    # Slack sends interaction payloads as form-encoded with payload field
    content_type = request.headers.get("content-type", "")

    if "application/x-www-form-urlencoded" in content_type:
        form_data = parse_qs(body.decode())
        payload_str = form_data.get("payload", ["{}"])[0]
        payload = json.loads(payload_str)
    else:
        payload = await request.json()

    # Verify signature
    if slack_adapter and slack_adapter.signing_secret:
        timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
        signature = request.headers.get("X-Slack-Signature", "")

        if not slack_adapter.verify_signature(body, timestamp, signature):
            raise HTTPException(status_code=401, detail="Invalid signature")

    # Handle different interaction types
    interaction_type = payload.get("type")

    if interaction_type == "block_actions":
        # Button clicks
        actions = payload.get("actions", [])
        user = payload.get("user", {}).get("name", "unknown")
        channel = payload.get("channel", {}).get("id")
        message_ts = payload.get("message", {}).get("ts")

        for action in actions:
            action_id = action.get("action_id", "")
            value = action.get("value", "{}")

            try:
                value_data = json.loads(value)
            except json.JSONDecodeError:
                value_data = {"raw": value}

            if action_id == "approve_action":
                # Execute approved action
                if investigation_manager:
                    inv_id = value_data.get("investigation_id")
                    act_id = value_data.get("action_id")

                    result = await investigation_manager.approve_action(inv_id, act_id)

                    # Update Slack message
                    if slack_adapter and slack_adapter.client:
                        slack_adapter.client.chat_postMessage(
                            channel=channel,
                            thread_ts=message_ts,
                            text=f"✅ Action approved by @{user}\n\n" +
                                 (f"Result: {result.get('stdout', 'Success')}" if result.get('success') else f"❌ Error: {result.get('error', 'Unknown error')}"),
                        )

            elif action_id == "investigate_more":
                # Request deeper investigation
                if slack_adapter and slack_adapter.client:
                    slack_adapter.client.chat_postMessage(
                        channel=channel,
                        thread_ts=message_ts,
                        text=f"🔍 @{user} requested further investigation...",
                    )
                # TODO: Trigger deeper investigation

            elif action_id == "dismiss":
                # Dismiss the alert
                if slack_adapter and slack_adapter.client:
                    slack_adapter.client.chat_update(
                        channel=channel,
                        ts=message_ts,
                        text=f"❌ Alert dismissed by @{user}",
                        blocks=[{
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"❌ *Alert dismissed by @{user}*"
                            }
                        }],
                    )

    # Return 200 OK immediately (Slack requires response within 3 seconds)
    return JSONResponse(content={"ok": True})


# =============================================================================
# Slack Health Check Endpoint
# =============================================================================

@api_router.get("/slack/health")
async def slack_health():
    """Check Slack integration health."""
    if not slack_adapter:
        return {"status": "not_initialized", "configured": False}

    return await slack_adapter.health_check()


# =============================================================================
# PagerDuty Integration & Webhooks
# =============================================================================

class PagerDutyWebhookMessage(BaseModel):
    """A single PagerDuty webhook message."""
    event: str
    incident: dict[str, Any] = {}
    log_entries: list[dict[str, Any]] = []


class PagerDutyWebhookPayload(BaseModel):
    """PagerDuty webhook payload (v3)."""
    messages: list[PagerDutyWebhookMessage] = []


@api_router.post("/webhook/pagerduty")
async def pagerduty_webhook(request: Request):
    """
    Handle PagerDuty webhook events.

    Configure a Generic Webhook (v3) in PagerDuty:
    1. Go to Services > Your Service > Integrations
    2. Add Integration > Generic Webhook (v3)
    3. Set URL: https://your-domain.com/api/webhook/pagerduty
    4. Subscribe to: incident.triggered

    When an incident is triggered, OpenSRE will:
    1. Auto-investigate the incident
    2. Post investigation results as a note
    """
    if not investigation_manager:
        raise HTTPException(status_code=500, detail="Server not initialized")

    data = await request.json()

    # Handle v3 webhook format
    messages = data.get("messages", [])

    results = []

    for message in messages:
        event = message.get("event")
        incident = message.get("incident", {})
        incident_id = incident.get("id")

        if event == "incident.triggered":
            # Auto-investigate new incidents
            issue = incident.get("title", "Unknown issue")
            namespace = "default"

            # Try to extract namespace from incident details
            body = incident.get("body", {})
            if isinstance(body, dict):
                details = body.get("details", "")
                if "namespace:" in details.lower():
                    # Extract namespace from details
                    for line in details.split("\n"):
                        if "namespace:" in line.lower():
                            namespace = line.split(":")[-1].strip()
                            break

            # Start investigation
            investigation_id = await investigation_manager.start_investigation(
                issue=issue,
                namespace=namespace,
            )

            # Wait for investigation to complete (with timeout)
            max_wait = 60  # seconds
            waited = 0
            investigation = None

            while waited < max_wait:
                investigation = await investigation_manager.get_investigation(
                    investigation_id
                )
                if investigation and investigation.status in [
                    "completed", "failed", "timeout"
                ]:
                    break
                await asyncio.sleep(2)
                waited += 2

            # Add investigation as PagerDuty note
            if pagerduty_adapter and pagerduty_adapter.api_key and investigation:
                try:
                    note = pagerduty_adapter.format_investigation_note(investigation)
                    await pagerduty_adapter.add_note(incident_id, note)
                except Exception as e:
                    # Log error but don't fail the webhook
                    print(f"Failed to post PagerDuty note: {e}")

            # Also post to Slack if configured
            if slack_adapter and investigation:
                investigation.alert_name = issue
                await slack_adapter.send_investigation(investigation)

            # Notify WebSocket clients
            await broadcast_update({
                "type": "pagerduty_incident",
                "event": event,
                "incident_id": incident_id,
                "investigation_id": investigation_id,
                "status": investigation.status if investigation else "running",
            })

            results.append({
                "incident_id": incident_id,
                "investigation_id": investigation_id,
                "status": investigation.status if investigation else "timeout",
            })

        elif event == "incident.acknowledged":
            # Log acknowledgment
            await broadcast_update({
                "type": "pagerduty_incident",
                "event": event,
                "incident_id": incident_id,
            })
            results.append({"incident_id": incident_id, "event": event})

        elif event == "incident.resolved":
            # Log resolution
            await broadcast_update({
                "type": "pagerduty_incident",
                "event": event,
                "incident_id": incident_id,
            })
            results.append({"incident_id": incident_id, "event": event})

    return {"status": "ok", "processed": len(results), "results": results}


@api_router.get("/pagerduty/health")
async def pagerduty_health():
    """Check PagerDuty integration health."""
    if not pagerduty_adapter:
        return {"status": "not_initialized", "configured": False}

    return await pagerduty_adapter.health_check()


@api_router.get("/pagerduty/incidents")
async def get_pagerduty_incidents(
    status: str | None = None,
    urgency: str | None = None,
    limit: int = 25,
):
    """
    Get open incidents from PagerDuty.

    Args:
        status: Filter by status (triggered, acknowledged, resolved)
        urgency: Filter by urgency (high, low)
        limit: Maximum number of incidents to return
    """
    if not pagerduty_adapter or not pagerduty_adapter.api_key:
        raise HTTPException(
            status_code=400,
            detail="PagerDuty not configured"
        )

    statuses = [status] if status else None
    urgencies = [urgency] if urgency else None

    try:
        incidents = await pagerduty_adapter.get_incidents(
            statuses=statuses,
            urgencies=urgencies,
            limit=limit,
        )
        return {
            "incidents": [
                {
                    "id": inc.id,
                    "title": inc.title,
                    "status": inc.status,
                    "urgency": inc.urgency,
                    "service_name": inc.service_name,
                    "created_at": inc.created_at.isoformat(),
                    "html_url": inc.html_url,
                }
                for inc in incidents
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/pagerduty/incidents/{incident_id}/investigate")
async def investigate_pagerduty_incident(
    incident_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Manually trigger an investigation for a PagerDuty incident.

    Args:
        incident_id: The PagerDuty incident ID to investigate
    """
    if not pagerduty_adapter or not pagerduty_adapter.api_key:
        raise HTTPException(
            status_code=400,
            detail="PagerDuty not configured"
        )

    if not investigation_manager:
        raise HTTPException(status_code=500, detail="Server not initialized")

    # Get incident details
    try:
        incident = await pagerduty_adapter.get_incident(incident_id)
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Audit log
    audit = get_audit_logger()
    audit.log_investigation(
        user=current_user.get("user", "unknown"),
        issue=incident.title,
        namespace="default",
    )

    # Acknowledge the incident to show we're working on it
    try:
        await pagerduty_adapter.acknowledge_incident(incident_id)
    except Exception:
        pass  # Non-fatal, continue with investigation

    # Run investigation
    result = await pagerduty_adapter.auto_investigate_incident(
        incident=incident,
        investigation_manager=investigation_manager,
    )

    return {
        "status": "ok",
        "investigation_id": result["investigation_id"],
        "incident_id": incident_id,
    }


# =============================================================================
# Remediation Management (Auto-Remediation with Approval Workflows)
# =============================================================================

from opensre_core.remediation.manager import get_remediation_manager


class QueueActionRequest(BaseModel):
    """Request to queue an action for remediation."""
    investigation_id: str
    action_id: str
    command: str
    description: str = ""
    risk: str = "medium"  # low, medium, high


class RollbackRequest(BaseModel):
    """Request to rollback an action."""
    reason: str = ""


@api_router.get("/remediation/actions")
async def list_remediation_actions(
    status: str | None = None,
    investigation_id: str | None = None,
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
):
    """
    List pending and recent remediation actions.

    Args:
        status: Filter by status (pending, completed, failed, etc.)
        investigation_id: Filter by investigation
        limit: Maximum number of actions to return
    """
    manager = get_remediation_manager()

    # Get pending actions
    pending = [a.to_dict() for a in manager.get_pending()]

    # Get recent history
    recent = [a.to_dict() for a in manager.get_recent(limit)]

    # Apply filters
    if status:
        pending = [a for a in pending if a["status"] == status]
        recent = [a for a in recent if a["status"] == status]

    if investigation_id:
        pending = [a for a in pending if a["investigation_id"] == investigation_id]
        recent = [a for a in recent if a["investigation_id"] == investigation_id]

    return {
        "pending": pending,
        "recent": recent[:limit],
        "stats": manager.get_stats(),
    }


@api_router.get("/remediation/actions/{action_id}")
async def get_remediation_action(
    action_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get details of a specific remediation action."""
    manager = get_remediation_manager()
    action = manager.get_action(action_id)

    if not action:
        raise HTTPException(status_code=404, detail="Action not found")

    return action.to_dict()


@api_router.post("/remediation/actions/{action_id}/approve")
async def approve_remediation_action(
    action_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Approve a pending remediation action and execute it.

    Requires APPROVE_ACTIONS permission.
    """
    # Check permission
    if not check_permission(current_user.get("roles", []), Permission.APPROVE_ACTIONS):
        audit = get_audit_logger()
        audit.log_permission_denied(
            user=current_user.get("user", "unknown"),
            action=f"approve remediation action {action_id}",
            required_permission=Permission.APPROVE_ACTIONS.value,
        )
        raise HTTPException(status_code=403, detail="Permission denied: requires approve:actions")

    manager = get_remediation_manager()
    username = current_user.get("user", "unknown")

    try:
        # Approve
        await manager.approve(action_id, username)

        # Execute
        result = await manager.execute(action_id)

        # Notify WebSocket clients
        await broadcast_update({
            "type": "remediation_executed",
            "action_id": action_id,
            "status": result.status.value,
            "result": result.result,
            "error": result.error,
        })

        return result.to_dict()

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/remediation/actions/{action_id}/reject")
async def reject_remediation_action(
    action_id: str,
    reason: str = "",
    current_user: dict = Depends(get_current_user),
):
    """
    Reject a pending remediation action.

    Any authenticated user can reject actions.
    """
    manager = get_remediation_manager()
    username = current_user.get("user", "unknown")

    try:
        result = await manager.reject(action_id, username, reason)

        # Notify WebSocket clients
        await broadcast_update({
            "type": "remediation_rejected",
            "action_id": action_id,
            "rejected_by": username,
            "reason": reason,
        })

        return result.to_dict()

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@api_router.post("/remediation/actions/{action_id}/rollback")
async def rollback_remediation_action(
    action_id: str,
    request: RollbackRequest | None = None,
    current_user: dict = Depends(get_current_user),
):
    """
    Rollback a completed remediation action.

    Only actions with a rollback command can be rolled back.
    Requires APPROVE_ACTIONS permission.
    """
    # Check permission
    if not check_permission(current_user.get("roles", []), Permission.APPROVE_ACTIONS):
        audit = get_audit_logger()
        audit.log_permission_denied(
            user=current_user.get("user", "unknown"),
            action=f"rollback remediation action {action_id}",
            required_permission=Permission.APPROVE_ACTIONS.value,
        )
        raise HTTPException(status_code=403, detail="Permission denied: requires approve:actions")

    manager = get_remediation_manager()
    username = current_user.get("user", "unknown")

    # Check if action can be rolled back
    action = manager.get_action(action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")

    if not action.rollback_command:
        raise HTTPException(
            status_code=400,
            detail="This action cannot be rolled back (no rollback command available)"
        )

    try:
        result = await manager.rollback(action_id, username)

        # Notify WebSocket clients
        await broadcast_update({
            "type": "remediation_rollback",
            "action_id": action_id,
            "user": username,
            "result": result,
        })

        return {
            "status": "rolled_back",
            "action_id": action_id,
            "result": result,
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=f"Rollback failed: {e}")


@api_router.get("/remediation/stats")
async def get_remediation_stats(
    current_user: dict = Depends(get_current_user),
):
    """Get remediation statistics."""
    manager = get_remediation_manager()
    return manager.get_stats()


# Create app instance for uvicorn
app = create_app()
