"""
Context Routes - Browse the context store.

Provides:
- Services table
- Recent changes
- Firing alerts
- Runbooks
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse

from autosre.foundation.context_store import ContextStore


router = APIRouter()


def get_templates(request: Request):
    """Get templates from app state."""
    return request.app.state.templates


@router.get("/", response_class=HTMLResponse)
async def context_page(request: Request, tab: str = "services"):
    """Main context page."""
    templates = get_templates(request)
    store = ContextStore()
    
    # Get all context data
    services = store.list_services()
    changes = store.get_recent_changes(hours=72, limit=50)
    alerts = store.get_firing_alerts()
    runbooks = store.find_runbook()
    
    # Summary counts
    summary = {
        "services": len(services),
        "changes": len(changes),
        "alerts": len(alerts),
        "runbooks": len(runbooks),
    }
    
    return templates.TemplateResponse(
            request=request,
            name="context.html",
            context={"tab": tab,
            "services": services,
            "changes": changes,
            "alerts": alerts,
            "runbooks": runbooks,
            "summary": summary}
        )


@router.get("/services", response_class=HTMLResponse)
async def services_table(
    request: Request,
    namespace: Optional[str] = None,
    cluster: Optional[str] = None,
):
    """HTMX endpoint for services table."""
    templates = get_templates(request)
    store = ContextStore()
    
    services = store.list_services(namespace=namespace, cluster=cluster)
    
    return templates.TemplateResponse(
            request=request,
            name="partials/services_table.html",
            context={"services": services}
        )


@router.get("/services/{service_name}", response_class=HTMLResponse)
async def service_detail(request: Request, service_name: str):
    """Service detail view."""
    templates = get_templates(request)
    store = ContextStore()
    
    service = store.get_service(service_name)
    if not service:
        return templates.TemplateResponse(
            request=request,
            name="partials/not_found.html",
            context={"entity": "Service", "name": service_name}
        )
    
    ownership = store.get_ownership(service_name)
    changes = store.get_recent_changes(service_name=service_name, hours=168, limit=20)
    runbooks = store.find_runbook(service_name=service_name)
    
    return templates.TemplateResponse(
            request=request,
            name="partials/service_detail.html",
            context={"service": service,
            "ownership": ownership,
            "changes": changes,
            "runbooks": runbooks}
        )


@router.get("/changes", response_class=HTMLResponse)
async def changes_table(
    request: Request,
    service: Optional[str] = None,
    hours: int = 72,
    limit: int = 50,
):
    """HTMX endpoint for changes table."""
    templates = get_templates(request)
    store = ContextStore()
    
    changes = store.get_recent_changes(
        service_name=service,
        hours=hours,
        limit=limit,
    )
    
    return templates.TemplateResponse(
            request=request,
            name="partials/changes_table.html",
            context={"changes": changes}
        )


@router.get("/alerts", response_class=HTMLResponse)
async def alerts_table(request: Request, service: Optional[str] = None):
    """HTMX endpoint for alerts table."""
    templates = get_templates(request)
    store = ContextStore()
    
    alerts = store.get_firing_alerts()
    
    # Filter by service if specified
    if service:
        alerts = [a for a in alerts if a.service_name == service]
    
    return templates.TemplateResponse(
            request=request,
            name="partials/alerts_table.html",
            context={"alerts": alerts}
        )


@router.get("/runbooks", response_class=HTMLResponse)
async def runbooks_table(request: Request, service: Optional[str] = None):
    """HTMX endpoint for runbooks table."""
    templates = get_templates(request)
    store = ContextStore()
    
    runbooks = store.find_runbook(service_name=service)
    
    return templates.TemplateResponse(
            request=request,
            name="partials/runbooks_table.html",
            context={"runbooks": runbooks}
        )


@router.get("/runbooks/{runbook_id}", response_class=HTMLResponse)
async def runbook_detail(request: Request, runbook_id: str):
    """Runbook detail view."""
    templates = get_templates(request)
    store = ContextStore()
    
    runbooks = store.find_runbook()
    runbook = next((r for r in runbooks if r.id == runbook_id), None)
    
    if not runbook:
        return templates.TemplateResponse(
            request=request,
            name="partials/not_found.html",
            context={"entity": "Runbook", "name": runbook_id}
        )
    
    return templates.TemplateResponse(
            request=request,
            name="partials/runbook_detail.html",
            context={"runbook": runbook}
        )


# API endpoints
@router.get("/api/services")
async def api_services(namespace: Optional[str] = None, cluster: Optional[str] = None):
    """API: List services."""
    store = ContextStore()
    services = store.list_services(namespace=namespace, cluster=cluster)
    return {"services": [s.model_dump() for s in services]}


@router.get("/api/changes")
async def api_changes(service: Optional[str] = None, hours: int = 72, limit: int = 50):
    """API: List changes."""
    store = ContextStore()
    changes = store.get_recent_changes(service_name=service, hours=hours, limit=limit)
    return {"changes": [c.model_dump() for c in changes]}


@router.get("/api/alerts")
async def api_alerts():
    """API: List firing alerts."""
    store = ContextStore()
    alerts = store.get_firing_alerts()
    return {"alerts": [a.model_dump() for a in alerts]}


@router.get("/api/runbooks")
async def api_runbooks(service: Optional[str] = None):
    """API: List runbooks."""
    store = ContextStore()
    runbooks = store.find_runbook(service_name=service)
    return {"runbooks": [r.model_dump() for r in runbooks]}
