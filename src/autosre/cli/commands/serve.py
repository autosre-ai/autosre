"""
AutoSRE Webhook Server - Alert Receiver for Proactive Investigations.

Provides a webhook server that:
1. Receives Prometheus/Alertmanager webhooks
2. Auto-starts investigations for incoming alerts
3. Stores results and optionally sends notifications
"""

import hashlib
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, UTC
from typing import Optional
from uuid import uuid4

import typer
from pydantic import BaseModel, Field
from rich.console import Console

logger = logging.getLogger(__name__)
console = Console()

app = typer.Typer(name="serve", help="Webhook server for alert-driven investigations")


# =============================================================================
# Alertmanager Webhook Models
# =============================================================================


class AlertmanagerAlert(BaseModel):
    """Single alert from Alertmanager webhook payload."""
    
    status: str  # "firing" or "resolved"
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)
    startsAt: str
    endsAt: Optional[str] = None
    generatorURL: Optional[str] = None
    fingerprint: Optional[str] = None
    
    @property
    def alertname(self) -> str:
        return self.labels.get("alertname", "unknown")
    
    @property
    def service(self) -> Optional[str]:
        """Extract service name from labels."""
        return (
            self.labels.get("service") or 
            self.labels.get("job") or 
            self.labels.get("app") or
            self.labels.get("deployment")
        )
    
    @property
    def severity(self) -> str:
        return self.labels.get("severity", "warning")
    
    @property
    def description(self) -> str:
        return self.annotations.get("description") or self.annotations.get("summary", "")


class AlertmanagerWebhook(BaseModel):
    """Full Alertmanager webhook payload."""
    
    version: str = "4"
    groupKey: Optional[str] = None
    truncatedAlerts: int = 0
    status: str  # "firing" or "resolved"
    receiver: str = ""
    groupLabels: dict[str, str] = Field(default_factory=dict)
    commonLabels: dict[str, str] = Field(default_factory=dict)
    commonAnnotations: dict[str, str] = Field(default_factory=dict)
    externalURL: Optional[str] = None
    alerts: list[AlertmanagerAlert] = Field(default_factory=list)


class InvestigationResult(BaseModel):
    """Result of an auto-started investigation."""
    
    investigation_id: str
    alert_fingerprint: str
    alertname: str
    service: Optional[str]
    severity: str
    status: str  # "pending", "running", "completed", "failed"
    started_at: datetime
    completed_at: Optional[datetime] = None
    root_cause: Optional[str] = None
    recommendations: list[str] = Field(default_factory=list)
    error: Optional[str] = None


class WebhookResponse(BaseModel):
    """Response to webhook caller."""
    
    status: str
    message: str
    investigations_started: int = 0
    investigation_ids: list[str] = Field(default_factory=list)


# =============================================================================
# Investigation Store (in-memory for now)
# =============================================================================


class InvestigationStore:
    """In-memory store for investigations started by webhooks."""
    
    def __init__(self):
        self._investigations: dict[str, InvestigationResult] = {}
        self._dedup_window: dict[str, datetime] = {}  # fingerprint -> last seen
        self._dedup_seconds = 300  # 5 minute dedup window
    
    def should_investigate(self, fingerprint: str) -> bool:
        """Check if we should start an investigation (deduplication)."""
        now = datetime.now(UTC)
        last_seen = self._dedup_window.get(fingerprint)
        
        if last_seen:
            elapsed = (now - last_seen).total_seconds()
            if elapsed < self._dedup_seconds:
                logger.info(f"Skipping duplicate alert {fingerprint} (last seen {elapsed:.0f}s ago)")
                return False
        
        self._dedup_window[fingerprint] = now
        return True
    
    def add(self, result: InvestigationResult) -> None:
        self._investigations[result.investigation_id] = result
    
    def get(self, investigation_id: str) -> Optional[InvestigationResult]:
        return self._investigations.get(investigation_id)
    
    def update(self, investigation_id: str, **kwargs) -> None:
        if inv := self._investigations.get(investigation_id):
            for key, value in kwargs.items():
                if hasattr(inv, key):
                    setattr(inv, key, value)
    
    def list_recent(self, limit: int = 50) -> list[InvestigationResult]:
        sorted_invs = sorted(
            self._investigations.values(),
            key=lambda x: x.started_at,
            reverse=True
        )
        return sorted_invs[:limit]
    
    def get_stats(self) -> dict:
        invs = list(self._investigations.values())
        return {
            "total": len(invs),
            "pending": sum(1 for i in invs if i.status == "pending"),
            "running": sum(1 for i in invs if i.status == "running"),
            "completed": sum(1 for i in invs if i.status == "completed"),
            "failed": sum(1 for i in invs if i.status == "failed"),
        }


