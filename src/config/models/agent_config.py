"""Agent configuration model."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base

if TYPE_CHECKING:
    from .skill_config import SkillConfig
    from .team import Team


class AgentConfig(Base):
    """Configuration for an AutoSRE agent instance."""
    
    __tablename__ = "agent_configs"
    
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    
    # Agent identification
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Model configuration
    model: Mapped[str] = mapped_column(String(100), default="claude-sonnet-4-20250514", nullable=False)
    temperature: Mapped[float] = mapped_column(default=0.7, nullable=False)
    max_tokens: Mapped[int] = mapped_column(Integer, default=4096, nullable=False)
    
    # Behavior settings
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    context_window: Mapped[int] = mapped_column(Integer, default=100000, nullable=False)
    
    # Integration settings (JSON for flexibility)
    integrations: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    
    # Alert routing
    alert_channels: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    
    # Rate limiting
    max_requests_per_minute: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    max_actions_per_incident: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
    
    # Foreign key
    team_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Relationships
    team: Mapped["Team"] = relationship("Team", back_populates="agent_configs")
    skills: Mapped[list["SkillConfig"]] = relationship(
        "SkillConfig",
        back_populates="agent_config",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    
    def __repr__(self) -> str:
        return f"<AgentConfig(id={self.id}, name={self.name})>"
