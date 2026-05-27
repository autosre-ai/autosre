"""
SLO Reporting for AutoSRE.

Provides comprehensive SLO reporting capabilities including:
- SLO compliance reports
- Error budget reports
- Trend analysis
- Executive summaries
"""

import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from .definition import (
    ComplianceStatus,
)
from .budget import (
    ErrorBudgetStatus,
)


class ReportPeriod(str, Enum):
    """Report period options."""
    
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    CUSTOM = "custom"


class ReportFormat(str, Enum):
    """Report output formats."""
    
    JSON = "json"
    MARKDOWN = "markdown"
    HTML = "html"
    TEXT = "text"
    SLACK = "slack"


class TrendDirection(str, Enum):
    """Trend direction indicators."""
    
    IMPROVING = "improving"
    STABLE = "stable"
    DEGRADING = "degrading"
    VOLATILE = "volatile"


class SLOComplianceRecord(BaseModel):
    """Single compliance measurement record."""
    
    timestamp: datetime
    slo_id: str
    slo_name: str
    target: float
    actual_sli: float
    is_compliant: bool
    budget_consumed_pct: float
    budget_remaining_pct: float
    burn_rate: float


class SLOTrend(BaseModel):
    """SLO trend analysis."""
    
    slo_id: str
    slo_name: str
    period_start: datetime
    period_end: datetime
    
    # Trend metrics
    direction: TrendDirection
    average_sli: float
    min_sli: float
    max_sli: float
    sli_variance: float
    
    # Compliance
    compliance_percentage: float    # % of time in compliance
    total_violations: int
    total_violation_minutes: float
    
    # Budget trends
    budget_trend_pct_per_day: float  # Average daily budget change
    projected_end_of_period_budget: float


class ServiceSLOSummary(BaseModel):
    """SLO summary for a single service."""
    
    service_id: str
    service_name: str
    
    # SLO counts
    total_slos: int
    healthy_slos: int
    warning_slos: int
    critical_slos: int
    violated_slos: int
    
    # Aggregate metrics
    average_compliance: float
    worst_slo_id: Optional[str] = None
    worst_slo_name: Optional[str] = None
    worst_slo_remaining_pct: Optional[float] = None
    
    # Risk assessment
    overall_risk: str = "low"   # low, medium, high, critical


