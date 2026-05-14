"""Tenant Manager for AutoSRE V2 Multi-Tenancy.

Provides comprehensive tenant lifecycle management including:
- Tenant creation, update, suspension, and deletion
- Tenant configuration and settings management
- Tenant status tracking and health monitoring
- Integration with billing and subscription systems
"""

from __future__ import annotations

import asyncio
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Awaitable
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

from autosre.utils.logging import get_logger

logger = get_logger(__name__)


class TenantStatus(str, Enum):
    """Tenant lifecycle status."""
    
    PENDING = "pending"  # Awaiting provisioning
    PROVISIONING = "provisioning"  # Being set up
    ACTIVE = "active"  # Fully operational
    SUSPENDED = "suspended"  # Temporarily disabled
    DEACTIVATED = "deactivated"  # Soft deleted
    ARCHIVED = "archived"  # Read-only archive
    DELETED = "deleted"  # Marked for hard deletion


class TenantTier(str, Enum):
    """Tenant subscription tiers with different capabilities."""
    
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"
    UNLIMITED = "unlimited"


class TenantFeature(str, Enum):
    """Feature flags for tenant capabilities."""
    
    BASIC_ALERTING = "basic_alerting"
    ADVANCED_ALERTING = "advanced_alerting"
    AI_INVESTIGATION = "ai_investigation"
    AI_REMEDIATION = "ai_remediation"
    CUSTOM_RUNBOOKS = "custom_runbooks"
    MULTI_CLUSTER = "multi_cluster"
    SSO = "sso"
    AUDIT_LOGS = "audit_logs"
    CUSTOM_INTEGRATIONS = "custom_integrations"
    PRIORITY_SUPPORT = "priority_support"
    SLA_REPORTING = "sla_reporting"
    DEDICATED_RESOURCES = "dedicated_resources"


# Tier feature mappings
TIER_FEATURES: Dict[TenantTier, set[TenantFeature]] = {
    TenantTier.FREE: {
        TenantFeature.BASIC_ALERTING,
    },
    TenantTier.STARTER: {
        TenantFeature.BASIC_ALERTING,
        TenantFeature.ADVANCED_ALERTING,
        TenantFeature.AI_INVESTIGATION,
        TenantFeature.CUSTOM_RUNBOOKS,
    },
    TenantTier.PROFESSIONAL: {
        TenantFeature.BASIC_ALERTING,
        TenantFeature.ADVANCED_ALERTING,
        TenantFeature.AI_INVESTIGATION,
        TenantFeature.AI_REMEDIATION,
        TenantFeature.CUSTOM_RUNBOOKS,
        TenantFeature.MULTI_CLUSTER,
        TenantFeature.AUDIT_LOGS,
    },
    TenantTier.ENTERPRISE: {
        TenantFeature.BASIC_ALERTING,
        TenantFeature.ADVANCED_ALERTING,
        TenantFeature.AI_INVESTIGATION,
        TenantFeature.AI_REMEDIATION,
        TenantFeature.CUSTOM_RUNBOOKS,
        TenantFeature.MULTI_CLUSTER,
        TenantFeature.SSO,
        TenantFeature.AUDIT_LOGS,
        TenantFeature.CUSTOM_INTEGRATIONS,
        TenantFeature.SLA_REPORTING,
        TenantFeature.PRIORITY_SUPPORT,
    },
    TenantTier.UNLIMITED: set(TenantFeature),
}


