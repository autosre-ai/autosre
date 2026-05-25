"""
SOC2 Type II Compliance Checker

Implements Trust Services Criteria (TSC) checks for:
- Security (CC - Common Criteria)
- Availability
- Processing Integrity
- Confidentiality
- Privacy
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable

from autosre.logging import get_logger

logger = get_logger(__name__)


class SOC2Category(Enum):
    """SOC2 Trust Services Categories."""

    SECURITY = "security"  # CC Series - Common Criteria
    AVAILABILITY = "availability"  # A Series
    PROCESSING_INTEGRITY = "processing_integrity"  # PI Series
    CONFIDENTIALITY = "confidentiality"  # C Series
    PRIVACY = "privacy"  # P Series


@dataclass
class SOC2Control:
    """Represents a SOC2 control point."""

    id: str  # e.g., "CC6.1", "A1.2"
    category: SOC2Category
    title: str
    description: str
    check_function: Callable[..., bool] | None = None
    evidence_required: list[str] = field(default_factory=list)
    automated: bool = True


@dataclass
class SOC2Finding:
    """A finding from SOC2 compliance check."""

    control_id: str
    category: SOC2Category
    passed: bool
    title: str
    description: str
    evidence: dict[str, Any] = field(default_factory=dict)
    remediation: str | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SOC2Report:
    """Complete SOC2 compliance report."""

    report_id: str
    generated_at: datetime
    period_start: datetime
    period_end: datetime
    findings: list[SOC2Finding]
    overall_score: float
    category_scores: dict[SOC2Category, float]
    auditor_notes: str = ""

    @property
    def passed(self) -> bool:
        """Check if overall compliance is met (>= 95% score)."""
        return self.overall_score >= 0.95

    def get_failures(self) -> list[SOC2Finding]:
        """Get all failed controls."""
        return [f for f in self.findings if not f.passed]


class SOC2Checker:
    """
    SOC2 Type II Compliance Checker.

    Performs automated checks against SOC2 Trust Services Criteria
    and generates compliance reports for audit purposes.
    """

    def __init__(self):
        self.controls: dict[str, SOC2Control] = {}
        self._register_default_controls()

    def _register_default_controls(self) -> None:
        """Register default SOC2 controls."""
        # Security Controls (CC Series)
        self._add_control(
            SOC2Control(
                id="CC6.1",
                category=SOC2Category.SECURITY,
                title="Logical and Physical Access Controls",
                description="The entity implements logical access security software, "
                "infrastructure, and architectures over protected information assets.",
                evidence_required=[
                    "access_control_policies",
                    "authentication_logs",
                    "rbac_configuration",
                ],
            )
        )
        self._add_control(
            SOC2Control(
                id="CC6.2",
                category=SOC2Category.SECURITY,
                title="System Account Management",
                description="Prior to issuing system credentials and granting system "
                "access, the entity registers and authorizes new users.",
                evidence_required=[
                    "user_provisioning_logs",
                    "approval_workflows",
                    "account_reviews",
                ],
            )
        )
        self._add_control(
            SOC2Control(
                id="CC6.3",
                category=SOC2Category.SECURITY,
                title="Access Removal",
                description="The entity removes access to protected information assets "
                "when appropriate.",
                evidence_required=[
                    "offboarding_procedures",
                    "access_revocation_logs",
                    "terminated_user_audits",
                ],
            )
        )
        self._add_control(
            SOC2Control(
                id="CC6.6",
                category=SOC2Category.SECURITY,
                title="Security Event Logging",
                description="The entity implements controls to prevent or detect and "
                "act upon the introduction of unauthorized or malicious software.",
                evidence_required=[
                    "security_logs",
                    "siem_configuration",
                    "incident_response_logs",
                ],
            )
        )
        self._add_control(
            SOC2Control(
                id="CC6.7",
                category=SOC2Category.SECURITY,
                title="Transmission Security",
                description="The entity restricts the transmission, movement, and "
                "removal of information to authorized users.",
                evidence_required=[
                    "encryption_configuration",
                    "tls_certificates",
                    "data_transfer_logs",
                ],
            )
        )
        self._add_control(
            SOC2Control(
                id="CC7.2",
                category=SOC2Category.SECURITY,
                title="Security Monitoring",
                description="The entity monitors system components and the operation "
                "of those components for anomalies.",
                evidence_required=[
                    "monitoring_dashboards",
                    "alert_configurations",
                    "anomaly_detection_rules",
                ],
            )
        )

        # Availability Controls (A Series)
        self._add_control(
            SOC2Control(
                id="A1.1",
                category=SOC2Category.AVAILABILITY,
                title="Capacity Planning",
                description="The entity maintains, monitors, and evaluates current "
                "processing capacity and use of system components.",
                evidence_required=[
                    "capacity_metrics",
                    "scaling_policies",
                    "resource_utilization_reports",
                ],
            )
        )
        self._add_control(
            SOC2Control(
                id="A1.2",
                category=SOC2Category.AVAILABILITY,
                title="Recovery Planning",
                description="The entity authorizes, designs, develops or acquires, "
                "implements, operates, approves, maintains, and monitors environmental "
                "protections, software, data backup processes, and recovery infrastructure.",
                evidence_required=[
                    "backup_configurations",
                    "disaster_recovery_plan",
                    "recovery_test_results",
                ],
            )
        )

        # Confidentiality Controls (C Series)
        self._add_control(
            SOC2Control(
                id="C1.1",
                category=SOC2Category.CONFIDENTIALITY,
                title="Confidential Information Identification",
                description="The entity identifies and maintains confidential "
                "information to meet the entity's objectives related to confidentiality.",
                evidence_required=[
                    "data_classification_policy",
                    "confidential_data_inventory",
                    "labeling_procedures",
                ],
            )
        )
        self._add_control(
            SOC2Control(
                id="C1.2",
                category=SOC2Category.CONFIDENTIALITY,
                title="Confidential Information Disposal",
                description="The entity disposes of confidential information to meet "
                "the entity's objectives related to confidentiality.",
                evidence_required=[
                    "data_retention_policy",
                    "disposal_procedures",
                    "destruction_certificates",
                ],
            )
        )

        # Processing Integrity Controls (PI Series)
        self._add_control(
            SOC2Control(
                id="PI1.1",
                category=SOC2Category.PROCESSING_INTEGRITY,
                title="Processing Quality Objectives",
                description="The entity obtains or generates, uses, and communicates "
                "relevant, quality information regarding the objectives related to processing.",
                evidence_required=[
                    "data_validation_rules",
                    "input_verification_logs",
                    "processing_accuracy_reports",
                ],
            )
        )

    def _add_control(self, control: SOC2Control) -> None:
        """Add a control to the checker."""
        self.controls[control.id] = control

    def register_control(
        self,
        id: str,
        category: SOC2Category,
        title: str,
        description: str,
        check_function: Callable[..., bool] | None = None,
        evidence_required: list[str] | None = None,
    ) -> None:
        """Register a custom SOC2 control."""
        self._add_control(
            SOC2Control(
                id=id,
                category=category,
                title=title,
                description=description,
                check_function=check_function,
                evidence_required=evidence_required or [],
            )
        )

    async def check_access_controls(self, context: dict[str, Any]) -> SOC2Finding:
        """Check logical and physical access controls (CC6.1)."""
        control = self.controls["CC6.1"]
        passed = True
        evidence = {}
        remediation = None

        # Check for RBAC implementation
        rbac_enabled = context.get("rbac_enabled", False)
        evidence["rbac_enabled"] = rbac_enabled
        if not rbac_enabled:
            passed = False
            remediation = "Enable Role-Based Access Control (RBAC) for all systems."

        # Check MFA enforcement
        mfa_enforced = context.get("mfa_enforced", False)
        evidence["mfa_enforced"] = mfa_enforced
        if not mfa_enforced:
            passed = False
            remediation = (remediation or "") + " Enable MFA for all user accounts."

        # Check password policy
        password_policy = context.get("password_policy", {})
        evidence["password_policy"] = password_policy
        min_length = password_policy.get("min_length", 0)
        if min_length < 12:
            passed = False
            remediation = (
                (remediation or "") + " Set minimum password length to 12 characters."
            )

        return SOC2Finding(
            control_id=control.id,
            category=control.category,
            passed=passed,
            title=control.title,
            description=control.description,
            evidence=evidence,
            remediation=remediation,
        )

    async def check_encryption(self, context: dict[str, Any]) -> SOC2Finding:
        """Check encryption controls (CC6.7)."""
        control = self.controls["CC6.7"]
        passed = True
        evidence = {}
        remediation = None

        # Check TLS configuration
        tls_version = context.get("tls_version", "1.0")
        evidence["tls_version"] = tls_version
        if tls_version < "1.2":
            passed = False
            remediation = "Upgrade to TLS 1.2 or higher."

        # Check encryption at rest
        encryption_at_rest = context.get("encryption_at_rest", False)
        evidence["encryption_at_rest"] = encryption_at_rest
        if not encryption_at_rest:
            passed = False
            remediation = (
                (remediation or "") + " Enable encryption at rest for all data stores."
            )

        # Check key management
        key_rotation = context.get("key_rotation_days", 365)
        evidence["key_rotation_days"] = key_rotation
        if key_rotation > 90:
            passed = False
            remediation = (remediation or "") + " Rotate encryption keys every 90 days."

        return SOC2Finding(
            control_id=control.id,
            category=control.category,
            passed=passed,
            title=control.title,
            description=control.description,
            evidence=evidence,
            remediation=remediation,
        )

    async def check_monitoring(self, context: dict[str, Any]) -> SOC2Finding:
        """Check security monitoring (CC7.2)."""
        control = self.controls["CC7.2"]
        passed = True
        evidence = {}
        remediation = None

        # Check logging enabled
        logging_enabled = context.get("centralized_logging", False)
        evidence["centralized_logging"] = logging_enabled
        if not logging_enabled:
            passed = False
            remediation = "Enable centralized logging for all systems."

        # Check alert configuration
        alerts_configured = context.get("security_alerts_configured", False)
        evidence["security_alerts_configured"] = alerts_configured
        if not alerts_configured:
            passed = False
            remediation = (
                (remediation or "") + " Configure security alerts for anomaly detection."
            )

        # Check log retention
        log_retention_days = context.get("log_retention_days", 0)
        evidence["log_retention_days"] = log_retention_days
        if log_retention_days < 90:
            passed = False
            remediation = (remediation or "") + " Set log retention to minimum 90 days."

        return SOC2Finding(
            control_id=control.id,
            category=control.category,
            passed=passed,
            title=control.title,
            description=control.description,
            evidence=evidence,
            remediation=remediation,
        )

    async def check_availability(self, context: dict[str, Any]) -> SOC2Finding:
        """Check availability controls (A1.2)."""
        control = self.controls["A1.2"]
        passed = True
        evidence = {}
        remediation = None

        # Check backup configuration
        backup_enabled = context.get("automated_backups", False)
        evidence["automated_backups"] = backup_enabled
        if not backup_enabled:
            passed = False
            remediation = "Enable automated backups for all critical systems."

        # Check DR plan
        dr_plan_tested = context.get("dr_plan_tested_recently", False)
        evidence["dr_plan_tested_recently"] = dr_plan_tested
        if not dr_plan_tested:
            passed = False
            remediation = (
                (remediation or "") + " Test disaster recovery plan at least annually."
            )

        # Check RTO/RPO
        rto_hours = context.get("rto_hours", 24)
        rpo_hours = context.get("rpo_hours", 24)
        evidence["rto_hours"] = rto_hours
        evidence["rpo_hours"] = rpo_hours

        return SOC2Finding(
            control_id=control.id,
            category=control.category,
            passed=passed,
            title=control.title,
            description=control.description,
            evidence=evidence,
            remediation=remediation,
        )

    async def run_all_checks(self, context: dict[str, Any]) -> list[SOC2Finding]:
        """Run all SOC2 compliance checks."""
        logger.info("Running SOC2 compliance checks")
        findings = []

        # Run automated checks
        findings.append(await self.check_access_controls(context))
        findings.append(await self.check_encryption(context))
        findings.append(await self.check_monitoring(context))
        findings.append(await self.check_availability(context))

        # Run custom check functions
        for control in self.controls.values():
            if control.check_function and control.id not in [
                f.control_id for f in findings
            ]:
                try:
                    result = control.check_function(context)
                    findings.append(
                        SOC2Finding(
                            control_id=control.id,
                            category=control.category,
                            passed=result,
                            title=control.title,
                            description=control.description,
                            evidence={"custom_check": True},
                        )
                    )
                except Exception as e:
                    logger.error(f"Error running check {control.id}: {e}")
                    findings.append(
                        SOC2Finding(
                            control_id=control.id,
                            category=control.category,
                            passed=False,
                            title=control.title,
                            description=control.description,
                            evidence={"error": str(e)},
                            remediation="Fix check function error.",
                        )
                    )

        return findings

    async def generate_report(
        self,
        context: dict[str, Any],
        period_start: datetime,
        period_end: datetime,
    ) -> SOC2Report:
        """Generate a complete SOC2 compliance report."""
        import uuid

        findings = await self.run_all_checks(context)

        # Calculate scores
        total_passed = sum(1 for f in findings if f.passed)
        overall_score = total_passed / len(findings) if findings else 0.0

        # Calculate per-category scores
        category_scores = {}
        for category in SOC2Category:
            cat_findings = [f for f in findings if f.category == category]
            if cat_findings:
                cat_passed = sum(1 for f in cat_findings if f.passed)
                category_scores[category] = cat_passed / len(cat_findings)
            else:
                category_scores[category] = 1.0

        return SOC2Report(
            report_id=str(uuid.uuid4()),
            generated_at=datetime.utcnow(),
            period_start=period_start,
            period_end=period_end,
            findings=findings,
            overall_score=overall_score,
            category_scores=category_scores,
        )
