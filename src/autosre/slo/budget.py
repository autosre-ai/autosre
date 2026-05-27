"""
Error Budget Management for AutoSRE.

Provides comprehensive error budget tracking including:
- Budget consumption tracking
- Burn rate calculations
- Budget forecasting
- Budget policy enforcement
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional, Callable
import math

from pydantic import BaseModel, Field

from .definition import (
    SLODefinition,
    SLOPeriod,
    ComplianceStatus,
    AlertSeverity,
)


class BudgetConsumptionRate(str, Enum):
    """Error budget consumption rate categories."""
    
    NOMINAL = "nominal"         # Normal consumption (< 1x)
    ELEVATED = "elevated"       # Slightly elevated (1-3x)
    HIGH = "high"               # High burn rate (3-10x)
    CRITICAL = "critical"       # Critical burn rate (> 10x)
    RECOVERING = "recovering"   # Negative consumption (recovery)


class BudgetAction(str, Enum):
    """Actions to take based on budget status."""
    
    CONTINUE = "continue"           # Continue normal operations
    REVIEW = "review"               # Review recent changes
    FREEZE_DEPLOYS = "freeze_deploys"   # Halt deployments
    INCIDENT = "incident"           # Declare incident
    ROLLBACK = "rollback"           # Initiate rollback


@dataclass
class BudgetDataPoint:
    """A single data point for budget tracking."""
    
    timestamp: datetime
    good_events: float
    total_events: float
    sli_value: float
    budget_consumed: float      # Absolute budget consumed
    budget_remaining: float     # Remaining budget
    burn_rate: float           # Current burn rate
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "good_events": self.good_events,
            "total_events": self.total_events,
            "sli_value": self.sli_value,
            "budget_consumed": self.budget_consumed,
            "budget_remaining": self.budget_remaining,
            "burn_rate": self.burn_rate,
        }


class BurnRateCalculation(BaseModel):
    """Result of burn rate calculation."""
    
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    window_hours: float
    burn_rate: float                    # Multiple of acceptable rate
    budget_consumed_pct: float          # Percentage consumed in window
    projected_exhaustion_hours: Optional[float] = None
    rate_category: BudgetConsumptionRate = BudgetConsumptionRate.NOMINAL
    
    @classmethod
    def from_events(
        cls,
        window_hours: float,
        good_events: float,
        total_events: float,
        target: float,
        total_budget: float,
    ) -> "BurnRateCalculation":
        """Calculate burn rate from event counts."""
        if total_events == 0:
            return cls(
                window_hours=window_hours,
                burn_rate=0.0,
                budget_consumed_pct=0.0,
                rate_category=BudgetConsumptionRate.NOMINAL,
            )
        
        # Calculate actual SLI
        sli = good_events / total_events
        
        # Calculate budget consumed
        error_rate = 1.0 - sli
        target_error_rate = 1.0 - target
        
        # Burn rate = actual error rate / acceptable error rate
        if target_error_rate > 0:
            burn_rate = error_rate / target_error_rate
        else:
            burn_rate = 0.0 if error_rate == 0 else float('inf')
        
        # Budget consumed as percentage
        budget_consumed = (error_rate / (1.0 - target)) * 100 if target < 1.0 else 0
        
        # Projected exhaustion
        if burn_rate > 1.0 and total_budget > 0:
            remaining = 100.0 - budget_consumed
            hours_to_exhaust = (remaining / (burn_rate - 1.0)) * window_hours if burn_rate > 1 else None
        else:
            hours_to_exhaust = None
        
        # Categorize burn rate
        if burn_rate < 0:
            category = BudgetConsumptionRate.RECOVERING
        elif burn_rate < 1.0:
            category = BudgetConsumptionRate.NOMINAL
        elif burn_rate < 3.0:
            category = BudgetConsumptionRate.ELEVATED
        elif burn_rate < 10.0:
            category = BudgetConsumptionRate.HIGH
        else:
            category = BudgetConsumptionRate.CRITICAL
        
        return cls(
            window_hours=window_hours,
            burn_rate=burn_rate,
            budget_consumed_pct=budget_consumed,
            projected_exhaustion_hours=hours_to_exhaust,
            rate_category=category,
        )


class ErrorBudgetStatus(BaseModel):
    """Current error budget status for an SLO."""
    
    slo_id: str
    slo_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Budget metrics
    total_budget_minutes: float             # Total budget for period
    consumed_budget_minutes: float          # Budget consumed so far
    remaining_budget_minutes: float         # Remaining budget
    consumed_percentage: float              # Percentage consumed
    remaining_percentage: float             # Percentage remaining
    
    # SLI metrics
    current_sli: float                      # Current SLI value
    target_sli: float                       # Target SLI value
    
    # Period info
    period_start: datetime
    period_end: datetime
    period_elapsed_percentage: float        # How much of period has elapsed
    
    # Burn rates for different windows
    burn_rates: dict[str, BurnRateCalculation] = Field(default_factory=dict)
    
    # Status
    compliance_status: ComplianceStatus = ComplianceStatus.UNKNOWN
    recommended_action: BudgetAction = BudgetAction.CONTINUE
    
    # Alerts
    active_alerts: list[str] = Field(default_factory=list)
    
    @property
    def is_healthy(self) -> bool:
        """Check if budget is healthy."""
        return self.compliance_status in [
            ComplianceStatus.HEALTHY,
            ComplianceStatus.WARNING,
        ]
    
    @property
    def is_violated(self) -> bool:
        """Check if SLO is violated."""
        return self.compliance_status == ComplianceStatus.VIOLATED
    
    def get_primary_burn_rate(self) -> Optional[BurnRateCalculation]:
        """Get the most relevant burn rate (1-hour window)."""
        return self.burn_rates.get("1h")


class BudgetPolicy(BaseModel):
    """Policy for error budget management."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    
    # Thresholds
    warning_threshold_pct: float = Field(default=50.0)      # Warn when this much consumed
    critical_threshold_pct: float = Field(default=80.0)     # Critical when this much consumed
    freeze_threshold_pct: float = Field(default=90.0)       # Freeze deploys at this level
    
    # Actions
    auto_freeze_deploys: bool = True
    notify_on_warning: bool = True
    notify_on_critical: bool = True
    create_incident_on_violation: bool = True
    
    # Team configuration
    notify_teams: list[str] = Field(default_factory=list)
    escalation_policy_id: Optional[str] = None
    
    def get_action(self, consumed_pct: float) -> BudgetAction:
        """Determine recommended action based on consumption."""
        if consumed_pct >= 100.0:
            return BudgetAction.INCIDENT
        elif consumed_pct >= self.freeze_threshold_pct:
            return BudgetAction.FREEZE_DEPLOYS
        elif consumed_pct >= self.critical_threshold_pct:
            return BudgetAction.REVIEW
        else:
            return BudgetAction.CONTINUE


