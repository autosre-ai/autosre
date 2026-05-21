"""Initial schema

Revision ID: 001
Revises: 
Create Date: 2025-01-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create teams table
    op.create_table(
        'teams',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('display_name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_teams_name', 'teams', ['name'], unique=True)
    
    # Create tokens table
    op.create_table(
        'tokens',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('token_hash', sa.String(255), nullable=False),
        sa.Column('token_prefix', sa.String(20), nullable=False),
        sa.Column('permissions', postgresql.ARRAY(sa.String(50)), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('team_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_tokens_team_id', 'tokens', ['team_id'])
    op.create_index('ix_tokens_token_hash', 'tokens', ['token_hash'], unique=True)
    
    # Create agent_configs table
    op.create_table(
        'agent_configs',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('model', sa.String(100), nullable=False, default='claude-sonnet-4-20250514'),
        sa.Column('temperature', sa.Float(), nullable=False, default=0.7),
        sa.Column('max_tokens', sa.Integer(), nullable=False, default=4096),
        sa.Column('system_prompt', sa.Text(), nullable=True),
        sa.Column('context_window', sa.Integer(), nullable=False, default=100000),
        sa.Column('integrations', postgresql.JSON(), nullable=False, default={}),
        sa.Column('alert_channels', postgresql.JSON(), nullable=False, default={}),
        sa.Column('max_requests_per_minute', sa.Integer(), nullable=False, default=60),
        sa.Column('max_actions_per_incident', sa.Integer(), nullable=False, default=50),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('team_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_agent_configs_team_id', 'agent_configs', ['team_id'])
    
    # Create skill_configs table
    op.create_table(
        'skill_configs',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('skill_id', sa.String(100), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(100), nullable=False, default='general'),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, default=True),
        sa.Column('config', postgresql.JSON(), nullable=False, default={}),
        sa.Column('requires_approval', sa.Boolean(), nullable=False, default=False),
        sa.Column('risk_level', sa.String(20), nullable=False, default='low'),
        sa.Column('max_calls_per_hour', sa.Integer(), nullable=True),
        sa.Column('timeout_seconds', sa.Integer(), nullable=False, default=30),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('agent_config_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['agent_config_id'], ['agent_configs.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_skill_configs_agent_config_id', 'skill_configs', ['agent_config_id'])
    op.create_index('ix_skill_configs_skill_id', 'skill_configs', ['skill_id'])


def downgrade() -> None:
    op.drop_table('skill_configs')
    op.drop_table('agent_configs')
    op.drop_table('tokens')
    op.drop_table('teams')
