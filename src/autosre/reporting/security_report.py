"""Security Reports for AutoSRE V2.

Provides security posture reporting:
- Vulnerability tracking
- Compliance status
- Security findings
- Risk assessment
"""

from __future__ import annotations

from datetime import datetime, timezone
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
)
from autosre.utils.logging import get_logger

logger = get_logger(__name__)


class SecuritySeverity(str, Enum):
    """Security finding severity levels."""
    
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class FindingStatus(str, Enum):
    """Status of a security finding."""
    
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    ACCEPTED = "accepted"  # Risk accepted
    FALSE_POSITIVE = "false_positive"


class FindingCategory(str, Enum):
    """Categories of security findings."""
    
    VULNERABILITY = "vulnerability"
    MISCONFIGURATION = "misconfiguration"
    COMPLIANCE = "compliance"
    ACCESS_CONTROL = "access_control"
    DATA_EXPOSURE = "data_exposure"
    NETWORK = "network"
    SECRETS = "secrets"
    CONTAINER = "container"
    INFRASTRUCTURE = "infrastructure"


class SecurityFinding(BaseModel):
    """A security finding."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    
    # Classification
    title: str
    description: str
    category: FindingCategory
    severity: SecuritySeverity
    
    # Status
    status: FindingStatus = FindingStatus.OPEN
    
    # Resource
    resource_type: str
    resource_id: str
    resource_name: Optional[str] = None
    
    # Additional context
    cve_ids: List[str] = Field(default_factory=list)
    cwe_ids: List[str] = Field(default_factory=list)
    compliance_frameworks: List[str] = Field(default_factory=list)
    
    # Risk
    cvss_score: Optional[float] = None
    exploitability: str = "unknown"  # none, low, medium, high
    
    # Remediation
    remediation_steps: List[str] = Field(default_factory=list)
    remediation_effort: str = "medium"  # low, medium, high
    
    # Timing
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None
    
    # Source
    source: str = "autosre"
    source_scan_id: Optional[str] = None


class ComplianceControl(BaseModel):
    """A compliance control."""
    
    id: str
    framework: str  # SOC2, HIPAA, PCI-DSS, etc.
    control_id: str
    title: str
    description: str
    
    # Status
    status: str = "unknown"  # compliant, non_compliant, partial, not_applicable
    
    # Evidence
    evidence: List[str] = Field(default_factory=list)
    
    # Gaps
    gaps: List[str] = Field(default_factory=list)


class SecurityReportData(BaseModel):
    """Data for generating a security report."""
    
    # Scope
    services: List[str] = Field(default_factory=list)
    environment: str = "production"
    
    # Findings
    findings: List[SecurityFinding] = Field(default_factory=list)
    
    # Summary counts
    total_findings: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    info_count: int = 0
    
    # Status counts
    open_count: int = 0
    in_progress_count: int = 0
    resolved_count: int = 0
    
    # Compliance
    compliance_controls: List[ComplianceControl] = Field(default_factory=list)
    compliance_score: Optional[float] = None  # 0-100
    
    # Trends
    findings_by_category: Dict[str, int] = Field(default_factory=dict)
    findings_trend: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Risk score
    overall_risk_score: Optional[float] = None  # 0-10


class SecurityReport:
    """
    Generates security posture reports.
    
    Provides:
    - Finding summary
    - Severity breakdown
    - Compliance status
    - Risk assessment
    - Remediation tracking
    
    Example:
        report_gen = SecurityReport(generator)
        
        data = SecurityReportData(
            total_findings=25,
            critical_count=2,
            high_count=5,
            medium_count=10,
            low_count=8,
        )
        
        # Add findings...
        
        report = await report_gen.generate(
            tenant_id="tenant-123",
            data=data,
            period_start=datetime(2024, 1, 1),
            period_end=datetime(2024, 1, 31),
        )
    """
    
    def __init__(self, generator: ReportGenerator):
        self.generator = generator
    
    async def generate(
        self,
        tenant_id: str,
        data: SecurityReportData,
        period_start: datetime,
        period_end: datetime,
        format: ReportFormat = ReportFormat.HTML,
    ) -> Report:
        """Generate a security report."""
        key_metrics = self._calculate_metrics(data)
        
        report = Report(
            tenant_id=tenant_id,
            report_type=ReportType.SECURITY,
            title="Security Posture Report",
            subtitle=f"Environment: {data.environment}",
            period_start=period_start,
            period_end=period_end,
            summary=self._generate_summary(data),
            key_metrics=key_metrics,
        )
        
        self._add_overview_section(report, data)
        self._add_findings_section(report, data)
        self._add_compliance_section(report, data)
        self._add_risk_section(report, data)
        self._add_recommendations_section(report, data)
        
        await self.generator.generate(report, format)
        
        return report
    
    def _calculate_metrics(self, data: SecurityReportData) -> Dict[str, Any]:
        """Calculate key metrics."""
        return {
            "Total Findings": data.total_findings,
            "Critical/High": data.critical_count + data.high_count,
            "Open Issues": data.open_count,
            "Compliance Score": f"{data.compliance_score:.0f}%" if data.compliance_score else "N/A",
            "Risk Score": f"{data.overall_risk_score:.1f}/10" if data.overall_risk_score else "N/A",
        }
    
    def _generate_summary(self, data: SecurityReportData) -> str:
        """Generate executive summary."""
        risk_level = "Low"
        if data.overall_risk_score:
            if data.overall_risk_score >= 7:
                risk_level = "Critical"
            elif data.overall_risk_score >= 5:
                risk_level = "High"
            elif data.overall_risk_score >= 3:
                risk_level = "Medium"
        
        return f"""
        <p>This report provides an overview of the security posture for the {data.environment} environment.</p>
        <p><strong>Overall Risk Level:</strong> {risk_level}</p>
        <p>There are currently {data.open_count} open security findings, including 
           {data.critical_count} critical and {data.high_count} high severity issues.</p>
        """
    
    def _add_overview_section(
        self,
        report: Report,
        data: SecurityReportData,
    ) -> None:
        """Add security overview section."""
        content = f"""
        <div class="security-overview">
            <div class="severity-cards">
                <div class="severity-card critical">
                    <div class="count">{data.critical_count}</div>
                    <div class="label">Critical</div>
                </div>
                <div class="severity-card high">
                    <div class="count">{data.high_count}</div>
                    <div class="label">High</div>
                </div>
                <div class="severity-card medium">
                    <div class="count">{data.medium_count}</div>
                    <div class="label">Medium</div>
                </div>
                <div class="severity-card low">
                    <div class="count">{data.low_count}</div>
                    <div class="label">Low</div>
                </div>
            </div>
            
            <h3>Findings by Category</h3>
            <table>
                <thead><tr><th>Category</th><th>Count</th></tr></thead>
                <tbody>
        """
        
        for category, count in data.findings_by_category.items():
            content += f"<tr><td>{category.replace('_', ' ').title()}</td><td>{count}</td></tr>"
        
        content += """
                </tbody>
            </table>
            
            <style>
            .severity-cards { display: flex; gap: 15px; margin: 20px 0; }
            .severity-card { flex: 1; padding: 20px; border-radius: 8px; text-align: center; color: white; }
            .severity-card .count { font-size: 2em; font-weight: bold; }
            .severity-card.critical { background: #dc3545; }
            .severity-card.high { background: #fd7e14; }
            .severity-card.medium { background: #ffc107; color: #333; }
            .severity-card.low { background: #28a745; }
            </style>
        </div>
        """
        
        report.add_section(
            title="Security Overview",
            content=content,
        )
    
    def _add_findings_section(
        self,
        report: Report,
        data: SecurityReportData,
    ) -> None:
        """Add findings details section."""
        # Sort findings by severity
        severity_order = {
            SecuritySeverity.CRITICAL: 0,
            SecuritySeverity.HIGH: 1,
            SecuritySeverity.MEDIUM: 2,
            SecuritySeverity.LOW: 3,
            SecuritySeverity.INFO: 4,
        }
        
        sorted_findings = sorted(
            data.findings,
            key=lambda f: severity_order.get(f.severity, 5),
        )
        
        # Only show open/in-progress findings
        active_findings = [
            f for f in sorted_findings
            if f.status in (FindingStatus.OPEN, FindingStatus.IN_PROGRESS)
        ][:20]  # Limit to 20
        
        rows = []
        for finding in active_findings:
            severity_class = f"status-{'danger' if finding.severity in (SecuritySeverity.CRITICAL, SecuritySeverity.HIGH) else 'warning'}"
            rows.append([
                finding.id[:8],
                finding.title[:50],
                finding.category.value.replace("_", " ").title(),
                f'<span class="{severity_class}">{finding.severity.value.upper()}</span>',
                finding.status.value.replace("_", " ").title(),
                finding.resource_name or finding.resource_id,
            ])
        
        if rows:
            table = TableData(
                headers=["ID", "Title", "Category", "Severity", "Status", "Resource"],
                rows=rows,
            )
            content = self.generator.render_table(table)
        else:
            content = "<p>No active findings.</p>"
        
        report.add_section(
            title="Active Security Findings",
            content=content,
        )
    
    def _add_compliance_section(
        self,
        report: Report,
        data: SecurityReportData,
    ) -> None:
        """Add compliance status section."""
        if not data.compliance_controls:
            return
        
        # Group by framework
        by_framework: Dict[str, List[ComplianceControl]] = {}
        for control in data.compliance_controls:
            if control.framework not in by_framework:
                by_framework[control.framework] = []
            by_framework[control.framework].append(control)
        
        content = '<div class="compliance">'
        
        for framework, controls in by_framework.items():
            compliant = sum(1 for c in controls if c.status == "compliant")
            total = len(controls)
            percentage = (compliant / total * 100) if total > 0 else 0
            
            content += f"""
            <div class="framework-card">
                <h3>{framework}</h3>
                <div class="compliance-meter">
                    <div class="meter-fill" style="width: {percentage}%;"></div>
                </div>
                <p>{compliant}/{total} controls compliant ({percentage:.0f}%)</p>
            </div>
            """
        
        content += """
            <style>
            .framework-card { margin: 20px 0; padding: 20px; background: #f8f9fa; border-radius: 8px; }
            .compliance-meter { height: 20px; background: #e9ecef; border-radius: 10px; overflow: hidden; }
            .meter-fill { height: 100%; background: linear-gradient(90deg, #28a745, #20c997); }
            </style>
        </div>
        """
        
        report.add_section(
            title="Compliance Status",
            content=content,
        )
    
    def _add_risk_section(
        self,
        report: Report,
        data: SecurityReportData,
    ) -> None:
        """Add risk assessment section."""
        risk_score = data.overall_risk_score or 0
        risk_level = "Low"
        risk_color = "#28a745"
        
        if risk_score >= 7:
            risk_level = "Critical"
            risk_color = "#dc3545"
        elif risk_score >= 5:
            risk_level = "High"
            risk_color = "#fd7e14"
        elif risk_score >= 3:
            risk_level = "Medium"
            risk_color = "#ffc107"
        
        content = f"""
        <div class="risk-assessment">
            <div class="risk-gauge">
                <div class="gauge-value" style="color: {risk_color};">{risk_score:.1f}</div>
                <div class="gauge-label">Risk Score (0-10)</div>
                <div class="risk-level" style="background: {risk_color};">{risk_level}</div>
            </div>
            
            <h3>Risk Factors</h3>
            <ul>
                <li>Critical vulnerabilities: {data.critical_count}</li>
                <li>High severity issues: {data.high_count}</li>
                <li>Compliance gaps: {sum(1 for c in data.compliance_controls if c.status == 'non_compliant')}</li>
            </ul>
            
            <style>
            .risk-gauge {{ text-align: center; margin: 30px 0; }}
            .gauge-value {{ font-size: 4em; font-weight: bold; }}
            .gauge-label {{ color: #666; margin-top: -10px; }}
            .risk-level {{ display: inline-block; padding: 10px 30px; border-radius: 20px; color: white; margin-top: 15px; font-weight: bold; }}
            </style>
        </div>
        """
        
        report.add_section(
            title="Risk Assessment",
            content=content,
        )
    
    def _add_recommendations_section(
        self,
        report: Report,
        data: SecurityReportData,
    ) -> None:
        """Add recommendations section."""
        recommendations = []
        
        # Critical findings
        if data.critical_count > 0:
            recommendations.append({
                "priority": "critical",
                "title": "Address Critical Vulnerabilities",
                "description": f"There are {data.critical_count} critical security findings that require immediate attention.",
            })
        
        # High findings
        if data.high_count > 0:
            recommendations.append({
                "priority": "high",
                "title": "Remediate High Severity Issues",
                "description": f"Plan remediation for {data.high_count} high severity findings within the next sprint.",
            })
        
        # Compliance gaps
        non_compliant = sum(1 for c in data.compliance_controls if c.status == "non_compliant")
        if non_compliant > 0:
            recommendations.append({
                "priority": "high",
                "title": "Address Compliance Gaps",
                "description": f"{non_compliant} compliance controls are non-compliant. Review and implement required controls.",
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
        
        content += "</div>"
        
        report.add_section(
            title="Recommendations",
            content=content,
            page_break_before=True,
        )
