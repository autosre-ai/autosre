"""
Error Budget Calculator

Calculates error budgets based on SLO targets and tracks consumption.
Key insight: Error budget = 1 - SLO (e.g., 99.9% SLO = 0.1% error budget)

Example: 99.9% monthly SLO
- Error budget: 0.1% of 43,200 minutes/month = ~43 minutes downtime allowed
- If 20 minutes consumed, 53% of budget remains
- Can deploy if >20% budget remaining
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)


class ErrorBudgetStatus(Enum):
    """Status of error budget consumption."""
    HEALTHY = "healthy"           # >50% remaining
    WARNING = "warning"           # 20-50% remaining
    CRITICAL = "critical"         # <20% remaining
    EXHAUSTED = "exhausted"       # 0% remaining


@dataclass
class DeploymentDecision:
    """Decision on whether a deployment should proceed."""
    can_deploy: bool
    reason: str
    budget_remaining_percent: float
    risk_level: str  # low, medium, high
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "can_deploy": self.can_deploy,
            "reason": self.reason,
            "budget_remaining_percent": self.budget_remaining_percent,
            "risk_level": self.risk_level,
            "recommendations": self.recommendations,
        }


@dataclass
class ErrorBudget:
    """
    Error budget calculation result.
    
    All values are expressed as ratios (0.0 to 1.0) unless noted.
    """
    slo: float                          # Target SLO (e.g., 0.999 for 99.9%)
    error_budget: float                 # 1 - SLO (e.g., 0.001 for 0.1%)
    consumed: float                     # Amount consumed (e.g., 0.0005)
    remaining: float                    # Amount remaining (e.g., 0.0005)
    percentage_remaining: float         # As percentage (e.g., 50.0)
    status: ErrorBudgetStatus
    
    # Time-based calculations
    window_minutes: int                 # Measurement window in minutes
    allowed_downtime_minutes: float     # Total allowed downtime
    consumed_downtime_minutes: float    # Consumed downtime
    remaining_downtime_minutes: float   # Remaining downtime
    
    # Burn rate
    burn_rate: float                    # Current burn rate multiplier
    time_until_exhausted: Optional[timedelta]  # At current burn rate
    
    # Metadata
    service: str
    calculated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "slo": self.slo,
            "slo_percent": f"{self.slo * 100:.3f}%",
            "error_budget": self.error_budget,
            "error_budget_percent": f"{self.error_budget * 100:.4f}%",
            "consumed": self.consumed,
            "remaining": self.remaining,
            "percentage_remaining": self.percentage_remaining,
            "status": self.status.value,
            "window_minutes": self.window_minutes,
            "allowed_downtime_minutes": round(self.allowed_downtime_minutes, 2),
            "consumed_downtime_minutes": round(self.consumed_downtime_minutes, 2),
            "remaining_downtime_minutes": round(self.remaining_downtime_minutes, 2),
            "burn_rate": round(self.burn_rate, 2),
            "time_until_exhausted_hours": (
                round(self.time_until_exhausted.total_seconds() / 3600, 1)
                if self.time_until_exhausted else None
            ),
            "service": self.service,
            "calculated_at": self.calculated_at.isoformat(),
        }

    @property
    def can_deploy(self) -> bool:
        """Safe to deploy if >20% budget remaining."""
        return self.percentage_remaining > 20.0

    def get_deployment_decision(self, deploy_risk: str = "normal") -> DeploymentDecision:
        """
        Determine if deployment should proceed.
        
        Args:
            deploy_risk: Risk level of the deployment (low, normal, high)
        """
        recommendations = []
        
        # Exhausted budget - block all deploys
        if self.status == ErrorBudgetStatus.EXHAUSTED:
            return DeploymentDecision(
                can_deploy=False,
                reason="Error budget exhausted - no deployments allowed",
                budget_remaining_percent=self.percentage_remaining,
                risk_level="critical",
                recommendations=[
                    "Wait for error budget to recover",
                    "Investigate current errors",
                    "Consider rolling back recent changes",
                ]
            )
        
        # Critical budget (<20%) - block high-risk deploys
        if self.status == ErrorBudgetStatus.CRITICAL:
            if deploy_risk == "high":
                return DeploymentDecision(
                    can_deploy=False,
                    reason=f"Error budget critical ({self.percentage_remaining:.1f}% remaining) - high-risk deploys blocked",
                    budget_remaining_percent=self.percentage_remaining,
                    risk_level="high",
                    recommendations=[
                        "Reduce deployment risk before proceeding",
                        "Implement canary deployment",
                        "Ensure quick rollback capability",
                    ]
                )
            recommendations.append("Consider delaying non-critical changes")
            recommendations.append("Have rollback plan ready")
        
        # Warning budget (20-50%) - allow with caution
        if self.status == ErrorBudgetStatus.WARNING:
            recommendations.append("Monitor closely after deployment")
            recommendations.append("Be prepared for quick rollback")
        
        # Healthy budget - proceed normally
        risk_level = "low" if self.status == ErrorBudgetStatus.HEALTHY else "medium"
        
        return DeploymentDecision(
            can_deploy=True,
            reason=f"Error budget healthy ({self.percentage_remaining:.1f}% remaining)",
            budget_remaining_percent=self.percentage_remaining,
            risk_level=risk_level,
            recommendations=recommendations,
        )


class ErrorBudgetCalculator:
    """
    Calculates error budgets from metrics.
    
    Uses Prometheus queries to determine:
    - Total requests
    - Failed requests (5xx errors)
    - Current burn rate
    """
    
    # Prometheus queries
    QUERIES = {
        "error_rate_1h": 'sum(rate(http_requests_total{{service="{service}",status=~"5.."}}[1h])) / sum(rate(http_requests_total{{service="{service}"}}[1h]))',
        "error_rate_window": 'sum(rate(http_requests_total{{service="{service}",status=~"5.."}}[{window}])) / sum(rate(http_requests_total{{service="{service}"}}[{window}]))',
        "total_requests": 'sum(increase(http_requests_total{{service="{service}"}}[{window}]))',
        "failed_requests": 'sum(increase(http_requests_total{{service="{service}",status=~"5.."}}[{window}]))',
        "burn_rate": 'sum(rate(http_requests_total{{service="{service}",status=~"5.."}}[1h])) / sum(rate(http_requests_total{{service="{service}"}}[1h])) / {error_budget}',
    }
    
    # Default SLOs by service type
    DEFAULT_SLOS = {
        "api": 0.999,           # 99.9% - ~43 min/month
        "web": 0.995,           # 99.5% - ~3.6 hours/month
        "batch": 0.99,          # 99% - ~7.3 hours/month
        "internal": 0.999,      # 99.9%
        "critical": 0.9999,     # 99.99% - ~4.3 min/month
    }
    
    # Window in minutes
    WINDOW_MONTHLY = 43200      # 30 days
    WINDOW_WEEKLY = 10080       # 7 days
    WINDOW_DAILY = 1440         # 24 hours
    
    def __init__(self, prometheus_client: Any = None):
        """
        Initialize calculator.
        
        Args:
            prometheus_client: Prometheus client for querying metrics
        """
        self.prometheus = prometheus_client
        self._slo_configs: dict[str, float] = {}
    
    def configure_slo(self, service: str, slo: float) -> None:
        """
        Configure SLO for a specific service.
        
        Args:
            service: Service name
            slo: SLO target (0.0 to 1.0)
        """
        if not 0 < slo < 1:
            raise ValueError(f"SLO must be between 0 and 1, got {slo}")
        self._slo_configs[service] = slo
        logger.info(f"Configured SLO for {service}: {slo * 100:.3f}%")
    
    def get_slo(self, service: str, service_type: str = "api") -> float:
        """Get SLO for a service."""
        if service in self._slo_configs:
            return self._slo_configs[service]
        return self.DEFAULT_SLOS.get(service_type, 0.999)
    
    def calculate(
        self,
        service: str,
        total_requests: int,
        failed_requests: int,
        window_minutes: int = WINDOW_MONTHLY,
        slo: Optional[float] = None,
        current_burn_rate: Optional[float] = None,
    ) -> ErrorBudget:
        """
        Calculate error budget from request counts.
        
        Args:
            service: Service name
            total_requests: Total requests in window
            failed_requests: Failed requests (5xx) in window
            window_minutes: Measurement window in minutes
            slo: SLO target (default: use configured or 99.9%)
            current_burn_rate: Current burn rate from Prometheus
        
        Returns:
            ErrorBudget with calculated values
        """
        # Get SLO
        target_slo = slo or self.get_slo(service)
        error_budget = 1 - target_slo
        
        # Calculate consumption
        if total_requests == 0:
            error_rate = 0.0
        else:
            error_rate = failed_requests / total_requests
        
        # Error budget consumed = error_rate / error_budget
        # If error_rate = error_budget, we've consumed 100%
        if error_budget == 0:
            consumed_ratio = 1.0 if error_rate > 0 else 0.0
        else:
            consumed_ratio = min(error_rate / error_budget, 1.0)
        
        remaining_ratio = max(1.0 - consumed_ratio, 0.0)
        percentage_remaining = remaining_ratio * 100
        
        # Time-based calculations
        allowed_downtime = window_minutes * error_budget
        consumed_downtime = allowed_downtime * consumed_ratio
        remaining_downtime = allowed_downtime * remaining_ratio
        
        # Burn rate (how fast we're consuming budget)
        # burn_rate = 1.0 means consuming budget at expected rate
        # burn_rate = 2.0 means consuming 2x faster than allowed
        if current_burn_rate is not None:
            burn_rate = current_burn_rate
        elif error_budget > 0:
            burn_rate = error_rate / error_budget
        else:
            burn_rate = float('inf') if error_rate > 0 else 0.0
        
        # Time until exhausted at current burn rate
        if burn_rate > 0 and remaining_ratio > 0:
            # Remaining minutes of budget / burn rate
            remaining_budget_minutes = remaining_downtime
            time_to_exhaust = remaining_budget_minutes / burn_rate
            time_until_exhausted = timedelta(minutes=time_to_exhaust)
        else:
            time_until_exhausted = None
        
        # Determine status
        if percentage_remaining <= 0:
            status = ErrorBudgetStatus.EXHAUSTED
        elif percentage_remaining < 20:
            status = ErrorBudgetStatus.CRITICAL
        elif percentage_remaining < 50:
            status = ErrorBudgetStatus.WARNING
        else:
            status = ErrorBudgetStatus.HEALTHY
        
        return ErrorBudget(
            slo=target_slo,
            error_budget=error_budget,
            consumed=error_rate,
            remaining=error_budget - error_rate if error_rate < error_budget else 0,
            percentage_remaining=percentage_remaining,
            status=status,
            window_minutes=window_minutes,
            allowed_downtime_minutes=allowed_downtime,
            consumed_downtime_minutes=consumed_downtime,
            remaining_downtime_minutes=remaining_downtime,
            burn_rate=burn_rate,
            time_until_exhausted=time_until_exhausted,
            service=service,
        )
    
    async def calculate_from_prometheus(
        self,
        service: str,
        window: str = "30d",
        slo: Optional[float] = None,
    ) -> ErrorBudget:
        """
        Calculate error budget from Prometheus metrics.
        
        Args:
            service: Service name
            window: Prometheus time window (e.g., "30d", "7d", "24h")
            slo: SLO target override
        """
        if not self.prometheus:
            raise RuntimeError("Prometheus client not configured")
        
        # Parse window to minutes
        window_minutes = self._parse_window(window)
        
        # Query Prometheus
        total_query = self.QUERIES["total_requests"].format(
            service=service, window=window
        )
        failed_query = self.QUERIES["failed_requests"].format(
            service=service, window=window
        )
        
        target_slo = slo or self.get_slo(service)
        burn_query = self.QUERIES["burn_rate"].format(
            service=service, error_budget=1 - target_slo
        )
        
        # Execute queries
        total_result = await self.prometheus.query(total_query)
        failed_result = await self.prometheus.query(failed_query)
        burn_result = await self.prometheus.query(burn_query)
        
        total_requests = self._extract_value(total_result, 0)
        failed_requests = self._extract_value(failed_result, 0)
        burn_rate = self._extract_value(burn_result, None)
        
        return self.calculate(
            service=service,
            total_requests=int(total_requests),
            failed_requests=int(failed_requests),
            window_minutes=window_minutes,
            slo=target_slo,
            current_burn_rate=burn_rate,
        )
    
    def get_prometheus_queries(self, service: str) -> dict[str, str]:
        """Get Prometheus queries for a service."""
        target_slo = self.get_slo(service)
        error_budget = 1 - target_slo
        
        return {
            "error_rate_1h": self.QUERIES["error_rate_1h"].format(service=service),
            "total_requests_30d": self.QUERIES["total_requests"].format(
                service=service, window="30d"
            ),
            "failed_requests_30d": self.QUERIES["failed_requests"].format(
                service=service, window="30d"
            ),
            "burn_rate": self.QUERIES["burn_rate"].format(
                service=service, error_budget=error_budget
            ),
        }
    
    def _parse_window(self, window: str) -> int:
        """Parse Prometheus window string to minutes."""
        if window.endswith("d"):
            return int(window[:-1]) * 1440
        elif window.endswith("h"):
            return int(window[:-1]) * 60
        elif window.endswith("m"):
            return int(window[:-1])
        else:
            return self.WINDOW_MONTHLY
    
    def _extract_value(
        self, result: Any, default: Any = None
    ) -> float | None:
        """Extract scalar value from Prometheus result."""
        try:
            if isinstance(result, dict):
                if "data" in result and "result" in result["data"]:
                    data = result["data"]["result"]
                    if data and len(data) > 0:
                        return float(data[0]["value"][1])
            elif isinstance(result, (int, float)):
                return float(result)
        except (KeyError, IndexError, TypeError, ValueError):
            pass
        return default
