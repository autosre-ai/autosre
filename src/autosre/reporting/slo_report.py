"""SLO Reports for AutoSRE V2.

Provides SLO compliance reporting:
- Error budget tracking
- Compliance status
- Trend analysis
- Burn rate alerts
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from autosre.reporting.report_generator import (
    Report,
    ReportFormat,
    ReportGenerator,
    ReportType,
    TableData,
    ChartData,
)
from autosre.utils.logging import get_logger

logger = get_logger(__name__)


class SLOStatus(str, Enum):
    """SLO compliance status."""
    
    HEALTHY = "healthy"  # Within budget
    AT_RISK = "at_risk"  # Approaching budget
    BREACHED = "breached"  # Budget exhausted
    UNKNOWN = "unknown"


class SLOType(str, Enum):
    """Types of SLOs."""
    
    AVAILABILITY = "availability"
    LATENCY = "latency"
    ERROR_RATE = "error_rate"
    THROUGHPUT = "throughput"
    CUSTOM = "custom"


class SLODefinition(BaseModel):
    """Definition of an SLO."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: Optional[str] = None
    
    # SLO target
    slo_type: SLOType
    target_percentage: float  # e.g., 99.9
    
    # Time window
    window_days: int = 30  # Rolling window
    
    # Service
    service: str
    environment: str = "production"
    
    # Labels
    labels: Dict[str, str] = Field(default_factory=dict)


class SLOMetrics(BaseModel):
    """Current metrics for an SLO."""
    
    slo_id: str
    
    # Current performance
    current_percentage: float
    
    # Error budget
    error_budget_total: float  # Total budget in the window
    error_budget_remaining: float  # Remaining budget
    error_budget_consumed_percentage: float
    
    # Status
    status: SLOStatus
    
    # Burn rate
    burn_rate_1h: Optional[float] = None  # Budget consumption rate (1 = normal)
    burn_rate_6h: Optional[float] = None
    burn_rate_24h: Optional[float] = None
    
    # Predictions
    projected_budget_exhaustion: Optional[datetime] = None
    projected_end_of_window: Optional[float] = None  # Projected remaining at end
    
    # Time range
    window_start: datetime
    window_end: datetime
    
    # Data points for trending
    historical_data: List[Dict[str, Any]] = Field(default_factory=list)


class SLOReportData(BaseModel):
    """Data for generating an SLO report."""
    
    # Report scope
    services: List[str] = Field(default_factory=list)  # Filter by service
    environment: str = "production"
    
    # SLO data
    slo_definitions: List[SLODefinition] = Field(default_factory=list)
    slo_metrics: List[SLOMetrics] = Field(default_factory=list)
    
    # Summary data
    total_slos: int = 0
    healthy_count: int = 0
    at_risk_count: int = 0
    breached_count: int = 0
    
    # Trend data
    overall_compliance_trend: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Notable events
    budget_exhaustion_events: List[Dict[str, Any]] = Field(default_factory=list)
    burn_rate_alerts: List[Dict[str, Any]] = Field(default_factory=list)


