"""
Compliance Audit Framework

Unified compliance auditing across SOC2, HIPAA, GDPR, and PCI-DSS.
Generates comprehensive audit reports and compliance dashboards.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from autosre.logging import get_logger
from autosre.compliance.soc2 import SOC2Checker, SOC2Report, SOC2Category
from autosre.compliance.hipaa import HIPAAChecker, HIPAAReport, SafeguardType
from autosre.compliance.gdpr import GDPRChecker, GDPRReport, GDPRPrinciple
from autosre.compliance.pci import PCIChecker, PCIReport, PCICategory, PCILevel

logger = get_logger(__name__)


class AuditSeverity(Enum):
    """Severity levels for audit findings."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class ComplianceStatus(Enum):
    """Overall compliance status."""

    COMPLIANT = "compliant"
    PARTIALLY_COMPLIANT = "partially_compliant"
    NON_COMPLIANT = "non_compliant"
    NOT_ASSESSED = "not_assessed"


class ComplianceFramework(Enum):
    """Supported compliance frameworks."""

    SOC2 = "soc2"
    HIPAA = "hipaa"
    GDPR = "gdpr"
    PCI_DSS = "pci_dss"


@dataclass
class AuditFinding:
    """Unified audit finding across all frameworks."""

    id: str
    framework: ComplianceFramework
    requirement_id: str
    title: str
    description: str
    passed: bool
    severity: AuditSeverity
    evidence: dict[str, Any] = field(default_factory=dict)
    remediation: str | None = None
    due_date: datetime | None = None
    assigned_to: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class AuditReport:
    """Comprehensive audit report across all compliance frameworks."""

    report_id: str
    organization: str
    generated_at: datetime
    audit_period_start: datetime
    audit_period_end: datetime
    frameworks_assessed: list[ComplianceFramework]
    findings: list[AuditFinding]
    framework_reports: dict[ComplianceFramework, Any]
    overall_status: ComplianceStatus
    framework_status: dict[ComplianceFramework, ComplianceStatus]
    executive_summary: str = ""
    auditor_name: str | None = None
    next_audit_date: datetime | None = None

    @property
    def critical_findings(self) -> list[AuditFinding]:
        """Get critical severity findings."""
        return [
            f for f in self.findings if f.severity == AuditSeverity.CRITICAL
        ]

    @property
    def high_findings(self) -> list[AuditFinding]:
        """Get high severity findings."""
        return [f for f in self.findings if f.severity == AuditSeverity.HIGH]

    def get_findings_by_framework(
        self, framework: ComplianceFramework
    ) -> list[AuditFinding]:
        """Get findings for a specific framework."""
        return [f for f in self.findings if f.framework == framework]

    def get_failed_findings(self) -> list[AuditFinding]:
        """Get all failed findings."""
        return [f for f in self.findings if not f.passed]

    def to_dict(self) -> dict[str, Any]:
        """Convert report to dictionary for serialization."""
        return {
            "report_id": self.report_id,
            "organization": self.organization,
            "generated_at": self.generated_at.isoformat(),
            "audit_period_start": self.audit_period_start.isoformat(),
            "audit_period_end": self.audit_period_end.isoformat(),
            "frameworks_assessed": [f.value for f in self.frameworks_assessed],
            "overall_status": self.overall_status.value,
            "framework_status": {
                f.value: s.value for f, s in self.framework_status.items()
            },
            "total_findings": len(self.findings),
            "failed_findings": len(self.get_failed_findings()),
            "critical_findings": len(self.critical_findings),
            "high_findings": len(self.high_findings),
            "executive_summary": self.executive_summary,
            "auditor_name": self.auditor_name,
        }


