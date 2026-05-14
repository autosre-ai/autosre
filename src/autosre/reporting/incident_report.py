"""Incident Reports for AutoSRE V2.

Provides detailed incident reporting:
- Timeline generation
- Root cause analysis
- Impact assessment
- Lessons learned
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from autosre.reporting.report_generator import (
    Report,
    ReportFormat,
    ReportGenerator,
    ReportSection,
    ReportType,
    TableData,
)
from autosre.utils.logging import get_logger

logger = get_logger(__name__)


class IncidentTimelineEvent(BaseModel):
    """An event in the incident timeline."""
    
    timestamp: datetime
    event_type: str  # alert, action, communication, status_change
    title: str
    description: Optional[str] = None
    actor: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class IncidentTimeline(BaseModel):
    """Complete incident timeline."""
    
    events: List[IncidentTimelineEvent] = Field(default_factory=list)
    
    def add_event(
        self,
        timestamp: datetime,
        event_type: str,
        title: str,
        **kwargs,
    ) -> IncidentTimelineEvent:
        """Add an event to the timeline."""
        event = IncidentTimelineEvent(
            timestamp=timestamp,
            event_type=event_type,
            title=title,
            **kwargs,
        )
        self.events.append(event)
        self.events.sort(key=lambda e: e.timestamp)
        return event
    
    def to_html(self) -> str:
        """Render timeline to HTML."""
        html = ['<div class="timeline">']
        
        for event in self.events:
            icon_map = {
                "alert": "🚨",
                "action": "⚡",
                "communication": "💬",
                "status_change": "🔄",
                "detection": "👀",
                "mitigation": "🛡️",
                "resolution": "✅",
            }
            icon = icon_map.get(event.event_type, "📌")
            
            html.append(f'''
            <div class="timeline-event">
                <div class="timeline-time">{event.timestamp.strftime("%H:%M:%S")}</div>
                <div class="timeline-icon">{icon}</div>
                <div class="timeline-content">
                    <strong>{event.title}</strong>
                    {f"<p>{event.description}</p>" if event.description else ""}
                    {f"<span class='actor'>— {event.actor}</span>" if event.actor else ""}
                </div>
            </div>
            ''')
        
        html.append('</div>')
        
        return "\n".join(html)


class ImpactAssessment(BaseModel):
    """Assessment of incident impact."""
    
    # User impact
    affected_users: Optional[int] = None
    affected_users_percentage: Optional[float] = None
    
    # Service impact
    affected_services: List[str] = Field(default_factory=list)
    affected_regions: List[str] = Field(default_factory=list)
    
    # Time impact
    detection_time_minutes: Optional[float] = None
    mitigation_time_minutes: Optional[float] = None
    resolution_time_minutes: Optional[float] = None
    total_downtime_minutes: Optional[float] = None
    
    # Business impact
    revenue_impact_usd: Optional[float] = None
    sla_breach: bool = False
    customer_tickets: int = 0
    
    # Severity
    severity: str = "medium"  # low, medium, high, critical


class RootCauseAnalysis(BaseModel):
    """Root cause analysis of the incident."""
    
    # Root cause
    root_cause: str
    root_cause_category: str  # code, config, infrastructure, external, human
    
    # Contributing factors
    contributing_factors: List[str] = Field(default_factory=list)
    
    # Detection
    how_detected: str
    detection_gap: Optional[str] = None  # Why wasn't it detected earlier?
    
    # Prevention
    could_have_been_prevented: bool = True
    prevention_measures: List[str] = Field(default_factory=list)


class LessonsLearned(BaseModel):
    """Lessons learned from the incident."""
    
    what_went_well: List[str] = Field(default_factory=list)
    what_went_wrong: List[str] = Field(default_factory=list)
    action_items: List[Dict[str, Any]] = Field(default_factory=list)
    # e.g., [{"action": "Add monitoring", "owner": "John", "due_date": "2024-01-15"}]


class IncidentReportData(BaseModel):
    """Data for generating an incident report."""
    
    # Incident identification
    incident_id: str
    incident_title: str
    incident_severity: str
    
    # Timing
    detected_at: datetime
    mitigated_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    
    # Summary
    executive_summary: str
    technical_summary: Optional[str] = None
    
    # Timeline
    timeline: IncidentTimeline = Field(default_factory=IncidentTimeline)
    
    # Analysis
    impact: ImpactAssessment = Field(default_factory=ImpactAssessment)
    root_cause: Optional[RootCauseAnalysis] = None
    lessons: LessonsLearned = Field(default_factory=LessonsLearned)
    
    # Related items
    related_alerts: List[str] = Field(default_factory=list)
    related_investigations: List[str] = Field(default_factory=list)
    actions_taken: List[Dict[str, Any]] = Field(default_factory=list)


class IncidentReport:
    """
    Generates detailed incident reports.
    
    Provides:
    - Executive summary
    - Technical details
    - Timeline visualization
    - Impact assessment
    - Root cause analysis
    - Action items
    
    Example:
        report_gen = IncidentReport(generator)
        
        data = IncidentReportData(
            incident_id="INC-001",
            incident_title="Database Outage",
            incident_severity="high",
            detected_at=datetime(2024, 1, 15, 10, 0),
            resolved_at=datetime(2024, 1, 15, 12, 30),
            executive_summary="A database connection pool exhaustion...",
        )
        
        data.timeline.add_event(
            timestamp=datetime(2024, 1, 15, 10, 0),
            event_type="detection",
            title="Alert triggered",
        )
        
        report = await report_gen.generate(
            tenant_id="tenant-123",
            data=data,
        )
    """
    
    def __init__(self, generator: ReportGenerator):
        """Initialize IncidentReport.
        
        Args:
            generator: ReportGenerator instance
        """
        self.generator = generator
    
    async def generate(
        self,
        tenant_id: str,
        data: IncidentReportData,
        format: ReportFormat = ReportFormat.HTML,
    ) -> Report:
        """Generate an incident report.
        
        Args:
            tenant_id: Tenant ID
            data: Incident report data
            format: Output format
            
        Returns:
            Generated report
        """
        # Calculate key metrics
        key_metrics = self._calculate_metrics(data)
        
        # Create report
        report = Report(
            tenant_id=tenant_id,
            report_type=ReportType.INCIDENT,
            title=f"Incident Report: {data.incident_title}",
            subtitle=f"Incident ID: {data.incident_id}",
            period_start=data.detected_at,
            period_end=data.resolved_at or datetime.now(timezone.utc),
            summary=data.executive_summary,
            key_metrics=key_metrics,
        )
        
        # Add sections
        self._add_executive_summary(report, data)
        self._add_timeline_section(report, data)
        self._add_impact_section(report, data)
        
        if data.root_cause:
            self._add_root_cause_section(report, data)
        
        self._add_actions_section(report, data)
        self._add_lessons_section(report, data)
        
        # Generate output
        await self.generator.generate(report, format)
        
        return report
    
    def _calculate_metrics(self, data: IncidentReportData) -> Dict[str, Any]:
        """Calculate key metrics for the report."""
        metrics = {}
        
        # Severity
        metrics["Severity"] = data.incident_severity.upper()
        
        # Time to detect (if applicable)
        if data.impact.detection_time_minutes:
            metrics["Time to Detect"] = f"{data.impact.detection_time_minutes:.1f} min"
        
        # Time to mitigate
        if data.mitigated_at:
            mttr = (data.mitigated_at - data.detected_at).total_seconds() / 60
            metrics["Time to Mitigate"] = f"{mttr:.1f} min"
        
        # Time to resolve
        if data.resolved_at:
            resolution = (data.resolved_at - data.detected_at).total_seconds() / 60
            metrics["Time to Resolve"] = f"{resolution:.1f} min"
        
        # Affected users
        if data.impact.affected_users:
            metrics["Affected Users"] = f"{data.impact.affected_users:,}"
        
        # Actions
        metrics["Actions Taken"] = len(data.actions_taken)
        
        return metrics
    
    def _add_executive_summary(
        self,
        report: Report,
        data: IncidentReportData,
    ) -> None:
        """Add executive summary section."""
        content = f"""
        <div class="executive-summary">
            <p>{data.executive_summary}</p>
            
            <table>
                <tr>
                    <th>Incident ID</th>
                    <td>{data.incident_id}</td>
                    <th>Severity</th>
                    <td class="status-{'danger' if data.incident_severity == 'critical' else 'warning'}">{data.incident_severity.upper()}</td>
                </tr>
                <tr>
                    <th>Detected</th>
                    <td>{data.detected_at.strftime('%Y-%m-%d %H:%M:%S UTC')}</td>
                    <th>Resolved</th>
                    <td>{data.resolved_at.strftime('%Y-%m-%d %H:%M:%S UTC') if data.resolved_at else 'Ongoing'}</td>
                </tr>
                <tr>
                    <th>Affected Services</th>
                    <td colspan="3">{', '.join(data.impact.affected_services) or 'N/A'}</td>
                </tr>
            </table>
        </div>
        """
        
        report.add_section(
            title="Executive Summary",
            content=content,
        )
    
    def _add_timeline_section(
        self,
        report: Report,
        data: IncidentReportData,
    ) -> None:
        """Add timeline section."""
        timeline_style = """
        <style>
        .timeline { position: relative; padding-left: 30px; }
        .timeline::before { content: ''; position: absolute; left: 10px; top: 0; bottom: 0; width: 2px; background: #dee2e6; }
        .timeline-event { position: relative; margin-bottom: 20px; }
        .timeline-time { font-size: 0.85em; color: #666; }
        .timeline-icon { position: absolute; left: -25px; }
        .timeline-content { padding-left: 10px; }
        .actor { font-size: 0.85em; color: #888; }
        </style>
        """
        
        content = timeline_style + data.timeline.to_html()
        
        report.add_section(
            title="Incident Timeline",
            content=content,
        )
    
    def _add_impact_section(
        self,
        report: Report,
        data: IncidentReportData,
    ) -> None:
        """Add impact assessment section."""
        impact = data.impact
        
        content = f"""
        <div class="impact-assessment">
            <h3>User Impact</h3>
            <ul>
                <li>Affected Users: {impact.affected_users or 'Unknown'} ({impact.affected_users_percentage or '?'}%)</li>
                <li>Customer Tickets: {impact.customer_tickets}</li>
            </ul>
            
            <h3>Service Impact</h3>
            <ul>
                <li>Affected Services: {', '.join(impact.affected_services) or 'N/A'}</li>
                <li>Affected Regions: {', '.join(impact.affected_regions) or 'All'}</li>
                <li>Total Downtime: {impact.total_downtime_minutes or 'N/A'} minutes</li>
            </ul>
            
            <h3>Business Impact</h3>
            <ul>
                <li>SLA Breach: {'Yes' if impact.sla_breach else 'No'}</li>
                {'<li>Revenue Impact: $' + f'{impact.revenue_impact_usd:,.2f}</li>' if impact.revenue_impact_usd else ''}
            </ul>
        </div>
        """
        
        report.add_section(
            title="Impact Assessment",
            content=content,
        )
    
    def _add_root_cause_section(
        self,
        report: Report,
        data: IncidentReportData,
    ) -> None:
        """Add root cause analysis section."""
        rca = data.root_cause
        if not rca:
            return
        
        content = f"""
        <div class="root-cause">
            <h3>Root Cause</h3>
            <p><strong>{rca.root_cause}</strong></p>
            <p>Category: {rca.root_cause_category.title()}</p>
            
            <h3>Contributing Factors</h3>
            <ul>
                {''.join(f'<li>{factor}</li>' for factor in rca.contributing_factors) or '<li>None identified</li>'}
            </ul>
            
            <h3>Detection</h3>
            <p><strong>How Detected:</strong> {rca.how_detected}</p>
            {f'<p><strong>Detection Gap:</strong> {rca.detection_gap}</p>' if rca.detection_gap else ''}
            
            <h3>Prevention</h3>
            <p>Could this have been prevented? {'Yes' if rca.could_have_been_prevented else 'No'}</p>
            <ul>
                {''.join(f'<li>{measure}</li>' for measure in rca.prevention_measures) or '<li>No additional measures identified</li>'}
            </ul>
        </div>
        """
        
        report.add_section(
            title="Root Cause Analysis",
            content=content,
        )
    
    def _add_actions_section(
        self,
        report: Report,
        data: IncidentReportData,
    ) -> None:
        """Add actions taken section."""
        if not data.actions_taken:
            return
        
        rows = []
        for action in data.actions_taken:
            rows.append([
                action.get("timestamp", ""),
                action.get("type", ""),
                action.get("description", ""),
                action.get("status", ""),
                action.get("performed_by", ""),
            ])
        
        table = TableData(
            title="Actions Taken",
            headers=["Time", "Type", "Description", "Status", "Performed By"],
            rows=rows,
        )
        
        content = self.generator.render_table(table)
        
        report.add_section(
            title="Actions Taken",
            content=content,
        )
    
    def _add_lessons_section(
        self,
        report: Report,
        data: IncidentReportData,
    ) -> None:
        """Add lessons learned section."""
        lessons = data.lessons
        
        content = f"""
        <div class="lessons-learned">
            <h3>What Went Well</h3>
            <ul>
                {''.join(f'<li>{item}</li>' for item in lessons.what_went_well) or '<li>No items recorded</li>'}
            </ul>
            
            <h3>What Went Wrong</h3>
            <ul>
                {''.join(f'<li>{item}</li>' for item in lessons.what_went_wrong) or '<li>No items recorded</li>'}
            </ul>
        """
        
        if lessons.action_items:
            content += """
            <h3>Action Items</h3>
            <table>
                <thead>
                    <tr>
                        <th>Action</th>
                        <th>Owner</th>
                        <th>Due Date</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
            """
            
            for item in lessons.action_items:
                content += f"""
                    <tr>
                        <td>{item.get('action', '')}</td>
                        <td>{item.get('owner', 'Unassigned')}</td>
                        <td>{item.get('due_date', 'TBD')}</td>
                        <td>{item.get('status', 'Open')}</td>
                    </tr>
                """
            
            content += """
                </tbody>
            </table>
            """
        
        content += "</div>"
        
        report.add_section(
            title="Lessons Learned",
            content=content,
            page_break_before=True,
        )