class TenantConfig(BaseModel):
    """Tenant-specific configuration settings."""
    
    # Resource limits
    max_users: int = Field(default=10, ge=1)
    max_clusters: int = Field(default=1, ge=1)
    max_alerts_per_day: int = Field(default=1000, ge=0)
    max_investigations_per_day: int = Field(default=100, ge=0)
    max_retention_days: int = Field(default=30, ge=1, le=365)
    max_runbooks: int = Field(default=50, ge=0)
    
    # AI settings
    llm_tokens_per_month: int = Field(default=100000, ge=0)
    max_llm_calls_per_investigation: int = Field(default=20, ge=1)
    
    # Feature flags (override tier defaults)
    feature_overrides: Dict[str, bool] = Field(default_factory=dict)
    
    # Integration settings
    allowed_integrations: List[str] = Field(default_factory=list)
    
    # Custom settings
    custom_settings: Dict[str, Any] = Field(default_factory=dict)
    
    # Security settings
    require_mfa: bool = False
    allowed_ip_ranges: List[str] = Field(default_factory=list)
    session_timeout_minutes: int = Field(default=60, ge=5, le=1440)
    
    # Notification settings
    notification_channels: List[str] = Field(default_factory=list)
    escalation_policy_id: Optional[str] = None
    
    def merge_with_tier(self, tier: TenantTier) -> "TenantConfig":
        """Create effective config by merging tier defaults."""
        tier_config = TIER_DEFAULT_CONFIG.get(tier, TenantConfig())
        
        # Create new config with tier defaults overridden by explicit values
        merged = self.model_copy()
        
        # Only use tier defaults for fields not explicitly set
        for field_name in self.model_fields:
            if getattr(self, field_name) == self.model_fields[field_name].default:
                tier_value = getattr(tier_config, field_name, None)
                if tier_value is not None:
                    setattr(merged, field_name, tier_value)
        
        return merged


# Default configurations per tier
TIER_DEFAULT_CONFIG: Dict[TenantTier, TenantConfig] = {
    TenantTier.FREE: TenantConfig(
        max_users=3,
        max_clusters=1,
        max_alerts_per_day=100,
        max_investigations_per_day=10,
        max_retention_days=7,
        max_runbooks=5,
        llm_tokens_per_month=10000,
    ),
    TenantTier.STARTER: TenantConfig(
        max_users=10,
        max_clusters=2,
        max_alerts_per_day=1000,
        max_investigations_per_day=100,
        max_retention_days=30,
        max_runbooks=50,
        llm_tokens_per_month=100000,
    ),
    TenantTier.PROFESSIONAL: TenantConfig(
        max_users=50,
        max_clusters=10,
        max_alerts_per_day=10000,
        max_investigations_per_day=500,
        max_retention_days=90,
        max_runbooks=200,
        llm_tokens_per_month=500000,
    ),
    TenantTier.ENTERPRISE: TenantConfig(
        max_users=500,
        max_clusters=100,
        max_alerts_per_day=100000,
        max_investigations_per_day=5000,
        max_retention_days=365,
        max_runbooks=1000,
        llm_tokens_per_month=5000000,
        require_mfa=True,
    ),
    TenantTier.UNLIMITED: TenantConfig(
        max_users=999999,
        max_clusters=999999,
        max_alerts_per_day=999999999,
        max_investigations_per_day=999999999,
        max_retention_days=365,
        max_runbooks=999999,
        llm_tokens_per_month=999999999,
    ),
}


class TenantContact(BaseModel):
    """Contact information for a tenant."""
    
    name: str
    email: str
    phone: Optional[str] = None
    role: str = "owner"


class TenantBilling(BaseModel):
    """Billing information for a tenant."""
    
    billing_email: str
    billing_address: Optional[str] = None
    payment_method_id: Optional[str] = None
    subscription_id: Optional[str] = None
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    next_invoice_date: Optional[datetime] = None
    balance_cents: int = 0


