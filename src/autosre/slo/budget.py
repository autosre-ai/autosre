"""
Error Budget Tracker for AutoSRE V2.

Tracks error budget consumption and burn rate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence

from autosre.utils.logging import get_logger
from .definition import SLODefinition, SLOTarget

logger = get_logger(__name__)


class BudgetHealthStatus(str, Enum):
    """Error budget health status."""
    
    HEALTHY = "healthy"  # > 50% remaining
    WARNING = "warning"  # 25-50% remaining
    CRITICAL = "critical"  # 0-25% remaining
    EXHAUSTED = "exhausted"  # 0% or negative


@dataclass
class TrackerConfig:
    """Configuration for budget tracking."""
    
    # Alert thresholds
    warning_threshold: float = 0.5  # 50% consumed
    critical_threshold: float = 0.75  # 75% consumed
    
    # Burn rate thresholds
    fast_burn_rate: float = 14.4  # Burns in ~1 hour
    slow_burn_rate: float = 1.0  # Burns exactly on schedule
    
    # Forecast settings
    forecast_hours: int = 24
    
    # Data points
    min_data_points: int = 10


@dataclass
class BudgetBurnRate:
    """Burn rate calculation result."""
    
    rate: float  # Current burn rate (1.0 = normal, 2.0 = 2x normal)
    window: str  # Measurement window
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    @property
    def burns_in_hours(self) -> Optional[float]:
        """Hours until budget exhaustion at current rate."""
        if self.rate <= 0:
            return None
        # Assuming 30-day window
        return 720 / self.rate  # 30 * 24 hours
    
    @property
    def severity(self) -> str:
        """Get severity based on burn rate."""
        if self.rate >= 14.4:
            return "critical"  # Burns budget in ~1 hour
        elif self.rate >= 6:
            return "high"  # Burns budget in ~5 hours
        elif self.rate >= 1:
            return "medium"
        return "low"
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "rate": self.rate,
            "window": self.window,
            "burns_in_hours": self.burns_in_hours,
            "severity": self.severity,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class BudgetForecast:
    """Forecast of budget exhaustion."""
    
    current_budget_percent: float
    burn_rate: float
    hours_until_exhaustion: Optional[float]
    exhaustion_time: Optional[datetime]
    confidence: float = 0.0
    
    @property
    def will_exhaust_in_window(self) -> bool:
        """Check if budget will exhaust within the SLO window."""
        if self.hours_until_exhaustion is None:
            return False
        return self.hours_until_exhaustion < 720  # 30 days
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "current_budget_percent": self.current_budget_percent,
            "burn_rate": self.burn_rate,
            "hours_until_exhaustion": self.hours_until_exhaustion,
            "exhaustion_time": self.exhaustion_time.isoformat() if self.exhaustion_time else None,
            "will_exhaust_in_window": self.will_exhaust_in_window,
            "confidence": self.confidence,
        }


@dataclass
class BudgetStatus:
    """Current error budget status."""
    
    slo_name: str
    
    # Budget values
    total_budget: float  # Total error budget (1 - target)
    consumed_budget: float  # Budget consumed so far
    remaining_budget: float  # Budget remaining
    
    # Percentages
    consumed_percent: float
    remaining_percent: float
    
    # Health
    health: BudgetHealthStatus
    
    # Burn rates
    burn_rate_1h: BudgetBurnRate
    burn_rate_6h: BudgetBurnRate
    burn_rate_24h: BudgetBurnRate
    
    # Forecast
    forecast: BudgetForecast
    
    # Time context
    window_start: datetime
    window_end: datetime
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    @property
    def is_healthy(self) -> bool:
        return self.health == BudgetHealthStatus.HEALTHY
    
    @property
    def is_critical(self) -> bool:
        return self.health in (BudgetHealthStatus.CRITICAL, BudgetHealthStatus.EXHAUSTED)
    
    @property
    def budget_remaining_minutes(self) -> float:
        """Remaining budget in minutes."""
        window_minutes = (self.window_end - self.window_start).total_seconds() / 60
        return window_minutes * self.remaining_budget / self.total_budget if self.total_budget > 0 else 0
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "slo_name": self.slo_name,
            "total_budget": self.total_budget,
            "consumed_budget": self.consumed_budget,
            "remaining_budget": self.remaining_budget,
            "consumed_percent": self.consumed_percent,
            "remaining_percent": self.remaining_percent,
            "health": self.health.value,
            "burn_rate_1h": self.burn_rate_1h.to_dict(),
            "burn_rate_6h": self.burn_rate_6h.to_dict(),
            "burn_rate_24h": self.burn_rate_24h.to_dict(),
            "forecast": self.forecast.to_dict(),
            "window_start": self.window_start.isoformat(),
            "window_end": self.window_end.isoformat(),
        }


class ErrorBudgetTracker:
    """
    Tracks error budget for SLOs.
    
    Example:
        tracker = ErrorBudgetTracker()
        
        # Evaluate with current SLI value
        status = tracker.evaluate(slo, current_sli=0.998)
        
        print(f"Budget remaining: {status.remaining_percent:.1f}%")
        print(f"Burn rate (1h): {status.burn_rate_1h.rate:.2f}x")
    """
    
    def __init__(self, config: Optional[TrackerConfig] = None):
        self.config = config or TrackerConfig()
        
        # Historical data for burn rate calculation
        self._history: dict[str, list[tuple[datetime, float]]] = {}
    
    def evaluate(
        self,
        slo: SLODefinition,
        current_sli: Optional[float] = None,
        sli_history: Optional[list[tuple[datetime, float]]] = None,
    ) -> BudgetStatus:
        """
        Evaluate error budget status for an SLO.
        
        Args:
            slo: SLO definition
            current_sli: Current SLI value (0-1)
            sli_history: Historical SLI values [(timestamp, value), ...]
        
        Returns:
            BudgetStatus with current state
        """
        target = slo.slo_target
        now = datetime.now(timezone.utc)
        
        # Calculate window
        window_days = target.window_days
        window_start = now - timedelta(days=window_days)
        window_end = now
        
        # Calculate budget consumption
        if current_sli is not None:
            # Simple calculation from current SLI
            error_rate = 1 - current_sli
            consumed_budget = error_rate
            remaining_budget = target.error_budget - consumed_budget
        else:
            # Need historical data
            consumed_budget = 0.0
            remaining_budget = target.error_budget
        
        # Calculate burn rates
        burn_1h = self._calculate_burn_rate(slo, "1h", sli_history)
        burn_6h = self._calculate_burn_rate(slo, "6h", sli_history)
        burn_24h = self._calculate_burn_rate(slo, "24h", sli_history)
        
        # Calculate forecast
        forecast = self._calculate_forecast(
            remaining_budget,
            target.error_budget,
            burn_1h.rate,
        )
        
        # Determine health status
        consumed_percent = consumed_budget / target.error_budget if target.error_budget > 0 else 0
        remaining_percent = 1 - consumed_percent
        
        if remaining_percent <= 0:
            health = BudgetHealthStatus.EXHAUSTED
        elif consumed_percent >= self.config.critical_threshold:
            health = BudgetHealthStatus.CRITICAL
        elif consumed_percent >= self.config.warning_threshold:
            health = BudgetHealthStatus.WARNING
        else:
            health = BudgetHealthStatus.HEALTHY
        
        return BudgetStatus(
            slo_name=slo.name,
            total_budget=target.error_budget,
            consumed_budget=consumed_budget,
            remaining_budget=max(0, remaining_budget),
            consumed_percent=consumed_percent * 100,
            remaining_percent=remaining_percent * 100,
            health=health,
            burn_rate_1h=burn_1h,
            burn_rate_6h=burn_6h,
            burn_rate_24h=burn_24h,
            forecast=forecast,
            window_start=window_start,
            window_end=window_end,
        )
    
    def record_sli(
        self,
        slo_name: str,
        value: float,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Record an SLI measurement for history."""
        ts = timestamp or datetime.now(timezone.utc)
        
        if slo_name not in self._history:
            self._history[slo_name] = []
        
        self._history[slo_name].append((ts, value))
        
        # Keep last 30 days of data
        cutoff = ts - timedelta(days=30)
        self._history[slo_name] = [
            (t, v) for t, v in self._history[slo_name]
            if t > cutoff
        ]
    
    def _calculate_burn_rate(
        self,
        slo: SLODefinition,
        window: str,
        history: Optional[list[tuple[datetime, float]]] = None,
    ) -> BudgetBurnRate:
        """Calculate burn rate for a time window."""
        now = datetime.now(timezone.utc)
        
        # Parse window
        window_hours = {"1h": 1, "6h": 6, "24h": 24, "7d": 168}.get(window, 1)
        window_start = now - timedelta(hours=window_hours)
        
        # Get relevant data points
        data = history or self._history.get(slo.name, [])
        window_data = [(t, v) for t, v in data if t >= window_start]
        
        if len(window_data) < 2:
            # Not enough data, assume normal rate
            return BudgetBurnRate(rate=1.0, window=window)
        
        # Calculate average error rate in window
        avg_error_rate = sum(1 - v for _, v in window_data) / len(window_data)
        
        # Calculate burn rate relative to allowed budget
        target_error_rate = 1 - slo.target
        
        if target_error_rate > 0:
            burn_rate = avg_error_rate / target_error_rate
        else:
            burn_rate = float('inf') if avg_error_rate > 0 else 1.0
        
        return BudgetBurnRate(
            rate=burn_rate,
            window=window,
            timestamp=now,
        )
    
    def _calculate_forecast(
        self,
        remaining_budget: float,
        total_budget: float,
        current_burn_rate: float,
    ) -> BudgetForecast:
        """Calculate budget exhaustion forecast."""
        now = datetime.now(timezone.utc)
        
        remaining_percent = (remaining_budget / total_budget * 100) if total_budget > 0 else 0
        
        if current_burn_rate <= 0:
            # Not burning budget
            return BudgetForecast(
                current_budget_percent=remaining_percent,
                burn_rate=current_burn_rate,
                hours_until_exhaustion=None,
                exhaustion_time=None,
                confidence=0.5,
            )
        
        if remaining_budget <= 0:
            # Already exhausted
            return BudgetForecast(
                current_budget_percent=0,
                burn_rate=current_burn_rate,
                hours_until_exhaustion=0,
                exhaustion_time=now,
                confidence=1.0,
            )
        
        # Calculate hours until exhaustion
        # Assuming 30-day window, each hour consumes budget at burn_rate
        hours_per_window = 30 * 24  # 720 hours
        normal_hourly_consumption = total_budget / hours_per_window
        actual_hourly_consumption = normal_hourly_consumption * current_burn_rate
        
        if actual_hourly_consumption > 0:
            hours_until_exhaustion = remaining_budget / actual_hourly_consumption
            exhaustion_time = now + timedelta(hours=hours_until_exhaustion)
        else:
            hours_until_exhaustion = None
            exhaustion_time = None
        
        return BudgetForecast(
            current_budget_percent=remaining_percent,
            burn_rate=current_burn_rate,
            hours_until_exhaustion=hours_until_exhaustion,
            exhaustion_time=exhaustion_time,
            confidence=0.7,  # Could be improved with more sophisticated modeling
        )
    
    def get_multi_window_status(
        self,
        slo: SLODefinition,
        current_sli: float,
    ) -> dict[str, Any]:
        """
        Get multi-window burn rate status (Google SRE style).
        
        Uses both long and short windows to detect different
        types of budget consumption patterns.
        """
        status = self.evaluate(slo, current_sli)
        
        # Multi-window alerting logic
        # Short window (1h) for fast burns
        # Long window (24h) for slow burns
        
        alerts = []
        
        # Page-worthy: 14.4x burn in 1h AND 6x burn in 6h
        if status.burn_rate_1h.rate >= 14.4 and status.burn_rate_6h.rate >= 6:
            alerts.append({
                "severity": "page",
                "message": f"Fast burn: 1h={status.burn_rate_1h.rate:.1f}x, 6h={status.burn_rate_6h.rate:.1f}x",
                "action": "immediate_investigation",
            })
        
        # Ticket-worthy: 1x burn in 6h AND 0.5x burn in 24h
        elif status.burn_rate_6h.rate >= 1 and status.burn_rate_24h.rate >= 0.5:
            alerts.append({
                "severity": "ticket",
                "message": f"Slow burn: 6h={status.burn_rate_6h.rate:.1f}x, 24h={status.burn_rate_24h.rate:.1f}x",
                "action": "scheduled_investigation",
            })
        
        return {
            "status": status.to_dict(),
            "alerts": alerts,
            "requires_action": len(alerts) > 0,
        }
    
    def compare_slos(
        self,
        slos: Sequence[SLODefinition],
        current_values: dict[str, float],
    ) -> list[BudgetStatus]:
        """Compare budget status across multiple SLOs."""
        statuses = []
        
        for slo in slos:
            current_sli = current_values.get(slo.name)
            if current_sli is not None:
                status = self.evaluate(slo, current_sli)
                statuses.append(status)
        
        # Sort by health (worst first)
        health_order = {
            BudgetHealthStatus.EXHAUSTED: 0,
            BudgetHealthStatus.CRITICAL: 1,
            BudgetHealthStatus.WARNING: 2,
            BudgetHealthStatus.HEALTHY: 3,
        }
        statuses.sort(key=lambda s: health_order.get(s.health, 4))
        
        return statuses
