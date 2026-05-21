"""
Initial memory system schema.

Revision ID: 001_initial
Revises:
Create Date: 2024-01-01 00:00:00.000000

Tables:
- episodes: Investigation episode records
- strategies: Learned investigation strategies
- key_findings: Significant findings from investigations
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# Revision identifiers
revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create memory system tables."""
    
    # ---------------------------------------------------------------------------
    # Episodes table
    # ---------------------------------------------------------------------------
    op.create_table(
        "episodes",
        # Primary key
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        
        # Foreign references
        sa.Column("agent_run_id", sa.String(255), nullable=True, index=True),
        sa.Column("org_id", sa.String(255), nullable=False, default="default", index=True),
        sa.Column("team_node_id", sa.String(255), nullable=True, index=True),
        
        # Alert context
        sa.Column("alert_type", sa.String(100), nullable=False, default="unknown", index=True),
        sa.Column("alert_description", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, default="info"),
        sa.Column("services", postgresql.ARRAY(sa.String(255)), nullable=False, server_default="{}"),
        
        # Investigation details
        sa.Column("agents_used", postgresql.ARRAY(sa.String(100)), nullable=False, server_default="{}"),
        sa.Column("skills_used", postgresql.ARRAY(sa.String(100)), nullable=False, server_default="{}"),
        sa.Column("key_findings", postgresql.JSONB(), nullable=False, server_default="[]"),
        
        # Outcome
        sa.Column("resolved", sa.Boolean(), nullable=False, default=False, index=True),
        sa.Column("root_cause", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("remediation_steps", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        
        # Metrics
        sa.Column("effectiveness_score", sa.Float(), nullable=False, default=0.0),
        sa.Column("confidence", sa.Float(), nullable=False, default=0.0),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        
        # Embedding for vector similarity search (optional, for future use)
        sa.Column("embedding", postgresql.ARRAY(sa.Float()), nullable=True),
    )
    
    # Create indexes for common query patterns
    op.create_index(
        "ix_episodes_org_alert_type",
        "episodes",
        ["org_id", "alert_type"],
    )
    
    op.create_index(
        "ix_episodes_org_created_at",
        "episodes",
        ["org_id", "created_at"],
    )
    
    op.create_index(
        "ix_episodes_services",
        "episodes",
        ["services"],
        postgresql_using="gin",
    )
    
    op.create_index(
        "ix_episodes_skills_used",
        "episodes",
        ["skills_used"],
        postgresql_using="gin",
    )
    
    # ---------------------------------------------------------------------------
    # Strategies table
    # ---------------------------------------------------------------------------
    op.create_table(
        "strategies",
        # Primary key
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        
        # Scope
        sa.Column("org_id", sa.String(255), nullable=False, default="default", index=True),
        sa.Column("team_node_id", sa.String(255), nullable=True, index=True),
        sa.Column("alert_type", sa.String(100), nullable=False, index=True),
        sa.Column("service_name", sa.String(255), nullable=False, default="*"),
        
        # Strategy content
        sa.Column("strategy_text", sa.Text(), nullable=False),
        sa.Column("common_root_causes", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("recommended_steps", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("key_skills", postgresql.ARRAY(sa.String(100)), nullable=False, server_default="{}"),
        sa.Column("anti_patterns", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        
        # Source metadata
        sa.Column("source_episode_ids", postgresql.ARRAY(sa.String(36)), nullable=False, server_default="{}"),
        sa.Column("episode_count", sa.Integer(), nullable=False, default=0),
        
        # Metrics
        sa.Column("success_rate", sa.Float(), nullable=False, default=0.0),
        sa.Column("avg_resolution_time", sa.Float(), nullable=True),
        
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    
    # Unique constraint for strategy scope
    op.create_unique_constraint(
        "uq_strategies_scope",
        "strategies",
        ["org_id", "alert_type", "service_name"],
    )
    
    op.create_index(
        "ix_strategies_org_alert_type",
        "strategies",
        ["org_id", "alert_type"],
    )
    
    op.create_index(
        "ix_strategies_expires_at",
        "strategies",
        ["expires_at"],
        postgresql_where=sa.text("expires_at IS NOT NULL"),
    )
    
    # ---------------------------------------------------------------------------
    # Key Findings table (normalized, optional)
    # ---------------------------------------------------------------------------
    op.create_table(
        "key_findings",
        # Primary key
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        
        # Foreign key to episode
        sa.Column("episode_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False, index=True),
        
        # Finding details
        sa.Column("skill", sa.String(100), nullable=False, index=True),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("finding", sa.Text(), nullable=False),
        
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    
    op.create_index(
        "ix_key_findings_episode_skill",
        "key_findings",
        ["episode_id", "skill"],
    )
    
    # ---------------------------------------------------------------------------
    # Triggers for updated_at
    # ---------------------------------------------------------------------------
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)
    
    op.execute("""
        CREATE TRIGGER update_episodes_updated_at
            BEFORE UPDATE ON episodes
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """)
    
    op.execute("""
        CREATE TRIGGER update_strategies_updated_at
            BEFORE UPDATE ON strategies
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    """Drop memory system tables."""
    
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS update_episodes_updated_at ON episodes;")
    op.execute("DROP TRIGGER IF EXISTS update_strategies_updated_at ON strategies;")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column();")
    
    # Drop tables (order matters due to foreign keys)
    op.drop_table("key_findings")
    op.drop_table("strategies")
    op.drop_table("episodes")