class Tenant(BaseModel):
    """Core tenant model representing an isolated organization."""
    
    # Identity
    id: str = Field(default_factory=lambda: str(uuid4()))
    slug: str = Field(..., min_length=3, max_length=63, pattern=r'^[a-z0-9][a-z0-9-]*[a-z0-9]$')
    name: str = Field(..., min_length=1, max_length=256)
    display_name: Optional[str] = None
    
    # Status
    status: TenantStatus = TenantStatus.PENDING
    tier: TenantTier = TenantTier.FREE
    
    # Configuration
    config: TenantConfig = Field(default_factory=TenantConfig)
    
    # Contact information
    primary_contact: Optional[TenantContact] = None
    technical_contact: Optional[TenantContact] = None
    
    # Billing
    billing: Optional[TenantBilling] = None
    
    # Database/resource identifiers
    database_schema: Optional[str] = None
    resource_namespace: Optional[str] = None
    
    # API access
    api_key_hash: Optional[str] = None
    api_key_prefix: Optional[str] = None  # First 8 chars for display
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    
    # Audit
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: Optional[str] = None
    suspended_at: Optional[datetime] = None
    suspended_reason: Optional[str] = None
    deleted_at: Optional[datetime] = None
    
    @field_validator('slug')
    @classmethod
    def validate_slug(cls, v: str) -> str:
        """Ensure slug is lowercase and valid."""
        v = v.lower()
        reserved_slugs = {'admin', 'api', 'system', 'internal', 'public', 'default'}
        if v in reserved_slugs:
            raise ValueError(f"Slug '{v}' is reserved")
        return v
    
    @model_validator(mode='after')
    def set_defaults(self) -> 'Tenant':
        """Set default values based on other fields."""
        if self.display_name is None:
            self.display_name = self.name
        if self.database_schema is None:
            self.database_schema = f"tenant_{self.slug.replace('-', '_')}"
        if self.resource_namespace is None:
            self.resource_namespace = f"autosre-{self.slug}"
        return self
    
    def has_feature(self, feature: TenantFeature) -> bool:
        """Check if tenant has access to a feature."""
        # Check explicit overrides first
        if feature.value in self.config.feature_overrides:
            return self.config.feature_overrides[feature.value]
        
        # Fall back to tier features
        return feature in TIER_FEATURES.get(self.tier, set())
    
    def is_active(self) -> bool:
        """Check if tenant is in an active state."""
        return self.status == TenantStatus.ACTIVE
    
    def can_receive_alerts(self) -> bool:
        """Check if tenant can receive and process alerts."""
        return self.status in (TenantStatus.ACTIVE, TenantStatus.PROVISIONING)
    
    def effective_config(self) -> TenantConfig:
        """Get effective configuration merged with tier defaults."""
        return self.config.merge_with_tier(self.tier)


class TenantCreateRequest(BaseModel):
    """Request model for creating a new tenant."""
    
    slug: str = Field(..., min_length=3, max_length=63)
    name: str = Field(..., min_length=1, max_length=256)
    tier: TenantTier = TenantTier.FREE
    primary_contact: TenantContact
    config: Optional[TenantConfig] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)


class TenantUpdateRequest(BaseModel):
    """Request model for updating a tenant."""
    
    name: Optional[str] = None
    display_name: Optional[str] = None
    tier: Optional[TenantTier] = None
    config: Optional[TenantConfig] = None
    primary_contact: Optional[TenantContact] = None
    technical_contact: Optional[TenantContact] = None
    metadata: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None


class TenantListFilter(BaseModel):
    """Filter options for listing tenants."""
    
    status: Optional[List[TenantStatus]] = None
    tier: Optional[List[TenantTier]] = None
    tags: Optional[List[str]] = None
    search: Optional[str] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=100)


class TenantProvisioningStep(BaseModel):
    """A step in the tenant provisioning process."""
    
    name: str
    status: str = "pending"  # pending, running, completed, failed
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


class TenantProvisioningState(BaseModel):
    """State of tenant provisioning process."""
    
    tenant_id: str
    steps: List[TenantProvisioningStep] = Field(default_factory=list)
    current_step: int = 0
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    
    def is_complete(self) -> bool:
        """Check if provisioning is complete."""
        return all(step.status == "completed" for step in self.steps)
    
    def has_failed(self) -> bool:
        """Check if provisioning has failed."""
        return any(step.status == "failed" for step in self.steps)


# Type for provisioning hooks
ProvisioningHook = Callable[[Tenant, TenantProvisioningState], Awaitable[None]]


class TenantManagerError(Exception):
    """Base exception for tenant management errors."""
    
    def __init__(self, message: str, tenant_id: Optional[str] = None):
        super().__init__(message)
        self.tenant_id = tenant_id


class TenantNotFoundError(TenantManagerError):
    """Tenant not found."""
    pass


