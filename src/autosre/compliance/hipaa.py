"""
HIPAA Compliance Checker

Implements Health Insurance Portability and Accountability Act checks for:
- Administrative Safeguards (§164.308)
- Physical Safeguards (§164.310)
- Technical Safeguards (§164.312)
- Organizational Requirements (§164.314)
- Policies & Procedures (§164.316)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable

from autosre.logging import get_logger

logger = get_logger(__name__)


class SafeguardType(Enum):
    """HIPAA Safeguard Types."""

    ADMINISTRATIVE = "administrative"  # §164.308
    PHYSICAL = "physical"  # §164.310
    TECHNICAL = "technical"  # §164.312
    ORGANIZATIONAL = "organizational"  # §164.314
    POLICIES = "policies"  # §164.316


@dataclass
class HIPAASafeguard:
    """Represents a HIPAA safeguard requirement."""

    id: str  # e.g., "164.308(a)(1)"
    safeguard_type: SafeguardType
    title: str
    description: str
    required: bool = True  # Required vs Addressable
    check_function: Callable[..., bool] | None = None
    evidence_required: list[str] = field(default_factory=list)


@dataclass
class HIPAAFinding:
    """A finding from HIPAA compliance check."""

    safeguard_id: str
    safeguard_type: SafeguardType
    passed: bool
    title: str
    description: str
    required: bool
    evidence: dict[str, Any] = field(default_factory=dict)
    remediation: str | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class HIPAAReport:
    """Complete HIPAA compliance report."""

    report_id: str
    generated_at: datetime
    covered_entity: str
    findings: list[HIPAAFinding]
    overall_score: float
    safeguard_scores: dict[SafeguardType, float]
    phi_scope: list[str]
    risk_assessment_date: datetime | None = None

    @property
    def compliant(self) -> bool:
        """Check if HIPAA compliant (all required safeguards passed)."""
        required_findings = [f for f in self.findings if f.required]
        return all(f.passed for f in required_findings)

    def get_violations(self) -> list[HIPAAFinding]:
        """Get all failed safeguards."""
        return [f for f in self.findings if not f.passed]

    def get_required_violations(self) -> list[HIPAAFinding]:
        """Get only required safeguard failures (critical)."""
        return [f for f in self.findings if not f.passed and f.required]


class HIPAAChecker:
    """
    HIPAA Compliance Checker.

    Performs automated checks against HIPAA Security Rule requirements
    for protecting electronic Protected Health Information (ePHI).
    """

    def __init__(self, covered_entity: str):
        self.covered_entity = covered_entity
        self.safeguards: dict[str, HIPAASafeguard] = {}
        self._register_default_safeguards()

    def _register_default_safeguards(self) -> None:
        """Register default HIPAA safeguards."""
        # Administrative Safeguards (§164.308)
        self._add_safeguard(
            HIPAASafeguard(
                id="164.308(a)(1)(i)",
                safeguard_type=SafeguardType.ADMINISTRATIVE,
                title="Security Management Process - Risk Analysis",
                description="Conduct an accurate and thorough assessment of the "
                "potential risks and vulnerabilities to ePHI.",
                required=True,
                evidence_required=[
                    "risk_assessment_report",
                    "vulnerability_scans",
                    "threat_inventory",
                ],
            )
        )
        self._add_safeguard(
            HIPAASafeguard(
                id="164.308(a)(1)(ii)(A)",
                safeguard_type=SafeguardType.ADMINISTRATIVE,
                title="Risk Management",
                description="Implement security measures sufficient to reduce risks "
                "and vulnerabilities to a reasonable and appropriate level.",
                required=True,
                evidence_required=[
                    "risk_mitigation_plan",
                    "security_controls",
                    "implementation_evidence",
                ],
            )
        )
        self._add_safeguard(
            HIPAASafeguard(
                id="164.308(a)(3)(i)",
                safeguard_type=SafeguardType.ADMINISTRATIVE,
                title="Workforce Security",
                description="Implement policies and procedures to ensure that all "
                "workforce members have appropriate access to ePHI.",
                required=True,
                evidence_required=[
                    "access_policies",
                    "role_definitions",
                    "access_logs",
                ],
            )
        )
        self._add_safeguard(
            HIPAASafeguard(
                id="164.308(a)(4)(i)",
                safeguard_type=SafeguardType.ADMINISTRATIVE,
                title="Information Access Management",
                description="Implement policies and procedures for authorizing "
                "access to ePHI.",
                required=True,
                evidence_required=[
                    "authorization_procedures",
                    "access_grants",
                    "review_logs",
                ],
            )
        )
        self._add_safeguard(
            HIPAASafeguard(
                id="164.308(a)(5)(i)",
                safeguard_type=SafeguardType.ADMINISTRATIVE,
                title="Security Awareness and Training",
                description="Implement a security awareness and training program "
                "for all workforce members.",
                required=False,  # Addressable
                evidence_required=[
                    "training_materials",
                    "completion_records",
                    "training_schedule",
                ],
            )
        )
        self._add_safeguard(
            HIPAASafeguard(
                id="164.308(a)(6)(i)",
                safeguard_type=SafeguardType.ADMINISTRATIVE,
                title="Security Incident Procedures",
                description="Implement policies and procedures to address security "
                "incidents.",
                required=True,
                evidence_required=[
                    "incident_response_plan",
                    "incident_logs",
                    "response_procedures",
                ],
            )
        )
        self._add_safeguard(
            HIPAASafeguard(
                id="164.308(a)(7)(i)",
                safeguard_type=SafeguardType.ADMINISTRATIVE,
                title="Contingency Plan",
                description="Establish and implement policies and procedures for "
                "responding to emergency or disaster.",
                required=True,
                evidence_required=[
                    "contingency_plan",
                    "data_backup_plan",
                    "disaster_recovery_plan",
                ],
            )
        )

        # Physical Safeguards (§164.310)
        self._add_safeguard(
            HIPAASafeguard(
                id="164.310(a)(1)",
                safeguard_type=SafeguardType.PHYSICAL,
                title="Facility Access Controls",
                description="Implement policies and procedures to limit physical "
                "access to electronic information systems.",
                required=True,
                evidence_required=[
                    "facility_security_plan",
                    "access_control_logs",
                    "visitor_logs",
                ],
            )
        )
        self._add_safeguard(
            HIPAASafeguard(
                id="164.310(b)",
                safeguard_type=SafeguardType.PHYSICAL,
                title="Workstation Use",
                description="Implement policies and procedures that specify proper "
                "functions to be performed at workstations.",
                required=True,
                evidence_required=[
                    "workstation_policy",
                    "acceptable_use_policy",
                    "workstation_inventory",
                ],
            )
        )
        self._add_safeguard(
            HIPAASafeguard(
                id="164.310(d)(1)",
                safeguard_type=SafeguardType.PHYSICAL,
                title="Device and Media Controls",
                description="Implement policies and procedures for receipt, removal, "
                "and disposal of hardware and electronic media.",
                required=True,
                evidence_required=[
                    "media_disposal_policy",
                    "device_inventory",
                    "destruction_logs",
                ],
            )
        )

        # Technical Safeguards (§164.312)
        self._add_safeguard(
            HIPAASafeguard(
                id="164.312(a)(1)",
                safeguard_type=SafeguardType.TECHNICAL,
                title="Access Control",
                description="Implement technical policies and procedures to allow "
                "access only to authorized persons or programs.",
                required=True,
                evidence_required=[
                    "access_control_config",
                    "authentication_logs",
                    "unique_user_ids",
                ],
            )
        )
        self._add_safeguard(
            HIPAASafeguard(
                id="164.312(b)",
                safeguard_type=SafeguardType.TECHNICAL,
                title="Audit Controls",
                description="Implement hardware, software, and procedural mechanisms "
                "to record and examine access and activity.",
                required=True,
                evidence_required=[
                    "audit_log_config",
                    "audit_reports",
                    "log_review_procedures",
                ],
            )
        )
        self._add_safeguard(
            HIPAASafeguard(
                id="164.312(c)(1)",
                safeguard_type=SafeguardType.TECHNICAL,
                title="Integrity",
                description="Implement policies and procedures to protect ePHI from "
                "improper alteration or destruction.",
                required=True,
                evidence_required=[
                    "integrity_controls",
                    "checksums",
                    "change_detection",
                ],
            )
        )
        self._add_safeguard(
            HIPAASafeguard(
                id="164.312(d)",
                safeguard_type=SafeguardType.TECHNICAL,
                title="Person or Entity Authentication",
                description="Implement procedures to verify that a person or entity "
                "seeking access is the one claimed.",
                required=True,
                evidence_required=[
                    "authentication_mechanisms",
                    "mfa_configuration",
                    "identity_verification",
                ],
            )
        )
        self._add_safeguard(
            HIPAASafeguard(
                id="164.312(e)(1)",
                safeguard_type=SafeguardType.TECHNICAL,
                title="Transmission Security",
                description="Implement technical security measures to guard against "
                "unauthorized access to ePHI transmitted over network.",
                required=True,
                evidence_required=[
                    "encryption_config",
                    "tls_certificates",
                    "vpn_configuration",
                ],
            )
        )

    def _add_safeguard(self, safeguard: HIPAASafeguard) -> None:
        """Add a safeguard to the checker."""
        self.safeguards[safeguard.id] = safeguard

    def register_safeguard(
        self,
        id: str,
        safeguard_type: SafeguardType,
        title: str,
        description: str,
        required: bool = True,
        check_function: Callable[..., bool] | None = None,
    ) -> None:
        """Register a custom HIPAA safeguard."""
        self._add_safeguard(
            HIPAASafeguard(
                id=id,
                safeguard_type=safeguard_type,
                title=title,
                description=description,
                required=required,
                check_function=check_function,
            )
        )

    async def check_access_controls(self, context: dict[str, Any]) -> HIPAAFinding:
        """Check technical access controls (§164.312(a)(1))."""
        safeguard = self.safeguards["164.312(a)(1)"]
        passed = True
        evidence = {}
        remediation = None

        # Check unique user identification
        unique_ids = context.get("unique_user_ids_enforced", False)
        evidence["unique_user_ids_enforced"] = unique_ids
        if not unique_ids:
            passed = False
            remediation = "Enforce unique user identification for all ePHI access."

        # Check automatic logoff
        auto_logoff = context.get("automatic_logoff_enabled", False)
        evidence["automatic_logoff_enabled"] = auto_logoff
        if not auto_logoff:
            passed = False
            remediation = (
                (remediation or "")
                + " Enable automatic logoff after period of inactivity."
            )

        # Check emergency access
        emergency_access = context.get("emergency_access_procedure", False)
        evidence["emergency_access_procedure"] = emergency_access
        if not emergency_access:
            passed = False
            remediation = (
                (remediation or "") + " Document emergency access procedures."
            )

        return HIPAAFinding(
            safeguard_id=safeguard.id,
            safeguard_type=safeguard.safeguard_type,
            passed=passed,
            title=safeguard.title,
            description=safeguard.description,
            required=safeguard.required,
            evidence=evidence,
            remediation=remediation,
        )

    async def check_audit_controls(self, context: dict[str, Any]) -> HIPAAFinding:
        """Check audit controls (§164.312(b))."""
        safeguard = self.safeguards["164.312(b)"]
        passed = True
        evidence = {}
        remediation = None

        # Check audit logging enabled
        audit_logging = context.get("audit_logging_enabled", False)
        evidence["audit_logging_enabled"] = audit_logging
        if not audit_logging:
            passed = False
            remediation = "Enable comprehensive audit logging for all ePHI access."

        # Check log retention
        log_retention = context.get("audit_log_retention_days", 0)
        evidence["audit_log_retention_days"] = log_retention
        if log_retention < 365 * 6:  # HIPAA requires 6 years
            passed = False
            remediation = (
                (remediation or "") + " Retain audit logs for minimum 6 years."
            )

        # Check log review
        log_review = context.get("regular_log_review", False)
        evidence["regular_log_review"] = log_review
        if not log_review:
            passed = False
            remediation = (
                (remediation or "") + " Implement regular audit log review procedures."
            )

        return HIPAAFinding(
            safeguard_id=safeguard.id,
            safeguard_type=safeguard.safeguard_type,
            passed=passed,
            title=safeguard.title,
            description=safeguard.description,
            required=safeguard.required,
            evidence=evidence,
            remediation=remediation,
        )

    async def check_encryption(self, context: dict[str, Any]) -> HIPAAFinding:
        """Check transmission security (§164.312(e)(1))."""
        safeguard = self.safeguards["164.312(e)(1)"]
        passed = True
        evidence = {}
        remediation = None

        # Check encryption in transit
        encryption_transit = context.get("encryption_in_transit", False)
        evidence["encryption_in_transit"] = encryption_transit
        if not encryption_transit:
            passed = False
            remediation = "Enable encryption for all ePHI in transit."

        # Check encryption at rest
        encryption_rest = context.get("encryption_at_rest", False)
        evidence["encryption_at_rest"] = encryption_rest
        if not encryption_rest:
            passed = False
            remediation = (remediation or "") + " Enable encryption for ePHI at rest."

        # Check TLS version
        tls_version = context.get("tls_version", "1.0")
        evidence["tls_version"] = tls_version
        if tls_version < "1.2":
            passed = False
            remediation = (remediation or "") + " Use TLS 1.2 or higher."

        return HIPAAFinding(
            safeguard_id=safeguard.id,
            safeguard_type=safeguard.safeguard_type,
            passed=passed,
            title=safeguard.title,
            description=safeguard.description,
            required=safeguard.required,
            evidence=evidence,
            remediation=remediation,
        )

    async def check_authentication(self, context: dict[str, Any]) -> HIPAAFinding:
        """Check authentication requirements (§164.312(d))."""
        safeguard = self.safeguards["164.312(d)"]
        passed = True
        evidence = {}
        remediation = None

        # Check MFA
        mfa_enabled = context.get("mfa_enabled", False)
        evidence["mfa_enabled"] = mfa_enabled
        if not mfa_enabled:
            passed = False
            remediation = "Enable multi-factor authentication for ePHI access."

        # Check password requirements
        password_policy = context.get("password_policy", {})
        evidence["password_policy"] = password_policy
        if password_policy.get("min_length", 0) < 14:
            passed = False
            remediation = (
                (remediation or "") + " Require minimum 14 character passwords."
            )
        if not password_policy.get("complexity_required", False):
            passed = False
            remediation = (remediation or "") + " Enforce password complexity."

        return HIPAAFinding(
            safeguard_id=safeguard.id,
            safeguard_type=safeguard.safeguard_type,
            passed=passed,
            title=safeguard.title,
            description=safeguard.description,
            required=safeguard.required,
            evidence=evidence,
            remediation=remediation,
        )

    async def check_contingency_plan(self, context: dict[str, Any]) -> HIPAAFinding:
        """Check contingency plan (§164.308(a)(7))."""
        safeguard = self.safeguards["164.308(a)(7)(i)"]
        passed = True
        evidence = {}
        remediation = None

        # Check backup plan
        backup_plan = context.get("data_backup_plan", False)
        evidence["data_backup_plan"] = backup_plan
        if not backup_plan:
            passed = False
            remediation = "Document and implement data backup plan."

        # Check DR plan
        dr_plan = context.get("disaster_recovery_plan", False)
        evidence["disaster_recovery_plan"] = dr_plan
        if not dr_plan:
            passed = False
            remediation = (
                (remediation or "") + " Document and implement disaster recovery plan."
            )

        # Check emergency mode
        emergency_mode = context.get("emergency_mode_operation", False)
        evidence["emergency_mode_operation"] = emergency_mode
        if not emergency_mode:
            passed = False
            remediation = (
                (remediation or "") + " Define emergency mode operation procedures."
            )

        # Check testing
        testing_performed = context.get("contingency_testing_performed", False)
        evidence["contingency_testing_performed"] = testing_performed
        if not testing_performed:
            passed = False
            remediation = (
                (remediation or "") + " Test contingency plan at least annually."
            )

        return HIPAAFinding(
            safeguard_id=safeguard.id,
            safeguard_type=safeguard.safeguard_type,
            passed=passed,
            title=safeguard.title,
            description=safeguard.description,
            required=safeguard.required,
            evidence=evidence,
            remediation=remediation,
        )

    async def run_all_checks(self, context: dict[str, Any]) -> list[HIPAAFinding]:
        """Run all HIPAA compliance checks."""
        logger.info(f"Running HIPAA compliance checks for {self.covered_entity}")
        findings = []

        # Run automated checks
        findings.append(await self.check_access_controls(context))
        findings.append(await self.check_audit_controls(context))
        findings.append(await self.check_encryption(context))
        findings.append(await self.check_authentication(context))
        findings.append(await self.check_contingency_plan(context))

        return findings

    async def generate_report(
        self,
        context: dict[str, Any],
        phi_scope: list[str] | None = None,
    ) -> HIPAAReport:
        """Generate a complete HIPAA compliance report."""
        import uuid

        findings = await self.run_all_checks(context)

        # Calculate scores
        total_passed = sum(1 for f in findings if f.passed)
        overall_score = total_passed / len(findings) if findings else 0.0

        # Calculate per-safeguard scores
        safeguard_scores = {}
        for safeguard_type in SafeguardType:
            type_findings = [
                f for f in findings if f.safeguard_type == safeguard_type
            ]
            if type_findings:
                type_passed = sum(1 for f in type_findings if f.passed)
                safeguard_scores[safeguard_type] = type_passed / len(type_findings)
            else:
                safeguard_scores[safeguard_type] = 1.0

        return HIPAAReport(
            report_id=str(uuid.uuid4()),
            generated_at=datetime.utcnow(),
            covered_entity=self.covered_entity,
            findings=findings,
            overall_score=overall_score,
            safeguard_scores=safeguard_scores,
            phi_scope=phi_scope or [],
            risk_assessment_date=context.get("last_risk_assessment"),
        )
