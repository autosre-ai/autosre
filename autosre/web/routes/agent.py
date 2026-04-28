"""
Agent Routes - Monitor and manage the AI SRE agent.

Provides:
- Config view/edit
- Run history
- Live logs (if running)
- Manual analysis trigger
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Request, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from autosre.config import settings
from autosre.foundation.context_store import ContextStore


router = APIRouter()


def get_templates(request: Request):
    """Get templates from app state."""
    return request.app.state.templates


# Agent state (would be in Redis/DB in production)
_agent_state = {
    "status": "stopped",
    "started_at": None,
    "last_check": None,
    "iterations": 0,
    "logs": [],
}


@router.get("/", response_class=HTMLResponse)
async def agent_page(request: Request):
    """Main agent page."""
    templates = get_templates(request)
    store = ContextStore()
    
    # Get config
    config = {
        "llm": {
            "provider": settings.llm_provider,
            "model": _get_active_model(),
            "configured": _is_llm_configured(),
        },
        "behavior": {
            "require_approval": settings.require_approval,
            "auto_approve_low_risk": settings.auto_approve_low_risk,
            "confidence_threshold": settings.confidence_threshold,
            "max_iterations": settings.max_iterations,
            "timeout_seconds": settings.timeout_seconds,
        },
        "integrations": {
            "prometheus_url": settings.prometheus_url,
            "slack_enabled": settings.slack_enabled,
            "pagerduty_enabled": settings.pagerduty_api_key is not None,
            "mcp_enabled": settings.mcp_enabled,
        },
    }
    
    # Get recent incidents (agent history)
    incidents = store.get_open_incidents()
    
    return templates.TemplateResponse(
        "agent.html",
        {
            "request": request,
            "config": config,
            "agent_state": _agent_state,
            "incidents": incidents[:10],
            "logs": _agent_state["logs"][-50:],
        }
    )


@router.get("/config", response_class=HTMLResponse)
async def config_panel(request: Request):
    """HTMX endpoint for config panel."""
    templates = get_templates(request)
    
    config = {
        "llm": {
            "provider": settings.llm_provider,
            "model": _get_active_model(),
            "configured": _is_llm_configured(),
        },
        "behavior": {
            "require_approval": settings.require_approval,
            "auto_approve_low_risk": settings.auto_approve_low_risk,
            "confidence_threshold": settings.confidence_threshold,
            "max_iterations": settings.max_iterations,
            "timeout_seconds": settings.timeout_seconds,
        },
        "integrations": {
            "prometheus_url": settings.prometheus_url,
            "slack_enabled": settings.slack_enabled,
            "pagerduty_enabled": settings.pagerduty_api_key is not None,
            "mcp_enabled": settings.mcp_enabled,
        },
    }
    
    return templates.TemplateResponse(
        "partials/agent_config.html",
        {"request": request, "config": config}
    )


@router.get("/history", response_class=HTMLResponse)
async def history_panel(request: Request, limit: int = 20):
    """HTMX endpoint for history panel."""
    templates = get_templates(request)
    store = ContextStore()
    
    incidents = store.get_open_incidents()
    
    return templates.TemplateResponse(
        "partials/agent_history.html",
        {"request": request, "incidents": incidents[:limit]}
    )


@router.get("/logs", response_class=HTMLResponse)
async def logs_panel(request: Request, limit: int = 50):
    """HTMX endpoint for logs panel."""
    templates = get_templates(request)
    
    logs = _agent_state["logs"][-limit:]
    
    return templates.TemplateResponse(
        "partials/agent_logs.html",
        {
            "request": request,
            "logs": logs,
            "agent_state": _agent_state,
        }
    )


@router.get("/status", response_class=HTMLResponse)
async def status_panel(request: Request):
    """HTMX endpoint for agent status."""
    templates = get_templates(request)
    
    return templates.TemplateResponse(
        "partials/agent_status.html",
        {"request": request, "agent_state": _agent_state}
    )


@router.post("/start")
async def start_agent(background_tasks: BackgroundTasks):
    """Start the agent (background task)."""
    if _agent_state["status"] == "running":
        return {"status": "already_running"}
    
    _agent_state["status"] = "running"
    _agent_state["started_at"] = datetime.now(timezone.utc).isoformat()
    _agent_state["iterations"] = 0
    _add_log("Agent started")
    
    # In production, would start actual agent process
    # background_tasks.add_task(run_agent_loop)
    
    return {"status": "started"}


@router.post("/stop")
async def stop_agent():
    """Stop the agent."""
    if _agent_state["status"] != "running":
        return {"status": "not_running"}
    
    _agent_state["status"] = "stopped"
    _add_log("Agent stopped")
    
    return {"status": "stopped"}


class AnalyzeRequest(BaseModel):
    """Manual analysis request."""
    alert_name: Optional[str] = None
    service_name: Optional[str] = None


@router.post("/analyze", response_class=HTMLResponse)
async def analyze(
    request: Request,
    alert_name: Optional[str] = Form(None),
    service_name: Optional[str] = Form(None),
):
    """Trigger manual analysis."""
    templates = get_templates(request)
    store = ContextStore()
    
    if not alert_name and not service_name:
        return templates.TemplateResponse(
            "partials/analyze_error.html",
            {"request": request, "error": "Please provide alert name or service name"}
        )
    
    # Build context for analysis
    context = {
        "alert_name": alert_name,
        "service_name": service_name,
        "services": [],
        "changes": [],
        "runbooks": [],
    }
    
    if service_name:
        service = store.get_service(service_name)
        if service:
            context["services"].append(service.model_dump())
        changes = store.get_recent_changes(service_name=service_name, hours=24)
        context["changes"] = [c.model_dump() for c in changes]
        runbooks = store.find_runbook(service_name=service_name)
        context["runbooks"] = [r.model_dump() for r in runbooks]
    
    # Mock analysis result (would call LLM in production)
    analysis = {
        "root_cause": "Analysis requires LLM integration",
        "confidence": 0.0,
        "affected_services": [service_name] if service_name else [],
        "related_changes": len(context["changes"]),
        "matching_runbooks": len(context["runbooks"]),
        "suggested_actions": [
            "Check recent deployments",
            "Review resource utilization",
            "Examine application logs",
        ],
    }
    
    _add_log(f"Manual analysis triggered: {alert_name or service_name}")
    
    return templates.TemplateResponse(
        "partials/analyze_result.html",
        {
            "request": request,
            "context": context,
            "analysis": analysis,
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


def _add_log(message: str):
    """Add a log entry."""
    timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
    _agent_state["logs"].append({
        "time": timestamp,
        "message": message,
    })
    # Keep only last 200 logs
    if len(_agent_state["logs"]) > 200:
        _agent_state["logs"] = _agent_state["logs"][-200:]
