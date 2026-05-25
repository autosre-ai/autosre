# Multi-Tenancy Guide

This guide covers AutoSRE's enterprise-grade multi-tenancy support, enabling SaaS deployments with complete tenant isolation, resource quotas, and billing.

## Overview

AutoSRE's multi-tenancy architecture provides:

- **Tenant Isolation**: Complete data separation between organizations
- **Workspace Management**: Multiple environments per tenant (prod, staging, dev)
- **Team Access Control**: Role-based access within tenants
- **Resource Quotas**: Per-tenant limits on usage
- **Usage Tracking & Billing**: Metered billing for SaaS deployments

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Tenant A                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │ Production  │  │  Staging    │  │ Development │          │
│  │  Workspace  │  │  Workspace  │  │  Workspace  │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
│  ┌─────────────────────────────────────────────────┐        │
│  │                    Teams                         │        │
│  │   SRE Team  │  Platform Team  │  Developers     │        │
│  └─────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Add Middleware to FastAPI

```python
from fastapi import FastAPI
from autosre.tenancy import (
    TenantMiddleware,
    HeaderBasedResolver,
    QuotaManager,
)

app = FastAPI()

# Configure tenant resolution
resolver = HeaderBasedResolver(
    tenant_store=my_tenant_store,
    workspace_store=my_workspace_store,
)

# Configure quota management
quota_manager = QuotaManager()

# Add middleware
app.add_middleware(
    TenantMiddleware,
    resolver=resolver,
    quota_manager=quota_manager,
    require_tenant=True,
    exclude_paths=["/health", "/api/docs"],
)
```

### 2. Access Tenant Context in Routes

```python
from fastapi import Depends
from autosre.tenancy import TenantContextDep, get_current_tenant

@app.get("/investigations")
async def list_investigations(ctx: TenantContextDep):
    # All queries automatically scoped to tenant
    return await investigation_store.list(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
    )
```

### 3. Apply Data Isolation

```python
from autosre.tenancy import TenantIsolation, IsolationLevel

class InvestigationStore:
    def __init__(self):
        self.isolation = TenantIsolation(
            isolation_level=IsolationLevel.WORKSPACE,
        )
    
    async def list(self, **filters) -> list[Investigation]:
        # Automatically adds tenant_id and workspace_id filters
        scoped_filters = self.isolation.scope_query(filters)
        return await self.db.query(scoped_filters)
    
    async def create(self, data: dict) -> Investigation:
        # Automatically sets tenant_id and workspace_id
        scoped_data = self.isolation.validate_create(data)
        return await self.db.insert(scoped_data)
```

## Models

### Tenant

Top-level organization account with subscription and limits.

```python
from autosre.tenancy import Tenant, TenantTier, TenantStatus

tenant = Tenant(
    name="Acme Corp",
    slug="acme-corp",
    admin_email="admin@acme.com",
    tier=TenantTier.PROFESSIONAL,
    status=TenantStatus.ACTIVE,
)

# Upgrade tier (updates limits automatically)
tenant.upgrade_tier(TenantTier.ENTERPRISE)

# Check features
if tenant.has_feature("auto_remediation"):
    # Enable automated fixes
    pass
```

### Workspace

Isolated environment within a tenant.

```python
from autosre.tenancy import Workspace, WorkspaceType

workspace = Workspace(
    tenant_id=tenant.id,
    name="Production",
    slug="production",
    workspace_type=WorkspaceType.PRODUCTION,
)

# Configure workspace-specific settings
workspace.settings.integrations["pagerduty"] = {
    "api_key": "xxx",
    "service_id": "yyy",
}
```

### Team

Group of users with shared access permissions.

```python
from autosre.tenancy import Team, TeamRole

team = Team(
    tenant_id=tenant.id,
    name="SRE Team",
    slug="sre-team",
    workspace_ids=[workspace.id],
)

# Add team member
team.add_member(
    user_id="user-123",
    email="engineer@acme.com",
    role=TeamRole.MEMBER,
)

# Check permissions
if team.has_permission("user-123", TeamRole.ADMIN):
    # User can manage team
    pass
```

## Tenant Tiers

| Feature | Free | Starter | Professional | Enterprise |
|---------|------|---------|--------------|------------|
| Workspaces | 1 | 3 | 10 | Unlimited |
| Team Members | 5 | 20 | 100 | Unlimited |
| Investigations/Day | 10 | 50 | 200 | Unlimited |
| API Calls/Hour | 1K | 10K | 100K | Unlimited |
| Data Retention | 30d | 90d | 180d | 365d |
| SSO | - | - | ✓ | ✓ |
| Custom Branding | - | - | - | ✓ |
| SLA | - | - | 99.9% | 99.99% |

## Data Isolation

### Isolation Levels

```python
from autosre.tenancy import IsolationLevel

# Tenant level - all tenant data in one pool
isolation = TenantIsolation(level=IsolationLevel.TENANT)

# Workspace level - data separated by workspace
isolation = TenantIsolation(level=IsolationLevel.WORKSPACE)

# Team level - data visible only to team members
isolation = TenantIsolation(level=IsolationLevel.TEAM)
```

