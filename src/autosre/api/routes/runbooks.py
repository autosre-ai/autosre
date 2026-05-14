"""
API routes for runbook automation.

Provides REST endpoints for:
- Runbook management
- Execution
- Variables
- Templates
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File
from pydantic import BaseModel, Field

from autosre.utils.logging import get_logger
from autosre.runbooks import RunbookParser, ParseError
from autosre.runbooks.models import (
    Runbook,
    RunbookExecution,
    ExecutionStatus,
    StepType,
)
from autosre.runbooks.executor import RunbookExecutor, StepExecutor

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/runbooks", tags=["runbooks"])


# ============================================================================
# Request/Response Models
# ============================================================================

class VariableInput(BaseModel):
    """Variable input for runbook execution."""
    
    name: str
    value: Any


class CreateRunbookRequest(BaseModel):
    """Request to create a runbook."""
    
    name: str
    description: str = ""
    content: str = Field(..., description="YAML or Markdown content")
    format: str = Field("yaml", pattern="^(yaml|markdown)$")
    tags: list[str] = Field(default_factory=list)


class ExecuteRunbookRequest(BaseModel):
    """Request to execute a runbook."""
    
    variables: list[VariableInput] = Field(default_factory=list)
    dry_run: bool = False
    triggered_by: str = "api"
    incident_id: str | None = None


class RunbookResponse(BaseModel):
    """Response with runbook details."""
    
    id: str
    name: str
    description: str
    version: str
    step_count: int
    variable_count: int
    requires_approval: bool
    tags: list[str]
    created_at: datetime


class RunbookDetailResponse(BaseModel):
    """Detailed runbook response."""
    
    id: str
    name: str
    description: str
    version: str
    variables: list[dict[str, Any]]
    steps: list[dict[str, Any]]
    triggers: list[dict[str, Any]]
    requires_approval: bool
    tags: list[str]


class ExecutionResponse(BaseModel):
    """Response with execution details."""
    
    id: UUID
    runbook_id: str
    runbook_name: str
    status: ExecutionStatus
    current_step_id: str | None
    current_step_index: int
    total_steps: int
    progress_percent: float
    dry_run: bool
    started_at: datetime
    completed_at: datetime | None
    error: str | None = None


class StepResultResponse(BaseModel):
    """Response with step execution result."""
    
    step_id: str
    step_name: str
    status: ExecutionStatus
    output: Any = None
    error: str | None = None
    duration_seconds: float
    attempts: int


# ============================================================================
# In-Memory Storage (would be database in production)
# ============================================================================

_runbooks: dict[str, Runbook] = {}
_executions: dict[UUID, RunbookExecution] = {}


# ============================================================================
# Dependencies
# ============================================================================

def get_parser() -> RunbookParser:
    """Get runbook parser instance."""
    return RunbookParser()


def get_executor() -> RunbookExecutor:
    """Get runbook executor instance."""
    return RunbookExecutor()


# ============================================================================
# Runbook Management Endpoints
# ============================================================================

@router.post("/", response_model=RunbookResponse)
async def create_runbook(
    request: CreateRunbookRequest,
    parser: RunbookParser = Depends(get_parser),
):
    """Create a new runbook from YAML or Markdown content."""
    try:
        if request.format == "yaml":
            runbook = parser.parse_yaml(request.content)
        else:
            runbook = parser.parse_markdown(request.content)
        
        # Validate
        errors = parser.validate_runbook(runbook)
        if errors:
            raise HTTPException(status_code=400, detail={"errors": errors})
        
        # Override name if provided
        if request.name:
            runbook.name = request.name
        if request.description:
            runbook.description = request.description
        if request.tags:
            runbook.tags = request.tags
        
        # Store
        _runbooks[runbook.id] = runbook
        
        return RunbookResponse(
            id=runbook.id,
            name=runbook.name,
            description=runbook.description,
            version=runbook.version,
            step_count=len(runbook.steps),
            variable_count=len(runbook.variables),
            requires_approval=runbook.requires_approval,
            tags=runbook.tags,
            created_at=runbook.created_at,
        )
        
    except ParseError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/upload", response_model=RunbookResponse)
async def upload_runbook(
    file: UploadFile = File(...),
    parser: RunbookParser = Depends(get_parser),
):
    """Upload a runbook file."""
    content = await file.read()
    content_str = content.decode("utf-8")
    
    # Detect format from filename
    if file.filename.endswith((".yaml", ".yml")):
        runbook = parser.parse_yaml(content_str)
    elif file.filename.endswith((".md", ".markdown")):
        runbook = parser.parse_markdown(content_str)
    else:
        # Try to auto-detect
        try:
            runbook = parser.parse_yaml(content_str)
        except:
            runbook = parser.parse_markdown(content_str)
    
    errors = parser.validate_runbook(runbook)
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})
    
    _runbooks[runbook.id] = runbook
    
    return RunbookResponse(
        id=runbook.id,
        name=runbook.name,
        description=runbook.description,
        version=runbook.version,
        step_count=len(runbook.steps),
        variable_count=len(runbook.variables),
        requires_approval=runbook.requires_approval,
        tags=runbook.tags,
        created_at=runbook.created_at,
    )


@router.get("/", response_model=list[RunbookResponse])
async def list_runbooks(
    tag: str | None = None,
    search: str | None = None,
):
    """List all runbooks."""
    runbooks = list(_runbooks.values())
    
    # Filter by tag
    if tag:
        runbooks = [r for r in runbooks if tag in r.tags]
    
    # Search by name/description
    if search:
        search_lower = search.lower()
        runbooks = [
            r for r in runbooks
            if search_lower in r.name.lower() or search_lower in r.description.lower()
        ]
    
    return [
        RunbookResponse(
            id=r.id,
            name=r.name,
            description=r.description,
            version=r.version,
            step_count=len(r.steps),
            variable_count=len(r.variables),
            requires_approval=r.requires_approval,
            tags=r.tags,
            created_at=r.created_at,
        )
        for r in runbooks
    ]


@router.get("/{runbook_id}", response_model=RunbookDetailResponse)
async def get_runbook(runbook_id: str):
    """Get runbook details."""
    if runbook_id not in _runbooks:
        raise HTTPException(status_code=404, detail="Runbook not found")
    
    runbook = _runbooks[runbook_id]
    
    return RunbookDetailResponse(
        id=runbook.id,
        name=runbook.name,
        description=runbook.description,
        version=runbook.version,
        variables=[
            {
                "name": v.name,
                "type": v.type.value,
                "required": v.required,
                "default": v.default,
                "description": v.description,
            }
            for v in runbook.variables
        ],
        steps=[
            {
                "id": s.id,
                "name": s.name,
                "type": s.type.value,
                "description": s.description,
                "timeout_seconds": s.timeout_seconds,
                "has_condition": s.condition is not None,
                "continue_on_failure": s.continue_on_failure,
            }
            for s in runbook.steps
        ],
        triggers=runbook.triggers,
        requires_approval=runbook.requires_approval,
        tags=runbook.tags,
    )


@router.delete("/{runbook_id}")
async def delete_runbook(runbook_id: str):
    """Delete a runbook."""
    if runbook_id not in _runbooks:
        raise HTTPException(status_code=404, detail="Runbook not found")
    
    del _runbooks[runbook_id]
    
    return {"message": f"Runbook {runbook_id} deleted"}


@router.get("/{runbook_id}/export")
async def export_runbook(
    runbook_id: str,
    format: str = Query("yaml", pattern="^(yaml|markdown)$"),
):
    """Export runbook as YAML or Markdown."""
    if runbook_id not in _runbooks:
        raise HTTPException(status_code=404, detail="Runbook not found")
    
    runbook = _runbooks[runbook_id]
    
    # Simple YAML export
    if format == "yaml":
        import yaml
        data = {
            "name": runbook.name,
            "description": runbook.description,
            "version": runbook.version,
            "variables": [
                {
                    "name": v.name,
                    "type": v.type.value,
                    "default": v.default,
                    "required": v.required,
                }
                for v in runbook.variables
            ],
            "steps": [
                {
                    "id": s.id,
                    "name": s.name,
                    "type": s.type.value,
                    "command": s.command,
                    "parameters": s.parameters,
                }
                for s in runbook.steps
            ],
        }
        return {"content": yaml.dump(data, default_flow_style=False)}
    
    else:
        # Markdown export
        lines = [
            f"# {runbook.name}",
            "",
            runbook.description,
            "",
            "## Variables",
            "",
        ]
        
        for v in runbook.variables:
            lines.append(f"- {v.name}: {v.default or '(required)'}")
        
        lines.extend(["", "## Steps", ""])
        
        for i, s in enumerate(runbook.steps, 1):
            lines.append(f"### {i}. {s.name}")
            if s.command:
                lines.append("```command")
                lines.append(s.command)
                lines.append("```")
            lines.append("")
        
        return {"content": "\n".join(lines)}


# ============================================================================
# Execution Endpoints
# ============================================================================

@router.post("/{runbook_id}/execute", response_model=ExecutionResponse)
async def execute_runbook(
    runbook_id: str,
    request: ExecuteRunbookRequest,
    executor: RunbookExecutor = Depends(get_executor),
):
    """Execute a runbook."""
    if runbook_id not in _runbooks:
        raise HTTPException(status_code=404, detail="Runbook not found")
    
    runbook = _runbooks[runbook_id]
    
    # Build context from variables
    context = {v.name: v.value for v in request.variables}
    
    try:
        execution = await executor.execute(
            runbook=runbook,
            context=context,
            dry_run=request.dry_run,
            triggered_by=request.triggered_by,
            incident_id=request.incident_id,
        )
        
        # Store execution
        _executions[execution.id] = execution
        
        return ExecutionResponse(
            id=execution.id,
            runbook_id=runbook.id,
            runbook_name=runbook.name,
            status=execution.status,
            current_step_id=execution.current_step_id,
            current_step_index=execution.current_step_index,
            total_steps=len(runbook.steps),
            progress_percent=execution.progress_percent,
            dry_run=execution.dry_run,
            started_at=execution.started_at,
            completed_at=execution.completed_at,
            error=execution.error,
        )
        
    except Exception as e:
        logger.error(f"Execution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/executions", response_model=list[ExecutionResponse])
async def list_executions(
    runbook_id: str | None = None,
    status: ExecutionStatus | None = None,
    limit: int = Query(100, ge=1, le=1000),
):
    """List runbook executions."""
    executions = list(_executions.values())
    
    if runbook_id:
        executions = [e for e in executions if e.runbook_id == runbook_id]
    
    if status:
        executions = [e for e in executions if e.status == status]
    
    # Sort by start time, most recent first
    executions.sort(key=lambda e: e.started_at, reverse=True)
    
    return [
        ExecutionResponse(
            id=e.id,
            runbook_id=e.runbook_id,
            runbook_name=e.runbook_name,
            status=e.status,
            current_step_id=e.current_step_id,
            current_step_index=e.current_step_index,
            total_steps=len(_runbooks.get(e.runbook_id, Runbook(name="", steps=[])).steps),
            progress_percent=e.progress_percent,
            dry_run=e.dry_run,
            started_at=e.started_at,
            completed_at=e.completed_at,
            error=e.error,
        )
        for e in executions[:limit]
    ]


@router.get("/executions/{execution_id}", response_model=ExecutionResponse)
async def get_execution(execution_id: UUID):
    """Get execution details."""
    if execution_id not in _executions:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    e = _executions[execution_id]
    
    return ExecutionResponse(
        id=e.id,
        runbook_id=e.runbook_id,
        runbook_name=e.runbook_name,
        status=e.status,
        current_step_id=e.current_step_id,
        current_step_index=e.current_step_index,
        total_steps=len(_runbooks.get(e.runbook_id, Runbook(name="", steps=[])).steps),
        progress_percent=e.progress_percent,
        dry_run=e.dry_run,
        started_at=e.started_at,
        completed_at=e.completed_at,
        error=e.error,
    )


@router.get("/executions/{execution_id}/steps", response_model=list[StepResultResponse])
async def get_execution_steps(execution_id: UUID):
    """Get step results for an execution."""
    if execution_id not in _executions:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    execution = _executions[execution_id]
    
    return [
        StepResultResponse(
            step_id=step_id,
            step_name=result.step_name if hasattr(result, 'step_name') else step_id,
            status=result.status,
            output=result.output,
            error=result.error,
            duration_seconds=result.duration_seconds,
            attempts=result.attempts,
        )
        for step_id, result in execution.step_results.items()
    ]


@router.post("/executions/{execution_id}/cancel")
async def cancel_execution(
    execution_id: UUID,
    executor: RunbookExecutor = Depends(get_executor),
):
    """Cancel a running execution."""
    cancelled = await executor.cancel(execution_id)
    
    if not cancelled:
        raise HTTPException(status_code=404, detail="Execution not found or not running")
    
    return {"message": f"Execution {execution_id} cancelled"}


@router.post("/executions/{execution_id}/resume")
async def resume_execution(
    execution_id: UUID,
    variables: list[VariableInput] = [],
    executor: RunbookExecutor = Depends(get_executor),
):
    """Resume a paused execution."""
    context = {v.name: v.value for v in variables}
    
    try:
        execution = await executor.resume(execution_id, context)
        
        return ExecutionResponse(
            id=execution.id,
            runbook_id=execution.runbook_id,
            runbook_name=execution.runbook_name,
            status=execution.status,
            current_step_id=execution.current_step_id,
            current_step_index=execution.current_step_index,
            total_steps=0,  # Would need runbook lookup
            progress_percent=execution.progress_percent,
            dry_run=execution.dry_run,
            started_at=execution.started_at,
            completed_at=execution.completed_at,
            error=execution.error,
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# Template Endpoints
# ============================================================================

@router.get("/templates")
async def list_templates():
    """List available runbook templates."""
    templates = [
        {
            "id": "restart-service",
            "name": "Restart Service",
            "description": "Safely restart a Kubernetes deployment",
            "category": "operations",
        },
        {
            "id": "scale-service",
            "name": "Scale Service",
            "description": "Scale a deployment up or down",
            "category": "operations",
        },
        {
            "id": "rollback-deployment",
            "name": "Rollback Deployment",
            "description": "Rollback a deployment to previous version",
            "category": "operations",
        },
        {
            "id": "database-failover",
            "name": "Database Failover",
            "description": "Failover from primary to secondary database",
            "category": "database",
        },
        {
            "id": "clear-cache",
            "name": "Clear Cache",
            "description": "Clear application or CDN cache",
            "category": "cache",
        },
    ]
    
    return {"templates": templates}


@router.get("/templates/{template_id}")
async def get_template(template_id: str):
    """Get a runbook template."""
    templates = {
        "restart-service": """
name: Restart Service
description: Safely restart a Kubernetes deployment
version: 1.0.0

variables:
  - name: namespace
    type: string
    required: true
  - name: deployment
    type: string
    required: true
  - name: grace_period
    type: integer
    default: 30

steps:
  - id: check-health
    name: Check current health
    type: command
    command: kubectl get pods -n {{ namespace }} -l app={{ deployment }}
    
  - id: restart
    name: Restart deployment
    type: kubernetes
    parameters:
      action: restart_deployment
      namespace: "{{ namespace }}"
      name: "{{ deployment }}"
      
  - id: verify
    name: Verify restart complete
    type: command
    command: kubectl rollout status deployment/{{ deployment }} -n {{ namespace }}
""",
    }
    
    if template_id not in templates:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return {"id": template_id, "content": templates[template_id]}
