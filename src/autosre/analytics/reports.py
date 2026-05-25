"""
Automated Report Generation

Generates comprehensive SRE reports including:
- Weekly/monthly incident summaries
- Service health reports
- SLO compliance reports
- Team performance reports
- Trend analysis reports
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ReportType(str, Enum):
    """Types of reports that can be generated."""
    INCIDENT_SUMMARY = "incident_summary"
    SERVICE_HEALTH = "service_health"
    SLO_COMPLIANCE = "slo_compliance"
    TEAM_PERFORMANCE = "team_performance"
    TREND_ANALYSIS = "trend_analysis"
    EXECUTIVE_SUMMARY = "executive_summary"
    ON_CALL_SUMMARY = "on_call_summary"


class ReportFormat(str, Enum):
    """Output formats for reports."""
    MARKDOWN = "markdown"
    HTML = "html"
    JSON = "json"
    PLAIN_TEXT = "plain_text"
    SLACK = "slack"  # Slack-formatted blocks


@dataclass
class ReportSection:
    """A section within a report."""
    title: str
    content: str
    data: dict[str, Any] = field(default_factory=dict)
    subsections: list["ReportSection"] = field(default_factory=list)
    charts: list[str] = field(default_factory=list)  # References to chart IDs
    
    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "content": self.content,
            "data": self.data,
            "subsections": [s.to_dict() for s in self.subsections],
            "charts": self.charts,
        }


@dataclass
class SREReport:
    """A complete SRE report."""
    report_type: ReportType
    title: str
    period_start: datetime
    period_end: datetime
    generated_at: datetime
    summary: str
    sections: list[ReportSection]
    key_metrics: dict[str, Any]
    recommendations: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "report_type": self.report_type.value,
            "title": self.title,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "generated_at": self.generated_at.isoformat(),
            "summary": self.summary,
            "sections": [s.to_dict() for s in self.sections],
            "key_metrics": self.key_metrics,
            "recommendations": self.recommendations,
            "metadata": self.metadata,
        }
    
    def to_markdown(self) -> str:
        """Render report as Markdown."""
        lines = [
            f"# {self.title}",
            "",
            f"**Period:** {self.period_start.strftime('%Y-%m-%d')} to {self.period_end.strftime('%Y-%m-%d')}",
            f"**Generated:** {self.generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
            "",
            "## Executive Summary",
            "",
            self.summary,
            "",
            "## Key Metrics",
            "",
        ]
        
        for key, value in self.key_metrics.items():
            display_key = key.replace("_", " ").title()
            if isinstance(value, float):
                lines.append(f"- **{display_key}:** {value:.2f}")
            else:
                lines.append(f"- **{display_key}:** {value}")
        
        lines.append("")
        
        for section in self.sections:
            lines.extend(self._render_section_markdown(section, level=2))
        
        if self.recommendations:
            lines.extend([
                "## Recommendations",
                "",
            ])
            for i, rec in enumerate(self.recommendations, 1):
                lines.append(f"{i}. {rec}")
        
        return "\n".join(lines)
    
    def _render_section_markdown(
        self,
        section: ReportSection,
        level: int = 2,
    ) -> list[str]:
        """Render a section as Markdown."""
        lines = [
            "#" * level + f" {section.title}",
            "",
            section.content,
            "",
        ]
        
        if section.data:
            for key, value in section.data.items():
                display_key = key.replace("_", " ").title()
                if isinstance(value, list):
                    lines.append(f"**{display_key}:**")
                    for item in value:
                        lines.append(f"  - {item}")
                elif isinstance(value, dict):
                    lines.append(f"**{display_key}:**")
                    for k, v in value.items():
                        lines.append(f"  - {k}: {v}")
                else:
                    lines.append(f"**{display_key}:** {value}")
            lines.append("")
        
        for subsection in section.subsections:
            lines.extend(self._render_section_markdown(subsection, level + 1))
        
        return lines
    
    def to_slack_blocks(self) -> list[dict]:
        """Render report as Slack blocks."""
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": self.title,
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": (
                            f"*Period:* {self.period_start.strftime('%Y-%m-%d')} to "
                            f"{self.period_end.strftime('%Y-%m-%d')}"
                        )
                    }
                ]
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Summary*\n{self.summary}"
                }
            },
        ]
        
        # Key metrics as fields
        fields = []
        for key, value in list(self.key_metrics.items())[:10]:  # Slack limit
            display_key = key.replace("_", " ").title()
            if isinstance(value, float):
                fields.append({
                    "type": "mrkdwn",
                    "text": f"*{display_key}*\n{value:.2f}"
                })
            else:
                fields.append({
                    "type": "mrkdwn",
                    "text": f"*{display_key}*\n{value}"
                })
        
        if fields:
            blocks.append({"type": "divider"})
            blocks.append({
                "type": "section",
                "fields": fields[:10]  # Slack limit
            })
        
        # Recommendations
        if self.recommendations:
            blocks.append({"type": "divider"})
            recs_text = "\n".join(f"• {r}" for r in self.recommendations[:5])
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Recommendations*\n{recs_text}"
                }
            })
        
        return blocks


class ReportGenerator:
    """
    Generates comprehensive SRE reports.
    
    Supports multiple report types and output formats.
    """
    
    def __init__(self):
        self._report_generators = {
            ReportType.INCIDENT_SUMMARY: self._generate_incident_summary,
            ReportType.SERVICE_HEALTH: self._generate_service_health,
            ReportType.SLO_COMPLIANCE: self._generate_slo_compliance,
            ReportType.TEAM_PERFORMANCE: self._generate_team_performance,
            ReportType.TREND_ANALYSIS: self._generate_trend_analysis,
            ReportType.EXECUTIVE_SUMMARY: self._generate_executive_summary,
            ReportType.ON_CALL_SUMMARY: self._generate_on_call_summary,
        }
    
    def generate(
        self,
        report_type: ReportType,
        data: dict[str, Any],
        period_days: int = 7,
        format: ReportFormat = ReportFormat.MARKDOWN,
    ) -> SREReport:
        """
        Generate a report of the specified type.
        
        Args:
            report_type: Type of report to generate
            data: Data to include in the report
            period_days: Number of days to cover
            format: Output format
            
        Returns:
            SREReport object
        """
        generator = self._report_generators.get(report_type)
        if not generator:
            raise ValueError(f"Unknown report type: {report_type}")
        
        now = datetime.now(timezone.utc)
        period_end = now
        period_start = now - timedelta(days=period_days)
        
        report = generator(data, period_start, period_end)
        return report
    
    def generate_weekly_summary(
        self,
        incidents: list[dict],
        services: list[str],
        metrics: dict[str, Any],
        slos: Optional[dict] = None,
    ) -> SREReport:
        """
        Generate a comprehensive weekly summary report.
        
        Convenience method that combines multiple report types.
        """
        data = {
            "incidents": incidents,
            "services": services,
            "metrics": metrics,
            "slos": slos or {},
        }
        
        return self.generate(
            ReportType.EXECUTIVE_SUMMARY,
            data,
            period_days=7,
        )
    
    def _generate_incident_summary(
        self,
        data: dict,
        period_start: datetime,
        period_end: datetime,
    ) -> SREReport:
        """Generate incident summary report."""
        incidents = data.get("incidents", [])
        
        # Calculate metrics
        total_incidents = len(incidents)
        
        # Group by severity
        severity_counts = {}
        for incident in incidents:
            sev = incident.get("severity", "unknown")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
        
        # Calculate MTTR
        ttr_values = [
            i.get("ttr") or i.get("time_to_resolve", 0)
            for i in incidents
            if i.get("ttr") or i.get("time_to_resolve")
        ]
        avg_mttr = sum(ttr_values) / len(ttr_values) if ttr_values else 0
        
        # Top affected services
        service_counts = {}
        for incident in incidents:
            service = incident.get("service", "unknown")
            service_counts[service] = service_counts.get(service, 0) + 1
        top_services = sorted(
            service_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:5]
        
        # Build sections
        sections = [
            ReportSection(
                title="Incident Breakdown",
                content="Distribution of incidents by severity.",
                data={"severity_breakdown": severity_counts},
            ),
            ReportSection(
                title="Top Affected Services",
                content="Services with the most incidents this period.",
                data={"services": [f"{s}: {c} incidents" for s, c in top_services]},
            ),
        ]
        
        # Add critical incidents section if any
        critical = [
            i for i in incidents
            if i.get("severity") in ("critical", "high")
        ]
        if critical:
            sections.append(ReportSection(
                title="Critical/High Severity Incidents",
                content=f"{len(critical)} critical or high severity incidents occurred.",
                data={
                    "incidents": [
                        f"{i.get('name', 'Unknown')} - {i.get('service', 'Unknown')}"
                        for i in critical[:10]
                    ]
                },
            ))
        
        # Generate recommendations
        recommendations = []
        if severity_counts.get("critical", 0) > 0:
            recommendations.append(
                "Review critical incidents and ensure post-mortems are completed"
            )
        if total_incidents > 20:
            recommendations.append(
                "High incident volume - consider noise reduction and automation"
            )
        if avg_mttr > 60:
            recommendations.append(
                f"MTTR of {avg_mttr:.0f} minutes is high - review runbooks and escalation"
            )
        if top_services:
            recommendations.append(
                f"Focus reliability improvements on {top_services[0][0]}"
            )
        
        return SREReport(
            report_type=ReportType.INCIDENT_SUMMARY,
            title="Incident Summary Report",
            period_start=period_start,
            period_end=period_end,
            generated_at=datetime.now(timezone.utc),
            summary=(
                f"This period saw {total_incidents} incidents. "
                f"Average time to resolve was {avg_mttr:.0f} minutes. "
                f"{severity_counts.get('critical', 0)} critical incidents occurred."
            ),
            sections=sections,
            key_metrics={
                "total_incidents": total_incidents,
                "critical_incidents": severity_counts.get("critical", 0),
                "high_incidents": severity_counts.get("high", 0),
                "avg_mttr_minutes": round(avg_mttr, 1),
                "top_service": top_services[0][0] if top_services else "N/A",
            },
            recommendations=recommendations,
        )
    
    def _generate_service_health(
        self,
        data: dict,
        period_start: datetime,
        period_end: datetime,
    ) -> SREReport:
        """Generate service health report."""
        services = data.get("services", [])
        metrics = data.get("metrics", {})
        incidents = data.get("incidents", [])
        
        sections = []
        service_scores = {}
        
        for service in services:
            service_metrics = metrics.get(service, {})
            service_incidents = [
                i for i in incidents
                if i.get("service") == service
            ]
            
            # Calculate health score (simplified)
            score = 100.0
            
            # Deduct for incidents
            score -= len(service_incidents) * 5
            
            # Deduct for error rate
            error_rate = service_metrics.get("error_rate", 0)
            if error_rate > 0.01:
                score -= (error_rate * 100) * 2
            
            # Deduct for high latency
            latency = service_metrics.get("latency_p99", 0)
            if latency > 1000:
                score -= 10
            elif latency > 500:
                score -= 5
            
            score = max(0, min(100, score))
            service_scores[service] = score
            
            health_status = "Healthy" if score >= 80 else "Degraded" if score >= 50 else "Critical"
            
            sections.append(ReportSection(
                title=f"{service}",
                content=f"Health Status: {health_status} ({score:.0f}/100)",
                data={
                    "incidents": len(service_incidents),
                    "error_rate": f"{error_rate:.2%}" if error_rate else "N/A",
                    "latency_p99": f"{latency:.0f}ms" if latency else "N/A",
                },
            ))
        
        # Calculate overall health
        avg_health = sum(service_scores.values()) / len(service_scores) if service_scores else 100
        
        # Recommendations
        recommendations = []
        unhealthy = [s for s, score in service_scores.items() if score < 80]
        if unhealthy:
            recommendations.append(f"Prioritize reliability work on: {', '.join(unhealthy[:3])}")
        
        return SREReport(
            report_type=ReportType.SERVICE_HEALTH,
            title="Service Health Report",
            period_start=period_start,
            period_end=period_end,
            generated_at=datetime.now(timezone.utc),
            summary=(
                f"Monitoring {len(services)} services. "
                f"Average health score: {avg_health:.0f}/100. "
                f"{len(unhealthy)} services need attention."
            ),
            sections=sections,
            key_metrics={
                "total_services": len(services),
                "average_health_score": round(avg_health, 1),
                "healthy_services": len([s for s, score in service_scores.items() if score >= 80]),
                "degraded_services": len([s for s, score in service_scores.items() if 50 <= score < 80]),
                "critical_services": len([s for s, score in service_scores.items() if score < 50]),
            },
            recommendations=recommendations,
        )
    
    def _generate_slo_compliance(
        self,
        data: dict,
        period_start: datetime,
        period_end: datetime,
    ) -> SREReport:
        """Generate SLO compliance report."""
        slos = data.get("slos", {})
        
        sections = []
        compliant_count = 0
        at_risk_count = 0
        breached_count = 0
        
        for slo_name, slo_data in slos.items():
            target = slo_data.get("target", 0.99)
            actual = slo_data.get("actual", 1.0)
            budget_remaining = slo_data.get("budget_remaining", 1.0)
            
            if actual >= target:
                status = "✅ Compliant"
                compliant_count += 1
            elif budget_remaining > 0.2:
                status = "⚠️ At Risk"
                at_risk_count += 1
            else:
                status = "❌ Breached"
                breached_count += 1
            
            sections.append(ReportSection(
                title=slo_name,
                content=f"Status: {status}",
                data={
                    "target": f"{target:.2%}",
                    "actual": f"{actual:.2%}",
                    "budget_remaining": f"{budget_remaining:.0%}",
                },
            ))
        
        total_slos = len(slos)
        compliance_rate = (compliant_count / total_slos * 100) if total_slos > 0 else 100
        
        recommendations = []
        if breached_count > 0:
            recommendations.append("Conduct post-mortem for breached SLOs")
        if at_risk_count > 0:
            recommendations.append("Focus on services with at-risk SLOs")
        if compliance_rate == 100:
            recommendations.append("Consider tightening SLO targets")
        
        return SREReport(
            report_type=ReportType.SLO_COMPLIANCE,
            title="SLO Compliance Report",
            period_start=period_start,
            period_end=period_end,
            generated_at=datetime.now(timezone.utc),
            summary=(
                f"Tracking {total_slos} SLOs. "
                f"Compliance rate: {compliance_rate:.0f}%. "
                f"{compliant_count} compliant, {at_risk_count} at risk, {breached_count} breached."
            ),
            sections=sections,
            key_metrics={
                "total_slos": total_slos,
                "compliance_rate": compliance_rate,
                "compliant": compliant_count,
                "at_risk": at_risk_count,
                "breached": breached_count,
            },
            recommendations=recommendations,
        )
    
    def _generate_team_performance(
        self,
        data: dict,
        period_start: datetime,
        period_end: datetime,
    ) -> SREReport:
        """Generate team performance report."""
        incidents = data.get("incidents", [])
        on_call_data = data.get("on_call", {})
        
        # Calculate metrics
        total_incidents = len(incidents)
        
        # Response time
        response_times = [
            i.get("ttd") or i.get("time_to_detect", 0)
            for i in incidents
            if i.get("ttd") or i.get("time_to_detect")
        ]
        avg_response = sum(response_times) / len(response_times) if response_times else 0
        
        # Resolution time
        resolution_times = [
            i.get("ttr") or i.get("time_to_resolve", 0)
            for i in incidents
            if i.get("ttr") or i.get("time_to_resolve")
        ]
        avg_resolution = sum(resolution_times) / len(resolution_times) if resolution_times else 0
        
        # On-call burden
        on_call_incidents = on_call_data.get("incidents_per_rotation", {})
        
        sections = [
            ReportSection(
                title="Response Metrics",
                content="Time to detect and respond to incidents.",
                data={
                    "avg_time_to_detect": f"{avg_response:.0f} minutes",
                    "avg_time_to_resolve": f"{avg_resolution:.0f} minutes",
                    "total_incidents_handled": total_incidents,
                },
            ),
        ]
        
        if on_call_incidents:
            sections.append(ReportSection(
                title="On-Call Distribution",
                content="Incident distribution across on-call rotations.",
                data=on_call_incidents,
            ))
        
        recommendations = []
        if avg_response > 15:
            recommendations.append("Work on reducing time to detect - improve alerting")
        if avg_resolution > 60:
            recommendations.append("Focus on reducing resolution time with better runbooks")
        
        return SREReport(
            report_type=ReportType.TEAM_PERFORMANCE,
            title="Team Performance Report",
            period_start=period_start,
            period_end=period_end,
            generated_at=datetime.now(timezone.utc),
            summary=(
                f"Team handled {total_incidents} incidents this period. "
                f"Average response time: {avg_response:.0f} minutes. "
                f"Average resolution time: {avg_resolution:.0f} minutes."
            ),
            sections=sections,
            key_metrics={
                "total_incidents": total_incidents,
                "avg_response_minutes": round(avg_response, 1),
                "avg_resolution_minutes": round(avg_resolution, 1),
            },
            recommendations=recommendations,
        )
    
    def _generate_trend_analysis(
        self,
        data: dict,
        period_start: datetime,
        period_end: datetime,
    ) -> SREReport:
        """Generate trend analysis report."""
        from autosre.analytics.trends import TrendAnalyzer, TrendDataPoint
        
        incidents = data.get("incidents", [])
        
        analyzer = TrendAnalyzer()
        
        # Create data points
        incident_data = []
        for incident in incidents:
            ts = incident.get("timestamp") or incident.get("created_at")
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if ts:
                incident_data.append(TrendDataPoint(timestamp=ts, value=1))
        
        # Analyze
        analysis = analyzer.analyze_incidents(incidents, period_days=30)
        
        sections = [
            ReportSection(
                title="Incident Volume Trend",
                content=analysis.incident_trend.summary,
                data={
                    "direction": analysis.incident_trend.direction.value,
                    "percent_change": f"{analysis.incident_trend.percent_change:+.1f}%",
                    "confidence": f"{analysis.incident_trend.confidence:.0%}",
                },
            ),
            ReportSection(
                title="MTTR Trend",
                content=analysis.mttr_trend.summary,
                data={
                    "direction": analysis.mttr_trend.direction.value,
                    "percent_change": f"{analysis.mttr_trend.percent_change:+.1f}%",
                },
            ),
        ]
        
        if analysis.alert_fatigue_score > 0.5:
            sections.append(ReportSection(
                title="Alert Fatigue Analysis",
                content=f"Alert fatigue score: {analysis.alert_fatigue_score:.0%}",
                data={"score": analysis.alert_fatigue_score},
            ))
        
        return SREReport(
            report_type=ReportType.TREND_ANALYSIS,
            title="Trend Analysis Report",
            period_start=period_start,
            period_end=period_end,
            generated_at=datetime.now(timezone.utc),
            summary=(
                f"Incident volume is {analysis.incident_trend.direction.value}. "
                f"MTTR is {analysis.mttr_trend.direction.value}. "
                f"Alert fatigue score: {analysis.alert_fatigue_score:.0%}."
            ),
            sections=sections,
            key_metrics={
                "incident_trend": analysis.incident_trend.direction.value,
                "incident_change": f"{analysis.incident_trend.percent_change:+.1f}%",
                "mttr_trend": analysis.mttr_trend.direction.value,
                "alert_fatigue_score": analysis.alert_fatigue_score,
            },
            recommendations=analysis.recommendations,
        )
    
    def _generate_executive_summary(
        self,
        data: dict,
        period_start: datetime,
        period_end: datetime,
    ) -> SREReport:
        """Generate executive summary report."""
        incidents = data.get("incidents", [])
        services = data.get("services", [])
        slos = data.get("slos", {})
        
        # High-level metrics
        total_incidents = len(incidents)
        critical_incidents = len([i for i in incidents if i.get("severity") == "critical"])
        
        # SLO compliance
        compliant_slos = len([s for s in slos.values() if s.get("actual", 1) >= s.get("target", 0.99)])
        total_slos = len(slos)
        slo_compliance = (compliant_slos / total_slos * 100) if total_slos > 0 else 100
        
        # Availability (simplified)
        uptime = 100 - (critical_incidents * 0.1)  # Rough estimate
        
        sections = [
            ReportSection(
                title="Reliability Overview",
                content="High-level reliability metrics for the period.",
                data={
                    "uptime": f"{uptime:.2f}%",
                    "slo_compliance": f"{slo_compliance:.0f}%",
                    "incident_volume": total_incidents,
                },
            ),
            ReportSection(
                title="Key Highlights",
                content="Notable events and achievements.",
                data={
                    "critical_incidents": critical_incidents,
                    "services_monitored": len(services),
                    "slos_tracked": total_slos,
                },
            ),
        ]
        
        # Top issues
        if incidents:
            service_counts = {}
            for incident in incidents:
                service = incident.get("service", "unknown")
                service_counts[service] = service_counts.get(service, 0) + 1
            top_issue = max(service_counts.items(), key=lambda x: x[1])
            sections.append(ReportSection(
                title="Top Reliability Concern",
                content=f"{top_issue[0]} had {top_issue[1]} incidents this period.",
                data={},
            ))
        
        recommendations = []
        if critical_incidents > 0:
            recommendations.append("Address root causes of critical incidents")
        if slo_compliance < 100:
            recommendations.append("Improve reliability for non-compliant SLOs")
        if total_incidents > 10:
            recommendations.append("Focus on reducing incident volume through automation")
        
        return SREReport(
            report_type=ReportType.EXECUTIVE_SUMMARY,
            title="Executive Summary - SRE Report",
            period_start=period_start,
            period_end=period_end,
            generated_at=datetime.now(timezone.utc),
            summary=(
                f"Platform maintained {uptime:.2f}% uptime with {slo_compliance:.0f}% SLO compliance. "
                f"{total_incidents} incidents occurred, {critical_incidents} critical. "
                f"Monitoring {len(services)} services."
            ),
            sections=sections,
            key_metrics={
                "uptime": round(uptime, 2),
                "slo_compliance": slo_compliance,
                "total_incidents": total_incidents,
                "critical_incidents": critical_incidents,
                "services_count": len(services),
            },
            recommendations=recommendations,
        )
    
    def _generate_on_call_summary(
        self,
        data: dict,
        period_start: datetime,
        period_end: datetime,
    ) -> SREReport:
        """Generate on-call summary report."""
        incidents = data.get("incidents", [])
        on_call_rotation = data.get("on_call_rotation", "Unknown")
        
        total_incidents = len(incidents)
        
        # Time distribution
        hour_counts = {}
        for incident in incidents:
            ts = incident.get("timestamp") or incident.get("created_at")
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if ts:
                hour = ts.hour
                period = "Night (00-06)" if 0 <= hour < 6 else \
                         "Morning (06-12)" if 6 <= hour < 12 else \
                         "Afternoon (12-18)" if 12 <= hour < 18 else \
                         "Evening (18-24)"
                hour_counts[period] = hour_counts.get(period, 0) + 1
        
        # Weekend vs weekday
        weekend_count = 0
        weekday_count = 0
        for incident in incidents:
            ts = incident.get("timestamp") or incident.get("created_at")
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if ts:
                if ts.weekday() >= 5:
                    weekend_count += 1
                else:
                    weekday_count += 1
        
        sections = [
            ReportSection(
                title="On-Call Load",
                content=f"Total pages/incidents handled: {total_incidents}",
                data={
                    "weekday_incidents": weekday_count,
                    "weekend_incidents": weekend_count,
                    "distribution_by_time": hour_counts,
                },
            ),
        ]
        
        recommendations = []
        night_count = hour_counts.get("Night (00-06)", 0)
        if night_count > total_incidents * 0.2:
            recommendations.append(
                f"High night-time pages ({night_count}) - review alerting thresholds"
            )
        if weekend_count > total_incidents * 0.3:
            recommendations.append(
                "High weekend load - consider adjusting change freeze windows"
            )
        
        return SREReport(
            report_type=ReportType.ON_CALL_SUMMARY,
            title="On-Call Summary Report",
            period_start=period_start,
            period_end=period_end,
            generated_at=datetime.now(timezone.utc),
            summary=(
                f"On-call rotation handled {total_incidents} incidents. "
                f"{weekday_count} weekday, {weekend_count} weekend incidents."
            ),
            sections=sections,
            key_metrics={
                "total_pages": total_incidents,
                "weekday_incidents": weekday_count,
                "weekend_incidents": weekend_count,
                "night_pages": night_count,
            },
            recommendations=recommendations,
            metadata={"on_call_rotation": on_call_rotation},
        )