class SLOReport(BaseModel):
    """Comprehensive SLO report."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    
    # Time period
    period_type: ReportPeriod
    period_start: datetime
    period_end: datetime
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Summary statistics
    total_slos: int = 0
    healthy_count: int = 0
    warning_count: int = 0
    critical_count: int = 0
    violated_count: int = 0
    
    # Aggregate compliance
    overall_compliance_pct: float = 100.0
    average_budget_remaining_pct: float = 100.0
    
    # Detailed data
    slo_statuses: list[dict] = Field(default_factory=list)
    service_summaries: list[ServiceSLOSummary] = Field(default_factory=list)
    trends: list[SLOTrend] = Field(default_factory=list)
    
    # Highlights
    top_violations: list[dict] = Field(default_factory=list)
    budget_alerts: list[dict] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    
    # Metadata
    generated_by: str = "autosre"
    
    def to_markdown(self) -> str:
        """Convert report to markdown format."""
        lines = [
            f"# SLO Report: {self.name}",
            "",
            f"**Period:** {self.period_start.strftime('%Y-%m-%d')} to {self.period_end.strftime('%Y-%m-%d')}",
            f"**Generated:** {self.generated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "",
            "## Summary",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Total SLOs | {self.total_slos} |",
            f"| Healthy | {self.healthy_count} ({self._pct(self.healthy_count)}%) |",
            f"| Warning | {self.warning_count} ({self._pct(self.warning_count)}%) |",
            f"| Critical | {self.critical_count} ({self._pct(self.critical_count)}%) |",
            f"| Violated | {self.violated_count} ({self._pct(self.violated_count)}%) |",
            f"| Overall Compliance | {self.overall_compliance_pct:.2f}% |",
            f"| Avg Budget Remaining | {self.average_budget_remaining_pct:.2f}% |",
            "",
        ]
        
        # Top violations
        if self.top_violations:
            lines.extend([
                "## Top Violations",
                "",
                "| SLO | Target | Actual | Budget Remaining |",
                "|-----|--------|--------|------------------|",
            ])
            for v in self.top_violations[:5]:
                lines.append(
                    f"| {v.get('slo_name', 'N/A')} | "
                    f"{v.get('target', 0)*100:.2f}% | "
                    f"{v.get('actual', 0)*100:.2f}% | "
                    f"{v.get('remaining_pct', 0):.2f}% |"
                )
            lines.append("")
        
        # Budget alerts
        if self.budget_alerts:
            lines.extend([
                "## Budget Alerts",
                "",
            ])
            for alert in self.budget_alerts[:5]:
                lines.append(f"- **{alert.get('slo_name', 'N/A')}**: {alert.get('message', '')}")
            lines.append("")
        
        # Recommendations
        if self.recommendations:
            lines.extend([
                "## Recommendations",
                "",
            ])
            for rec in self.recommendations:
                lines.append(f"- {rec}")
            lines.append("")
        
        return "\n".join(lines)
    
    def _pct(self, count: int) -> float:
        """Calculate percentage of total."""
        if self.total_slos == 0:
            return 0.0
        return round((count / self.total_slos) * 100, 1)
    
    def to_slack_blocks(self) -> list[dict]:
        """Convert report to Slack block format."""
        status_emoji = "🟢" if self.violated_count == 0 else "🔴" if self.violated_count > 0 else "🟡"
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{status_emoji} SLO Report: {self.name}",
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Period:*\n{self.period_start.strftime('%Y-%m-%d')} to {self.period_end.strftime('%Y-%m-%d')}"},
                    {"type": "mrkdwn", "text": f"*Overall Compliance:*\n{self.overall_compliance_pct:.2f}%"},
                ]
            },
            {"type": "divider"},
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Healthy:* {self.healthy_count} 🟢"},
                    {"type": "mrkdwn", "text": f"*Warning:* {self.warning_count} 🟡"},
                    {"type": "mrkdwn", "text": f"*Critical:* {self.critical_count} 🟠"},
                    {"type": "mrkdwn", "text": f"*Violated:* {self.violated_count} 🔴"},
                ]
            },
        ]
        
        # Add top violations
        if self.top_violations:
            violation_text = "\n".join([
                f"• {v.get('slo_name', 'N/A')}: {v.get('remaining_pct', 0):.1f}% remaining"
                for v in self.top_violations[:3]
            ])
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Top Violations:*\n{violation_text}",
                }
            })
        
        return blocks


class ReportGenerator:
    """Generator for SLO reports."""
    
    def __init__(self):
        """Initialize the report generator."""
        self._compliance_history: dict[str, list[SLOComplianceRecord]] = {}
    
    def record_compliance(
        self,
        slo_id: str,
        slo_name: str,
        target: float,
        actual_sli: float,
        budget_consumed_pct: float,
        burn_rate: float = 0.0,
        timestamp: Optional[datetime] = None,
    ) -> SLOComplianceRecord:
        """Record a compliance measurement."""
        timestamp = timestamp or datetime.now(timezone.utc)
        
        record = SLOComplianceRecord(
            timestamp=timestamp,
            slo_id=slo_id,
            slo_name=slo_name,
            target=target,
            actual_sli=actual_sli,
            is_compliant=actual_sli >= target,
            budget_consumed_pct=budget_consumed_pct,
            budget_remaining_pct=100.0 - budget_consumed_pct,
            burn_rate=burn_rate,
        )
        
        if slo_id not in self._compliance_history:
            self._compliance_history[slo_id] = []
        self._compliance_history[slo_id].append(record)
        
        return record
    
    def generate_report(
        self,
        name: str,
        statuses: list[ErrorBudgetStatus],
        period_type: ReportPeriod = ReportPeriod.WEEKLY,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
    ) -> SLOReport:
        """Generate an SLO report from current statuses."""
        now = datetime.now(timezone.utc)
        
        # Calculate period
        if period_start is None:
            if period_type == ReportPeriod.DAILY:
                period_start = now - timedelta(days=1)
            elif period_type == ReportPeriod.WEEKLY:
                period_start = now - timedelta(days=7)
            elif period_type == ReportPeriod.MONTHLY:
                period_start = now - timedelta(days=30)
            elif period_type == ReportPeriod.QUARTERLY:
                period_start = now - timedelta(days=90)
            else:
                period_start = now - timedelta(days=7)
        
        period_end = period_end or now
        
        # Count statuses
        healthy = sum(1 for s in statuses if s.compliance_status == ComplianceStatus.HEALTHY)
        warning = sum(1 for s in statuses if s.compliance_status == ComplianceStatus.WARNING)
        critical = sum(1 for s in statuses if s.compliance_status == ComplianceStatus.CRITICAL)
        violated = sum(1 for s in statuses if s.compliance_status == ComplianceStatus.VIOLATED)
        
        total = len(statuses)
        
        # Calculate averages
        avg_remaining = sum(s.remaining_percentage for s in statuses) / total if total > 0 else 100.0
        
        # Compliance is based on meeting target
        compliant = sum(1 for s in statuses if s.current_sli >= s.target_sli)
        compliance_pct = (compliant / total * 100) if total > 0 else 100.0
        
        # Find top violations (lowest budget remaining)
        sorted_by_budget = sorted(statuses, key=lambda s: s.remaining_percentage)
        top_violations = [
            {
                "slo_id": s.slo_id,
                "slo_name": s.slo_name,
                "target": s.target_sli,
                "actual": s.current_sli,
                "remaining_pct": s.remaining_percentage,
            }
            for s in sorted_by_budget[:5]
            if s.remaining_percentage < 50.0 or s.compliance_status != ComplianceStatus.HEALTHY
        ]
        
        # Generate budget alerts
        budget_alerts = []
        for s in statuses:
            if s.compliance_status == ComplianceStatus.VIOLATED:
                budget_alerts.append({
                    "slo_id": s.slo_id,
                    "slo_name": s.slo_name,
                    "severity": "critical",
                    "message": f"Error budget exhausted! {s.remaining_percentage:.1f}% remaining",
                })
            elif s.compliance_status == ComplianceStatus.CRITICAL:
                budget_alerts.append({
                    "slo_id": s.slo_id,
                    "slo_name": s.slo_name,
                    "severity": "warning",
                    "message": f"Error budget critically low: {s.remaining_percentage:.1f}% remaining",
                })
        
        # Generate recommendations
        recommendations = self._generate_recommendations(statuses)
        
        return SLOReport(
            name=name,
            period_type=period_type,
            period_start=period_start,
            period_end=period_end,
            total_slos=total,
            healthy_count=healthy,
            warning_count=warning,
            critical_count=critical,
            violated_count=violated,
            overall_compliance_pct=compliance_pct,
            average_budget_remaining_pct=avg_remaining,
            slo_statuses=[s.model_dump() for s in statuses],
            top_violations=top_violations,
            budget_alerts=budget_alerts,
            recommendations=recommendations,
        )
    
    def _generate_recommendations(
        self,
        statuses: list[ErrorBudgetStatus],
    ) -> list[str]:
        """Generate recommendations based on SLO statuses."""
        recommendations = []
        
        # Check for violations
        violated = [s for s in statuses if s.compliance_status == ComplianceStatus.VIOLATED]
        if violated:
            recommendations.append(
                f"URGENT: {len(violated)} SLO(s) have exhausted error budgets. "
                "Consider halting non-critical deployments and investigating root causes."
            )
        
        # Check for high burn rates
        high_burn = [
            s for s in statuses
            if s.burn_rates.get("1h") and s.burn_rates["1h"].burn_rate > 10
        ]
        if high_burn:
            recommendations.append(
                f"HIGH ALERT: {len(high_burn)} SLO(s) have critical burn rates (>10x). "
                "Immediate investigation required."
            )
        
        # Check for consistently low budgets
        low_budget = [s for s in statuses if s.remaining_percentage < 30.0 and s.compliance_status != ComplianceStatus.VIOLATED]
        if low_budget:
            recommendations.append(
                f"CAUTION: {len(low_budget)} SLO(s) have less than 30% error budget remaining. "
                "Plan reliability improvements and consider reducing deployment frequency."
            )
        
        # Suggest target adjustments for repeatedly violated SLOs
        # (Would need historical data to implement fully)
        
        # Check for SLOs with no issues
        healthy = [s for s in statuses if s.compliance_status == ComplianceStatus.HEALTHY and s.remaining_percentage > 80]
        if healthy and len(healthy) == len(statuses):
            recommendations.append(
                "All SLOs are healthy with ample error budget. "
                "Consider whether targets are appropriately ambitious."
            )
        
        return recommendations
    
    def generate_trend_analysis(
        self,
        slo_id: str,
        slo_name: str,
        period_days: int = 30,
    ) -> Optional[SLOTrend]:
        """Generate trend analysis for an SLO."""
        history = self._compliance_history.get(slo_id, [])
        
        if not history:
            return None
        
        now = datetime.now(timezone.utc)
        period_start = now - timedelta(days=period_days)
        
        # Filter to period
        period_records = [
            r for r in history
            if r.timestamp >= period_start
        ]
        
        if not period_records:
            return None
        
        # Calculate metrics
        sli_values = [r.actual_sli for r in period_records]
        avg_sli = sum(sli_values) / len(sli_values)
        min_sli = min(sli_values)
        max_sli = max(sli_values)
        
        # Variance
        variance = sum((v - avg_sli) ** 2 for v in sli_values) / len(sli_values)
        
        # Compliance percentage
        compliant_count = sum(1 for r in period_records if r.is_compliant)
        compliance_pct = (compliant_count / len(period_records)) * 100
        
        # Violations
        violations = [r for r in period_records if not r.is_compliant]
        total_violations = len(violations)
        
        # Trend direction
        if len(period_records) >= 2:
            first_half = sli_values[:len(sli_values)//2]
            second_half = sli_values[len(sli_values)//2:]
            
            first_avg = sum(first_half) / len(first_half) if first_half else 0
            second_avg = sum(second_half) / len(second_half) if second_half else 0
            
            diff = second_avg - first_avg
            
            if variance > 0.001:  # High variance
                direction = TrendDirection.VOLATILE
            elif diff > 0.001:
                direction = TrendDirection.IMPROVING
            elif diff < -0.001:
                direction = TrendDirection.DEGRADING
            else:
                direction = TrendDirection.STABLE
        else:
            direction = TrendDirection.STABLE
        
        # Budget trend
        budget_values = [r.budget_remaining_pct for r in period_records]
        if len(budget_values) >= 2:
            budget_change = budget_values[-1] - budget_values[0]
            budget_trend = budget_change / period_days
        else:
            budget_trend = 0.0
        
        return SLOTrend(
            slo_id=slo_id,
            slo_name=slo_name,
            period_start=period_start,
            period_end=now,
            direction=direction,
            average_sli=avg_sli,
            min_sli=min_sli,
            max_sli=max_sli,
            sli_variance=variance,
            compliance_percentage=compliance_pct,
            total_violations=total_violations,
            total_violation_minutes=0.0,  # Would need more granular data
            budget_trend_pct_per_day=budget_trend,
            projected_end_of_period_budget=budget_values[-1] + (budget_trend * 30) if budget_values else 100.0,
        )
    
    def generate_service_summary(
        self,
        service_id: str,
        service_name: str,
        statuses: list[ErrorBudgetStatus],
    ) -> ServiceSLOSummary:
        """Generate summary for a service's SLOs."""
        total = len(statuses)
        healthy = sum(1 for s in statuses if s.compliance_status == ComplianceStatus.HEALTHY)
        warning = sum(1 for s in statuses if s.compliance_status == ComplianceStatus.WARNING)
        critical = sum(1 for s in statuses if s.compliance_status == ComplianceStatus.CRITICAL)
        violated = sum(1 for s in statuses if s.compliance_status == ComplianceStatus.VIOLATED)
        
        # Average compliance
        avg_compliance = (
            sum(s.remaining_percentage for s in statuses) / total
            if total > 0 else 100.0
        )
        
        # Find worst SLO
        worst = min(statuses, key=lambda s: s.remaining_percentage) if statuses else None
        
        # Assess risk
        if violated > 0:
            risk = "critical"
        elif critical > 0:
            risk = "high"
        elif warning > 0:
            risk = "medium"
        else:
            risk = "low"
        
        return ServiceSLOSummary(
            service_id=service_id,
            service_name=service_name,
            total_slos=total,
            healthy_slos=healthy,
            warning_slos=warning,
            critical_slos=critical,
            violated_slos=violated,
            average_compliance=avg_compliance,
            worst_slo_id=worst.slo_id if worst else None,
            worst_slo_name=worst.slo_name if worst else None,
            worst_slo_remaining_pct=worst.remaining_percentage if worst else None,
            overall_risk=risk,
        )