class ComplianceAuditor:
    """
    Unified Compliance Auditor.

    Orchestrates compliance checks across multiple frameworks
    and generates comprehensive audit reports.
    """

    def __init__(
        self,
        organization: str,
        soc2_enabled: bool = True,
        hipaa_enabled: bool = False,
        gdpr_enabled: bool = False,
        pci_enabled: bool = False,
    ):
        self.organization = organization
        self.soc2_enabled = soc2_enabled
        self.hipaa_enabled = hipaa_enabled
        self.gdpr_enabled = gdpr_enabled
        self.pci_enabled = pci_enabled

        # Initialize checkers
        self.soc2_checker = SOC2Checker() if soc2_enabled else None
        self.hipaa_checker = (
            HIPAAChecker(covered_entity=organization) if hipaa_enabled else None
        )
        self.gdpr_checker = (
            GDPRChecker(data_controller=organization) if gdpr_enabled else None
        )
        self.pci_checker = (
            PCIChecker(merchant_id=organization) if pci_enabled else None
        )

    def _determine_severity(
        self, passed: bool, framework: ComplianceFramework, requirement_id: str
    ) -> AuditSeverity:
        """Determine severity based on framework and requirement."""
        if passed:
            return AuditSeverity.INFORMATIONAL

        # Critical requirements
        critical_requirements = {
            ComplianceFramework.SOC2: ["CC6.1", "CC6.7", "CC7.2"],
            ComplianceFramework.HIPAA: [
                "164.312(a)(1)",
                "164.312(e)(1)",
                "164.308(a)(1)(i)",
            ],
            ComplianceFramework.GDPR: ["ART5.1.F", "ART32", "ART33"],
            ComplianceFramework.PCI_DSS: ["3.4", "4.2", "8.3"],
        }

        # High requirements
        high_requirements = {
            ComplianceFramework.SOC2: ["CC6.2", "CC6.3", "CC6.6", "A1.2"],
            ComplianceFramework.HIPAA: [
                "164.312(b)",
                "164.312(d)",
                "164.308(a)(7)(i)",
            ],
            ComplianceFramework.GDPR: ["ART5.1.A", "ART15", "ART17"],
            ComplianceFramework.PCI_DSS: ["1.1", "7.2", "10.2", "11.3"],
        }

        if requirement_id in critical_requirements.get(framework, []):
            return AuditSeverity.CRITICAL
        elif requirement_id in high_requirements.get(framework, []):
            return AuditSeverity.HIGH
        else:
            return AuditSeverity.MEDIUM

    def _determine_framework_status(self, score: float) -> ComplianceStatus:
        """Determine compliance status from score."""
        if score >= 0.95:
            return ComplianceStatus.COMPLIANT
        elif score >= 0.70:
            return ComplianceStatus.PARTIALLY_COMPLIANT
        else:
            return ComplianceStatus.NON_COMPLIANT

    async def run_soc2_audit(
        self,
        context: dict[str, Any],
        period_start: datetime,
        period_end: datetime,
    ) -> tuple[SOC2Report, list[AuditFinding]]:
        """Run SOC2 audit and convert to unified findings."""
        if not self.soc2_checker:
            raise ValueError("SOC2 checker not enabled")

        report = await self.soc2_checker.generate_report(
            context, period_start, period_end
        )
        findings = []

        for f in report.findings:
            finding = AuditFinding(
                id=f"{ComplianceFramework.SOC2.value}_{f.control_id}",
                framework=ComplianceFramework.SOC2,
                requirement_id=f.control_id,
                title=f.title,
                description=f.description,
                passed=f.passed,
                severity=self._determine_severity(
                    f.passed, ComplianceFramework.SOC2, f.control_id
                ),
                evidence=f.evidence,
                remediation=f.remediation,
                timestamp=f.timestamp,
            )
            findings.append(finding)

        return report, findings

    async def run_hipaa_audit(
        self,
        context: dict[str, Any],
        phi_scope: list[str] | None = None,
    ) -> tuple[HIPAAReport, list[AuditFinding]]:
        """Run HIPAA audit and convert to unified findings."""
        if not self.hipaa_checker:
            raise ValueError("HIPAA checker not enabled")

        report = await self.hipaa_checker.generate_report(context, phi_scope)
        findings = []

        for f in report.findings:
            finding = AuditFinding(
                id=f"{ComplianceFramework.HIPAA.value}_{f.safeguard_id}",
                framework=ComplianceFramework.HIPAA,
                requirement_id=f.safeguard_id,
                title=f.title,
                description=f.description,
                passed=f.passed,
                severity=self._determine_severity(
                    f.passed, ComplianceFramework.HIPAA, f.safeguard_id
                ),
                evidence=f.evidence,
                remediation=f.remediation,
                timestamp=f.timestamp,
            )
            findings.append(finding)

        return report, findings

    async def run_gdpr_audit(
        self,
        context: dict[str, Any],
        processing_activities: list[str] | None = None,
    ) -> tuple[GDPRReport, list[AuditFinding]]:
        """Run GDPR audit and convert to unified findings."""
        if not self.gdpr_checker:
            raise ValueError("GDPR checker not enabled")

        report = await self.gdpr_checker.generate_report(context, processing_activities)
        findings = []

        for f in report.findings:
            finding = AuditFinding(
                id=f"{ComplianceFramework.GDPR.value}_{f.requirement_id}",
                framework=ComplianceFramework.GDPR,
                requirement_id=f.requirement_id,
                title=f.title,
                description=f.description,
                passed=f.passed,
                severity=self._determine_severity(
                    f.passed, ComplianceFramework.GDPR, f.requirement_id
                ),
                evidence=f.evidence,
                remediation=f.remediation,
                timestamp=f.timestamp,
            )
            findings.append(finding)

        return report, findings

    async def run_pci_audit(
        self,
        context: dict[str, Any],
        saq_type: str | None = None,
    ) -> tuple[PCIReport, list[AuditFinding]]:
        """Run PCI-DSS audit and convert to unified findings."""
        if not self.pci_checker:
            raise ValueError("PCI-DSS checker not enabled")

        report = await self.pci_checker.generate_report(context, saq_type)
        findings = []

        for f in report.findings:
            finding = AuditFinding(
                id=f"{ComplianceFramework.PCI_DSS.value}_{f.requirement_id}",
                framework=ComplianceFramework.PCI_DSS,
                requirement_id=f.requirement_id,
                title=f.title,
                description=f.description,
                passed=f.passed,
                severity=self._determine_severity(
                    f.passed, ComplianceFramework.PCI_DSS, f.requirement_id
                ),
                evidence=f.evidence,
                remediation=f.remediation,
                timestamp=f.timestamp,
            )
            findings.append(finding)

        return report, findings

    async def run_full_audit(
        self,
        context: dict[str, Any],
        period_start: datetime,
        period_end: datetime,
        phi_scope: list[str] | None = None,
        processing_activities: list[str] | None = None,
        saq_type: str | None = None,
    ) -> AuditReport:
        """Run comprehensive audit across all enabled frameworks."""
        import uuid

        logger.info(f"Starting full compliance audit for {self.organization}")

        all_findings: list[AuditFinding] = []
        framework_reports: dict[ComplianceFramework, Any] = {}
        framework_status: dict[ComplianceFramework, ComplianceStatus] = {}
        frameworks_assessed: list[ComplianceFramework] = []

        # Run SOC2
        if self.soc2_enabled:
            logger.info("Running SOC2 audit")
            soc2_report, soc2_findings = await self.run_soc2_audit(
                context, period_start, period_end
            )
            all_findings.extend(soc2_findings)
            framework_reports[ComplianceFramework.SOC2] = soc2_report
            framework_status[ComplianceFramework.SOC2] = self._determine_framework_status(
                soc2_report.overall_score
            )
            frameworks_assessed.append(ComplianceFramework.SOC2)

        # Run HIPAA
        if self.hipaa_enabled:
            logger.info("Running HIPAA audit")
            hipaa_report, hipaa_findings = await self.run_hipaa_audit(
                context, phi_scope
            )
            all_findings.extend(hipaa_findings)
            framework_reports[ComplianceFramework.HIPAA] = hipaa_report
            framework_status[ComplianceFramework.HIPAA] = (
                ComplianceStatus.COMPLIANT
                if hipaa_report.compliant
                else ComplianceStatus.NON_COMPLIANT
            )
            frameworks_assessed.append(ComplianceFramework.HIPAA)

        # Run GDPR
        if self.gdpr_enabled:
            logger.info("Running GDPR audit")
            gdpr_report, gdpr_findings = await self.run_gdpr_audit(
                context, processing_activities
            )
            all_findings.extend(gdpr_findings)
            framework_reports[ComplianceFramework.GDPR] = gdpr_report
            framework_status[ComplianceFramework.GDPR] = self._determine_framework_status(
                gdpr_report.overall_score
            )
            frameworks_assessed.append(ComplianceFramework.GDPR)

        # Run PCI-DSS
        if self.pci_enabled:
            logger.info("Running PCI-DSS audit")
            pci_report, pci_findings = await self.run_pci_audit(context, saq_type)
            all_findings.extend(pci_findings)
            framework_reports[ComplianceFramework.PCI_DSS] = pci_report
            framework_status[ComplianceFramework.PCI_DSS] = (
                ComplianceStatus.COMPLIANT
                if pci_report.compliant
                else ComplianceStatus.NON_COMPLIANT
            )
            frameworks_assessed.append(ComplianceFramework.PCI_DSS)

        # Determine overall status
        if all(s == ComplianceStatus.COMPLIANT for s in framework_status.values()):
            overall_status = ComplianceStatus.COMPLIANT
        elif any(s == ComplianceStatus.NON_COMPLIANT for s in framework_status.values()):
            overall_status = ComplianceStatus.NON_COMPLIANT
        else:
            overall_status = ComplianceStatus.PARTIALLY_COMPLIANT

        # Generate executive summary
        failed_count = len([f for f in all_findings if not f.passed])
        critical_count = len([f for f in all_findings if f.severity == AuditSeverity.CRITICAL and not f.passed])
        high_count = len([f for f in all_findings if f.severity == AuditSeverity.HIGH and not f.passed])

        executive_summary = (
            f"Compliance audit for {self.organization} covering {len(frameworks_assessed)} "
            f"framework(s). Found {failed_count} total findings requiring remediation, "
            f"including {critical_count} critical and {high_count} high severity issues. "
            f"Overall status: {overall_status.value}."
        )

        return AuditReport(
            report_id=str(uuid.uuid4()),
            organization=self.organization,
            generated_at=datetime.now(timezone.utc),
            audit_period_start=period_start,
            audit_period_end=period_end,
            frameworks_assessed=frameworks_assessed,
            findings=all_findings,
            framework_reports=framework_reports,
            overall_status=overall_status,
            framework_status=framework_status,
            executive_summary=executive_summary,
        )


