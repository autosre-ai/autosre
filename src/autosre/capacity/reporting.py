"""
Capacity Reporting for AutoSRE.

Provides capacity reporting capabilities including:
- Capacity metrics and utilization reports
- Trend analysis and insights
- Capacity alerts and notifications
- Report generation in multiple formats
"""

import uuid
import statistics
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ReportFormat(str, Enum):
    """Report output formats."""
    
    JSON = "json"
    MARKDOWN = "markdown"
    HTML = "html"
    PDF = "pdf"
    SLACK = "slack"  # Slack-formatted
    CSV = "csv"


class ReportFrequency(str, Enum):
    """Report generation frequency."""
    
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ON_DEMAND = "on_demand"


class ReportSection(str, Enum):
    """Sections in a capacity report."""
    
    SUMMARY = "summary"
    UTILIZATION = "utilization"
    TRENDS = "trends"
    ALERTS = "alerts"
    RECOMMENDATIONS = "recommendations"
    FORECAST = "forecast"
    COST = "cost"
    COMPARISON = "comparison"


class TrendIndicator(str, Enum):
    """Visual indicators for trends."""
    
    UP = "up"           # ↑
    DOWN = "down"       # ↓
    STABLE = "stable"   # →
    CRITICAL = "critical"  # ⚠


class HealthStatus(str, Enum):
    """Health status for capacity."""
    
    HEALTHY = "healthy"          # Green - all good
    WARNING = "warning"          # Yellow - attention needed
    CRITICAL = "critical"        # Red - immediate action
    UNKNOWN = "unknown"          # Gray - no data
    OVER_PROVISIONED = "over_provisioned"  # Blue - too much capacity


class CapacityMetric(BaseModel):
    """A capacity metric data point."""
    
    name: str
    value: float
    unit: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Context
    resource_type: str = ""
    service: str = ""
    region: str = ""
    
    # Thresholds
    warning_threshold: Optional[float] = None
    critical_threshold: Optional[float] = None
    
    # Comparison
    previous_value: Optional[float] = None
    change_percent: Optional[float] = None
    trend: TrendIndicator = TrendIndicator.STABLE
    
    def is_warning(self) -> bool:
        """Check if metric is in warning state."""
        if self.warning_threshold is None:
            return False
        return self.value >= self.warning_threshold
    
    def is_critical(self) -> bool:
        """Check if metric is in critical state."""
        if self.critical_threshold is None:
            return False
        return self.value >= self.critical_threshold
    
    def get_status(self) -> HealthStatus:
        """Get health status for this metric."""
        if self.is_critical():
            return HealthStatus.CRITICAL
        elif self.is_warning():
            return HealthStatus.WARNING
        return HealthStatus.HEALTHY


class ResourceUtilization(BaseModel):
    """Resource utilization summary."""
    
    resource_type: str
    resource_name: str = ""
    
    # Current state
    current_utilization: float
    current_allocation: float
    current_usage: float
    unit: str
    
    # Statistics
    avg_utilization_24h: Optional[float] = None
    max_utilization_24h: Optional[float] = None
    min_utilization_24h: Optional[float] = None
    p95_utilization_24h: Optional[float] = None
    
    # Trends
    trend: TrendIndicator = TrendIndicator.STABLE
    change_vs_yesterday: Optional[float] = None
    change_vs_last_week: Optional[float] = None
    
    # Status
    status: HealthStatus = HealthStatus.HEALTHY
    
    def get_headroom(self) -> float:
        """Get available headroom percentage."""
        return 100 - self.current_utilization


class CapacityTrend(BaseModel):
    """Capacity trend analysis."""
    
    resource_type: str
    period_start: datetime
    period_end: datetime
    
    # Trend data
    data_points: int
    trend_direction: TrendIndicator
    trend_slope: float  # Change per day
    
    # Statistics
    min_value: float
    max_value: float
    avg_value: float
    std_dev: float
    
    # Forecast
    projected_value_7d: Optional[float] = None
    projected_value_30d: Optional[float] = None
    days_until_threshold: Optional[int] = None
    threshold_value: Optional[float] = None
    
    def get_trend_description(self) -> str:
        """Get human-readable trend description."""
        if self.trend_direction == TrendIndicator.CRITICAL:
            return "Critical increase"
        elif self.trend_direction == TrendIndicator.UP:
            return f"Increasing by {self.trend_slope:.1f}% per day"
        elif self.trend_direction == TrendIndicator.DOWN:
            return f"Decreasing by {abs(self.trend_slope):.1f}% per day"
        else:
            return "Stable"