class TenantAlreadyExistsError(TenantManagerError):
    """Tenant with slug already exists."""
    pass


class TenantProvisioningError(TenantManagerError):
    """Error during tenant provisioning."""
    pass


class TenantOperationError(TenantManagerError):
    """Error during tenant operation."""
    pass


class TenantManager:
    """
    Manages tenant lifecycle and operations.
    
    Provides comprehensive tenant management including:
    - CRUD operations with validation
    - Asynchronous provisioning with hooks
    - Status management and transitions
    - API key generation and management
    - Integration with external systems
    
    Example:
        manager = TenantManager(repository=tenant_repo)
        
        # Create tenant
        tenant = await manager.create_tenant(TenantCreateRequest(
            slug="acme-corp",
            name="Acme Corporation",
            tier=TenantTier.PROFESSIONAL,
            primary_contact=TenantContact(
                name="John Doe",
                email="john@acme.com"
            ),
        ))
        
        # Generate API key
        key = await manager.generate_api_key(tenant.id)
        
        # Provision resources
        await manager.provision_tenant(tenant.id)
    """
    
    def __init__(
        self,
        repository: Optional["TenantRepository"] = None,
        provisioning_hooks: Optional[List[ProvisioningHook]] = None,
        deprovisioning_hooks: Optional[List[ProvisioningHook]] = None,
    ):
        """Initialize TenantManager.
        
        Args:
            repository: Storage backend for tenants (optional, uses in-memory if not provided)
            provisioning_hooks: Hooks to run during provisioning
            deprovisioning_hooks: Hooks to run during deprovisioning
        """
        self._repository = repository
        self._tenants: Dict[str, Tenant] = {}  # In-memory fallback
        self._provisioning_hooks = provisioning_hooks or []
        self._deprovisioning_hooks = deprovisioning_hooks or []
        self._provisioning_states: Dict[str, TenantProvisioningState] = {}
        self._lock = asyncio.Lock()
    
    async def create_tenant(
        self,
        request: TenantCreateRequest,
        created_by: Optional[str] = None,
        auto_provision: bool = True,
    ) -> Tenant:
        """Create a new tenant.
        
        Args:
            request: Tenant creation request
            created_by: User ID of creator
            auto_provision: Whether to automatically provision resources
            
        Returns:
            Created tenant
            
        Raises:
            TenantAlreadyExistsError: If tenant with slug already exists
            TenantProvisioningError: If auto-provisioning fails
        """
        async with self._lock:
            # Check for existing tenant
            existing = await self._get_by_slug(request.slug)
            if existing:
                raise TenantAlreadyExistsError(
                    f"Tenant with slug '{request.slug}' already exists",
                    tenant_id=existing.id,
                )
            
            # Create tenant
            tenant = Tenant(
                slug=request.slug,
                name=request.name,
                tier=request.tier,
                config=request.config or TenantConfig(),
                primary_contact=request.primary_contact,
                metadata=request.metadata,
                tags=request.tags,
                created_by=created_by,
            )
            
            # Store tenant
            await self._save(tenant)
            
            logger.info(
                "Created tenant",
                tenant_id=tenant.id,
                slug=tenant.slug,
                tier=tenant.tier.value,
            )
        
        # Provision if requested (outside lock to allow parallel provisioning)
        if auto_provision:
            await self.provision_tenant(tenant.id)
        
        return tenant
    
    async def get_tenant(self, tenant_id: str) -> Tenant:
        """Get tenant by ID.
        
        Args:
            tenant_id: Tenant ID
            
        Returns:
            Tenant
            
        Raises:
            TenantNotFoundError: If tenant not found
        """
        tenant = await self._get_by_id(tenant_id)
        if not tenant:
            raise TenantNotFoundError(
                f"Tenant '{tenant_id}' not found",
                tenant_id=tenant_id,
            )
        return tenant
    
    async def get_tenant_by_slug(self, slug: str) -> Tenant:
        """Get tenant by slug.
        
        Args:
            slug: Tenant slug
            
        Returns:
            Tenant
            
        Raises:
            TenantNotFoundError: If tenant not found
        """
        tenant = await self._get_by_slug(slug)
        if not tenant:
            raise TenantNotFoundError(f"Tenant with slug '{slug}' not found")
        return tenant
    
    async def list_tenants(
        self,
        filters: Optional[TenantListFilter] = None,
    ) -> tuple[List[Tenant], int]:
        """List tenants with optional filters.
        
        Args:
            filters: Optional filters
            
        Returns:
            Tuple of (tenants, total_count)
        """
        filters = filters or TenantListFilter()
        
        if self._repository:
            return await self._repository.list(filters)
        
        # In-memory filtering
        tenants = list(self._tenants.values())
        
        # Apply filters
        if filters.status:
            tenants = [t for t in tenants if t.status in filters.status]
        if filters.tier:
            tenants = [t for t in tenants if t.tier in filters.tier]
        if filters.tags:
            tenants = [t for t in tenants if any(tag in t.tags for tag in filters.tags)]
        if filters.search:
            search = filters.search.lower()
            tenants = [
                t for t in tenants
                if search in t.name.lower() or search in t.slug.lower()
            ]
        if filters.created_after:
            tenants = [t for t in tenants if t.created_at >= filters.created_after]
        if filters.created_before:
            tenants = [t for t in tenants if t.created_at <= filters.created_before]
        
        total = len(tenants)
        
        # Apply pagination
        tenants = tenants[filters.offset:filters.offset + filters.limit]
        
        return tenants, total
    
    async def update_tenant(
        self,
        tenant_id: str,
        request: TenantUpdateRequest,
        updated_by: Optional[str] = None,
    ) -> Tenant:
        """Update tenant settings.
        
        Args:
            tenant_id: Tenant ID
            request: Update request
            updated_by: User ID of updater
            
        Returns:
            Updated tenant
        """
        async with self._lock:
            tenant = await self.get_tenant(tenant_id)
            
            # Track if tier changed for potential resource adjustments
            tier_changed = request.tier is not None and request.tier != tenant.tier
            
            # Apply updates
            if request.name is not None:
                tenant.name = request.name
            if request.display_name is not None:
                tenant.display_name = request.display_name
            if request.tier is not None:
                tenant.tier = request.tier
            if request.config is not None:
                tenant.config = request.config
            if request.primary_contact is not None:
                tenant.primary_contact = request.primary_contact
            if request.technical_contact is not None:
                tenant.technical_contact = request.technical_contact
            if request.metadata is not None:
                tenant.metadata.update(request.metadata)
            if request.tags is not None:
                tenant.tags = request.tags
            
            tenant.updated_at = datetime.now(timezone.utc)
            
            await self._save(tenant)
            
            logger.info(
                "Updated tenant",
                tenant_id=tenant.id,
                tier_changed=tier_changed,
                updated_by=updated_by,
            )
            
            return tenant
    
    async def suspend_tenant(
        self,
        tenant_id: str,
        reason: str,
        suspended_by: Optional[str] = None,
    ) -> Tenant:
        """Suspend a tenant.
        
        Suspended tenants cannot receive new alerts or start investigations,
        but existing data remains accessible for review.
        
        Args:
            tenant_id: Tenant ID
            reason: Reason for suspension
            suspended_by: User ID of suspender
            
        Returns:
            Updated tenant
        """
        async with self._lock:
            tenant = await self.get_tenant(tenant_id)
            
            if tenant.status == TenantStatus.SUSPENDED:
                logger.warning("Tenant already suspended", tenant_id=tenant_id)
                return tenant
            
            if tenant.status not in (TenantStatus.ACTIVE, TenantStatus.PROVISIONING):
                raise TenantOperationError(
                    f"Cannot suspend tenant in status '{tenant.status.value}'",
                    tenant_id=tenant_id,
                )
            
            tenant.status = TenantStatus.SUSPENDED
            tenant.suspended_at = datetime.now(timezone.utc)
            tenant.suspended_reason = reason
            tenant.updated_at = datetime.now(timezone.utc)
            
            await self._save(tenant)
            
            logger.info(
                "Suspended tenant",
                tenant_id=tenant.id,
                reason=reason,
                suspended_by=suspended_by,
            )
            
            return tenant
    
    async def reactivate_tenant(
        self,
        tenant_id: str,
        reactivated_by: Optional[str] = None,
    ) -> Tenant:
        """Reactivate a suspended tenant.
        
        Args:
            tenant_id: Tenant ID
            reactivated_by: User ID of reactivator
            
        Returns:
            Updated tenant
        """
        async with self._lock:
            tenant = await self.get_tenant(tenant_id)
            
            if tenant.status != TenantStatus.SUSPENDED:
                raise TenantOperationError(
                    f"Can only reactivate suspended tenants, current status: {tenant.status.value}",
                    tenant_id=tenant_id,
                )
            
            tenant.status = TenantStatus.ACTIVE
            tenant.suspended_at = None
            tenant.suspended_reason = None
            tenant.updated_at = datetime.now(timezone.utc)
            
            await self._save(tenant)
            
            logger.info(
                "Reactivated tenant",
                tenant_id=tenant.id,
                reactivated_by=reactivated_by,
            )
            
            return tenant
    
    async def delete_tenant(
        self,
        tenant_id: str,
        deleted_by: Optional[str] = None,
        hard_delete: bool = False,
        grace_period_days: int = 30,
    ) -> Tenant:
        """Delete a tenant.
        
        By default, performs a soft delete with grace period for recovery.
        Use hard_delete=True to immediately schedule permanent deletion.
        
        Args:
            tenant_id: Tenant ID
            deleted_by: User ID of deleter
            hard_delete: Whether to hard delete immediately
            grace_period_days: Days before hard deletion (for soft delete)
            
        Returns:
            Updated tenant
        """
        async with self._lock:
            tenant = await self.get_tenant(tenant_id)
            
            if tenant.status == TenantStatus.DELETED:
                raise TenantOperationError(
                    "Tenant already deleted",
                    tenant_id=tenant_id,
                )
            
            # Run deprovisioning hooks
            if tenant.status == TenantStatus.ACTIVE:
                await self._run_deprovisioning(tenant)
            
            if hard_delete:
                tenant.status = TenantStatus.DELETED
            else:
                tenant.status = TenantStatus.DEACTIVATED
            
            tenant.deleted_at = datetime.now(timezone.utc)
            tenant.updated_at = datetime.now(timezone.utc)
            
            await self._save(tenant)
            
            logger.info(
                "Deleted tenant",
                tenant_id=tenant.id,
                hard_delete=hard_delete,
                deleted_by=deleted_by,
            )
            
            return tenant
    
    async def provision_tenant(self, tenant_id: str) -> TenantProvisioningState:
        """Provision resources for a tenant.
        
        Runs through provisioning steps including:
        - Database schema creation
        - Resource namespace setup
        - Default configuration
        - Integration setup
        - Custom provisioning hooks
        
        Args:
            tenant_id: Tenant ID
            
        Returns:
            Provisioning state
        """
        tenant = await self.get_tenant(tenant_id)
        
        if tenant.status not in (TenantStatus.PENDING, TenantStatus.PROVISIONING):
            raise TenantOperationError(
                f"Cannot provision tenant in status '{tenant.status.value}'",
                tenant_id=tenant_id,
            )
        
        # Initialize provisioning state
        state = TenantProvisioningState(
            tenant_id=tenant_id,
            steps=[
                TenantProvisioningStep(name="Initialize database schema"),
                TenantProvisioningStep(name="Create resource namespace"),
                TenantProvisioningStep(name="Configure default settings"),
                TenantProvisioningStep(name="Setup integrations"),
                *[
                    TenantProvisioningStep(name=f"Custom hook: {hook.__name__}")
                    for hook in self._provisioning_hooks
                ],
                TenantProvisioningStep(name="Finalize provisioning"),
            ],
        )
        self._provisioning_states[tenant_id] = state
        
        # Update tenant status
        tenant.status = TenantStatus.PROVISIONING
        await self._save(tenant)
        
        try:
            # Step 1: Database schema
            await self._run_step(state, 0, self._provision_database_schema, tenant)
            
            # Step 2: Resource namespace
            await self._run_step(state, 1, self._provision_resource_namespace, tenant)
            
            # Step 3: Default settings
            await self._run_step(state, 2, self._provision_default_settings, tenant)
            
            # Step 4: Integrations
            await self._run_step(state, 3, self._provision_integrations, tenant)
            
            # Custom hooks
            for i, hook in enumerate(self._provisioning_hooks):
                await self._run_step(state, 4 + i, hook, tenant, state)
            
            # Final step
            final_step_index = len(state.steps) - 1
            await self._run_step(state, final_step_index, self._finalize_provisioning, tenant)
            
            # Mark complete
            state.completed_at = datetime.now(timezone.utc)
            tenant.status = TenantStatus.ACTIVE
            await self._save(tenant)
            
            logger.info(
                "Tenant provisioning complete",
                tenant_id=tenant_id,
                duration_seconds=(state.completed_at - state.started_at).total_seconds(),
            )
            
        except Exception as e:
            state.error = str(e)
            tenant.status = TenantStatus.PENDING  # Reset for retry
            await self._save(tenant)
            
            logger.error(
                "Tenant provisioning failed",
                tenant_id=tenant_id,
                error=str(e),
            )
            raise TenantProvisioningError(str(e), tenant_id=tenant_id) from e
        
        return state
    
    async def get_provisioning_state(
        self,
        tenant_id: str,
    ) -> Optional[TenantProvisioningState]:
        """Get current provisioning state for a tenant.
        
        Args:
            tenant_id: Tenant ID
            
        Returns:
            Provisioning state or None
        """
        return self._provisioning_states.get(tenant_id)
    
    async def generate_api_key(
        self,
        tenant_id: str,
        generated_by: Optional[str] = None,
    ) -> str:
        """Generate a new API key for a tenant.
        
        The full key is returned only once. Only the hash is stored.
        
        Args:
            tenant_id: Tenant ID
            generated_by: User who generated the key
            
        Returns:
            The full API key (store securely, shown only once)
        """
        async with self._lock:
            tenant = await self.get_tenant(tenant_id)
            
            # Generate key with tenant prefix
            raw_key = secrets.token_urlsafe(32)
            api_key = f"asr_{tenant.slug}_{raw_key}"
            
            # Store hash and prefix
            tenant.api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
            tenant.api_key_prefix = api_key[:12]
            tenant.updated_at = datetime.now(timezone.utc)
            
            await self._save(tenant)
            
            logger.info(
                "Generated API key for tenant",
                tenant_id=tenant_id,
                key_prefix=tenant.api_key_prefix,
                generated_by=generated_by,
            )
            
            return api_key
    
    async def validate_api_key(self, api_key: str) -> Optional[Tenant]:
        """Validate an API key and return the associated tenant.
        
        Args:
            api_key: The API key to validate
            
        Returns:
            Tenant if valid, None otherwise
        """
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        # Search for tenant with matching hash
        if self._repository:
            return await self._repository.get_by_api_key_hash(key_hash)
        
        for tenant in self._tenants.values():
            if tenant.api_key_hash == key_hash and tenant.is_active():
                return tenant
        
        return None
    
    async def revoke_api_key(
        self,
        tenant_id: str,
        revoked_by: Optional[str] = None,
    ) -> None:
        """Revoke the current API key for a tenant.
        
        Args:
            tenant_id: Tenant ID
            revoked_by: User who revoked the key
        """
        async with self._lock:
            tenant = await self.get_tenant(tenant_id)
            
            tenant.api_key_hash = None
            tenant.api_key_prefix = None
            tenant.updated_at = datetime.now(timezone.utc)
            
            await self._save(tenant)
            
            logger.info(
                "Revoked API key for tenant",
                tenant_id=tenant_id,
                revoked_by=revoked_by,
            )
    
    # Private methods
    
    async def _get_by_id(self, tenant_id: str) -> Optional[Tenant]:
        """Get tenant by ID from storage."""
        if self._repository:
            return await self._repository.get(tenant_id)
        return self._tenants.get(tenant_id)
    
    async def _get_by_slug(self, slug: str) -> Optional[Tenant]:
        """Get tenant by slug from storage."""
        if self._repository:
            return await self._repository.get_by_slug(slug)
        
        for tenant in self._tenants.values():
            if tenant.slug == slug:
                return tenant
        return None
    
    async def _save(self, tenant: Tenant) -> None:
        """Save tenant to storage."""
        if self._repository:
            await self._repository.save(tenant)
        else:
            self._tenants[tenant.id] = tenant
    
    async def _run_step(
        self,
        state: TenantProvisioningState,
        step_index: int,
        handler: Callable,
        *args,
        **kwargs,
    ) -> None:
        """Run a provisioning step with state tracking."""
        step = state.steps[step_index]
        step.status = "running"
        step.started_at = datetime.now(timezone.utc)
        state.current_step = step_index
        
        try:
            await handler(*args, **kwargs)
            step.status = "completed"
            step.completed_at = datetime.now(timezone.utc)
        except Exception as e:
            step.status = "failed"
            step.error = str(e)
            step.completed_at = datetime.now(timezone.utc)
            raise
    
    async def _provision_database_schema(self, tenant: Tenant) -> None:
        """Create database schema for tenant."""
        # In production, this would create actual database schema
        logger.debug(
            "Creating database schema",
            tenant_id=tenant.id,
            schema=tenant.database_schema,
        )
        await asyncio.sleep(0.1)  # Simulate work
    
    async def _provision_resource_namespace(self, tenant: Tenant) -> None:
        """Create resource namespace for tenant."""
        logger.debug(
            "Creating resource namespace",
            tenant_id=tenant.id,
            namespace=tenant.resource_namespace,
        )
        await asyncio.sleep(0.1)
    
    async def _provision_default_settings(self, tenant: Tenant) -> None:
        """Apply default settings for tenant."""
        logger.debug(
            "Applying default settings",
            tenant_id=tenant.id,
            tier=tenant.tier.value,
        )
        await asyncio.sleep(0.1)
    
    async def _provision_integrations(self, tenant: Tenant) -> None:
        """Setup default integrations for tenant."""
        logger.debug(
            "Setting up integrations",
            tenant_id=tenant.id,
        )
        await asyncio.sleep(0.1)
    
    async def _finalize_provisioning(self, tenant: Tenant) -> None:
        """Finalize tenant provisioning."""
        logger.debug(
            "Finalizing provisioning",
            tenant_id=tenant.id,
        )
        await asyncio.sleep(0.1)
    
    async def _run_deprovisioning(self, tenant: Tenant) -> None:
        """Run deprovisioning hooks."""
        for hook in self._deprovisioning_hooks:
            try:
                await hook(tenant, TenantProvisioningState(tenant_id=tenant.id))
            except Exception as e:
                logger.error(
                    "Deprovisioning hook failed",
                    tenant_id=tenant.id,
                    hook=hook.__name__,
                    error=str(e),
                )


class TenantRepository:
    """Abstract repository interface for tenant storage.
    
    Implementations should provide persistent storage for tenants.
    """
    
    async def get(self, tenant_id: str) -> Optional[Tenant]:
        """Get tenant by ID."""
        raise NotImplementedError
    
    async def get_by_slug(self, slug: str) -> Optional[Tenant]:
        """Get tenant by slug."""
        raise NotImplementedError
    
    async def get_by_api_key_hash(self, key_hash: str) -> Optional[Tenant]:
        """Get tenant by API key hash."""
        raise NotImplementedError
    
    async def save(self, tenant: Tenant) -> None:
        """Save tenant."""
        raise NotImplementedError
    
    async def delete(self, tenant_id: str) -> None:
        """Delete tenant."""
        raise NotImplementedError
    
    async def list(
        self,
        filters: TenantListFilter,
    ) -> tuple[List[Tenant], int]:
        """List tenants with filters."""
        raise NotImplementedError