class SLODashboard:
    """Dashboard for SLO visualization and monitoring."""
    
    def __init__(self, report_generator: ReportGenerator):
        """Initialize the dashboard."""
        self.report_generator = report_generator
        self._refresh_interval_seconds: int = 60
    
    def get_overview(
        self,
        statuses: list[ErrorBudgetStatus],
    ) -> dict[str, Any]:
        """Get dashboard overview data."""
        total = len(statuses)
        
        # Status counts
        status_counts = {
            "healthy": sum(1 for s in statuses if s.compliance_status == ComplianceStatus.HEALTHY),
            "warning": sum(1 for s in statuses if s.compliance_status == ComplianceStatus.WARNING),
            "critical": sum(1 for s in statuses if s.compliance_status == ComplianceStatus.CRITICAL),
            "violated": sum(1 for s in statuses if s.compliance_status == ComplianceStatus.VIOLATED),
        }
        
        # Overall health score (0-100)
        if total > 0:
            weighted_score = (
                status_counts["healthy"] * 100 +
                status_counts["warning"] * 70 +
                status_counts["critical"] * 30 +
                status_counts["violated"] * 0
            ) / total
        else:
            weighted_score = 100.0
        
        # Top issues
        issues = sorted(
            [s for s in statuses if s.compliance_status != ComplianceStatus.HEALTHY],
            key=lambda s: s.remaining_percentage,
        )
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_slos": total,
            "status_counts": status_counts,
            "health_score": round(weighted_score, 1),
            "health_status": self._score_to_status(weighted_score),
            "top_issues": [
                {
                    "slo_id": s.slo_id,
                    "slo_name": s.slo_name,
                    "status": s.compliance_status.value,
                    "remaining_pct": round(s.remaining_percentage, 1),
                    "action": s.recommended_action.value,
                }
                for s in issues[:5]
            ],
            "refresh_interval_seconds": self._refresh_interval_seconds,
        }
    
    def _score_to_status(self, score: float) -> str:
        """Convert health score to status string."""
        if score >= 90:
            return "excellent"
        elif score >= 70:
            return "good"
        elif score >= 50:
            return "fair"
        elif score >= 30:
            return "poor"
        else:
            return "critical"
    
    def get_slo_detail(
        self,
        status: ErrorBudgetStatus,
    ) -> dict[str, Any]:
        """Get detailed view for a single SLO."""
        return {
            "slo_id": status.slo_id,
            "slo_name": status.slo_name,
            "timestamp": status.timestamp.isoformat(),
            
            # Current status
            "compliance_status": status.compliance_status.value,
            "recommended_action": status.recommended_action.value,
            
            # SLI metrics
            "current_sli": round(status.current_sli * 100, 4),
            "target_sli": round(status.target_sli * 100, 4),
            "sli_gap": round((status.target_sli - status.current_sli) * 100, 4),
            
            # Budget metrics
            "budget": {
                "total_minutes": round(status.total_budget_minutes, 2),
                "consumed_minutes": round(status.consumed_budget_minutes, 2),
                "remaining_minutes": round(status.remaining_budget_minutes, 2),
                "consumed_pct": round(status.consumed_percentage, 2),
                "remaining_pct": round(status.remaining_percentage, 2),
            },
            
            # Period info
            "period": {
                "start": status.period_start.isoformat(),
                "end": status.period_end.isoformat(),
                "elapsed_pct": round(status.period_elapsed_percentage, 2),
            },
            
            # Burn rates
            "burn_rates": {
                name: {
                    "rate": round(br.burn_rate, 2),
                    "category": br.rate_category.value,
                    "budget_consumed_pct": round(br.budget_consumed_pct, 2),
                    "projected_exhaustion_hours": round(br.projected_exhaustion_hours, 1) if br.projected_exhaustion_hours else None,
                }
                for name, br in status.burn_rates.items()
            },
            
            # Alerts
            "active_alerts": status.active_alerts,
        }


