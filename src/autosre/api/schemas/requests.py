"""Request Schemas.

Pydantic models for validating incoming API requests.
"""

from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AlertCreate(BaseModel):
    """Schema for creating a new alert."""

    alertname: str = Field(..., min_length=1, max_length=255)
    severity: str = Field(..., pattern="^(critical|warning|info)$")
    summary: str = Field(..., min_length=1, max_length=1000)
    description: Optional[str] = Field(None, max_length=5000)
    source: str = Field(..., min_length=1, max_length=255)
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)
    external_url: Optional[str] = Field(None, max_length=2000)

    model_config = {
        "json_schema_extra": {
            "example": {
                "alertname": "HighCPUUsage",
                "severity": "critical",
                "summary": "CPU usage above 90% for 5 minutes",
                "description": "Host prod-web-01 has sustained high CPU usage",
                "source": "prometheus",
                "labels": {"host": "prod-web-01", "env": "production"},
                "annotations": {"dashboard": "https://grafana.example.com/d/cpu"},
            }
        }
    }


class AlertUpdate(BaseModel):
    """Schema for updating an existing alert."""

    status: Optional[str] = Field(None, pattern="^(firing|acknowledged|resolved)$")
    severity: Optional[str] = Field(None, pattern="^(critical|warning|info)$")
    summary: Optional[str] = Field(None, min_length=1, max_length=1000)
    description: Optional[str] = Field(None, max_length=5000)
    labels: Optional[dict[str, str]] = None
    annotations: Optional[dict[str, str]] = None
    assigned_to: Optional[str] = None


class InvestigationTrigger(BaseModel):
    """Schema for triggering an investigation on an alert."""

    auto_remediate: bool = Field(
        default=False,
        description="Allow automatic remediation actions",
    )
    runbook_ids: list[UUID] = Field(
        default_factory=list,
        description="Specific runbooks to consider during investigation",
    )
    priority: str = Field(
        default="normal",
        pattern="^(low|normal|high|critical)$",
        description="Investigation priority",
    )
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context for the investigation",
    )


class ChatMessage(BaseModel):
    """Schema for a chat message."""

    content: str = Field(..., min_length=1, max_length=10000)
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context (e.g., selected alerts, time range)",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "content": "What's causing the high latency on the API servers?",
                "context": {"alert_ids": ["uuid-1", "uuid-2"]},
            }
        }
    }


class RunbookCreate(BaseModel):
    """Schema for creating a new runbook."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    category: str = Field(..., min_length=1, max_length=100)
    trigger_conditions: dict[str, Any] = Field(
        default_factory=dict,
        description="Conditions that auto-trigger this runbook",
    )
    steps: list[dict[str, Any]] = Field(
        ...,
        min_length=1,
        description="Ordered list of runbook steps",
    )
    parameters: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Input parameters for the runbook",
    )
    tags: list[str] = Field(default_factory=list)
    enabled: bool = Field(default=True)

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Restart Service",
                "description": "Safely restart a service with health checks",
                "category": "remediation",
                "steps": [
                    {"type": "check", "action": "verify_service_health"},
                    {"type": "action", "action": "restart_service"},
                    {"type": "wait", "seconds": 30},
                    {"type": "check", "action": "verify_service_health"},
                ],
                "parameters": [
                    {
                        "name": "service_name",
                        "type": "string",
                        "required": True,
                    }
                ],
                "tags": ["restart", "service"],
            }
        }
    }


class RunbookUpdate(BaseModel):
    """Schema for updating an existing runbook."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    category: Optional[str] = Field(None, min_length=1, max_length=100)
    trigger_conditions: Optional[dict[str, Any]] = None
    steps: Optional[list[dict[str, Any]]] = None
    parameters: Optional[list[dict[str, Any]]] = None
    tags: Optional[list[str]] = None
    enabled: Optional[bool] = None


class RunbookExecute(BaseModel):
    """Schema for executing a runbook."""

    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Parameter values for the runbook",
    )
    dry_run: bool = Field(
        default=False,
        description="Simulate execution without making changes",
    )
    alert_id: Optional[UUID] = Field(
        None,
        description="Associated alert ID",
    )
    investigation_id: Optional[UUID] = Field(
        None,
        description="Associated investigation ID",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "parameters": {"service_name": "api-gateway"},
                "dry_run": False,
            }
        }
    }


class InvestigationAction(BaseModel):
    """Schema for executing an action within an investigation."""

    action_type: str = Field(
        ...,
        pattern="^(approve|reject|escalate|add_note|run_command)$",
        description="Type of action to execute",
    )
    target: Optional[str] = Field(
        None,
        description="Target of the action (e.g., remediation ID, command)",
    )
    message: Optional[str] = Field(
        None,
        max_length=5000,
        description="Note or reason for the action",
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional action parameters",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "action_type": "approve",
                    "target": "remediation-uuid",
                    "message": "Approved automatic restart",
                },
                {
                    "action_type": "add_note",
                    "message": "Checked logs, no obvious errors",
                },
                {
                    "action_type": "run_command",
                    "target": "kubectl get pods -n production",
                },
            ]
        }
    }