class ErrorBudget(BaseModel):
    """Error budget tracker for a single SLO."""
    
    slo_id: str
    slo: SLODefinition
    policy: BudgetPolicy = Field(default_factory=lambda: BudgetPolicy(name="default"))
    
    # Tracking data
    data_points: list[dict] = Field(default_factory=list)   # BudgetDataPoint as dict
    
    # Current state
    period_start: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_good_events: float = 0
    total_events: float = 0
    
    # Cache
    last_status_cache: Optional[ErrorBudgetStatus] = Field(default=None, exclude=True)
    
    def record_events(
        self,
        good_events: float,
        total_events: float,
        timestamp: Optional[datetime] = None,
    ) -> BudgetDataPoint:
        """Record event data for budget tracking."""
        timestamp = timestamp or datetime.now(timezone.utc)
        
        self.total_good_events += good_events
        self.total_events += total_events
        
        # Calculate metrics
        sli_value = good_events / total_events if total_events > 0 else 1.0
        
        # Calculate budget
        error_rate = 1.0 - sli_value
        target_error_rate = self.slo.error_budget_fraction
        
        budget_consumed = (error_rate * total_events) / target_error_rate if target_error_rate > 0 else 0
        
        current_consumption = self.get_current_consumption()
        budget_remaining = (1.0 - current_consumption) * self.slo.calculate_error_budget_minutes()
        
        # Calculate burn rate
        burn_rate = error_rate / target_error_rate if target_error_rate > 0 else 0
        
        data_point = BudgetDataPoint(
            timestamp=timestamp,
            good_events=good_events,
            total_events=total_events,
            sli_value=sli_value,
            budget_consumed=budget_consumed,
            budget_remaining=budget_remaining,
            burn_rate=burn_rate,
        )
        
        self.data_points.append(data_point.to_dict())
        return data_point
    
    def get_current_sli(self) -> float:
        """Get current SLI value."""
        if self.total_events == 0:
            return 1.0
        return self.total_good_events / self.total_events
    
    def get_current_consumption(self) -> float:
        """Get current budget consumption as fraction (0-1)."""
        if self.total_events == 0:
            return 0.0
        
        actual_sli = self.get_current_sli()
        target_sli = self.slo.target
        error_budget = self.slo.error_budget_fraction
        
        if error_budget == 0:
            return 0.0 if actual_sli >= target_sli else 1.0
        
        actual_errors = 1.0 - actual_sli
        consumption = actual_errors / error_budget
        
        return min(max(consumption, 0.0), 2.0)  # Cap at 200%
    
    def get_remaining_budget_minutes(self) -> float:
        """Get remaining error budget in minutes."""
        total_budget = self.slo.calculate_error_budget_minutes()
        consumed = self.get_current_consumption()
        return total_budget * (1.0 - consumed)
    
    def calculate_burn_rate(
        self,
        window_hours: float,
        good_events: Optional[float] = None,
        total_events: Optional[float] = None,
    ) -> BurnRateCalculation:
        """Calculate burn rate for a time window."""
        good = good_events if good_events is not None else self.total_good_events
        total = total_events if total_events is not None else self.total_events
        
        return BurnRateCalculation.from_events(
            window_hours=window_hours,
            good_events=good,
            total_events=total,
            target=self.slo.target,
            total_budget=self.slo.calculate_error_budget_minutes(),
        )
    
    def get_status(self) -> ErrorBudgetStatus:
        """Get current error budget status."""
        now = datetime.now(timezone.utc)
        period_days = self.slo.get_period_days()
        
        # Ensure period_start is timezone-aware
        if self.period_start.tzinfo is None:
            period_start_aware = self.period_start.replace(tzinfo=timezone.utc)
        else:
            period_start_aware = self.period_start
        
        period_end = period_start_aware + timedelta(days=period_days)
        
        elapsed = (now - period_start_aware).total_seconds()
        total_seconds = period_days * 24 * 3600
        elapsed_pct = (elapsed / total_seconds) * 100 if total_seconds > 0 else 0
        
        consumed_pct = self.get_current_consumption() * 100
        remaining_pct = 100.0 - consumed_pct
        
        # Calculate burn rates for different windows
        burn_rates = {
            "1h": self.calculate_burn_rate(1.0),
            "6h": self.calculate_burn_rate(6.0),
            "24h": self.calculate_burn_rate(24.0),
            "7d": self.calculate_burn_rate(168.0),
        }
        
        # Determine compliance status
        if consumed_pct >= 100.0:
            status = ComplianceStatus.VIOLATED
        elif consumed_pct >= self.policy.critical_threshold_pct:
            status = ComplianceStatus.CRITICAL
        elif consumed_pct >= self.policy.warning_threshold_pct:
            status = ComplianceStatus.WARNING
        else:
            status = ComplianceStatus.HEALTHY
        
        # Get recommended action
        action = self.policy.get_action(consumed_pct)
        
        return ErrorBudgetStatus(
            slo_id=self.slo_id,
            slo_name=self.slo.name,
            timestamp=now,
            total_budget_minutes=self.slo.calculate_error_budget_minutes(),
            consumed_budget_minutes=self.slo.calculate_error_budget_minutes() * (consumed_pct / 100),
            remaining_budget_minutes=self.get_remaining_budget_minutes(),
            consumed_percentage=consumed_pct,
            remaining_percentage=remaining_pct,
            current_sli=self.get_current_sli(),
            target_sli=self.slo.target,
            period_start=period_start_aware,
            period_end=period_end,
            period_elapsed_percentage=elapsed_pct,
            burn_rates=burn_rates,
            compliance_status=status,
            recommended_action=action,
        )
    
    def reset_period(self) -> None:
        """Reset the budget tracking for a new period."""
        self.period_start = datetime.now(timezone.utc)
        self.total_good_events = 0
        self.total_events = 0
        self.data_points = []
        self.last_status_cache = None
    
    def forecast_exhaustion(self) -> Optional[datetime]:
        """Forecast when budget will be exhausted at current burn rate."""
        status = self.get_status()
        burn_rate_1h = status.burn_rates.get("1h")
        
        if not burn_rate_1h or burn_rate_1h.burn_rate <= 1.0:
            return None  # Budget not being consumed faster than allowed
        
        remaining = status.remaining_budget_minutes
        consumption_rate = burn_rate_1h.burn_rate  # Minutes consumed per minute
        
        if consumption_rate <= 0:
            return None
        
        hours_to_exhaust = remaining / (consumption_rate * 60)
        return datetime.now(timezone.utc) + timedelta(hours=hours_to_exhaust)


