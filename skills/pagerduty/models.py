"""Pydantic models for PagerDuty skill."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class PagerDutyError(Exception):
    """PagerDuty API error."""

    def __init__(self, code: int, message: str, errors: Optional[list[str]] = None):
        self.code = code
        self.message = message
        self.errors = errors or []
        super().__init__(f"[{code}] {message}")


class Service(BaseModel):
    """PagerDuty service."""

    id: str
    name: str
    description: Optional[str] = None
    status: Optional[str] = None


class OnCallUser(BaseModel):
    """On-call user info."""

    id: str
    name: str
    email: str
    avatar_url: Optional[str] = None


class OnCall(BaseModel):
    """On-call schedule entry."""

    user: OnCallUser
    schedule_id: str
    schedule_name: Optional[str] = None
    escalation_level: int = 1
    start: Optional[datetime] = None
    end: Optional[datetime] = None


class Incident(BaseModel):
    """PagerDuty incident."""

    id: str
    incident_number: int
    title: str
    status: str = Field(description="triggered, acknowledged, or resolved")
    urgency: str = Field(description="high or low")
    service: Service
    created_at: datetime
    updated_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    html_url: str
    description: Optional[str] = None
    assignments: list[dict[str, Any]] = Field(default_factory=list)
    acknowledgements: list[dict[str, Any]] = Field(default_factory=list)

    @property
    def is_triggered(self) -> bool:
        return self.status == "triggered"

    @property
    def is_acknowledged(self) -> bool:
        return self.status == "acknowledged"

    @property
    def is_resolved(self) -> bool:
        return self.status == "resolved"


class IncidentList(BaseModel):
    """List of incidents with pagination."""

    incidents: list[Incident]
    total: int
    offset: int = 0
    limit: int = 25
    more: bool = False


class IncidentNote(BaseModel):
    """Note on an incident."""

    id: str
    content: str
    created_at: datetime
    user: Optional[OnCallUser] = None