def generate_compliance_dashboard(
    audit_report: AuditReport,
) -> dict[str, Any]:
    """
    Generate a compliance dashboard summary from an audit report.

    Returns data suitable for dashboard visualization.
    """
    # Calculate metrics
    total_findings = len(audit_report.findings)
    passed_findings = len([f for f in audit_report.findings if f.passed])
    failed_findings = total_findings - passed_findings

    # Severity breakdown
    severity_counts = {
        AuditSeverity.CRITICAL: 0,
        AuditSeverity.HIGH: 0,
        AuditSeverity.MEDIUM: 0,
        AuditSeverity.LOW: 0,
        AuditSeverity.INFORMATIONAL: 0,
    }
    for finding in audit_report.findings:
        if not finding.passed:
            severity_counts[finding.severity] += 1

    # Framework breakdown
    framework_metrics = {}
    for framework in audit_report.frameworks_assessed:
        fw_findings = audit_report.get_findings_by_framework(framework)
        fw_passed = len([f for f in fw_findings if f.passed])
        framework_metrics[framework.value] = {
            "total": len(fw_findings),
            "passed": fw_passed,
            "failed": len(fw_findings) - fw_passed,
            "score": fw_passed / len(fw_findings) if fw_findings else 1.0,
            "status": audit_report.framework_status.get(
                framework, ComplianceStatus.NOT_ASSESSED
            ).value,
        }

    # Top remediations needed
    top_remediations = [
        {
            "framework": f.framework.value,
            "requirement": f.requirement_id,
            "title": f.title,
            "severity": f.severity.value,
            "remediation": f.remediation,
        }
        for f in sorted(
            [f for f in audit_report.findings if not f.passed],
            key=lambda x: list(AuditSeverity).index(x.severity),
        )[:10]
    ]

    return {
        "report_id": audit_report.report_id,
        "organization": audit_report.organization,
        "generated_at": audit_report.generated_at.isoformat(),
        "overall_status": audit_report.overall_status.value,
        "summary": {
            "total_findings": total_findings,
            "passed": passed_findings,
            "failed": failed_findings,
            "compliance_percentage": (
                passed_findings / total_findings * 100 if total_findings else 100
            ),
        },
        "severity_breakdown": {
            k.value: v for k, v in severity_counts.items()
        },
        "framework_metrics": framework_metrics,
        "top_remediations": top_remediations,
        "executive_summary": audit_report.executive_summary,
    }
