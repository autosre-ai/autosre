"""
Usage Tracking and Billing

Enterprise billing system for multi-tenant SaaS:
- Usage event tracking
- Metered billing
- Invoice generation
- Subscription management
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from autosre.tenancy.models import Tenant, TenantTier


def utcnow() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def generate_id() -> str:
    """Generate a unique ID."""
    return str(uuid4())


class UsageMetric(str, Enum):
    """Billable usage metrics."""
    
    # Investigation metrics
    INVESTIGATION_STARTED = "investigation_started"
    INVESTIGATION_COMPLETED = "investigation_completed"
    INVESTIGATION_MINUTES = "investigation_minutes"
    
    # API metrics
    API_CALL = "api_call"
    WEBHOOK_RECEIVED = "webhook_received"
    
    # LLM metrics
    LLM_INPUT_TOKENS = "llm_input_tokens"
    LLM_OUTPUT_TOKENS = "llm_output_tokens"
    LLM_TOTAL_TOKENS = "llm_total_tokens"
    
    # Storage metrics
    STORAGE_GB_HOURS = "storage_gb_hours"
    LOG_INGESTION_GB = "log_ingestion_gb"
    
    # Action metrics
    AUTOMATED_ACTION_EXECUTED = "automated_action_executed"
    RUNBOOK_EXECUTED = "runbook_executed"
    ALERT_PROCESSED = "alert_processed"


class BillingPeriod(str, Enum):
    """Billing period types."""
    MONTHLY = "monthly"
    ANNUAL = "annual"
    USAGE_BASED = "usage_based"


class InvoiceStatus(str, Enum):
    """Invoice status."""
    DRAFT = "draft"
    PENDING = "pending"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class UsageEvent(BaseModel):
    """A single usage event for billing."""
    
    id: str = Field(default_factory=generate_id)
    tenant_id: str
    workspace_id: Optional[str] = None
    
    # Event details
    metric: UsageMetric
    quantity: Decimal = Field(default=Decimal("1"))
    unit_price: Optional[Decimal] = Field(None, description="Price per unit at event time")
    
    # Context
    resource_id: Optional[str] = Field(None, description="Related resource ID")
    resource_type: Optional[str] = Field(None, description="Type of resource")
    metadata: dict[str, Any] = Field(default_factory=dict)
    
    # Timestamps
    timestamp: datetime = Field(default_factory=utcnow)
    
    # Billing
    billed: bool = Field(default=False)
    invoice_id: Optional[str] = None


class PricingTier(BaseModel):
    """Pricing configuration for a tier."""
    
    tier: TenantTier
    
    # Base subscription
    monthly_base_price: Decimal = Field(default=Decimal("0"))
    annual_base_price: Decimal = Field(default=Decimal("0"))
    
    # Included quantities
    included_investigations: int = Field(default=0)
    included_api_calls: int = Field(default=0)
    included_llm_tokens: int = Field(default=0)
    included_storage_gb: int = Field(default=0)
    
    # Overage pricing
    investigation_overage_price: Decimal = Field(
        default=Decimal("0.50"),
        description="Price per investigation over included"
    )
    api_call_overage_price: Decimal = Field(
        default=Decimal("0.0001"),
        description="Price per 1000 API calls over included"
    )
    llm_token_overage_price: Decimal = Field(
        default=Decimal("0.00001"),
        description="Price per 1000 LLM tokens over included"
    )
    storage_overage_price: Decimal = Field(
        default=Decimal("0.10"),
        description="Price per GB over included"
    )


# Default pricing tiers
DEFAULT_PRICING: dict[TenantTier, PricingTier] = {
    TenantTier.FREE: PricingTier(
        tier=TenantTier.FREE,
        monthly_base_price=Decimal("0"),
        annual_base_price=Decimal("0"),
        included_investigations=100,
        included_api_calls=10000,
        included_llm_tokens=500000,
        included_storage_gb=1,
    ),
    TenantTier.STARTER: PricingTier(
        tier=TenantTier.STARTER,
        monthly_base_price=Decimal("99"),
        annual_base_price=Decimal("990"),
        included_investigations=500,
        included_api_calls=100000,
        included_llm_tokens=2000000,
        included_storage_gb=10,
    ),
    TenantTier.PROFESSIONAL: PricingTier(
        tier=TenantTier.PROFESSIONAL,
        monthly_base_price=Decimal("499"),
        annual_base_price=Decimal("4990"),
        included_investigations=2000,
        included_api_calls=1000000,
        included_llm_tokens=10000000,
        included_storage_gb=100,
    ),
    TenantTier.ENTERPRISE: PricingTier(
        tier=TenantTier.ENTERPRISE,
        monthly_base_price=Decimal("2499"),
        annual_base_price=Decimal("24990"),
        included_investigations=-1,  # Unlimited
        included_api_calls=-1,
        included_llm_tokens=-1,
        included_storage_gb=1000,
    ),
}


class InvoiceLineItem(BaseModel):
    """A line item on an invoice."""
    
    description: str
    quantity: Decimal
    unit_price: Decimal
    total: Decimal
    metric: Optional[UsageMetric] = None
    
    # Details
    is_base_subscription: bool = Field(default=False)
    is_overage: bool = Field(default=False)


class Invoice(BaseModel):
    """A billing invoice."""
    
    id: str = Field(default_factory=generate_id)
    tenant_id: str
    
    # Period
    period_start: datetime
    period_end: datetime
    billing_period: BillingPeriod = Field(default=BillingPeriod.MONTHLY)
    
    # Line items
    line_items: list[InvoiceLineItem] = Field(default_factory=list)
    
    # Totals
    subtotal: Decimal = Field(default=Decimal("0"))
    tax: Decimal = Field(default=Decimal("0"))
    discount: Decimal = Field(default=Decimal("0"))
    total: Decimal = Field(default=Decimal("0"))
    
    # Currency
    currency: str = Field(default="USD")
    
    # Status
    status: InvoiceStatus = Field(default=InvoiceStatus.DRAFT)
    
    # Payment
    due_date: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    payment_method: Optional[str] = None
    payment_reference: Optional[str] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    
    def add_line_item(self, item: InvoiceLineItem) -> None:
        """Add a line item and update totals."""
        self.line_items.append(item)
        self._recalculate_totals()
    
    def _recalculate_totals(self) -> None:
        """Recalculate invoice totals."""
        self.subtotal = sum(item.total for item in self.line_items)
        self.total = self.subtotal + self.tax - self.discount
        self.updated_at = utcnow()


@dataclass
class UsageAggregation:
    """Aggregated usage for a billing period."""
    
    tenant_id: str
    period_start: datetime
    period_end: datetime
    
    # Aggregated metrics
    metrics: dict[UsageMetric, Decimal] = field(default_factory=dict)
    
    # Event counts
    event_count: int = 0


class UsageTracker:
    """
    Tracks usage events for billing.
    
    Collects granular usage events and provides aggregation
    for billing period calculations.
    """
    
    def __init__(
        self,
        storage_backend: Optional[Any] = None,
        flush_interval_seconds: int = 60,
        batch_size: int = 100,
    ):
        self.storage = storage_backend
        self.flush_interval = flush_interval_seconds
        self.batch_size = batch_size
        
        # In-memory buffer for batching
        self._event_buffer: list[UsageEvent] = []
        self._buffer_lock = asyncio.Lock()
        
        # Aggregation cache
        self._aggregations: dict[str, UsageAggregation] = {}
    
    async def track(
        self,
        tenant_id: str,
        metric: UsageMetric,
        quantity: Decimal = Decimal("1"),
        workspace_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> UsageEvent:
        """
        Track a usage event.
        
        Events are buffered and flushed periodically for efficiency.
        """
        event = UsageEvent(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            metric=metric,
            quantity=quantity,
            resource_id=resource_id,
            resource_type=resource_type,
            metadata=metadata or {},
        )
        
        async with self._buffer_lock:
            self._event_buffer.append(event)
            
            # Update aggregation
            self._update_aggregation(event)
            
            # Flush if batch size reached
            if len(self._event_buffer) >= self.batch_size:
                await self._flush_buffer()
        
        return event
    
    def _update_aggregation(self, event: UsageEvent) -> None:
        """Update in-memory aggregation."""
        # Get current period
        now = utcnow()
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        key = f"{event.tenant_id}:{period_start.isoformat()}"
        
        if key not in self._aggregations:
            # Calculate period end
            if period_start.month == 12:
                period_end = period_start.replace(year=period_start.year + 1, month=1)
            else:
                period_end = period_start.replace(month=period_start.month + 1)
            
            self._aggregations[key] = UsageAggregation(
                tenant_id=event.tenant_id,
                period_start=period_start,
                period_end=period_end,
            )
        
        agg = self._aggregations[key]
        agg.metrics[event.metric] = agg.metrics.get(event.metric, Decimal("0")) + event.quantity
        agg.event_count += 1
    
    async def _flush_buffer(self) -> None:
        """Flush buffered events to storage."""
        if not self._event_buffer:
            return
        
        events_to_flush = self._event_buffer.copy()
        self._event_buffer.clear()
        
        if self.storage:
            # Persist to storage backend
            await self.storage.save_events(events_to_flush)
    
    async def get_aggregation(
        self,
        tenant_id: str,
        period_start: datetime,
        period_end: datetime,
    ) -> UsageAggregation:
        """Get aggregated usage for a billing period."""
        key = f"{tenant_id}:{period_start.isoformat()}"
        
        if key in self._aggregations:
            return self._aggregations[key]
        
        # If not in cache, query storage
        if self.storage:
            return await self.storage.get_aggregation(tenant_id, period_start, period_end)
        
        return UsageAggregation(
            tenant_id=tenant_id,
            period_start=period_start,
            period_end=period_end,
        )
    
    async def get_current_month_usage(
        self,
        tenant_id: str,
    ) -> UsageAggregation:
        """Get usage for the current billing month."""
        now = utcnow()
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        if period_start.month == 12:
            period_end = period_start.replace(year=period_start.year + 1, month=1)
        else:
            period_end = period_start.replace(month=period_start.month + 1)
        
        return await self.get_aggregation(tenant_id, period_start, period_end)


class BillingService:
    """
    Billing service for invoice generation and subscription management.
    """
    
    def __init__(
        self,
        usage_tracker: UsageTracker,
        storage_backend: Optional[Any] = None,
        payment_provider: Optional[Any] = None,
    ):
        self.usage_tracker = usage_tracker
        self.storage = storage_backend
        self.payment_provider = payment_provider
        
        # Custom pricing overrides
        self._custom_pricing: dict[str, PricingTier] = {}
    
    def get_pricing(self, tenant: Tenant) -> PricingTier:
        """Get pricing for a tenant."""
        if tenant.id in self._custom_pricing:
            return self._custom_pricing[tenant.id]
        return DEFAULT_PRICING.get(tenant.tier, DEFAULT_PRICING[TenantTier.FREE])
    
    def set_custom_pricing(self, tenant_id: str, pricing: PricingTier) -> None:
        """Set custom pricing for a tenant (enterprise negotiations)."""
        self._custom_pricing[tenant_id] = pricing
    
    async def generate_invoice(
        self,
        tenant: Tenant,
        period_start: datetime,
        period_end: datetime,
    ) -> Invoice:
        """
        Generate an invoice for a billing period.
        """
        pricing = self.get_pricing(tenant)
        usage = await self.usage_tracker.get_aggregation(
            tenant.id, period_start, period_end
        )
        
        invoice = Invoice(
            tenant_id=tenant.id,
            period_start=period_start,
            period_end=period_end,
            due_date=period_end + timedelta(days=30),
        )
        
        # Add base subscription
        is_annual = (period_end - period_start).days > 32
        base_price = pricing.annual_base_price if is_annual else pricing.monthly_base_price
        
        if base_price > 0:
            invoice.add_line_item(InvoiceLineItem(
                description=f"{tenant.tier.value.title()} Plan - {'Annual' if is_annual else 'Monthly'}",
                quantity=Decimal("1"),
                unit_price=base_price,
                total=base_price,
                is_base_subscription=True,
            ))
        
        # Calculate overages
        overages = self._calculate_overages(usage, pricing)
        for overage in overages:
            invoice.add_line_item(overage)
        
        invoice.status = InvoiceStatus.PENDING
        
        return invoice
    
    def _calculate_overages(
        self,
        usage: UsageAggregation,
        pricing: PricingTier,
    ) -> list[InvoiceLineItem]:
        """Calculate overage charges."""
        overages = []
        
        # Investigation overages
        investigations = usage.metrics.get(UsageMetric.INVESTIGATION_COMPLETED, Decimal("0"))
        if pricing.included_investigations >= 0:  # Not unlimited
            overage_qty = investigations - Decimal(pricing.included_investigations)
            if overage_qty > 0:
                overages.append(InvoiceLineItem(
                    description="Additional Investigations",
                    quantity=overage_qty,
                    unit_price=pricing.investigation_overage_price,
                    total=overage_qty * pricing.investigation_overage_price,
                    metric=UsageMetric.INVESTIGATION_COMPLETED,
                    is_overage=True,
                ))
        
        # API call overages
        api_calls = usage.metrics.get(UsageMetric.API_CALL, Decimal("0"))
        if pricing.included_api_calls >= 0:
            overage_qty = (api_calls - Decimal(pricing.included_api_calls)) / 1000
            if overage_qty > 0:
                overages.append(InvoiceLineItem(
                    description="Additional API Calls (per 1000)",
                    quantity=overage_qty,
                    unit_price=pricing.api_call_overage_price,
                    total=overage_qty * pricing.api_call_overage_price,
                    metric=UsageMetric.API_CALL,
                    is_overage=True,
                ))
        
        # LLM token overages
        llm_tokens = usage.metrics.get(UsageMetric.LLM_TOTAL_TOKENS, Decimal("0"))
        if pricing.included_llm_tokens >= 0:
            overage_qty = (llm_tokens - Decimal(pricing.included_llm_tokens)) / 1000
            if overage_qty > 0:
                overages.append(InvoiceLineItem(
                    description="Additional LLM Tokens (per 1000)",
                    quantity=overage_qty,
                    unit_price=pricing.llm_token_overage_price,
                    total=overage_qty * pricing.llm_token_overage_price,
                    metric=UsageMetric.LLM_TOTAL_TOKENS,
                    is_overage=True,
                ))
        
        # Storage overages
        storage_gb_hours = usage.metrics.get(UsageMetric.STORAGE_GB_HOURS, Decimal("0"))
        storage_gb_months = storage_gb_hours / Decimal("730")  # Average hours per month
        if pricing.included_storage_gb >= 0:
            overage_qty = storage_gb_months - Decimal(pricing.included_storage_gb)
            if overage_qty > 0:
                overages.append(InvoiceLineItem(
                    description="Additional Storage (per GB)",
                    quantity=overage_qty,
                    unit_price=pricing.storage_overage_price,
                    total=overage_qty * pricing.storage_overage_price,
                    metric=UsageMetric.STORAGE_GB_HOURS,
                    is_overage=True,
                ))
        
        return overages
    
    async def get_current_billing_status(
        self,
        tenant: Tenant,
    ) -> dict[str, Any]:
        """
        Get current billing status including usage and projected costs.
        """
        usage = await self.usage_tracker.get_current_month_usage(tenant.id)
        pricing = self.get_pricing(tenant)
        
        # Calculate projected costs
        days_in_period = (usage.period_end - usage.period_start).days
        days_elapsed = (utcnow() - usage.period_start).days or 1
        
        # Project full month usage
        projection_factor = Decimal(days_in_period) / Decimal(days_elapsed)
        
        projected_investigations = (
            usage.metrics.get(UsageMetric.INVESTIGATION_COMPLETED, Decimal("0")) 
            * projection_factor
        )
        projected_api_calls = (
            usage.metrics.get(UsageMetric.API_CALL, Decimal("0")) 
            * projection_factor
        )
        
        return {
            "tenant_id": tenant.id,
            "tier": tenant.tier.value,
            "period_start": usage.period_start.isoformat(),
            "period_end": usage.period_end.isoformat(),
            "current_usage": {
                metric.value: float(quantity)
                for metric, quantity in usage.metrics.items()
            },
            "projected_usage": {
                "investigations": float(projected_investigations),
                "api_calls": float(projected_api_calls),
            },
            "included_in_plan": {
                "investigations": pricing.included_investigations,
                "api_calls": pricing.included_api_calls,
                "llm_tokens": pricing.included_llm_tokens,
                "storage_gb": pricing.included_storage_gb,
            },
            "base_price": float(pricing.monthly_base_price),
            "projected_overages": self._estimate_overages(
                projected_investigations,
                projected_api_calls,
                pricing,
            ),
        }
    
    def _estimate_overages(
        self,
        projected_investigations: Decimal,
        projected_api_calls: Decimal,
        pricing: PricingTier,
    ) -> float:
        """Estimate projected overage charges."""
        total = Decimal("0")
        
        if pricing.included_investigations >= 0:
            inv_overage = max(
                Decimal("0"),
                projected_investigations - Decimal(pricing.included_investigations)
            )
            total += inv_overage * pricing.investigation_overage_price
        
        if pricing.included_api_calls >= 0:
            api_overage = max(
                Decimal("0"),
                (projected_api_calls - Decimal(pricing.included_api_calls)) / 1000
            )
            total += api_overage * pricing.api_call_overage_price
        
        return float(total)
    
    async def get_invoice_history(
        self,
        tenant_id: str,
        limit: int = 12,
    ) -> list[Invoice]:
        """Get historical invoices for a tenant."""
        if self.storage:
            return await self.storage.get_invoices(tenant_id, limit)
        return []
    
    async def process_payment(
        self,
        invoice: Invoice,
        payment_method: str,
    ) -> bool:
        """Process payment for an invoice."""
        if self.payment_provider:
            success = await self.payment_provider.charge(
                amount=invoice.total,
                currency=invoice.currency,
                payment_method=payment_method,
                metadata={"invoice_id": invoice.id, "tenant_id": invoice.tenant_id},
            )
            
            if success:
                invoice.status = InvoiceStatus.PAID
                invoice.paid_at = utcnow()
                invoice.payment_method = payment_method
                return True
        
        return False
