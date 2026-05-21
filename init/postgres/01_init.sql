-- =============================================================================
-- AutoSRE PostgreSQL Initialization
-- =============================================================================

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create schemas
CREATE SCHEMA IF NOT EXISTS autosre;
CREATE SCHEMA IF NOT EXISTS audit;

-- Set search path
SET search_path TO autosre, public;

-- =============================================================================
-- Core Tables
-- =============================================================================

-- Users table
CREATE TABLE IF NOT EXISTS autosre.users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    is_active BOOLEAN DEFAULT true,
    is_superuser BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create index on email
CREATE INDEX IF NOT EXISTS idx_users_email ON autosre.users(email);

-- API Keys table
CREATE TABLE IF NOT EXISTS autosre.api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES autosre.users(id) ON DELETE CASCADE,
    key_hash VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    scopes TEXT[] DEFAULT ARRAY[]::TEXT[],
    expires_at TIMESTAMP WITH TIME ZONE,
    last_used_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Incidents table
CREATE TABLE IF NOT EXISTS autosre.incidents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(500) NOT NULL,
    description TEXT,
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('critical', 'high', 'medium', 'low')),
    status VARCHAR(20) NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'investigating', 'identified', 'monitoring', 'resolved', 'closed')),
    source VARCHAR(100),
    source_id VARCHAR(255),
    assigned_to UUID REFERENCES autosre.users(id),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP WITH TIME ZONE
);

-- Create indexes for incidents
CREATE INDEX IF NOT EXISTS idx_incidents_status ON autosre.incidents(status);
CREATE INDEX IF NOT EXISTS idx_incidents_severity ON autosre.incidents(severity);
CREATE INDEX IF NOT EXISTS idx_incidents_created_at ON autosre.incidents(created_at DESC);

-- Agent actions table
CREATE TABLE IF NOT EXISTS autosre.agent_actions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    incident_id UUID REFERENCES autosre.incidents(id) ON DELETE SET NULL,
    action_type VARCHAR(100) NOT NULL,
    action_input JSONB NOT NULL DEFAULT '{}',
    action_output JSONB,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    error_message TEXT,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for agent actions
CREATE INDEX IF NOT EXISTS idx_agent_actions_incident_id ON autosre.agent_actions(incident_id);
CREATE INDEX IF NOT EXISTS idx_agent_actions_status ON autosre.agent_actions(status);

-- Runbooks table
CREATE TABLE IF NOT EXISTS autosre.runbooks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    content TEXT NOT NULL,
    version INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT true,
    tags TEXT[] DEFAULT ARRAY[]::TEXT[],
    metadata JSONB DEFAULT '{}',
    created_by UUID REFERENCES autosre.users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create index for runbook search
CREATE INDEX IF NOT EXISTS idx_runbooks_name_trgm ON autosre.runbooks USING gin(name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_runbooks_tags ON autosre.runbooks USING gin(tags);

-- =============================================================================
-- Audit Tables
-- =============================================================================

CREATE TABLE IF NOT EXISTS audit.activity_log (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100),
    resource_id VARCHAR(255),
    details JSONB DEFAULT '{}',
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for audit log
CREATE INDEX IF NOT EXISTS idx_activity_log_user_id ON audit.activity_log(user_id);
CREATE INDEX IF NOT EXISTS idx_activity_log_created_at ON audit.activity_log(created_at DESC);

-- =============================================================================
-- Functions
-- =============================================================================

-- Update timestamp function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply triggers
DROP TRIGGER IF EXISTS update_users_updated_at ON autosre.users;
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON autosre.users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_incidents_updated_at ON autosre.incidents;
CREATE TRIGGER update_incidents_updated_at
    BEFORE UPDATE ON autosre.incidents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_runbooks_updated_at ON autosre.runbooks;
CREATE TRIGGER update_runbooks_updated_at
    BEFORE UPDATE ON autosre.runbooks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- Initial Data
-- =============================================================================

-- Insert default admin user (password: changeme)
INSERT INTO autosre.users (email, hashed_password, full_name, is_superuser)
VALUES ('admin@autosre.local', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.DVyPXpVbfj5Wm2', 'Admin User', true)
ON CONFLICT (email) DO NOTHING;

COMMIT;
