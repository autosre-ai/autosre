"""Common types and utilities shared across models."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, ConfigDict


def generate_id() -> str:
    """Generate a unique ID."""
    return str(uuid4())


def utc_now() -> datetime:
    """Get current UTC timestamp."""
    from datetime import timezone
    return datetime.now(timezone.utc)


class Priority(str, Enum):
    """Priority levels for tasks and actions."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ExecutionStatus(str, Enum):
    """Status of an execution or task."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class BaseEntity(BaseModel):
    """Base model with common fields."""
    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        validate_assignment=True,
    )
    
    id: str = Field(default_factory=generate_id)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TimeRange(BaseModel):
    """A time range with start and optional end."""
    model_config = ConfigDict(validate_assignment=True)
    
    start: datetime
    end: datetime | None = None
    
    def duration_seconds(self) -> float | None:
        """Get duration in seconds, or None if ongoing."""
        if self.end is None:
            return None
        return (self.end - self.start).total_seconds()
