-- AutoSRE V2 - Database Initialization
-- Run this to set up the initial database schema

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";      -- UUID generation
CREATE EXTENSION IF NOT EXISTS "pg_trgm";        -- Trigram similarity for search
CREATE EXTENSION IF NOT EXISTS "btree_gin";      -- GIN index support

-- Create schema
CREATE SCHEMA IF NOT EXISTS autosre;

-- Set search path
SET search_path TO autosre, public;

--------------------------------------------------------------------------------
-- CORE TABLES
--------------------------------------------------------------------------------

-- Organizations (multi-tenant support)
CREATE TABLE IF NOT EXISTS organizations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(63) NOT NULL UNIQUE,
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Users
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    role VARCHAR(50) NOT NULL DEFAULT 'viewer',
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(org_id, email)
);

-- API Keys
CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    name VARCHAR(255) NOT NULL,
    key_hash VARCHAR(64) NOT NULL UNIQUE,  -- SHA-256 hash
    prefix VARCHAR(8) NOT NULL,             -- For identification
    scopes TEXT[] DEFAULT '{}',
    expires_at TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

--------------------------------------------------------------------------------
-- RUNBOOK SYSTEM
--------------------------------------------------------------------------------

-- Runbooks (the main entity)
CREATE TABLE IF NOT EXISTS runbooks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(63) NOT NULL,
    description TEXT,
    trigger_config JSONB DEFAULT '{}',      -- Alert patterns, webhooks, etc.
    version INTEGER NOT NULL DEFAULT 1,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(org_id, slug)
);

-- Runbook Steps
CREATE TABLE IF NOT EXISTS runbook_steps (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    runbook_id UUID NOT NULL REFERENCES runbooks(id) ON DELETE CASCADE,
    order_index INTEGER NOT NULL,
    name VARCHAR(255) NOT NULL,
    step_type VARCHAR(50) NOT NULL,         -- 'action', 'decision', 'parallel', 'wait'
    config JSONB NOT NULL DEFAULT '{}',     -- Step-specific configuration
    timeout_seconds INTEGER DEFAULT 300,
    retry_config JSONB DEFAULT '{"max_retries": 0}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(runbook_id, order_index)
);

-- Runbook Executions
CREATE TABLE IF NOT EXISTS runbook_executions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    runbook_id UUID NOT NULL REFERENCES runbooks(id) ON DELETE CASCADE,
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',  -- pending, running, completed, failed, cancelled
    trigger_source VARCHAR(100),             -- 'alert', 'manual', 'api', 'schedule'
    trigger_data JSONB DEFAULT '{}',
    context JSONB DEFAULT '{}',              -- Variables, inputs
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Step Executions
CREATE TABLE IF NOT EXISTS step_executions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    execution_id UUID NOT NULL REFERENCES runbook_executions(id) ON DELETE CASCADE,
    step_id UUID NOT NULL REFERENCES runbook_steps(id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    input_data JSONB DEFAULT '{}',
    output_data JSONB DEFAULT '{}',
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

--------------------------------------------------------------------------------
-- INTEGRATIONS
--------------------------------------------------------------------------------

-- Integration Configurations
CREATE TABLE IF NOT EXISTS integrations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    type VARCHAR(50) NOT NULL,              -- 'pagerduty', 'slack', 'datadog', etc.
    name VARCHAR(255) NOT NULL,
    config JSONB NOT NULL DEFAULT '{}',     -- Encrypted credentials, settings
    is_active BOOLEAN NOT NULL DEFAULT true,
    last_health_check TIMESTAMPTZ,
    health_status VARCHAR(50) DEFAULT 'unknown',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(org_id, type, name)
);

-- Incoming Alerts
CREATE TABLE IF NOT EXISTS alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    integration_id UUID REFERENCES integrations(id) ON DELETE SET NULL,
    external_id VARCHAR(255),               -- ID from source system
    severity VARCHAR(50) NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    source VARCHAR(100) NOT NULL,
    labels JSONB DEFAULT '{}',
    raw_payload JSONB DEFAULT '{}',
    status VARCHAR(50) NOT NULL DEFAULT 'open',
    acknowledged_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

--------------------------------------------------------------------------------
-- AUDIT & ANALYTICS
--------------------------------------------------------------------------------

-- Audit Log
CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100) NOT NULL,
    resource_id UUID,
    old_value JSONB,
    new_value JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Metrics (for analytics)
