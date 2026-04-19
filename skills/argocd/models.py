"""Pydantic models for ArgoCD skill."""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class ArgoCDError(Exception):
    """ArgoCD API error."""
    
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


class ResourceHealth(BaseModel):
    """Health of a single resource."""
    
    kind: str
    name: str
    namespace: Optional[str] = None
    status: str = Field(description="Healthy, Progressing, Degraded, Suspended, Missing, Unknown")
    message: Optional[str] = None


class ApplicationHealth(BaseModel):
    """Application health status."""
    
    status: str = Field(description="Healthy, Progressing, Degraded, Suspended, Missing, Unknown")
    message: Optional[str] = None
    resources: list[ResourceHealth] = Field(default_factory=list)
    
    @property
    def is_healthy(self) -> bool:
        return self.status == "Healthy"
    
    @property
    def is_degraded(self) -> bool:
        return self.status == "Degraded"
    
    @property
    def is_progressing(self) -> bool:
        return self.status == "Progressing"


class SyncStatus(BaseModel):
    """Application sync status."""
    
    status: str = Field(description="Synced, OutOfSync, Unknown")
    revision: Optional[str] = None
    
    @property
    def is_synced(self) -> bool:
        return self.status == "Synced"


class ApplicationSource(BaseModel):
    """Application source configuration."""
    
    repo_url: str
    path: Optional[str] = None
    target_revision: str = "HEAD"
    chart: Optional[str] = None
    helm: Optional[dict[str, Any]] = None


class ApplicationDestination(BaseModel):
    """Application destination."""
    
    server: str
    namespace: str


class Application(BaseModel):
    """ArgoCD application."""
    
    name: str
    namespace: str = "argocd"
    project: str = "default"
    source: ApplicationSource
    destination: ApplicationDestination
    health_status: str
    sync_status: str
    revision: Optional[str] = None
    created_at: Optional[datetime] = None
    
    @property
    def is_healthy(self) -> bool:
        return self.health_status == "Healthy"
    
    @property
    def is_synced(self) -> bool:
        return self.sync_status == "Synced"


class ApplicationList(BaseModel):
    """List of applications."""
    
    items: list[Application]
    
    @property
    def count(self) -> int:
        return len(self.items)


class SyncResult(BaseModel):
    """Sync operation result."""
    
    revision: str
    phase: str = Field(description="Running, Succeeded, Failed, Error, Terminated")
    message: Optional[str] = None
    resources: list[dict[str, Any]] = Field(default_factory=list)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    
    @property
    def is_successful(self) -> bool:
        return self.phase == "Succeeded"
    
    @property
    def is_running(self) -> bool:
        return self.phase == "Running"
