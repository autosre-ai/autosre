"""Skill configuration model."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base


class SkillConfig(Base):
    """Configuration for an agent skill/capability."""
    
    __tablename__ = "skill_configs"
    
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    
    # Skill identification
    skill_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(100), default="general", nullable=False)
    
    # Status
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Configuration
    config: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    
    # Safety settings
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), default="low", nullable=False)  # low, medium, high, critical
    
    # Limits
    max_calls_per_hour: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    
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
    agent_config_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("agent_configs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Relationship
    agent_config = relationship("AgentConfig", back_populates="skills")
    
    def __repr__(self) -> str:
        return f"<SkillConfig(id={self.id}, skill_id={self.skill_id}, enabled={self.is_enabled})>"
