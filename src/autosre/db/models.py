"""SQLAlchemy 2.0 Async Models for AutoSRE.

Defines all database models for alerts, investigations, observations,
actions, runbooks, and chat messages.
"""

from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from sqlalchemy import (
    Column,
    String,
    DateTime,
    JSON,
    Text,
    ForeignKey,
    Integer,
    Boolean,
    Index,
)
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column


def generate_uuid() -> str:
    """Generate a UUID string."""
    return str(uuid4())


def utc_now() -> datetime:
    """Get current UTC timestamp."""
    return datetime.utcnow()


class Base(AsyncAttrs, DeclarativeBase):
    """Base class for all models with async support."""
    pass


class AlertModel(Base):
    """Represents an incoming alert from monitoring systems.
    
    Alerts are the entry point for investigations. Each alert can
    trigger one or more investigations.
    """
    __tablename__ = "alerts"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=generate_uuid)
    external_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    labels: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    annotations: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    fingerprint: Mapped[Optional[str]] = mapped_column(String(256), nullable=True, index=True)
    
    starts_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)
    
    # Relationships
    investigations: Mapped[List["InvestigationModel"]] = relationship(
        back_populates="alert",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    
    __table_args__ = (
        Index("ix_alerts_source_status", "source", "status"),
        Index("ix_alerts_severity_status", "severity", "status"),
    )


class InvestigationModel(Base):
    """Represents an AI-driven investigation into an alert.
    
    An investigation contains observations (data gathered), actions taken,
    and chat messages from the AI reasoning process.
    """
    __tablename__ = "investigations"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=generate_uuid)
    alert_id: Mapped[str] = mapped_column(
        String(64), 
        ForeignKey("alerts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    status: Mapped[str] = mapped_column(
        String(32), 
        nullable=False, 
        default="pending",
        index=True,
    )  # pending, in_progress, completed, failed, escalated
    
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    root_cause: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    
    # Metadata
    runbook_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("runbooks.id", ondelete="SET NULL"),
        nullable=True,
    )
    metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)
    
    # Relationships
    alert: Mapped["AlertModel"] = relationship(back_populates="investigations")
    runbook: Mapped[Optional["RunbookModel"]] = relationship(back_populates="investigations")
    observations: Mapped[List["ObservationModel"]] = relationship(
        back_populates="investigation",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    actions: Mapped[List["ActionModel"]] = relationship(
        back_populates="investigation",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    chat_messages: Mapped[List["ChatMessageModel"]] = relationship(
        back_populates="investigation",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    
    __table_args__ = (
        Index("ix_investigations_alert_status", "alert_id", "status"),
    )


class ObservationModel(Base):
    """Data gathered during an investigation.
    
    Observations are pieces of evidence collected from various sources
    like metrics, logs, traces, or external APIs.
    """
    __tablename__ = "observations"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=generate_uuid)
    investigation_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("investigations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    observation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # Types: metric, log, trace, api_response, command_output, etc.
    
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    # Source system: prometheus, elasticsearch, jaeger, kubernetes, etc.
    
    query: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # The query or command used to fetch this observation
    
    data: Mapped[dict] = mapped_column(JSON, nullable=False)
    # Raw observation data
    
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # AI-generated summary of what this observation shows
    
    relevance_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    # How relevant this observation is to the investigation (0-1)
    
    sequence_num: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Order in which observations were collected
    
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    
    # Relationships
    investigation: Mapped["InvestigationModel"] = relationship(back_populates="observations")
    
    __table_args__ = (
        Index("ix_observations_type_source", "observation_type", "source"),
    )


class ActionModel(Base):
    """Actions taken during an investigation.
    
    Actions represent remediation steps or diagnostic commands
    executed by the AI or approved by humans.
    """
    __tablename__ = "actions"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=generate_uuid)
    investigation_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("investigations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # Types: diagnostic, remediation, notification, escalation
    
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    command: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # The actual command or API call
    
    parameters: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Parameters for the action
    
    status: Mapped[str] = mapped_column(
        String(32), 
        nullable=False, 
        default="pending",
    )  # pending, approved, executing, completed, failed, rejected
    
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approved_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Result of executing the action
    
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    sequence_num: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    
    # Relationships
    investigation: Mapped["InvestigationModel"] = relationship(back_populates="actions")
    
    __table_args__ = (
        Index("ix_actions_type_status", "action_type", "status"),
    )


class RunbookModel(Base):
    """Runbooks define standard procedures for handling alerts.
    
    Runbooks can be auto-generated or manually defined, and guide
    the AI through investigation and remediation steps.
    """
    __tablename__ = "runbooks"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Matching criteria for alerts
    alert_name_pattern: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    alert_labels: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Labels that must match for this runbook to apply
    
    # Runbook content
    steps: Mapped[List[dict]] = mapped_column(JSON, nullable=False, default=list)
    # List of steps with type, description, commands, etc.
    
    # Metadata
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    is_auto_generated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    
    # Statistics
    times_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_rate: Mapped[Optional[float]] = mapped_column(nullable=True)
    avg_resolution_time_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)
    created_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    
    # Relationships
    investigations: Mapped[List["InvestigationModel"]] = relationship(
        back_populates="runbook",
        lazy="selectin",
    )


class ChatMessageModel(Base):
    """Chat messages during an investigation.
    
    Represents the conversation between the AI, system prompts,
    tool calls, and human operators during investigation.
    """
    __tablename__ = "chat_messages"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=generate_uuid)
    investigation_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("investigations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    # Roles: system, user, assistant, tool
    
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Message content (null for tool calls)
    
    # For tool calls
    tool_calls: Mapped[Optional[List[dict]]] = mapped_column(JSON, nullable=True)
    tool_call_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    tool_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    
    # Metadata
    model: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    sequence_num: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    
    # Relationships
    investigation: Mapped["InvestigationModel"] = relationship(back_populates="chat_messages")
    
    __table_args__ = (
        Index("ix_chat_messages_investigation_seq", "investigation_id", "sequence_num"),
    )