class SLOReport:
    """
    Generates SLO compliance reports.
    
    Provides:
    - SLO status overview
    - Error budget tracking
    - Burn rate analysis
    - Trend visualization
    - Compliance recommendations
    
    Example:
        report_gen = SLOReport(generator)
        
        data = SLOReportData(
            total_slos=10,
            healthy_count=7,
            at_risk_count=2,
            breached_count=1,
        )
        
        # Add SLO definitions and metrics...
        
        report = await report_gen.generate(
            tenant_id="tenant-123",
            data=data,
            period_start=datetime(2024, 1, 1),
            period_end=datetime(2024, 1, 31),
        )
    """
    
    def __init__(self, generator: ReportGenerator):
        """Initialize SLOReport.
        
        Args:
            generator: ReportGenerator instance
        """
        self.generator = generator
    
    async def generate(
        self,
        tenant_id: str,
        data: SLOReportData,
        period_start: datetime,
        period_end: datetime,
        format: ReportFormat = ReportFormat.HTML,
    ) -> Report:
        """Generate an SLO report.
        
        Args:
            tenant_id: Tenant ID
            data: SLO report data
            period_start: Report period start
            period_end: Report period end
            format: Output format
            
        Returns:
            Generated report
        """
        # Calculate key metrics
        key_metrics = self._calculate_metrics(data)
        
        # Create report
        report = Report(
            tenant_id=tenant_id,
            report_type=ReportType.SLO,
            title="SLO Compliance Report",
            subtitle=f"Environment: {data.environment}",
            period_start=period_start,
            period_end=period_end,
            summary=self._generate_summary(data),
            key_metrics=key_metrics,
        )
        
        # Add sections
        self._add_overview_section(report, data)
        self._add_slo_details_section(report, data)
        self._add_error_budget_section(report, data)
        self._add_burn_rate_section(report, data)
        self._add_recommendations_section(report, data)
        
        # Generate output
        await self.generator.generate(report, format)
        
        return report
    
    def _calculate_metrics(self, data: SLOReportData) -> Dict[str, Any]:
        """Calculate key metrics for the report."""
        compliance_rate = (
            (data.healthy_count / data.total_slos * 100)
            if data.total_slos > 0 else 0
        )
        
        return {
            "Total SLOs": data.total_slos,
            "Healthy": data.healthy_count,
            "At Risk": data.at_risk_count,
            "Breached": data.breached_count,
            "Compliance Rate": f"{compliance_rate:.1f}%",
        }
    
    def _generate_summary(self, data: SLOReportData) -> str:
        """Generate executive summary."""
        compliance_rate = (
            (data.healthy_count / data.total_slos * 100)
            if data.total_slos > 0 else 0
        )
        
        if data.breached_count > 0:
            status_text = f"⚠️ {data.breached_count} SLO(s) have breached their error budget and require immediate attention."
        elif data.at_risk_count > 0:
            status_text = f"⏳ {data.at_risk_count} SLO(s) are at risk of breaching. Consider taking preventive action."
        else:
            status_text = "✅ All SLOs are healthy and within their error budgets."
        
        return f"""
        <p>This report provides an overview of SLO compliance for the {data.environment} environment.</p>
        <p><strong>Overall Status:</strong> {compliance_rate:.1f}% of SLOs are healthy.</p>
        <p>{status_text}</p>
        """
    
    def _add_overview_section(
        self,
        report: Report,
        data: SLOReportData,
    ) -> None:
        """Add SLO overview section."""
        # Status distribution chart
        content = """
        <div class="slo-overview">
            <div class="status-cards">
                <div class="status-card healthy">
                    <div class="count">""" + str(data.healthy_count) + """</div>
                    <div class="label">Healthy</div>
                </div>
                <div class="status-card at-risk">
                    <div class="count">""" + str(data.at_risk_count) + """</div>
                    <div class="label">At Risk</div>
                </div>
                <div class="status-card breached">
                    <div class="count">""" + str(data.breached_count) + """</div>
                    <div class="label">Breached</div>
                </div>
            </div>
            
            <style>
            .status-cards { display: flex; gap: 20px; margin: 20px 0; }
            .status-card { flex: 1; padding: 20px; border-radius: 8px; text-align: center; }
            .status-card .count { font-size: 2.5em; font-weight: bold; }
            .status-card.healthy { background: #d4edda; color: #155724; }
            .status-card.at-risk { background: #fff3cd; color: #856404; }
            .status-card.breached { background: #f8d7da; color: #721c24; }
            </style>
        </div>
        """
        
        report.add_section(
            title="SLO Status Overview",
            content=content,
        )
    
    def _add_slo_details_section(
        self,
        report: Report,
        data: SLOReportData,
    ) -> None:
        """Add detailed SLO status section."""
        rows = []
        
        # Match definitions with metrics
        for definition in data.slo_definitions:
            metrics = next(
                (m for m in data.slo_metrics if m.slo_id == definition.id),
                None,
            )
            
            if metrics:
                status_class = {
                    SLOStatus.HEALTHY: "status-success",
                    SLOStatus.AT_RISK: "status-warning",
                    SLOStatus.BREACHED: "status-danger",
                }.get(metrics.status, "")
                
                rows.append([
                    definition.name,
                    definition.service,
                    f"{definition.target_percentage}%",
                    f"{metrics.current_percentage:.2f}%",
                    f"{metrics.error_budget_remaining:.2f}%",
                    f'<span class="{status_class}">{metrics.status.value.title()}</span>',
                ])
        
        if rows:
            table = TableData(
                headers=["SLO Name", "Service", "Target", "Current", "Budget Remaining", "Status"],
                rows=rows,
            )
            
            content = self.generator.render_table(table)
        else:
            content = "<p>No SLO data available.</p>"
        
        report.add_section(
            title="SLO Details",
            content=content,
        )
    
    def _add_error_budget_section(
        self,
        report: Report,
        data: SLOReportData,
    ) -> None:
        """Add error budget tracking section."""
        content = """
        <div class="error-budget">
            <h3>Error Budget Consumption</h3>
            <p>The error budget represents the acceptable amount of unreliability within the SLO window.</p>
        """
        
        # Add budget bars for each SLO
        for definition in data.slo_definitions:
            metrics = next(
                (m for m in data.slo_metrics if m.slo_id == definition.id),
                None,
            )
            
            if metrics:
                consumed = metrics.error_budget_consumed_percentage
                remaining = max(0, 100 - consumed)
                
                bar_color = "#28a745" if consumed < 50 else ("#ffc107" if consumed < 80 else "#dc3545")
                
                content += f"""
                <div class="budget-item">
                    <div class="budget-label">{definition.name}</div>
                    <div class="budget-bar">
                        <div class="budget-consumed" style="width: {consumed}%; background: {bar_color};"></div>
                    </div>
                    <div class="budget-text">{consumed:.1f}% consumed</div>
                </div>
                """
        
        content += """
            <style>
            .budget-item { margin: 15px 0; }
            .budget-label { font-weight: bold; margin-bottom: 5px; }
            .budget-bar { height: 20px; background: #e9ecef; border-radius: 4px; overflow: hidden; }
            .budget-consumed { height: 100%; transition: width 0.3s; }
            .budget-text { font-size: 0.9em; color: #666; margin-top: 5px; }
            </style>
        </div>
        """
        
        report.add_section(
            title="Error Budget Tracking",
            content=content,
        )
    
    def _add_burn_rate_section(
        self,
        report: Report,
        data: SLOReportData,
    ) -> None:
        """Add burn rate analysis section."""
        content = """
        <div class="burn-rate">
            <h3>Burn Rate Analysis</h3>
            <p>Burn rate indicates how quickly the error budget is being consumed. A burn rate of 1.0 means the budget will be exactly exhausted at the end of the window.</p>
        """
        
        rows = []
        for definition in data.slo_definitions:
            metrics = next(
                (m for m in data.slo_metrics if m.slo_id == definition.id),
                None,
            )
            
            if metrics:
                def format_rate(rate: Optional[float]) -> str:
                    if rate is None:
                        return "N/A"
                    if rate < 1:
                        return f'<span class="status-success">{rate:.2f}x</span>'
                    elif rate < 2:
                        return f'<span class="status-warning">{rate:.2f}x</span>'
                    else:
                        return f'<span class="status-danger">{rate:.2f}x</span>'
                
                rows.append([
                    definition.name,
                    format_rate(metrics.burn_rate_1h),
                    format_rate(metrics.burn_rate_6h),
                    format_rate(metrics.burn_rate_24h),
                    metrics.projected_budget_exhaustion.strftime("%Y-%m-%d") if metrics.projected_budget_exhaustion else "N/A",
                ])
        
        if rows:
            table = TableData(
                headers=["SLO", "1h Rate", "6h Rate", "24h Rate", "Projected Exhaustion"],
                rows=rows,
            )
            content += self.generator.render_table(table)
        
        content += "</div>"
        
        report.add_section(
            title="Burn Rate Analysis",
            content=content,
        )
    
    def _add_recommendations_section(
        self,
        report: Report,
        data: SLOReportData,
    ) -> None:
        """Add recommendations section."""
        recommendations = []
        
        # Check for breached SLOs
        breached_slos = [
            m for m in data.slo_metrics
            if m.status == SLOStatus.BREACHED
        ]
        if breached_slos:
            recommendations.append({
                "priority": "high",
                "title": "Address Breached SLOs",
                "description": f"{len(breached_slos)} SLO(s) have exhausted their error budget. Investigate root causes and implement improvements.",
            })
        
        # Check for high burn rates
        high_burn = [
            m for m in data.slo_metrics
            if m.burn_rate_1h and m.burn_rate_1h > 2
        ]
        if high_burn:
            recommendations.append({
                "priority": "high",
                "title": "Investigate High Burn Rates",
                "description": f"{len(high_burn)} SLO(s) have burn rates >2x. This indicates accelerated budget consumption.",
            })
        
        # Check for at-risk SLOs
        at_risk = [
            m for m in data.slo_metrics
            if m.status == SLOStatus.AT_RISK
        ]
        if at_risk:
            recommendations.append({
                "priority": "medium",
                "title": "Monitor At-Risk SLOs",
                "description": f"{len(at_risk)} SLO(s) are approaching their budget limits. Consider proactive measures.",
            })
        
        if not recommendations:
            recommendations.append({
                "priority": "low",
                "title": "Maintain Current Performance",
                "description": "All SLOs are healthy. Continue monitoring and maintain current reliability practices.",
            })
        
        content = '<div class="recommendations">'
        
        for rec in recommendations:
            priority_class = f"priority-{rec['priority']}"
            content += f"""
            <div class="recommendation {priority_class}">
                <h4>{rec['title']}</h4>
                <p>{rec['description']}</p>
            </div>
            """
        
        content += """
            <style>
            .recommendation { padding: 15px; border-radius: 8px; margin: 15px 0; border-left: 4px solid; }
            .priority-high { background: #fff5f5; border-color: #dc3545; }
            .priority-medium { background: #fffbf0; border-color: #ffc107; }
            .priority-low { background: #f0fff4; border-color: #28a745; }
            </style>
        </div>
        """
        
        report.add_section(
            title="Recommendations",
            content=content,
            page_break_before=True,
        )