class ErrorBudgetTracker:
    """Manager for tracking error budgets across multiple SLOs."""
    
    def __init__(self):
        """Initialize the error budget tracker."""
        self._budgets: dict[str, ErrorBudget] = {}
        self._policies: dict[str, BudgetPolicy] = {}
    
    def create_budget(
        self,
        slo: SLODefinition,
        policy: Optional[BudgetPolicy] = None,
    ) -> ErrorBudget:
        """Create a new error budget tracker for an SLO."""
        budget = ErrorBudget(
            slo_id=slo.id,
            slo=slo,
            policy=policy or BudgetPolicy(name=f"{slo.name}_policy"),
        )
        self._budgets[slo.id] = budget
        return budget
    
    def get_budget(self, slo_id: str) -> Optional[ErrorBudget]:
        """Get error budget tracker for an SLO."""
        return self._budgets.get(slo_id)
    
    def record_events(
        self,
        slo_id: str,
        good_events: float,
        total_events: float,
        timestamp: Optional[datetime] = None,
    ) -> Optional[BudgetDataPoint]:
        """Record events for an SLO's budget."""
        budget = self._budgets.get(slo_id)
        if not budget:
            return None
        return budget.record_events(good_events, total_events, timestamp)
    
    def get_all_statuses(self) -> list[ErrorBudgetStatus]:
        """Get status for all tracked budgets."""
        return [budget.get_status() for budget in self._budgets.values()]
    
    def get_unhealthy_budgets(self) -> list[ErrorBudgetStatus]:
        """Get budgets that are not healthy."""
        return [
            status for status in self.get_all_statuses()
            if not status.is_healthy
        ]
    
    def get_violated_budgets(self) -> list[ErrorBudgetStatus]:
        """Get budgets that have been violated."""
        return [
            status for status in self.get_all_statuses()
            if status.is_violated
        ]
    
    def create_policy(
        self,
        name: str,
        **kwargs: Any,
    ) -> BudgetPolicy:
        """Create a budget policy."""
        policy = BudgetPolicy(name=name, **kwargs)
        self._policies[policy.id] = policy
        return policy
    
    def apply_policy(
        self,
        slo_id: str,
        policy_id: str,
    ) -> bool:
        """Apply a policy to an SLO's budget."""
        budget = self._budgets.get(slo_id)
        policy = self._policies.get(policy_id)
        
        if not budget or not policy:
            return False
        
        budget.policy = policy
        return True
    
    def get_summary(self) -> dict[str, Any]:
        """Get summary of all error budgets."""
        statuses = self.get_all_statuses()
        
        summary = {
            "total_slos": len(statuses),
            "healthy": 0,
            "warning": 0,
            "critical": 0,
            "violated": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": [],
        }
        
        for status in statuses:
            summary["details"].append({
                "slo_id": status.slo_id,
                "slo_name": status.slo_name,
                "status": status.compliance_status.value,
                "remaining_pct": round(status.remaining_percentage, 2),
                "current_sli": round(status.current_sli * 100, 3),
                "target_sli": round(status.target_sli * 100, 3),
            })
            
            if status.compliance_status == ComplianceStatus.HEALTHY:
                summary["healthy"] += 1
            elif status.compliance_status == ComplianceStatus.WARNING:
                summary["warning"] += 1
            elif status.compliance_status == ComplianceStatus.CRITICAL:
                summary["critical"] += 1
            elif status.compliance_status == ComplianceStatus.VIOLATED:
                summary["violated"] += 1
        
        return summary