### Context Manager

```python
from autosre.tenancy import tenant_context, TenantContext

# Create context
ctx = TenantContext(
    tenant=tenant,
    workspace=workspace,
    team=team,
    user_id="user-123",
    user_role=TeamRole.MEMBER,
)

# Use context manager
with tenant_context(ctx):
    # All operations scoped to this tenant
    data = await store.list_all()
```

### Cross-Tenant Access Prevention

```python
from autosre.tenancy import (
    TenantIsolation,
    IsolationPolicy,
    CrossTenantAccessError,
)

isolation = TenantIsolation(
    isolation_level=IsolationLevel.WORKSPACE,
    policy=IsolationPolicy.STRICT,  # Raises on violation
)

try:
    # This will raise if resource belongs to different tenant
    isolation.validate_access(
        resource_tenant_id="tenant-456",  # Different tenant!
    )
except CrossTenantAccessError as e:
    logger.warning(f"Blocked: {e}")
```

## Resource Quotas

### Quota Types

```python
from autosre.tenancy import QuotaType

# Investigation limits
QuotaType.INVESTIGATIONS_PER_DAY
QuotaType.CONCURRENT_INVESTIGATIONS

# API limits
QuotaType.API_CALLS_PER_HOUR
QuotaType.API_CALLS_PER_DAY

# Resource limits
QuotaType.WORKSPACES
QuotaType.TEAM_MEMBERS
QuotaType.SERVICES_MONITORED

# LLM limits
QuotaType.LLM_TOKENS_PER_DAY
QuotaType.LLM_TOKENS_PER_MONTH
```

### Checking and Consuming Quotas

```python
from autosre.tenancy import QuotaManager, QuotaExceededError

quota_manager = QuotaManager()

# Check before operation
try:
    await quota_manager.check_quota(
        tenant=tenant,
        quota_type=QuotaType.INVESTIGATIONS_PER_DAY,
        requested=1,
    )
    
    # Perform operation
    investigation = await start_investigation(alert)
    
    # Consume quota after success
    await quota_manager.consume_quota(
        tenant=tenant,
        quota_type=QuotaType.INVESTIGATIONS_PER_DAY,
    )
except QuotaExceededError as e:
    return {"error": "quota_exceeded", "limit": e.limit}
```

### Rate Limiting

```python
from autosre.tenancy import RateLimiter, RateLimitConfig

# Configure rate limits
config = RateLimitConfig(
    requests_per_second=100.0,
    burst_size=200,
    per_tenant=True,
    per_endpoint=True,
)

limiter = RateLimiter(config)

# Check rate limit
if await limiter.acquire(tenant.id, endpoint="/api/investigate"):
    # Process request
    pass
else:
    # Rate limited
    retry_after = limiter.get_retry_after(tenant.id, endpoint="/api/investigate")
    return Response(status_code=429, headers={"Retry-After": str(retry_after)})
```

### Custom Limits

```python
# Override default limits for enterprise deals
quota_manager.set_custom_limit(
    tenant_id="enterprise-customer",
    quota_type=QuotaType.INVESTIGATIONS_PER_DAY,
    limit=10000,
)
```

## Usage Tracking & Billing

### Track Usage Events

```python
from autosre.tenancy import UsageTracker, UsageMetric
from decimal import Decimal

tracker = UsageTracker()

# Track investigation
await tracker.track(
    tenant_id=tenant.id,
    metric=UsageMetric.INVESTIGATION_COMPLETED,
    workspace_id=workspace.id,
    resource_id=investigation.id,
)

# Track LLM usage
await tracker.track(
    tenant_id=tenant.id,
    metric=UsageMetric.LLM_TOTAL_TOKENS,
    quantity=Decimal("1500"),
    metadata={"model": "gpt-4", "investigation_id": inv.id},
)
```

### Generate Invoices

```python
from autosre.tenancy import BillingService
from datetime import datetime

billing = BillingService(usage_tracker=tracker)

# Generate monthly invoice
invoice = await billing.generate_invoice(
    tenant=tenant,
    period_start=datetime(2024, 1, 1),
    period_end=datetime(2024, 2, 1),
)

print(f"Invoice total: ${invoice.total}")
for item in invoice.line_items:
    print(f"  {item.description}: ${item.total}")
```

### Billing Status

```python
# Get current billing status with projections
status = await billing.get_current_billing_status(tenant)

print(f"Current usage: {status['current_usage']}")
print(f"Projected month end: {status['projected_usage']}")
print(f"Projected overages: ${status['projected_overages']}")
```

## FastAPI Integration

### Middleware Configuration

```python
from autosre.tenancy import TenantMiddleware, HeaderBasedResolver

# Full configuration
app.add_middleware(
    TenantMiddleware,
    resolver=HeaderBasedResolver(
        tenant_store=tenant_store,
        workspace_store=workspace_store,
        team_store=team_store,
    ),
    quota_manager=QuotaManager(
        alert_callback=send_quota_alert,
    ),
    require_tenant=True,
    exclude_paths=["/health", "/api/docs", "/api/redoc"],
)
```

### Route Dependencies