# Global store instance
_store = InvestigationStore()


# =============================================================================
# FastAPI Application
# =============================================================================


def create_fastapi_app(
    auto_investigate: bool = True,
    notification_webhook: Optional[str] = None,
):
    """Create the FastAPI application for the webhook server."""
    from fastapi import FastAPI, HTTPException, BackgroundTasks
    
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Startup and shutdown events."""
        logger.info("AutoSRE Webhook Server starting up")
        yield
        logger.info("AutoSRE Webhook Server shutting down")
    
    fastapi_app = FastAPI(
        title="AutoSRE Webhook Server",
        description="Receives Prometheus/Alertmanager webhooks and auto-starts investigations",
        version="0.2.0",
        lifespan=lifespan,
    )
    
    # Store config in app state
    fastapi_app.state.auto_investigate = auto_investigate
    fastapi_app.state.notification_webhook = notification_webhook
    
    @fastapi_app.get("/health")
    async def health_check():
        """Health check endpoint for load balancers and monitoring."""
        return {
            "status": "healthy",
            "service": "autosre-webhook-server",
            "timestamp": datetime.now(UTC).isoformat(),
            "investigations": _store.get_stats(),
        }
    
    @fastapi_app.get("/readiness")
    async def readiness_check():
        """Readiness probe for Kubernetes."""
        return {"status": "ready"}
    
    @fastapi_app.get("/liveness")
    async def liveness_check():
        """Liveness probe for Kubernetes."""
        return {"status": "alive"}
    
    @fastapi_app.post("/webhook/alertmanager", response_model=WebhookResponse)
    async def alertmanager_webhook(
        webhook: AlertmanagerWebhook,
        background_tasks: BackgroundTasks,
    ):
        """
        Receive Alertmanager webhook and start investigations.
        
        This endpoint accepts the standard Alertmanager webhook format.
        For firing alerts, it will:
        1. Deduplicate alerts (5 min window by fingerprint)
        2. Create investigation records
        3. Optionally auto-start investigations in background
        4. Return immediately with investigation IDs
        
        Configure in Alertmanager:
        ```yaml
        receivers:
          - name: autosre
            webhook_configs:
              - url: http://autosre:8080/webhook/alertmanager
                send_resolved: true
        ```
        """
        logger.info(f"Received webhook: status={webhook.status}, alerts={len(webhook.alerts)}")
        
        investigation_ids = []
        
        for alert in webhook.alerts:
            # Only investigate firing alerts
            if alert.status != "firing":
                logger.debug(f"Skipping resolved alert: {alert.alertname}")
                continue
            
            # Generate fingerprint if not provided
            fingerprint = alert.fingerprint or hashlib.md5(
                json.dumps(alert.labels, sort_keys=True).encode()
            ).hexdigest()[:16]
            
            # Deduplication check
            if not _store.should_investigate(fingerprint):
                continue
            
            # Create investigation record
            investigation_id = str(uuid4())[:8]
            result = InvestigationResult(
                investigation_id=investigation_id,
                alert_fingerprint=fingerprint,
                alertname=alert.alertname,
                service=alert.service,
                severity=alert.severity,
                status="pending",
                started_at=datetime.now(UTC),
            )
            _store.add(result)
            investigation_ids.append(investigation_id)
            
            logger.info(
                f"Created investigation {investigation_id} for alert "
                f"{alert.alertname} (service={alert.service}, severity={alert.severity})"
            )
            
            # Start background investigation if enabled
            if fastapi_app.state.auto_investigate:
                background_tasks.add_task(
                    run_investigation_background,
                    investigation_id=investigation_id,
                    alert=alert,
                    notification_webhook=fastapi_app.state.notification_webhook,
                )
        
        return WebhookResponse(
            status="accepted",
            message=f"Processed {len(webhook.alerts)} alerts, started {len(investigation_ids)} investigations",
            investigations_started=len(investigation_ids),
            investigation_ids=investigation_ids,
        )
    
    @fastapi_app.get("/investigations")
    async def list_investigations(limit: int = 50):
        """List recent investigations."""
        return {
            "investigations": [inv.model_dump() for inv in _store.list_recent(limit)],
            "stats": _store.get_stats(),
        }
    
    @fastapi_app.get("/investigations/{investigation_id}")
    async def get_investigation(investigation_id: str):
        """Get a specific investigation by ID."""
        inv = _store.get(investigation_id)
        if not inv:
            raise HTTPException(status_code=404, detail="Investigation not found")
        return inv.model_dump()
    
    @fastapi_app.post("/investigate")
    async def manual_investigate(
        background_tasks: BackgroundTasks,
        alert_description: str,
        service: Optional[str] = None,
        severity: str = "high",
    ):
        """
        Manually trigger an investigation via API.
        
        Useful for testing or integrating with systems that don't use Alertmanager.
        """
        investigation_id = str(uuid4())[:8]
        fingerprint = hashlib.md5(
            f"{alert_description}:{service}:{datetime.now(UTC)}".encode()
        ).hexdigest()[:16]
        
        result = InvestigationResult(
            investigation_id=investigation_id,
            alert_fingerprint=fingerprint,
            alertname="manual_investigation",
            service=service,
            severity=severity,
            status="pending",
            started_at=datetime.now(UTC),
        )
        _store.add(result)
        
        # Create a mock alert for the investigation
        mock_alert = AlertmanagerAlert(
            status="firing",
            labels={
                "alertname": "manual_investigation",
                "severity": severity,
            },
            annotations={"description": alert_description},
            startsAt=datetime.now(UTC).isoformat(),
            fingerprint=fingerprint,
        )
        if service:
            mock_alert.labels["service"] = service
        
        if fastapi_app.state.auto_investigate:
            background_tasks.add_task(
                run_investigation_background,
                investigation_id=investigation_id,
                alert=mock_alert,
                notification_webhook=fastapi_app.state.notification_webhook,
            )
        
        return {
            "status": "accepted",
            "investigation_id": investigation_id,
            "message": "Investigation started",
        }
    
    return fastapi_app


async def run_investigation_background(
    investigation_id: str,
    alert: AlertmanagerAlert,
    notification_webhook: Optional[str] = None,
):
    """Run an investigation in the background."""
    
    logger.info(f"Starting background investigation {investigation_id}")
    _store.update(investigation_id, status="running")
    
    try:
        # Import the investigation orchestrator
        from autosre.orchestrator import Orchestrator
        from autosre.config import settings
        
        orchestrator = Orchestrator(settings)
        
        # Create investigation context
        context = {
            "alert": alert.alertname,
            "service": alert.service,
            "severity": alert.severity,
            "description": alert.description,
            "labels": alert.labels,
            "annotations": alert.annotations,
        }
        
        # Start and run investigation
        investigation = await orchestrator.start_investigation(
            alert_id=alert.fingerprint or investigation_id,
            context=context,
        )
        
        result = await orchestrator.run_investigation(investigation.id)
        
        # Update store with results
        _store.update(
            investigation_id,
            status="completed",
            completed_at=datetime.now(UTC),
            root_cause=result.get("triage_result", {}).get("root_cause_hypothesis"),
            recommendations=result.get("triage_result", {}).get("recommended_actions", []),
        )
        
        logger.info(f"Investigation {investigation_id} completed successfully")
        
        # Send notification if configured
        if notification_webhook:
            await send_notification(
                notification_webhook,
                investigation_id=investigation_id,
                alert=alert,
                result=result,
            )
        
    except Exception as e:
        logger.exception(f"Investigation {investigation_id} failed: {e}")
        _store.update(
            investigation_id,
            status="failed",
            completed_at=datetime.now(UTC),
            error=str(e),
        )


async def send_notification(
    webhook_url: str,
    investigation_id: str,
    alert: AlertmanagerAlert,
    result: dict,
):
    """Send notification to configured webhook (e.g., Slack incoming webhook)."""
    import httpx
    
    try:
        payload = {
            "text": f"🔍 AutoSRE Investigation Complete",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"🔍 Investigation: {alert.alertname}",
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Service:* {alert.service or 'Unknown'}"},
                        {"type": "mrkdwn", "text": f"*Severity:* {alert.severity}"},
                        {"type": "mrkdwn", "text": f"*Investigation ID:* {investigation_id}"},
                        {"type": "mrkdwn", "text": f"*Status:* Completed"},
                    ]
                },
            ]
        }
        
        # Add root cause if found
        root_cause = result.get("triage_result", {}).get("root_cause_hypothesis")
        if root_cause:
            payload["blocks"].append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Root Cause:* {root_cause}"}
            })
        
        async with httpx.AsyncClient() as client:
            response = await client.post(webhook_url, json=payload, timeout=10.0)
            response.raise_for_status()
            logger.info(f"Notification sent for investigation {investigation_id}")
            
    except Exception as e:
        logger.warning(f"Failed to send notification: {e}")


# =============================================================================
# CLI Commands
# =============================================================================


@app.command("start")
def start_server(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Host to bind to"),
    port: int = typer.Option(8080, "--port", "-p", help="Port to listen on"),
    auto_investigate: bool = typer.Option(
        True, "--auto-investigate/--no-auto-investigate",
        help="Automatically start investigations for incoming alerts"
    ),
    notification_webhook: Optional[str] = typer.Option(
        None, "--notification-webhook",
        help="Webhook URL to send notifications (e.g., Slack incoming webhook)"
    ),
    workers: int = typer.Option(1, "--workers", "-w", help="Number of worker processes"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload for development"),
    log_level: str = typer.Option("info", "--log-level", help="Log level"),
):
    """
    Start the webhook server for alert-driven investigations.
    
    This server receives Prometheus/Alertmanager webhooks and automatically
    starts investigations for firing alerts.
    
    Examples:
        autosre serve start
        autosre serve start --port 9090
        autosre serve start --no-auto-investigate  # Just record alerts
        autosre serve start --notification-webhook https://hooks.slack.com/...
    
    Configure Alertmanager to send to this server:
    
        receivers:
          - name: autosre
            webhook_configs:
              - url: http://autosre-server:8080/webhook/alertmanager
                send_resolved: true
    """
    import uvicorn
    from rich.panel import Panel
    
    console.print()
    console.print(Panel.fit(
        f"[bold cyan]🚀 AutoSRE Webhook Server[/bold cyan]\n\n"
        f"Host: {host}\n"
        f"Port: {port}\n"
        f"Auto-investigate: {'[green]enabled[/green]' if auto_investigate else '[yellow]disabled[/yellow]'}\n"
        f"Notification webhook: {notification_webhook or '[dim]not configured[/dim]'}\n\n"
        f"[bold]Endpoints:[/bold]\n"
        f"  • Health check: http://{host if host != '0.0.0.0' else 'localhost'}:{port}/health\n"
        f"  • Alertmanager webhook: http://{host if host != '0.0.0.0' else 'localhost'}:{port}/webhook/alertmanager\n"
        f"  • Investigations list: http://{host if host != '0.0.0.0' else 'localhost'}:{port}/investigations\n"
        f"  • API docs: http://{host if host != '0.0.0.0' else 'localhost'}:{port}/docs\n\n"
        f"[dim]Press Ctrl+C to stop[/dim]",
        border_style="cyan"
    ))
    console.print()
    
    # Create app factory for uvicorn
    def create_app():
        return create_fastapi_app(
            auto_investigate=auto_investigate,
            notification_webhook=notification_webhook,
        )
    
    # For reload mode, we need to use a string reference
    # For non-reload, we can use the app directly
    if reload:
        # Use module:factory pattern for reload
        uvicorn.run(
            "autosre.cli.commands.serve:create_fastapi_app",
            host=host,
            port=port,
            reload=reload,
            log_level=log_level,
            factory=True,
        )
    else:
        uvicorn.run(
            create_app(),
            host=host,
            port=port,
            workers=workers if workers > 1 else None,
            log_level=log_level,
        )


@app.command("status")
def server_status(
    host: str = typer.Option("localhost", "--host", "-h", help="Server host"),
    port: int = typer.Option(8080, "--port", "-p", help="Server port"),
):
    """Check if the webhook server is running."""
    import httpx
    
    url = f"http://{host}:{port}/health"
    
    try:
        response = httpx.get(url, timeout=2.0)
        if response.status_code == 200:
            data = response.json()
            stats = data.get("investigations", {})
            
            console.print(f"[green]✓[/green] Webhook server is running at http://{host}:{port}")
            console.print()
            console.print("[bold]Investigation Stats:[/bold]")
            console.print(f"  Total:     {stats.get('total', 0)}")
            console.print(f"  Pending:   {stats.get('pending', 0)}")
            console.print(f"  Running:   {stats.get('running', 0)}")
            console.print(f"  Completed: {stats.get('completed', 0)}")
            console.print(f"  Failed:    {stats.get('failed', 0)}")
        else:
            console.print(f"[yellow]⚠[/yellow] Server responded with status {response.status_code}")
    except httpx.ConnectError:
        console.print(f"[red]✗[/red] Webhook server is not running")
        console.print(f"[dim]Start it with: autosre serve start[/dim]")
    except Exception as e:
        console.print(f"[red]✗[/red] Error checking status: {e}")


@app.command("test-webhook")
def test_webhook(
    host: str = typer.Option("localhost", "--host", "-h", help="Server host"),
    port: int = typer.Option(8080, "--port", "-p", help="Server port"),
    alertname: str = typer.Option("HighErrorRate", "--alert", "-a", help="Alert name"),
    service: Optional[str] = typer.Option(None, "--service", "-s", help="Service name"),
    severity: str = typer.Option("critical", "--severity", help="Alert severity"),
):
    """
    Send a test webhook to the server.
    
    Useful for testing the webhook endpoint without a real Alertmanager.
    
    Examples:
        autosre serve test-webhook
        autosre serve test-webhook --alert HighLatency --service api-gateway
    """
    import httpx
    
    url = f"http://{host}:{port}/webhook/alertmanager"
    
    # Create test webhook payload
    payload = AlertmanagerWebhook(
        version="4",
        status="firing",
        receiver="autosre",
        groupLabels={"alertname": alertname},
        commonLabels={"alertname": alertname, "severity": severity},
        alerts=[
            AlertmanagerAlert(
                status="firing",
                labels={
                    "alertname": alertname,
                    "severity": severity,
                    **({"service": service} if service else {}),
                },
                annotations={
                    "summary": f"Test alert: {alertname}",
                    "description": f"This is a test webhook for {alertname}",
                },
                startsAt=datetime.now(UTC).isoformat(),
            )
        ],
    )
    
    console.print(f"[bold]Sending test webhook to {url}[/bold]")
    console.print()
    
    try:
        response = httpx.post(
            url,
            json=payload.model_dump(),
            timeout=10.0,
        )
        
        if response.status_code == 200:
            data = response.json()
            console.print(f"[green]✓[/green] Webhook accepted")
            console.print(f"  Status: {data.get('status')}")
            console.print(f"  Message: {data.get('message')}")
            console.print(f"  Investigations started: {data.get('investigations_started')}")
            if data.get('investigation_ids'):
                console.print(f"  Investigation IDs: {', '.join(data['investigation_ids'])}")
        else:
            console.print(f"[red]✗[/red] Webhook rejected: {response.status_code}")
            console.print(f"  Response: {response.text}")
    except httpx.ConnectError:
        console.print(f"[red]✗[/red] Could not connect to server")
        console.print(f"[dim]Start the server with: autosre serve start[/dim]")
    except Exception as e:
        console.print(f"[red]✗[/red] Error: {e}")
