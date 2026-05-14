"""Initial schema

Revision ID: 001
Revises:
Create Date: 2025-01-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all initial tables."""
    
    # Runbooks table (no foreign keys, create first)
    op.create_table(
        "runbooks",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(256), nullable=False, index=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("alert_name_pattern", sa.String(512), nullable=True),
        sa.Column("alert_labels", sa.JSON, nullable=True),
        sa.Column("steps", sa.JSON, nullable=False),
        sa.Column("version", sa.Integer, nullable=False, default=1),
        sa.Column("is_active", sa.Boolean, nullable=False, default=True, index=True),
        sa.Column("is_auto_generated", sa.Boolean, nullable=False, default=False),
        sa.Column("times_used", sa.Integer, nullable=False, default=0),
        sa.Column("success_rate", sa.Float, nullable=True),
        sa.Column("avg_resolution_time_seconds", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.Column("created_by", sa.String(128), nullable=True),
    )
    
    # Alerts table
    op.create_table(
        "alerts",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("external_id", sa.String(256), nullable=True, index=True),
        sa.Column("name", sa.String(512), nullable=False),
        sa.Column("severity", sa.String(32), nullable=False, index=True),
        sa.Column("status", sa.String(32), nullable=False, default="active", index=True),
        sa.Column("source", sa.String(128), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("labels", sa.JSON, nullable=True),
        sa.Column("annotations", sa.JSON, nullable=True),
        sa.Column("fingerprint", sa.String(256), nullable=True, index=True),
        sa.Column("starts_at", sa.DateTime, nullable=False),
        sa.Column("ends_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    
    op.create_index(
        "ix_alerts_source_status",
        "alerts",
        ["source", "status"],
    )
    op.create_index(
        "ix_alerts_severity_status",
        "alerts",
        ["severity", "status"],
    )
    
    # Investigations table
    op.create_table(
        "investigations",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "alert_id",
            sa.String(64),
            sa.ForeignKey("alerts.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("status", sa.String(32), nullable=False, default="pending", index=True),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("root_cause", sa.Text, nullable=True),
        sa.Column("resolution", sa.Text, nullable=True),
        sa.Column("confidence_score", sa.Float, nullable=True),
        sa.Column(
            "runbook_id",
            sa.String(64),
            sa.ForeignKey("runbooks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("metadata", sa.JSON, nullable=True),
        sa.Column("started_at", sa.DateTime, nullable=True),
        sa.Column("completed_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    
    op.create_index(
        "ix_investigations_alert_status",
        "investigations",
        ["alert_id", "status"],
    )
    
    # Observations table
    op.create_table(
        "observations",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "investigation_id",
            sa.String(64),
            sa.ForeignKey("investigations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("observation_type", sa.String(64), nullable=False),
        sa.Column("source", sa.String(128), nullable=False),
        sa.Column("query", sa.Text, nullable=True),
        sa.Column("data", sa.JSON, nullable=False),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("relevance_score", sa.Float, nullable=True),
        sa.Column("sequence_num", sa.Integer, nullable=False, default=0),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    
    op.create_index(
        "ix_observations_type_source",
        "observations",
        ["observation_type", "source"],
    )
    
    # Actions table
    op.create_table(
        "actions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "investigation_id",
            sa.String(64),
            sa.ForeignKey("investigations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("action_type", sa.String(64), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("command", sa.Text, nullable=True),
        sa.Column("parameters", sa.JSON, nullable=True),
        sa.Column("status", sa.String(32), nullable=False, default="pending"),
        sa.Column("requires_approval", sa.Boolean, nullable=False, default=False),
        sa.Column("approved_by", sa.String(128), nullable=True),
        sa.Column("approved_at", sa.DateTime, nullable=True),
        sa.Column("result", sa.JSON, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("sequence_num", sa.Integer, nullable=False, default=0),
        sa.Column("started_at", sa.DateTime, nullable=True),
        sa.Column("completed_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    
    op.create_index(
        "ix_actions_type_status",
        "actions",
        ["action_type", "status"],
    )
    
    # Chat messages table
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "investigation_id",
            sa.String(64),
            sa.ForeignKey("investigations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("content", sa.Text, nullable=True),
        sa.Column("tool_calls", sa.JSON, nullable=True),
        sa.Column("tool_call_id", sa.String(128), nullable=True),
        sa.Column("tool_name", sa.String(128), nullable=True),
        sa.Column("model", sa.String(64), nullable=True),
        sa.Column("tokens_used", sa.Integer, nullable=True),
        sa.Column("sequence_num", sa.Integer, nullable=False, default=0),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    
    op.create_index(
        "ix_chat_messages_investigation_seq",
        "chat_messages",
        ["investigation_id", "sequence_num"],
    )


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table("chat_messages")
    op.drop_table("actions")
    op.drop_table("observations")
    op.drop_table("investigations")
    op.drop_table("alerts")
    op.drop_table("runbooks")
