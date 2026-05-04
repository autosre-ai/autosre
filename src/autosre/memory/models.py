"""
Memory Models

Pydantic models for the episodic memory system.
"""
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any


def _utc_now() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


class Episode(BaseModel):
    """Represents a single incident investigation episode."""
    
    id: str
    created_at: datetime = Field(default_factory=_utc_now)
    alert_type: str
    service_name: Optional[str] = None
    severity: str = "info"
    root_cause: Optional[str] = None
    summary: Optional[str] = None
    resolved: bool = False
    effectiveness_score: float = 0.0
    skills_used: List[str] = []
    key_findings: List[dict] = []
    duration_seconds: Optional[int] = None
    
    # Extended fields for compatibility with existing code
    symptoms: List[str] = []
    metrics: Dict[str, Any] = {}
    logs: List[str] = []
    topology: Dict[str, Any] = {}
    steps_taken: List[str] = []
    hypotheses: List[str] = []
    resolution: Optional[str] = None
    tags: List[str] = []
    embedding: Optional[List[float]] = None
    
    # Aliases for backward compatibility
    @property
    def service(self) -> Optional[str]:
        """Alias for service_name."""
        return self.service_name
    
    @property
    def timestamp(self) -> datetime:
        """Alias for created_at."""
        return self.created_at
    
    @property
    def success(self) -> bool:
        """Alias for resolved."""
        return self.resolved


class Strategy(BaseModel):
    """Represents a learned strategy for handling specific alert types."""
    
    id: str
    alert_type: str
    service_name: str = "*"
    strategy_text: str
    source_episode_ids: List[str] = []
    created_at: datetime = Field(default_factory=_utc_now)


class MemoryQuery(BaseModel):
    """Query for retrieving relevant episodes."""
    
    text: str
    service: Optional[str] = None
    alert_type: Optional[str] = None
    tags: List[str] = []
    time_range_hours: Optional[int] = None