# Convenience functions
def generate_weekly_report(
    name: str,
    statuses: list[ErrorBudgetStatus],
) -> SLOReport:
    """Generate a weekly SLO report."""
    generator = ReportGenerator()
    return generator.generate_report(
        name=name,
        statuses=statuses,
        period_type=ReportPeriod.WEEKLY,
    )


def generate_monthly_report(
    name: str,
    statuses: list[ErrorBudgetStatus],
) -> SLOReport:
    """Generate a monthly SLO report."""
    generator = ReportGenerator()
    return generator.generate_report(
        name=name,
        statuses=statuses,
        period_type=ReportPeriod.MONTHLY,
    )


def format_report(
    report: SLOReport,
    format: ReportFormat = ReportFormat.MARKDOWN,
) -> str:
    """Format a report for output."""
    if format == ReportFormat.MARKDOWN:
        return report.to_markdown()
    elif format == ReportFormat.JSON:
        return report.model_dump_json(indent=2)
    elif format == ReportFormat.TEXT:
        # Simple text format
        lines = [
            f"SLO Report: {report.name}",
            f"Period: {report.period_start.strftime('%Y-%m-%d')} to {report.period_end.strftime('%Y-%m-%d')}",
            "",
            f"Total SLOs: {report.total_slos}",
            f"Healthy: {report.healthy_count}",
            f"Warning: {report.warning_count}",
            f"Critical: {report.critical_count}",
            f"Violated: {report.violated_count}",
            "",
            f"Overall Compliance: {report.overall_compliance_pct:.2f}%",
            f"Avg Budget Remaining: {report.average_budget_remaining_pct:.2f}%",
        ]
        return "\n".join(lines)
    else:
        return report.model_dump_json(indent=2)
