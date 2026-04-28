"""
Dashboard Routes - Main landing page with system overview.

Shows:
- System status (config, LLM, connectors)
- Recent agent activity
- Quick actions
- Key metrics
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from autosre.config import settings
from autosre.foundation.context_store import ContextStore


router = APIRouter()


def get_templates(request: Request):
    """Get templates from app state."""
    return request.app.state.templates


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page."""
    templates = get_templates(request)
    store = ContextStore()
    
    # Gather status information
    status = {
        "config": {
            "llm_provider": settings.llm_provider,
            "llm_model": _get_active_model(),
            "status": "configured" if _is_llm_configured() else "not_configured",
        },
        "connectors": {
            "prometheus": {
                "url": settings.prometheus_url,
                "status": "configured",
            },
            "slack": {
                "enabled": settings.slack_enabled,
                "status": "connected" if settings.slack_enabled else "disabled",
            },
            "pagerduty": {
                "enabled": settings.pagerduty_api_key is not None,
                "status": "connected" if settings.pagerduty_api_key else "disabled",
            },
        },
        "context_store": {
            "services": len(store.list_services()),
            "alerts": len(store.get_firing_alerts()),
            "changes_24h": len(store.get_recent_changes(hours=24)),
            "runbooks": len(store.find_runbook()),
        },
    }
    
    # Get recent activity
    recent_incidents = store.get_open_incidents()[:5]
    recent_changes = store.get_recent_changes(hours=24, limit=5)
    firing_alerts = store.get_firing_alerts()[:5]
    
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "status": status,
            "recent_incidents": recent_incidents,
            "recent_changes": recent_changes,
            "firing_alerts": firing_alerts,
            "now": datetime.now(timezone.utc),
        }
    )


@router.get("/status", response_class=HTMLResponse)
async def status_cards(request: Request):
    """HTMX endpoint for refreshing status cards."""
    templates = get_templates(request)
    store = ContextStore()
    
    status = {
        "config": {
            "llm_provider": settings.llm_provider,
            "llm_model": _get_active_model(),
            "status": "configured" if _is_llm_configured() else "not_configured",
        },
        "context_store": {
            "services": len(store.list_services()),
            "alerts": len(store.get_firing_alerts()),
            "changes_24h": len(store.get_recent_changes(hours=24)),
            "runbooks": len(store.find_runbook()),
        },
    }
    
    return templates.TemplateResponse(
        "partials/status_cards.html",
        {"request": request, "status": status}
    )


@router.get("/activity", response_class=HTMLResponse)
async def activity_feed(request: Request):
    """HTMX endpoint for refreshing activity feed."""
    templates = get_templates(request)
    store = ContextStore()
    
    recent_incidents = store.get_open_incidents()[:5]
    recent_changes = store.get_recent_changes(hours=24, limit=5)
    firing_alerts = store.get_firing_alerts()[:5]
    
    return templates.TemplateResponse(
        "partials/activity_feed.html",
        {
            "request": request,
            "recent_incidents": recent_incidents,
            "recent_changes": recent_changes,
            "firing_alerts": firing_alerts,
        }
    )


def _get_active_model() -> str:
    """Get the currently active model name."""
    if settings.llm_provider == "ollama":
        return settings.ollama_model
    elif settings.llm_provider == "openai":
        return settings.openai_model
    elif settings.llm_provider == "anthropic":
        return settings.anthropic_model
    elif settings.llm_provider == "azure":
        return settings.azure_openai_deployment
    return "unknown"


def _is_llm_configured() -> bool:
    """Check if LLM is properly configured."""
    if settings.llm_provider == "ollama":
        return bool(settings.ollama_host)
    elif settings.llm_provider == "openai":
        return bool(settings.openai_api_key)
    elif settings.llm_provider == "anthropic":
        return bool(settings.anthropic_api_key)
    elif settings.llm_provider == "azure":
        return bool(settings.azure_openai_api_key and settings.azure_openai_endpoint)
    return False