# Convenience functions
def calculate_burn_rate(
    good_events: float,
    total_events: float,
    target: float,
) -> float:
    """Calculate simple burn rate."""
    if total_events == 0:
        return 0.0
    
    actual_sli = good_events / total_events
    error_rate = 1.0 - actual_sli
    target_error_rate = 1.0 - target
    
    if target_error_rate <= 0:
        return 0.0 if error_rate <= 0 else float('inf')
    
    return error_rate / target_error_rate


def calculate_time_to_exhaustion(
    remaining_budget_minutes: float,
    burn_rate: float,
) -> Optional[float]:
    """Calculate time until budget exhaustion in hours."""
    if burn_rate <= 1.0:
        return None  # Won't exhaust at current rate
    
    minutes_until_exhaustion = remaining_budget_minutes / (burn_rate - 1.0)
    return minutes_until_exhaustion / 60


def budget_allows_deployment(
    status: ErrorBudgetStatus,
    deployment_risk_factor: float = 0.05,
) -> tuple[bool, str]:
    """
    Check if error budget allows deployment.
    
    Args:
        status: Current error budget status
        deployment_risk_factor: Expected risk of deployment (0-1)
        
    Returns:
        Tuple of (allowed, reason)
    """
    # Never allow if violated
    if status.is_violated:
        return False, "Error budget exhausted - deployment blocked"
    
    # Check if remaining budget can absorb deployment risk
    risk_budget_needed = deployment_risk_factor * 100
    
    if status.remaining_percentage < risk_budget_needed:
        return False, f"Insufficient budget for deployment risk ({status.remaining_percentage:.1f}% < {risk_budget_needed:.1f}%)"
    
    # Check burn rate
    burn_rate_1h = status.burn_rates.get("1h")
    if burn_rate_1h and burn_rate_1h.burn_rate > 10.0:
        return False, f"Burn rate too high ({burn_rate_1h.burn_rate:.1f}x) - deployment blocked"
    
    # Check recommended action
    if status.recommended_action in [BudgetAction.FREEZE_DEPLOYS, BudgetAction.INCIDENT]:
        return False, f"Budget policy recommends {status.recommended_action.value}"
    
    return True, "Deployment allowed"
