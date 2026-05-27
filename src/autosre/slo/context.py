"""
SLO Context Provider

Injects SLO and error budget context into incident investigations.
This helps operators understand the impact of incidents on SLOs.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
import logging

from .error_budget import ErrorBudget, ErrorBudgetCalculator, ErrorBudgetStatus
from .availability import ServiceAvailability, AvailabilityCalculator

logger = logging.getLogger(__name__)


@dataclass
class IncidentBudgetImpact:
    """Impact of an incident on error budget."""
    incident_id: str
    service: str
    
    # Duration
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_minutes: float = 0
    
    # Request impact
    requests_affected: int = 0
    requests_failed: int = 0
    
    # Budget impact
    budget_consumed_percent: float = 0  # Of total monthly budget
    budget_remaining_after: float = 0   # Remaining after incident
    
    # Monthly context
    monthly_budget_minutes: float = 0
    monthly_budget_consumed_before: float = 0
    
    # Severity assessment
    severity: str = "low"  # low, medium, high, critical
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "service": self.service,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration_minutes": round(self.duration_minutes, 2),
            "requests_affected": self.requests_affected,
            "requests_failed": self.requests_failed,
            "budget_consumed_percent": round(self.budget_consumed_percent, 2),
            "budget_remaining_after": round(self.budget_remaining_after, 2),
            "monthly_budget_minutes": round(self.monthly_budget_minutes, 2),
            "severity": self.severity,
        }
    
    def get_summary(self) -> str:
        """Human-readable summary."""
        status_emoji = {
            "low": "🟢",
            "medium": "🟡", 
            "high": "🟠",
            "critical": "🔴",
        }.get(self.severity, "⚪")
        
        lines = [
            f"{status_emoji} Incident Budget Impact: {self.severity.upper()}",
            f"",
            f"Duration: {self.duration_minutes:.1f} minutes",
            f"Requests Failed: {self.requests_failed:,} / {self.requests_affected:,}",
            f"",
            f"Budget Consumed: {self.budget_consumed_percent:.2f}% of monthly",
            f"Budget Remaining: {self.budget_remaining_after:.1f}%",
        ]
        
        if self.budget_remaining_after < 20:
            lines.append("")
            lines.append("⚠️  WARNING: Error budget critically low!")
            lines.append("   Consider pausing non-critical deployments")
        
        return "\n".join(lines)


@dataclass
class SLOContext:
    """Complete SLO context for an investigation."""
    service: str
    
    # Current state
    current_availability: Optional[ServiceAvailability] = None
    current_budget: Optional[ErrorBudget] = None
    
    # Incident impact
    incident_impact: Optional[IncidentBudgetImpact] = None
    
    # Historical
    historical_compliance: list[dict[str, Any]] = field(default_factory=list)
    slo_history_days: int = 30
    
    # Recommendations
    recommendations: list[str] = field(default_factory=list)
    
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "service": self.service,
            "current_availability": (
                self.current_availability.to_dict()
                if self.current_availability else None
            ),
            "current_budget": (
                self.current_budget.to_dict()
                if self.current_budget else None
            ),
            "incident_impact": (
                self.incident_impact.to_dict()
                if self.incident_impact else None
            ),
            "historical_compliance": self.historical_compliance,
            "recommendations": self.recommendations,
            "generated_at": self.generated_at.isoformat(),
        }
    
    def get_investigation_context(self) -> str:
        """
        Generate context string for inclusion in investigation prompts.
        
        This provides the LLM with SLO-aware context for decision making.
        """
        lines = [
            "## SLO Context",
            "",
            f"**Service:** {self.service}",
        ]
        
        if self.current_availability:
            av = self.current_availability
            lines.extend([
                "",
                "### Current Availability",
                f"- Availability: {av.availability_percent:.3f}%",
                f"- Total Requests: {av.total_requests:,}",
                f"- Failed Requests: {av.failed_requests:,}",
            ])
            if av.slo_target:
                status = "✅ Met" if av.slo_met else "❌ Not Met"
                lines.append(f"- SLO Target: {av.slo_target * 100:.3f}% ({status})")
        
        if self.current_budget:
            eb = self.current_budget
            lines.extend([
                "",
                "### Error Budget",
                f"- SLO: {eb.slo * 100:.3f}%",
                f"- Budget Remaining: {eb.percentage_remaining:.1f}%",
                f"- Status: {eb.status.value.upper()}",
                f"- Remaining Downtime: {eb.remaining_downtime_minutes:.1f} minutes this month",
            ])
            if eb.burn_rate > 1.5:
                lines.append(f"- ⚠️ Burn Rate: {eb.burn_rate:.1f}x (elevated)")
            
            if not eb.can_deploy:
                lines.append("- 🚫 Deployments BLOCKED due to low budget")
        
        if self.incident_impact:
            imp = self.incident_impact
            lines.extend([
                "",
                "### Incident Impact",
                f"- Duration: {imp.duration_minutes:.1f} minutes",
                f"- Budget Consumed: {imp.budget_consumed_percent:.2f}%",
                f"- Severity: {imp.severity.upper()}",
            ])
        
        if self.recommendations:
            lines.extend([
                "",
                "### Recommendations",
            ])
            for rec in self.recommendations:
                lines.append(f"- {rec}")
        
        return "\n".join(lines)


class SLOContextProvider:
    """
    Provides SLO context for incident investigations.
    
    Integrates with:
    - Error budget calculator
    - Availability calculator
    - Historical SLO data
    """
    
    def __init__(
        self,
        error_budget_calculator: Optional[ErrorBudgetCalculator] = None,
        availability_calculator: Optional[AvailabilityCalculator] = None,
        prometheus_client: Any = None,
    ):
        self.budget_calc = error_budget_calculator or ErrorBudgetCalculator(prometheus_client)
        self.availability_calc = availability_calculator or AvailabilityCalculator(prometheus_client)
        self.prometheus = prometheus_client
        
        # SLO configurations
        self._slo_configs: dict[str, dict[str, Any]] = {}
    
    def configure_service_slo(
        self,
        service: str,
        slo: float,
        window_days: int = 30,
        metadata: Optional[dict] = None,
    ) -> None:
        """
        Configure SLO for a service.
        
        Args:
            service: Service name
            slo: SLO target (0.0 to 1.0)
            window_days: Measurement window in days
            metadata: Additional metadata (owner, tier, etc.)
        """
        self._slo_configs[service] = {
            "slo": slo,
            "window_days": window_days,
            "metadata": metadata or {},
        }
        self.budget_calc.configure_slo(service, slo)
        logger.info(f"Configured SLO for {service}: {slo * 100:.3f}%")
    
    def get_context(
        self,
        service: str,
        incident_id: Optional[str] = None,
        incident_start: Optional[datetime] = None,
        incident_end: Optional[datetime] = None,
        requests_failed: int = 0,
        requests_total: int = 0,
    ) -> SLOContext:
        """
        Get SLO context for a service (synchronous, from cached/local data).
        
        For real-time Prometheus data, use get_context_from_prometheus().
        """
        config = self._slo_configs.get(service, {})
        slo = config.get("slo", 0.999)
        
        # Create context with incident impact if provided
        context = SLOContext(service=service)
        
        if incident_id and incident_start:
            context.incident_impact = self._calculate_incident_impact(
                incident_id=incident_id,
                service=service,
                started_at=incident_start,
                ended_at=incident_end,
                requests_failed=requests_failed,
                requests_total=requests_total,
                slo=slo,
            )
        
        # Generate recommendations
        context.recommendations = self._generate_recommendations(context)
        
        return context
    
    async def get_context_from_prometheus(
        self,
        service: str,
        incident_id: Optional[str] = None,
        incident_start: Optional[datetime] = None,
        incident_end: Optional[datetime] = None,
    ) -> SLOContext:
        """
        Get complete SLO context from Prometheus.
        
        Args:
            service: Service name
            incident_id: Optional incident ID for impact calculation
            incident_start: Incident start time
            incident_end: Incident end time (None = ongoing)
        """
        config = self._slo_configs.get(service, {})
        slo = config.get("slo", 0.999)
        window_days = config.get("window_days", 30)
        
        # Get current availability
        availability = await self.availability_calc.calculate_from_prometheus(
            service=service,
            window="1h",
            slo_target=slo,
        )
        
        # Get error budget
        budget = await self.budget_calc.calculate_from_prometheus(
            service=service,
            window=f"{window_days}d",
            slo=slo,
        )
        
        # Calculate incident impact if incident info provided
        incident_impact = None
        if incident_id and incident_start:
            incident_impact = await self._calculate_incident_impact_from_prometheus(
                incident_id=incident_id,
                service=service,
                started_at=incident_start,
                ended_at=incident_end,
                slo=slo,
                budget=budget,
            )
        
        # Get historical compliance
        historical = await self._get_historical_compliance(service, days=30)
        
        context = SLOContext(
            service=service,
            current_availability=availability,
            current_budget=budget,
            incident_impact=incident_impact,
            historical_compliance=historical,
        )
        
        # Generate recommendations
        context.recommendations = self._generate_recommendations(context)
        
        return context
    
    def _calculate_incident_impact(
        self,
        incident_id: str,
        service: str,
        started_at: datetime,
        ended_at: Optional[datetime],
        requests_failed: int,
        requests_total: int,
        slo: float,
    ) -> IncidentBudgetImpact:
        """Calculate incident impact on error budget."""
        # Calculate duration
        end_time = ended_at or datetime.now(timezone.utc)
        duration = (end_time - started_at).total_seconds() / 60
        
        # Calculate monthly budget
        error_budget = 1 - slo
        monthly_minutes = 43200  # 30 days
        monthly_budget_minutes = monthly_minutes * error_budget
        
        # Calculate impact
        if requests_total > 0:
            incident_error_rate = requests_failed / requests_total
            budget_consumed_percent = (incident_error_rate / error_budget) * 100
        else:
            # Fall back to duration-based calculation
            budget_consumed_percent = (duration / monthly_budget_minutes) * 100
        
        budget_consumed_percent = min(budget_consumed_percent, 100)
        
        # Determine severity
        if budget_consumed_percent > 50:
            severity = "critical"
        elif budget_consumed_percent > 20:
            severity = "high"
        elif budget_consumed_percent > 5:
            severity = "medium"
        else:
            severity = "low"
        
        return IncidentBudgetImpact(
            incident_id=incident_id,
            service=service,
            started_at=started_at,
            ended_at=ended_at,
            duration_minutes=duration,
            requests_affected=requests_total,
            requests_failed=requests_failed,
            budget_consumed_percent=budget_consumed_percent,
            budget_remaining_after=100 - budget_consumed_percent,  # Simplified
            monthly_budget_minutes=monthly_budget_minutes,
            severity=severity,
        )
    
    async def _calculate_incident_impact_from_prometheus(
        self,
        incident_id: str,
        service: str,
        started_at: datetime,
        ended_at: Optional[datetime],
        slo: float,
        budget: ErrorBudget,
    ) -> IncidentBudgetImpact:
        """Calculate incident impact using Prometheus queries."""
        end_time = ended_at or datetime.now(timezone.utc)
        duration = (end_time - started_at).total_seconds() / 60
        
        # Query for requests during incident window
        window_seconds = int((end_time - started_at).total_seconds())
        window = f"{window_seconds}s"
        
        if self.prometheus:
            try:
                # Query failed requests during incident
                failed_query = f'sum(increase(http_requests_total{{service="{service}",status=~"5.."}}[{window}]))'
                total_query = f'sum(increase(http_requests_total{{service="{service}"}}[{window}]))'
                
                failed_result = await self.prometheus.query(failed_query)
                total_result = await self.prometheus.query(total_query)
                
                requests_failed = int(self._extract_value(failed_result, 0))
                requests_total = int(self._extract_value(total_result, 0))
            except Exception as e:
                logger.warning(f"Failed to query incident metrics: {e}")
                requests_failed = 0
                requests_total = 0
        else:
            requests_failed = 0
            requests_total = 0
        
        return self._calculate_incident_impact(
            incident_id=incident_id,
            service=service,
            started_at=started_at,
            ended_at=ended_at,
            requests_failed=requests_failed,
            requests_total=requests_total,
            slo=slo,
        )
    
    async def _get_historical_compliance(
        self, service: str, days: int = 30
    ) -> list[dict[str, Any]]:
        """Get historical SLO compliance data."""
        if not self.prometheus:
            return []
        
        # Query daily availability for the past N days
        # This is a simplified version - production would use recording rules
        history = []
        
        try:
            config = self._slo_configs.get(service, {})
            slo = config.get("slo", 0.999)
            
            # Query average daily availability
            query = f'''
                avg_over_time(
                    (
                        sum(rate(http_requests_total{{service="{service}",status=~"2.."}}[1d]))
                        /
                        sum(rate(http_requests_total{{service="{service}"}}[1d]))
                    )[{days}d:1d]
                )
            '''
            
            result = await self.prometheus.query_range(
                query,
                start=datetime.now(timezone.utc) - timedelta(days=days),
                end=datetime.now(timezone.utc),
                step="1d",
            )
            
            if isinstance(result, dict) and "data" in result:
                for item in result["data"].get("result", []):
                    for ts, value in item.get("values", []):
                        availability = float(value)
                        history.append({
                            "date": datetime.fromtimestamp(ts).date().isoformat(),
                            "availability": availability,
                            "slo_met": availability >= slo,
                        })
        except Exception as e:
            logger.warning(f"Failed to get historical compliance: {e}")
        
        return history
    
    def _generate_recommendations(self, context: SLOContext) -> list[str]:
        """Generate recommendations based on SLO context."""
        recommendations = []
        
        if context.current_budget:
            budget = context.current_budget
            
            if budget.status == ErrorBudgetStatus.EXHAUSTED:
                recommendations.extend([
                    "🚨 Error budget exhausted - halt all non-critical deployments",
                    "Investigate and resolve current errors immediately",
                    "Consider rolling back recent changes",
                ])
            elif budget.status == ErrorBudgetStatus.CRITICAL:
                recommendations.extend([
                    "⚠️ Error budget critically low - proceed with extreme caution",
                    "Only deploy critical fixes with rollback plans",
                    "Increase monitoring during any changes",
                ])
            elif budget.status == ErrorBudgetStatus.WARNING:
                recommendations.extend([
                    "Error budget below 50% - consider risk carefully",
                    "Ensure robust rollback capability for deployments",
                ])
            
            if budget.burn_rate > 2.0:
                recommendations.append(
                    f"🔥 High burn rate ({budget.burn_rate:.1f}x) - "
                    "errors accumulating faster than sustainable"
                )
        
        if context.current_availability:
            av = context.current_availability
            
            if av.worst_endpoints:
                worst = av.worst_endpoints[0]
                if worst.availability < 0.95:
                    recommendations.append(
                        f"Focus on worst endpoint: {worst.method} {worst.endpoint} "
                        f"({worst.availability_percent:.1f}% availability)"
                    )
        
        if context.incident_impact:
            impact = context.incident_impact
            
            if impact.severity in ("high", "critical"):
                recommendations.append(
                    "Consider scheduling a post-incident review"
                )
            
            if impact.budget_remaining_after < 30:
                recommendations.append(
                    "After resolution, allow time for budget recovery before new changes"
                )
        
        return recommendations
    
    def _extract_value(self, result: Any, default: Any = None) -> float | None:
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