class CapacityAlert(BaseModel):
    """A capacity alert."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    severity: HealthStatus
    resource_type: str
    resource_name: str = ""
    service: str = ""
    region: str = ""
    
    # Alert details
    title: str
    description: str
    current_value: float
    threshold_value: float
    unit: str
    
    # Timing
    triggered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    
    # Actions
    recommended_action: str = ""
    runbook_url: str = ""
    
    @property
    def is_active(self) -> bool:
        """Check if alert is still active."""
        return self.resolved_at is None


class CapacityInsight(BaseModel):
    """An insight from capacity analysis."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    category: str  # e.g., "optimization", "risk", "trend", "anomaly"
    severity: HealthStatus
    
    # Content
    title: str
    description: str
    impact: str = ""
    recommendation: str = ""
    
    # Supporting data
    affected_resources: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    
    # Confidence
    confidence: float = Field(default=0.8, ge=0, le=1)
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CapacitySummary(BaseModel):
    """Summary of overall capacity status."""
    
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    period: str = "current"  # e.g., "current", "24h", "7d"
    
    # Overall health
    overall_health: HealthStatus
    health_score: float = Field(ge=0, le=100)  # 0-100
    
    # Resource counts
    total_resources: int = 0
    healthy_resources: int = 0
    warning_resources: int = 0
    critical_resources: int = 0
    
    # Utilization
    avg_utilization: float = 0.0
    max_utilization: float = 0.0
    
    # Alerts
    active_alerts: int = 0
    critical_alerts: int = 0
    
    # Recommendations
    pending_recommendations: int = 0
    critical_recommendations: int = 0
    
    # Cost
    estimated_monthly_cost: float = 0.0
    potential_savings: float = 0.0
    
    def get_status_emoji(self) -> str:
        """Get emoji for status."""
        return {
            HealthStatus.HEALTHY: "✅",
            HealthStatus.WARNING: "⚠️",
            HealthStatus.CRITICAL: "🚨",
            HealthStatus.UNKNOWN: "❓",
            HealthStatus.OVER_PROVISIONED: "💰",
        }.get(self.overall_health, "❓")