```python
from autosre.tenancy import (
    TenantContextDep,
    require_tenant,
    require_workspace,
    require_team_role,
    TeamRole,
)

# Inject tenant context
@app.get("/data")
async def get_data(ctx: TenantContextDep):
    return {"tenant": ctx.tenant_id}

# Require specific context
@app.post("/actions")
@require_workspace
async def run_action():
    ctx = get_current_tenant()
    # workspace is guaranteed to exist
    pass

# Require role
@app.delete("/workspace/{id}")
@require_team_role(TeamRole.ADMIN)
async def delete_workspace(id: str):
    # Only admins can delete
    pass
```

### JWT-Based Resolution

```python
from autosre.tenancy import JWTBasedResolver

def decode_jwt(token: str) -> dict:
    # Your JWT decoding logic
    return jwt.decode(token, key, algorithms=["RS256"])

resolver = JWTBasedResolver(
    jwt_decoder=decode_jwt,
    tenant_store=tenant_store,
)

app.add_middleware(TenantMiddleware, resolver=resolver)
```

## Security Best Practices

### 1. Always Use Isolation Layer

```python
# WRONG - direct database access
async def get_investigations():
    return await db.query("SELECT * FROM investigations")

# RIGHT - use isolation layer
async def get_investigations():
    filters = self.isolation.scope_query({})
    return await db.query(
        "SELECT * FROM investigations WHERE tenant_id = :tenant_id",
        filters
    )
```

### 2. Validate Cross-Tenant Access

```python
# Before accessing any shared resource
try:
    self.isolation.validate_access(
        resource_tenant_id=resource.tenant_id,
        resource_workspace_id=resource.workspace_id,
    )
except CrossTenantAccessError:
    raise HTTPException(403, "Access denied")
```

### 3. Audit Sensitive Operations

```python
from autosre.tenancy import IsolationPolicy

# Use audit mode for debugging cross-tenant access
isolation = TenantIsolation(
    policy=IsolationPolicy.AUDIT,
    audit_callback=lambda src, tgt, res: logger.warning(
        f"Cross-tenant access: {src} -> {tgt} ({res})"
    ),
)
```

### 4. Secure Tenant Headers

```python
# In production, validate X-Tenant-ID against authenticated user
class SecureResolver(HeaderBasedResolver):
    async def resolve_tenant(self, request: Request) -> Tenant:
        tenant_id = request.headers.get("X-Tenant-ID")
        user = await self.auth.get_user(request)
        
        # Verify user belongs to tenant
        if not await self.user_store.belongs_to_tenant(user.id, tenant_id):
            raise HTTPException(403, "User not authorized for tenant")
        
        return await self.tenant_store.get(tenant_id)
```

## Database Patterns

### Row-Level Security (PostgreSQL)

```sql
-- Create policy for tenant isolation
CREATE POLICY tenant_isolation ON investigations
    USING (tenant_id = current_setting('app.current_tenant')::uuid);

-- Set tenant context
SET app.current_tenant = 'tenant-123';
```

### Tenant-Prefixed Tables

```python
def get_table_name(base_name: str) -> str:
    ctx = get_current_tenant()
    return f"tenant_{ctx.tenant_id}_{base_name}"
```

### Schema-per-Tenant

```python
async def execute_query(query: str):
    ctx = get_current_tenant()
    schema = f"tenant_{ctx.tenant_id}"
    await db.execute(f"SET search_path TO {schema}")
    return await db.execute(query)
```

## Monitoring

### Tenant Metrics

```python
from prometheus_client import Counter, Gauge

# Per-tenant metrics
investigations_total = Counter(
    'autosre_investigations_total',
    'Total investigations',
    ['tenant_id', 'workspace_id']
)

quota_usage = Gauge(
    'autosre_quota_usage',
    'Current quota usage',
    ['tenant_id', 'quota_type']
)
```

### Quota Alerts

```python
def quota_alert_callback(tenant_id: str, quota_type: QuotaType, percentage: float):
    if percentage >= 95:
        send_alert(
            severity="critical",
            message=f"Tenant {tenant_id} at {percentage}% of {quota_type.value} quota"
        )
    elif percentage >= 80:
        send_alert(
            severity="warning", 
            message=f"Tenant {tenant_id} approaching {quota_type.value} limit"
        )

quota_manager = QuotaManager(alert_callback=quota_alert_callback)
```

## Troubleshooting

### Missing Tenant Context

```
Error: TenantContextError: No tenant context available
```

**Solution**: Ensure TenantMiddleware is added and X-Tenant-ID header is provided.

### Cross-Tenant Access Denied

```
Error: CrossTenantAccessError: tenant 'A' attempted to access resource belonging to tenant 'B'
```

**Solution**: Check that resource ownership matches current tenant context.

### Quota Exceeded

```
Error: QuotaExceededError: investigations_per_day: 50/50
```

**Solution**: Upgrade tenant tier or wait for quota reset.

## Next Steps

- [API Reference](../api/tenancy.md)
- [Database Setup](./database-multitenancy.md)
- [SSO Integration](./sso-setup.md)
- [Billing Integration](./billing-providers.md)
