"""
Multi-Tenancy Models

Core data models for multi-tenant SaaS architecture:
- Tenant: Top-level organization/account
- Workspace: Isolated environment within a tenant
- Team: Group of users with shared permissions
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


def utcnow() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def generate_id() -> str:
    """Generate a unique ID."""
    return str(uuid4())


class TenantStatus(str, Enum):
    """Tenant account status."""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    TRIAL = "trial"
    TRIAL_EXPIRED = "trial_expired"
    PENDING_ACTIVATION = "pending_activation"
    DEACTIVATED = "deactivated"


class TenantTier(str, Enum):
    """Tenant pricing tier / plan."""
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"
    CUSTOM = "custom"


class WorkspaceType(str, Enum):
    """Type of workspace."""
    PRODUCTION = "production"
    STAGING = "staging"
    DEVELOPMENT = "development"
    SANDBOX = "sandbox"


class TeamRole(str, Enum):
    """Team member roles with hierarchical permissions."""
    OWNER = "owner"           # Full control, billing, delete tenant
    ADMIN = "admin"           # Manage teams, workspaces, users
    MEMBER = "member"         # Use features, view data
    VIEWER = "viewer"         # Read-only access
    SERVICE_ACCOUNT = "service_account"  # API-only access


class TenantSettings(BaseModel):
    """Tenant-level settings and configuration."""
    
    # Feature flags
    features: dict[str, bool] = Field(
        default_factory=lambda: {
            "auto_remediation": False,
            "custom_runbooks": True,
            "api_access": True,
            "sso_enabled": False,
            "audit_logging": True,
            "advanced_analytics": False,
        }
    )
    
    # Security settings
    require_mfa: bool = Field(default=False, description="Require MFA for all users")
    allowed_ip_ranges: list[str] = Field(default_factory=list, description="Allowed IP CIDR ranges")
    session_timeout_minutes: int = Field(default=480, description="Session timeout in minutes")
    
    # SSO configuration
    sso_provider: Optional[str] = Field(None, description="SSO provider (okta, auth0, azure_ad)")
    sso_config: dict[str, Any] = Field(default_factory=dict, description="SSO configuration")
    
    # Notification settings
    notification_channels: list[str] = Field(
        default_factory=lambda: ["email"],
        description="Enabled notification channels"
    )
    
    # Data retention
    data_retention_days: int = Field(default=90, description="Data retention period")
    
    # Custom branding
    custom_domain: Optional[str] = Field(None, description="Custom domain for white-labeling")
    logo_url: Optional[str] = Field(None, description="Custom logo URL")
    theme: dict[str, str] = Field(default_factory=dict, description="Custom theme colors")


class WorkspaceSettings(BaseModel):
    """Workspace-level settings."""
    
    # Environment configuration
    environment_variables: dict[str, str] = Field(
        default_factory=dict,
        description="Environment-specific variables"
    )
    
    # Integration settings
    integrations: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Workspace-specific integration configs"
    )
    
    # Alert routing
    alert_routing_rules: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Workspace-specific alert routing"
    )
    
    # Permissions
    default_team_access: bool = Field(
        default=True,
        description="Grant team members access by default"
    )


class TeamMember(BaseModel):
    """A member of a team."""
    
    user_id: str = Field(..., description="User identifier")
    email: str = Field(..., description="User email")
    role: TeamRole = Field(default=TeamRole.MEMBER, description="Role within the team")
    
    # Timestamps
    joined_at: datetime = Field(default_factory=utcnow)
    last_active_at: Optional[datetime] = None
    
    # Status
    is_active: bool = Field(default=True)
    invited_by: Optional[str] = Field(None, description="User ID of inviter")


class Team(BaseModel):
    """
    A team within a tenant.
    
    Teams provide logical groupings for users with shared access
    to workspaces and resources.
    """
    
    id: str = Field(default_factory=generate_id, description="Unique team identifier")
    tenant_id: str = Field(..., description="Parent tenant ID")
    
    # Basic info
    name: str = Field(..., description="Team name", min_length=1, max_length=100)
    slug: str = Field(..., description="URL-friendly team identifier")
    description: Optional[str] = Field(None, max_length=500)
    
    # Members
    members: list[TeamMember] = Field(default_factory=list)
    
    # Workspace access
    workspace_ids: list[str] = Field(
        default_factory=list,
        description="Workspaces this team has access to"
    )
    
    # Permissions
    default_role: TeamRole = Field(
        default=TeamRole.MEMBER,
        description="Default role for new members"
    )
    
    # Metadata
    labels: dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    created_by: Optional[str] = Field(None, description="Creator user ID")
    
    @field_validator('slug')
    @classmethod
    def validate_slug(cls, v: str) -> str:
        """Ensure slug is URL-friendly."""
        import re
        if not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$', v.lower()):
            raise ValueError('Slug must be lowercase alphanumeric with hyphens')
        return v.lower()
    
    def add_member(self, user_id: str, email: str, role: TeamRole = TeamRole.MEMBER, 
                   invited_by: Optional[str] = None) -> TeamMember:
        """Add a member to the team."""
        member = TeamMember(
            user_id=user_id,
            email=email,
            role=role,
            invited_by=invited_by,
        )
        self.members.append(member)
        self.updated_at = utcnow()
        return member
    
    def remove_member(self, user_id: str) -> bool:
        """Remove a member from the team."""
        original_count = len(self.members)
        self.members = [m for m in self.members if m.user_id != user_id]
        if len(self.members) < original_count:
            self.updated_at = utcnow()
            return True
        return False
    
    def get_member(self, user_id: str) -> Optional[TeamMember]:
        """Get a specific member."""
        for member in self.members:
            if member.user_id == user_id:
                return member
        return None
    
    def has_permission(self, user_id: str, required_role: TeamRole) -> bool:
        """Check if user has required role or higher."""
        member = self.get_member(user_id)
        if not member or not member.is_active:
            return False
        
        role_hierarchy = {
            TeamRole.OWNER: 4,
            TeamRole.ADMIN: 3,
            TeamRole.MEMBER: 2,
            TeamRole.VIEWER: 1,
            TeamRole.SERVICE_ACCOUNT: 2,  # Same as member
        }
        
        return role_hierarchy.get(member.role, 0) >= role_hierarchy.get(required_role, 0)


class Workspace(BaseModel):
    """
    An isolated workspace within a tenant.
    
    Workspaces provide environment separation (prod, staging, dev)
    and data isolation within a tenant.
    """
    
    id: str = Field(default_factory=generate_id, description="Unique workspace identifier")
    tenant_id: str = Field(..., description="Parent tenant ID")
    
    # Basic info
    name: str = Field(..., description="Workspace name", min_length=1, max_length=100)
    slug: str = Field(..., description="URL-friendly workspace identifier")
    description: Optional[str] = Field(None, max_length=500)
    
    # Type and status
    workspace_type: WorkspaceType = Field(default=WorkspaceType.PRODUCTION)
    is_active: bool = Field(default=True)
    
    # Settings
    settings: WorkspaceSettings = Field(default_factory=WorkspaceSettings)
    
    # Resource limits (can override tenant defaults)
    max_investigations_per_day: Optional[int] = Field(None, description="Daily investigation limit")
    max_services_monitored: Optional[int] = Field(None, description="Max services to monitor")
    
    # Metadata
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)
    
    # Timestamps
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    created_by: Optional[str] = Field(None, description="Creator user ID")
    
    @field_validator('slug')
    @classmethod
    def validate_slug(cls, v: str) -> str:
        """Ensure slug is URL-friendly."""
        import re
        if not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$', v.lower()):
            raise ValueError('Slug must be lowercase alphanumeric with hyphens')
        return v.lower()
    
    @property
    def full_slug(self) -> str:
        """Full slug including tenant context."""
        return f"{self.tenant_id}/{self.slug}"


class Tenant(BaseModel):
    """
    A tenant (organization/account) in the multi-tenant system.
    
    Tenants are the top-level isolation boundary. All data, users,
    and resources belong to exactly one tenant.
    """
    
    id: str = Field(default_factory=generate_id, description="Unique tenant identifier")
    
    # Basic info
    name: str = Field(..., description="Organization name", min_length=1, max_length=200)
    slug: str = Field(..., description="URL-friendly tenant identifier")
    
    # Contact
    admin_email: str = Field(..., description="Primary admin email")
    billing_email: Optional[str] = Field(None, description="Billing contact email")
    
    # Status and tier
    status: TenantStatus = Field(default=TenantStatus.PENDING_ACTIVATION)
    tier: TenantTier = Field(default=TenantTier.FREE)
    
    # Settings
    settings: TenantSettings = Field(default_factory=TenantSettings)
    
    # Trial info
    trial_ends_at: Optional[datetime] = Field(None, description="Trial expiration date")
    
    # Subscription info
    subscription_id: Optional[str] = Field(None, description="External subscription ID")
    subscription_started_at: Optional[datetime] = None
    
    # Resource limits (based on tier)
    max_workspaces: int = Field(default=1, description="Maximum workspaces allowed")
    max_team_members: int = Field(default=5, description="Maximum team members")
    max_api_calls_per_hour: int = Field(default=1000, description="API rate limit")
    
    # Metadata
    metadata: dict[str, Any] = Field(default_factory=dict, description="Custom metadata")
    labels: dict[str, str] = Field(default_factory=dict)
    
    # Timestamps
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    activated_at: Optional[datetime] = None
    suspended_at: Optional[datetime] = None
    
    @field_validator('slug')
    @classmethod
    def validate_slug(cls, v: str) -> str:
        """Ensure slug is URL-friendly."""
        import re
        if not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$', v.lower()):
            raise ValueError('Slug must be lowercase alphanumeric with hyphens')
        return v.lower()
    
    @property
    def is_active(self) -> bool:
        """Check if tenant can use the system."""
        return self.status in (TenantStatus.ACTIVE, TenantStatus.TRIAL)
    
    @property
    def is_enterprise(self) -> bool:
        """Check if tenant has enterprise features."""
        return self.tier in (TenantTier.ENTERPRISE, TenantTier.CUSTOM)
    
    @property
    def is_trial(self) -> bool:
        """Check if tenant is on trial."""
        return self.status == TenantStatus.TRIAL
    
    @property
    def trial_days_remaining(self) -> Optional[int]:
        """Days remaining in trial."""
        if not self.is_trial or not self.trial_ends_at:
            return None
        delta = self.trial_ends_at - utcnow()
        return max(0, delta.days)
    
    def activate(self) -> None:
        """Activate the tenant."""
        self.status = TenantStatus.ACTIVE
        self.activated_at = utcnow()
        self.updated_at = utcnow()
    
    def suspend(self, reason: Optional[str] = None) -> None:
        """Suspend the tenant."""
        self.status = TenantStatus.SUSPENDED
        self.suspended_at = utcnow()
        self.updated_at = utcnow()
        if reason:
            self.metadata["suspension_reason"] = reason
    
    def upgrade_tier(self, new_tier: TenantTier) -> None:
        """Upgrade tenant to a new tier."""
        self.tier = new_tier
        self.updated_at = utcnow()
        
        # Update limits based on tier
        tier_limits = {
            TenantTier.FREE: {"workspaces": 1, "members": 5, "api_calls": 1000},
            TenantTier.STARTER: {"workspaces": 3, "members": 20, "api_calls": 10000},
            TenantTier.PROFESSIONAL: {"workspaces": 10, "members": 100, "api_calls": 100000},
            TenantTier.ENTERPRISE: {"workspaces": -1, "members": -1, "api_calls": -1},  # Unlimited
            TenantTier.CUSTOM: {"workspaces": -1, "members": -1, "api_calls": -1},
        }
        
        limits = tier_limits.get(new_tier, tier_limits[TenantTier.FREE])
        self.max_workspaces = limits["workspaces"]
        self.max_team_members = limits["members"]
        self.max_api_calls_per_hour = limits["api_calls"]
    
    def has_feature(self, feature: str) -> bool:
        """Check if tenant has a specific feature enabled."""
        # Enterprise gets all features
        if self.is_enterprise:
            return True
        return self.settings.features.get(feature, False)