class CapacityReport(BaseModel):
    """A capacity report."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: str = ""
    
    # Scope
    service: str = ""
    environment: str = ""
    region: str = ""
    
    # Time range
    report_start: datetime
    report_end: datetime
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Sections
    sections: list[ReportSection] = Field(default_factory=list)
    
    # Content
    summary: Optional[CapacitySummary] = None
    utilization: list[ResourceUtilization] = Field(default_factory=list)
    trends: list[CapacityTrend] = Field(default_factory=list)
    alerts: list[CapacityAlert] = Field(default_factory=list)
    insights: list[CapacityInsight] = Field(default_factory=list)
    
    # Metadata
    generated_by: str = "autosre"
    format: ReportFormat = ReportFormat.JSON
    
    def add_utilization(self, util: ResourceUtilization) -> None:
        """Add utilization data."""
        self.utilization.append(util)
    
    def add_trend(self, trend: CapacityTrend) -> None:
        """Add trend data."""
        self.trends.append(trend)
    
    def add_alert(self, alert: CapacityAlert) -> None:
        """Add an alert."""
        self.alerts.append(alert)
    
    def add_insight(self, insight: CapacityInsight) -> None:
        """Add an insight."""
        self.insights.append(insight)
    
    def get_active_alerts(self) -> list[CapacityAlert]:
        """Get active alerts."""
        return [a for a in self.alerts if a.is_active]
    
    def get_critical_insights(self) -> list[CapacityInsight]:
        """Get critical insights."""
        return [i for i in self.insights if i.severity == HealthStatus.CRITICAL]


class ReportConfig(BaseModel):
    """Configuration for report generation."""
    
    # Content
    sections: list[ReportSection] = Field(
        default_factory=lambda: [
            ReportSection.SUMMARY,
            ReportSection.UTILIZATION,
            ReportSection.ALERTS,
        ]
    )
    
    # Time range
    lookback_hours: int = Field(default=24, ge=1)
    
    # Thresholds
    warning_threshold: float = Field(default=70.0, ge=0, le=100)
    critical_threshold: float = Field(default=85.0, ge=0, le=100)
    
    # Filtering
    include_healthy: bool = True
    min_severity: HealthStatus = HealthStatus.HEALTHY
    resource_types: Optional[list[str]] = None  # Filter by type
    services: Optional[list[str]] = None  # Filter by service
    
    # Output
    format: ReportFormat = ReportFormat.JSON
    include_raw_data: bool = False
    max_alerts: int = Field(default=50, ge=1)
    max_insights: int = Field(default=20, ge=1)


class CapacityReporter:
    """Reporter for capacity metrics and insights."""
    
    def __init__(self, config: Optional[ReportConfig] = None):
        """Initialize the reporter."""
        self.config = config or ReportConfig()
        self._reports: dict[str, CapacityReport] = {}
    
    def generate_report(
        self,
        title: str,
        utilization_data: list[dict[str, Any]],
        config: Optional[ReportConfig] = None,
        **kwargs: Any,
    ) -> CapacityReport:
        """
        Generate a capacity report.
        
        Args:
            title: Report title
            utilization_data: List of utilization data dicts
            config: Report configuration
            **kwargs: Additional report attributes
            
        Returns:
            Generated report
        """
        config = config or self.config
        now = datetime.now(timezone.utc)
        
        report = CapacityReport(
            title=title,
            report_start=now - timedelta(hours=config.lookback_hours),
            report_end=now,
            sections=config.sections,
            format=config.format,
            **kwargs,
        )
        
        # Process utilization data
        utils = []
        for data in utilization_data:
            util = self._process_utilization(data, config)
            if self._should_include(util, config):
                utils.append(util)
        report.utilization = utils
        
        # Generate summary
        if ReportSection.SUMMARY in config.sections:
            report.summary = self._generate_summary(utils, config)
        
        # Generate alerts
        if ReportSection.ALERTS in config.sections:
            alerts = self._generate_alerts(utils, config)
            for alert in alerts[:config.max_alerts]:
                report.add_alert(alert)
        
        # Generate insights
        if ReportSection.RECOMMENDATIONS in config.sections:
            insights = self._generate_insights(utils, config)
            for insight in insights[:config.max_insights]:
                report.add_insight(insight)
        
        self._reports[report.id] = report
        return report
    
    def _process_utilization(
        self,
        data: dict[str, Any],
        config: ReportConfig,
    ) -> ResourceUtilization:
        """Process raw utilization data."""
        current_util = data.get("utilization", 0)
        
        # Determine status
        if current_util >= config.critical_threshold:
            status = HealthStatus.CRITICAL
        elif current_util >= config.warning_threshold:
            status = HealthStatus.WARNING
        elif current_util < 20:
            status = HealthStatus.OVER_PROVISIONED
        else:
            status = HealthStatus.HEALTHY
        
        # Determine trend
        change = data.get("change_vs_yesterday", 0)
        if change > 5:
            trend = TrendIndicator.UP
        elif change < -5:
            trend = TrendIndicator.DOWN
        else:
            trend = TrendIndicator.STABLE
        
        return ResourceUtilization(
            resource_type=data.get("resource_type", "unknown"),
            resource_name=data.get("name", ""),
            current_utilization=current_util,
            current_allocation=data.get("allocation", 0),
            current_usage=data.get("usage", 0),
            unit=data.get("unit", ""),
            avg_utilization_24h=data.get("avg_24h"),
            max_utilization_24h=data.get("max_24h"),
            min_utilization_24h=data.get("min_24h"),
            p95_utilization_24h=data.get("p95_24h"),
            trend=trend,
            change_vs_yesterday=change,
            change_vs_last_week=data.get("change_vs_last_week"),
            status=status,
        )
    
    def _should_include(
        self,
        util: ResourceUtilization,
        config: ReportConfig,
    ) -> bool:
        """Check if utilization should be included in report."""
        # Check healthy filter
        if not config.include_healthy and util.status == HealthStatus.HEALTHY:
            return False
        
        # Check severity filter
        severity_order = {
            HealthStatus.HEALTHY: 0,
            HealthStatus.OVER_PROVISIONED: 1,
            HealthStatus.WARNING: 2,
            HealthStatus.CRITICAL: 3,
            HealthStatus.UNKNOWN: 0,
        }
        if severity_order.get(util.status, 0) < severity_order.get(config.min_severity, 0):
            return False
        
        # Check resource type filter
        if config.resource_types and util.resource_type not in config.resource_types:
            return False
        
        return True
    
    def _generate_summary(
        self,
        utils: list[ResourceUtilization],
        config: ReportConfig,
    ) -> CapacitySummary:
        """Generate capacity summary."""
        if not utils:
            return CapacitySummary(
                overall_health=HealthStatus.UNKNOWN,
                health_score=0,
            )
        
        # Count by status
        healthy = sum(1 for u in utils if u.status == HealthStatus.HEALTHY)
        warning = sum(1 for u in utils if u.status == HealthStatus.WARNING)
        critical = sum(1 for u in utils if u.status == HealthStatus.CRITICAL)
        
        # Calculate utilization stats
        utilizations = [u.current_utilization for u in utils]
        avg_util = statistics.mean(utilizations)
        max_util = max(utilizations)
        
        # Determine overall health
        if critical > 0:
            overall_health = HealthStatus.CRITICAL
        elif warning > 0:
            overall_health = HealthStatus.WARNING
        elif avg_util < 20:
            overall_health = HealthStatus.OVER_PROVISIONED
        else:
            overall_health = HealthStatus.HEALTHY
        
        # Calculate health score (0-100)
        # Penalize for critical and warning resources
        health_score = 100 - (critical * 20) - (warning * 5)
        health_score = max(0, min(100, health_score))
        
        return CapacitySummary(
            overall_health=overall_health,
            health_score=health_score,
            total_resources=len(utils),
            healthy_resources=healthy,
            warning_resources=warning,
            critical_resources=critical,
            avg_utilization=avg_util,
            max_utilization=max_util,
        )
    
    def _generate_alerts(
        self,
        utils: list[ResourceUtilization],
        config: ReportConfig,
    ) -> list[CapacityAlert]:
        """Generate alerts from utilization data."""
        alerts = []
        
        for util in utils:
            if util.status in [HealthStatus.WARNING, HealthStatus.CRITICAL]:
                threshold = (config.critical_threshold if util.status == HealthStatus.CRITICAL 
                            else config.warning_threshold)
                
                alert = CapacityAlert(
                    severity=util.status,
                    resource_type=util.resource_type,
                    resource_name=util.resource_name,
                    title=f"{util.resource_type} capacity {util.status.value}",
                    description=f"Current utilization at {util.current_utilization:.1f}% "
                                f"exceeds {util.status.value} threshold of {threshold}%",
                    current_value=util.current_utilization,
                    threshold_value=threshold,
                    unit="%",
                    recommended_action=self._get_recommended_action(util),
                )
                alerts.append(alert)
        
        # Sort by severity
        severity_order = {
            HealthStatus.CRITICAL: 0,
            HealthStatus.WARNING: 1,
            HealthStatus.HEALTHY: 2,
            HealthStatus.OVER_PROVISIONED: 3,
            HealthStatus.UNKNOWN: 4,
        }
        alerts.sort(key=lambda a: severity_order.get(a.severity, 5))
        
        return alerts
    
    def _get_recommended_action(self, util: ResourceUtilization) -> str:
        """Get recommended action for a utilization issue."""
        if util.status == HealthStatus.CRITICAL:
            return f"Immediately scale up {util.resource_type} capacity to prevent outage"
        elif util.status == HealthStatus.WARNING:
            return f"Plan to increase {util.resource_type} capacity within the next week"
        elif util.status == HealthStatus.OVER_PROVISIONED:
            return f"Consider reducing {util.resource_type} allocation to save costs"
        return "No action required"
    
    def _generate_insights(
        self,
        utils: list[ResourceUtilization],
        config: ReportConfig,
    ) -> list[CapacityInsight]:
        """Generate insights from utilization data."""
        insights = []
        
        if not utils:
            return insights
        
        # Check for over-provisioning
        over_provisioned = [u for u in utils if u.status == HealthStatus.OVER_PROVISIONED]
        if over_provisioned:
            total_headroom = sum(u.get_headroom() for u in over_provisioned)
            avg_headroom = total_headroom / len(over_provisioned)
            
            insights.append(CapacityInsight(
                category="optimization",
                severity=HealthStatus.WARNING,
                title="Over-provisioned resources detected",
                description=f"{len(over_provisioned)} resources are significantly "
                            f"under-utilized with an average of {avg_headroom:.1f}% headroom",
                impact="Potential cost savings available",
                recommendation="Review and right-size these resources",
                affected_resources=[u.resource_name for u in over_provisioned],
                metrics={"count": len(over_provisioned), "avg_headroom": avg_headroom},
            ))
        
        # Check for critical capacity
        critical = [u for u in utils if u.status == HealthStatus.CRITICAL]
        if critical:
            insights.append(CapacityInsight(
                category="risk",
                severity=HealthStatus.CRITICAL,
                title="Critical capacity shortage",
                description=f"{len(critical)} resources at critical utilization levels",
                impact="Risk of service degradation or outage",
                recommendation="Immediate scaling required",
                affected_resources=[u.resource_name for u in critical],
                metrics={"count": len(critical)},
            ))
        
        # Check for trending up
        trending_up = [u for u in utils if u.trend == TrendIndicator.UP and 
                       u.current_utilization > 60]
        if trending_up:
            insights.append(CapacityInsight(
                category="trend",
                severity=HealthStatus.WARNING,
                title="Capacity trending upward",
                description=f"{len(trending_up)} resources showing increasing utilization",
                impact="May require scaling in the near future",
                recommendation="Monitor closely and plan for capacity increase",
                affected_resources=[u.resource_name for u in trending_up],
                metrics={"count": len(trending_up)},
            ))
        
        # Sort by severity
        severity_order = {
            HealthStatus.CRITICAL: 0,
            HealthStatus.WARNING: 1,
            HealthStatus.HEALTHY: 2,
            HealthStatus.OVER_PROVISIONED: 3,
            HealthStatus.UNKNOWN: 4,
        }
        insights.sort(key=lambda i: severity_order.get(i.severity, 5))
        
        return insights
    
    def get_report(self, report_id: str) -> Optional[CapacityReport]:
        """Get a report by ID."""
        return self._reports.get(report_id)
    
    def format_report(
        self,
        report: CapacityReport,
        format: Optional[ReportFormat] = None,
    ) -> str:
        """
        Format a report for output.
        
        Args:
            report: Report to format
            format: Output format (uses report's format if not specified)
            
        Returns:
            Formatted report string
        """
        format = format or report.format
        
        if format == ReportFormat.MARKDOWN:
            return self._format_markdown(report)
        elif format == ReportFormat.SLACK:
            return self._format_slack(report)
        else:
            # Default to JSON
            return report.model_dump_json(indent=2)
    
    def _format_markdown(self, report: CapacityReport) -> str:
        """Format report as Markdown."""
        lines = [
            f"# {report.title}",
            "",
            f"**Generated:** {report.generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
            f"**Period:** {report.report_start.strftime('%Y-%m-%d %H:%M')} - "
            f"{report.report_end.strftime('%Y-%m-%d %H:%M')}",
            "",
        ]
        
        # Summary
        if report.summary:
            s = report.summary
            lines.extend([
                "## Summary",
                "",
                f"- **Overall Health:** {s.get_status_emoji()} {s.overall_health.value}",
                f"- **Health Score:** {s.health_score:.0f}/100",
                f"- **Resources:** {s.total_resources} total "
                f"({s.healthy_resources} healthy, {s.warning_resources} warning, "
                f"{s.critical_resources} critical)",
                f"- **Average Utilization:** {s.avg_utilization:.1f}%",
                "",
            ])
        
        # Alerts
        active_alerts = report.get_active_alerts()
        if active_alerts:
            lines.extend([
                "## Active Alerts",
                "",
            ])
            for alert in active_alerts[:10]:
                emoji = "🚨" if alert.severity == HealthStatus.CRITICAL else "⚠️"
                lines.append(f"- {emoji} **{alert.title}** - {alert.description}")
            lines.append("")
        
        # Utilization
        if report.utilization:
            lines.extend([
                "## Resource Utilization",
                "",
                "| Resource | Type | Utilization | Status | Trend |",
                "|----------|------|-------------|--------|-------|",
            ])
            for util in report.utilization[:20]:
                trend_emoji = {"up": "↑", "down": "↓", "stable": "→", "critical": "⚠"}.get(
                    util.trend.value, "→"
                )
                status_emoji = {
                    "healthy": "✅", "warning": "⚠️", "critical": "🚨",
                    "over_provisioned": "💰", "unknown": "❓"
                }.get(util.status.value, "❓")
                lines.append(
                    f"| {util.resource_name or util.resource_type} | "
                    f"{util.resource_type} | {util.current_utilization:.1f}% | "
                    f"{status_emoji} | {trend_emoji} |"
                )
            lines.append("")
        
        # Insights
        if report.insights:
            lines.extend([
                "## Insights",
                "",
            ])
            for insight in report.insights[:10]:
                emoji = {"critical": "🚨", "warning": "⚠️", "healthy": "💡"}.get(
                    insight.severity.value, "ℹ️"
                )
                lines.extend([
                    f"### {emoji} {insight.title}",
                    "",
                    f"{insight.description}",
                    "",
                    f"**Impact:** {insight.impact}",
                    "",
                    f"**Recommendation:** {insight.recommendation}",
                    "",
                ])
        
        return "\n".join(lines)
    
    def _format_slack(self, report: CapacityReport) -> str:
        """Format report for Slack."""
        blocks = []
        
        # Header
        if report.summary:
            s = report.summary
            emoji = s.get_status_emoji()
            blocks.append(
                f"*{report.title}* {emoji}\n"
                f"Health Score: *{s.health_score:.0f}/100* | "
                f"Resources: {s.critical_resources} critical, {s.warning_resources} warning"
            )
        
        # Active alerts
        active_alerts = report.get_active_alerts()
        if active_alerts:
            alert_lines = ["*Active Alerts:*"]
            for alert in active_alerts[:5]:
                emoji = "🚨" if alert.severity == HealthStatus.CRITICAL else "⚠️"
                alert_lines.append(f"  {emoji} {alert.title}")
            blocks.append("\n".join(alert_lines))
        
        # Top insights
        if report.insights:
            insight_lines = ["*Key Insights:*"]
            for insight in report.insights[:3]:
                insight_lines.append(f"  • {insight.title}")
            blocks.append("\n".join(insight_lines))
        
        return "\n\n".join(blocks)


def generate_quick_report(
    utilization_data: list[dict[str, Any]],
    title: str = "Capacity Report",
) -> CapacityReport:
    """
    Generate a quick capacity report.
    
    Args:
        utilization_data: List of utilization dicts with keys:
            - resource_type: Type of resource
            - name: Resource name
            - utilization: Current utilization %
            - allocation: Current allocation
            - usage: Current usage
            - unit: Unit of measurement
            
    Returns:
        Generated report
    """
    reporter = CapacityReporter()
    return reporter.generate_report(title, utilization_data)


def get_capacity_health(
    utilization_data: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Get quick capacity health assessment.
    
    Args:
        utilization_data: List of utilization dicts
        
    Returns:
        Health assessment
    """
    report = generate_quick_report(utilization_data, "Health Check")
    
    if not report.summary:
        return {
            "status": "unknown",
            "score": 0,
            "message": "No data available",
        }
    
    s = report.summary
    return {
        "status": s.overall_health.value,
        "score": s.health_score,
        "total_resources": s.total_resources,
        "critical": s.critical_resources,
        "warning": s.warning_resources,
        "healthy": s.healthy_resources,
        "avg_utilization": s.avg_utilization,
        "emoji": s.get_status_emoji(),
        "active_alerts": len(report.get_active_alerts()),
    }