CREATE TABLE IF NOT EXISTS execution_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    runbook_id UUID REFERENCES runbooks(id) ON DELETE SET NULL,
    execution_id UUID REFERENCES runbook_executions(id) ON DELETE SET NULL,
    metric_type VARCHAR(100) NOT NULL,      -- 'duration', 'step_count', 'error_rate'
    metric_value NUMERIC NOT NULL,
    labels JSONB DEFAULT '{}',
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

--------------------------------------------------------------------------------
-- INDEXES
--------------------------------------------------------------------------------

-- Organizations
CREATE INDEX IF NOT EXISTS idx_organizations_slug ON organizations(slug);

-- Users
CREATE INDEX IF NOT EXISTS idx_users_org_id ON users(org_id);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- API Keys
CREATE INDEX IF NOT EXISTS idx_api_keys_org_id ON api_keys(org_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_prefix ON api_keys(prefix);

-- Runbooks
CREATE INDEX IF NOT EXISTS idx_runbooks_org_id ON runbooks(org_id);
CREATE INDEX IF NOT EXISTS idx_runbooks_slug ON runbooks(org_id, slug);
CREATE INDEX IF NOT EXISTS idx_runbooks_active ON runbooks(org_id, is_active) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_runbooks_trigger_gin ON runbooks USING GIN(trigger_config);

-- Runbook Steps
CREATE INDEX IF NOT EXISTS idx_runbook_steps_runbook_id ON runbook_steps(runbook_id);

-- Executions
CREATE INDEX IF NOT EXISTS idx_executions_runbook_id ON runbook_executions(runbook_id);
CREATE INDEX IF NOT EXISTS idx_executions_org_id ON runbook_executions(org_id);
CREATE INDEX IF NOT EXISTS idx_executions_status ON runbook_executions(org_id, status);
CREATE INDEX IF NOT EXISTS idx_executions_created_at ON runbook_executions(org_id, created_at DESC);

-- Step Executions
CREATE INDEX IF NOT EXISTS idx_step_executions_execution_id ON step_executions(execution_id);

-- Integrations
CREATE INDEX IF NOT EXISTS idx_integrations_org_id ON integrations(org_id);
CREATE INDEX IF NOT EXISTS idx_integrations_type ON integrations(org_id, type);

-- Alerts
CREATE INDEX IF NOT EXISTS idx_alerts_org_id ON alerts(org_id);
CREATE INDEX IF NOT EXISTS idx_alerts_external_id ON alerts(org_id, external_id);
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(org_id, status);
CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON alerts(org_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_labels_gin ON alerts USING GIN(labels);

-- Audit Log
CREATE INDEX IF NOT EXISTS idx_audit_log_org_id ON audit_log(org_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_user_id ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_resource ON audit_log(resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log(org_id, created_at DESC);

-- Metrics
CREATE INDEX IF NOT EXISTS idx_metrics_org_id ON execution_metrics(org_id);
CREATE INDEX IF NOT EXISTS idx_metrics_runbook_id ON execution_metrics(runbook_id);
CREATE INDEX IF NOT EXISTS idx_metrics_recorded_at ON execution_metrics(org_id, recorded_at DESC);

--------------------------------------------------------------------------------
-- FUNCTIONS
--------------------------------------------------------------------------------

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply updated_at trigger to relevant tables
DO $$
DECLARE
    t TEXT;
BEGIN
    FOR t IN SELECT unnest(ARRAY['organizations', 'users', 'runbooks', 'integrations'])
    LOOP
        EXECUTE format('
            DROP TRIGGER IF EXISTS trigger_update_updated_at ON autosre.%I;
            CREATE TRIGGER trigger_update_updated_at
            BEFORE UPDATE ON autosre.%I
            FOR EACH ROW EXECUTE FUNCTION update_updated_at();
        ', t, t);
    END LOOP;
END;
$$;

--------------------------------------------------------------------------------
-- INITIAL DATA
--------------------------------------------------------------------------------

-- Create default organization (for development)
INSERT INTO organizations (id, name, slug, settings)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'Default Organization',
    'default',
    '{"plan": "free"}'
) ON CONFLICT (slug) DO NOTHING;

-- Grant permissions
GRANT USAGE ON SCHEMA autosre TO autosre;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA autosre TO autosre;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA autosre TO autosre;

-- Done
SELECT 'AutoSRE database initialized successfully' AS status;
