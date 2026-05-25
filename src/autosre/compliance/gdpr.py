"""
GDPR Compliance Checker

Implements General Data Protection Regulation checks for:
- Lawfulness, fairness and transparency
- Purpose limitation
- Data minimization
- Accuracy
- Storage limitation
- Integrity and confidentiality
- Accountability
- Data Subject Rights
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable

from autosre.logging import get_logger

logger = get_logger(__name__)


class GDPRPrinciple(Enum):
    """GDPR Data Protection Principles (Article 5)."""

    LAWFULNESS = "lawfulness"  # Article 5(1)(a)
    PURPOSE_LIMITATION = "purpose_limitation"  # Article 5(1)(b)
    DATA_MINIMIZATION = "data_minimization"  # Article 5(1)(c)
    ACCURACY = "accuracy"  # Article 5(1)(d)
    STORAGE_LIMITATION = "storage_limitation"  # Article 5(1)(e)
    INTEGRITY_CONFIDENTIALITY = "integrity_confidentiality"  # Article 5(1)(f)
    ACCOUNTABILITY = "accountability"  # Article 5(2)


class DataSubjectRight(Enum):
    """GDPR Data Subject Rights (Articles 12-22)."""

    INFORMATION = "right_to_information"  # Article 13-14
    ACCESS = "right_of_access"  # Article 15
    RECTIFICATION = "right_to_rectification"  # Article 16
    ERASURE = "right_to_erasure"  # Article 17 (Right to be forgotten)
    RESTRICT_PROCESSING = "right_to_restrict"  # Article 18
    DATA_PORTABILITY = "right_to_portability"  # Article 20
    OBJECT = "right_to_object"  # Article 21
    AUTOMATED_DECISIONS = "automated_decisions"  # Article 22


@dataclass
class GDPRRequirement:
    """Represents a GDPR requirement."""

    id: str  # e.g., "ART5.1.A"
    article: str
    principle: GDPRPrinciple | None = None
    data_subject_right: DataSubjectRight | None = None
    title: str = ""
    description: str = ""
    check_function: Callable[..., bool] | None = None
    evidence_required: list[str] = field(default_factory=list)


@dataclass
class GDPRFinding:
    """A finding from GDPR compliance check."""

    requirement_id: str
    article: str
    principle: GDPRPrinciple | None
    data_subject_right: DataSubjectRight | None
    passed: bool
    title: str
    description: str
    evidence: dict[str, Any] = field(default_factory=dict)
    remediation: str | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class GDPRReport:
    """Complete GDPR compliance report."""

    report_id: str
    generated_at: datetime
    data_controller: str
    data_processor: str | None
    findings: list[GDPRFinding]
    overall_score: float
    principle_scores: dict[GDPRPrinciple, float]
    rights_scores: dict[DataSubjectRight, float]
    processing_activities: list[str]
    dpo_contact: str | None = None
    supervisory_authority: str | None = None

    @property
    def compliant(self) -> bool:
        """Check if GDPR compliant (>= 90% score)."""
        return self.overall_score >= 0.90

    def get_violations(self) -> list[GDPRFinding]:
        """Get all failed requirements."""
        return [f for f in self.findings if not f.passed]


class GDPRChecker:
    """
    GDPR Compliance Checker.

    Performs automated checks against GDPR requirements
    for protecting personal data of EU residents.
    """

    def __init__(self, data_controller: str, data_processor: str | None = None):
        self.data_controller = data_controller
        self.data_processor = data_processor
        self.requirements: dict[str, GDPRRequirement] = {}
        self._register_default_requirements()

    def _register_default_requirements(self) -> None:
        """Register default GDPR requirements."""
        # Article 5 - Principles
        self._add_requirement(
            GDPRRequirement(
                id="ART5.1.A",
                article="Article 5(1)(a)",
                principle=GDPRPrinciple.LAWFULNESS,
                title="Lawfulness, Fairness, and Transparency",
                description="Process personal data lawfully, fairly, and transparently.",
                evidence_required=[
                    "lawful_basis_records",
                    "privacy_notices",
                    "consent_records",
                ],
            )
        )
        self._add_requirement(
            GDPRRequirement(
                id="ART5.1.B",
                article="Article 5(1)(b)",
                principle=GDPRPrinciple.PURPOSE_LIMITATION,
                title="Purpose Limitation",
                description="Collect data for specified, explicit, legitimate purposes.",
                evidence_required=[
                    "purpose_documentation",
                    "processing_records",
                    "purpose_change_logs",
                ],
            )
        )
        self._add_requirement(
            GDPRRequirement(
                id="ART5.1.C",
                article="Article 5(1)(c)",
                principle=GDPRPrinciple.DATA_MINIMIZATION,
                title="Data Minimization",
                description="Process only data adequate, relevant, and necessary.",
                evidence_required=[
                    "data_inventory",
                    "minimization_review",
                    "field_justification",
                ],
            )
        )
        self._add_requirement(
            GDPRRequirement(
                id="ART5.1.D",
                article="Article 5(1)(d)",
                principle=GDPRPrinciple.ACCURACY,
                title="Accuracy",
                description="Keep personal data accurate and up to date.",
                evidence_required=[
                    "data_quality_procedures",
                    "correction_logs",
                    "validation_rules",
                ],
            )
        )
        self._add_requirement(
            GDPRRequirement(
                id="ART5.1.E",
                article="Article 5(1)(e)",
                principle=GDPRPrinciple.STORAGE_LIMITATION,
                title="Storage Limitation",
                description="Keep data only as long as necessary.",
                evidence_required=[
                    "retention_policy",
                    "deletion_procedures",
                    "retention_schedule",
                ],
            )
        )
        self._add_requirement(
            GDPRRequirement(
                id="ART5.1.F",
                article="Article 5(1)(f)",
                principle=GDPRPrinciple.INTEGRITY_CONFIDENTIALITY,
                title="Integrity and Confidentiality",
                description="Ensure appropriate security of personal data.",
                evidence_required=[
                    "security_measures",
                    "encryption_config",
                    "access_controls",
                ],
            )
        )
        self._add_requirement(
            GDPRRequirement(
                id="ART5.2",
                article="Article 5(2)",
                principle=GDPRPrinciple.ACCOUNTABILITY,
                title="Accountability",
                description="Demonstrate compliance with all principles.",
                evidence_required=[
                    "compliance_documentation",
                    "audit_trails",
                    "policy_documents",
                ],
            )
        )

        # Data Subject Rights (Articles 12-22)
        self._add_requirement(
            GDPRRequirement(
                id="ART15",
                article="Article 15",
                data_subject_right=DataSubjectRight.ACCESS,
                title="Right of Access",
                description="Data subjects can access their personal data.",
                evidence_required=[
                    "access_request_procedure",
                    "data_export_capability",
                    "request_logs",
                ],
            )
        )
        self._add_requirement(
            GDPRRequirement(
                id="ART16",
                article="Article 16",
                data_subject_right=DataSubjectRight.RECTIFICATION,
                title="Right to Rectification",
                description="Data subjects can correct inaccurate data.",
                evidence_required=[
                    "rectification_procedure",
                    "data_update_capability",
                    "correction_logs",
                ],
            )
        )
        self._add_requirement(
            GDPRRequirement(
                id="ART17",
                article="Article 17",
                data_subject_right=DataSubjectRight.ERASURE,
                title="Right to Erasure",
                description="Data subjects can request deletion of their data.",
                evidence_required=[
                    "deletion_procedure",
                    "erasure_capability",
                    "deletion_logs",
                ],
            )
        )
        self._add_requirement(
            GDPRRequirement(
                id="ART20",
                article="Article 20",
                data_subject_right=DataSubjectRight.DATA_PORTABILITY,
                title="Right to Data Portability",
                description="Data subjects can receive data in portable format.",
                evidence_required=[
                    "export_formats",
                    "api_documentation",
                    "portability_procedure",
                ],
            )
        )

        # Additional requirements
        self._add_requirement(
            GDPRRequirement(
                id="ART25",
                article="Article 25",
                principle=GDPRPrinciple.ACCOUNTABILITY,
                title="Data Protection by Design and Default",
                description="Implement privacy by design and by default.",
                evidence_required=[
                    "privacy_impact_assessment",
                    "default_privacy_settings",
                    "design_documentation",
                ],
            )
        )
        self._add_requirement(
            GDPRRequirement(
                id="ART30",
                article="Article 30",
                principle=GDPRPrinciple.ACCOUNTABILITY,
                title="Records of Processing Activities",
                description="Maintain records of all processing activities.",
                evidence_required=[
                    "processing_records",
                    "data_flows",
                    "third_party_processors",
                ],
            )
        )
        self._add_requirement(
            GDPRRequirement(
                id="ART32",
                article="Article 32",
                principle=GDPRPrinciple.INTEGRITY_CONFIDENTIALITY,
                title="Security of Processing",
                description="Implement appropriate technical and organizational measures.",
                evidence_required=[
                    "security_controls",
                    "risk_assessment",
                    "incident_response_plan",
                ],
            )
        )
        self._add_requirement(
            GDPRRequirement(
                id="ART33",
                article="Article 33",
                principle=GDPRPrinciple.ACCOUNTABILITY,
                title="Breach Notification to Authority",
                description="Notify supervisory authority of breaches within 72 hours.",
                evidence_required=[
                    "breach_notification_procedure",
                    "incident_response_plan",
                    "notification_templates",
                ],
            )
        )
        self._add_requirement(
            GDPRRequirement(
                id="ART35",
                article="Article 35",
                principle=GDPRPrinciple.ACCOUNTABILITY,
                title="Data Protection Impact Assessment",
                description="Conduct DPIA for high-risk processing.",
                evidence_required=[
                    "dpia_procedure",
                    "dpia_reports",
                    "risk_criteria",
                ],
            )
        )

    def _add_requirement(self, requirement: GDPRRequirement) -> None:
        """Add a requirement to the checker."""
        self.requirements[requirement.id] = requirement

    async def check_lawful_basis(self, context: dict[str, Any]) -> GDPRFinding:
        """Check lawful basis for processing (Article 5(1)(a))."""
        req = self.requirements["ART5.1.A"]
        passed = True
        evidence = {}
        remediation = None

        # Check documented lawful basis
        lawful_basis = context.get("lawful_basis_documented", False)
        evidence["lawful_basis_documented"] = lawful_basis
        if not lawful_basis:
            passed = False
            remediation = "Document lawful basis for all processing activities."

        # Check privacy notices
        privacy_notices = context.get("privacy_notices_published", False)
        evidence["privacy_notices_published"] = privacy_notices
        if not privacy_notices:
            passed = False
            remediation = (remediation or "") + " Publish clear privacy notices."

        # Check consent mechanism
        consent_mechanism = context.get("consent_mechanism", False)
        evidence["consent_mechanism"] = consent_mechanism
        if context.get("requires_consent", False) and not consent_mechanism:
            passed = False
            remediation = (
                (remediation or "") + " Implement valid consent collection mechanism."
            )

        return GDPRFinding(
            requirement_id=req.id,
            article=req.article,
            principle=req.principle,
            data_subject_right=req.data_subject_right,
            passed=passed,
            title=req.title,
            description=req.description,
            evidence=evidence,
            remediation=remediation,
        )

    async def check_data_minimization(self, context: dict[str, Any]) -> GDPRFinding:
        """Check data minimization (Article 5(1)(c))."""
        req = self.requirements["ART5.1.C"]
        passed = True
        evidence = {}
        remediation = None

        # Check data inventory
        data_inventory = context.get("data_inventory_exists", False)
        evidence["data_inventory_exists"] = data_inventory
        if not data_inventory:
            passed = False
            remediation = "Create comprehensive data inventory."

        # Check necessity review
        necessity_review = context.get("data_necessity_reviewed", False)
        evidence["data_necessity_reviewed"] = necessity_review
        if not necessity_review:
            passed = False
            remediation = (
                (remediation or "") + " Review necessity of all data fields collected."
            )

        # Check sensitive data
        sensitive_data = context.get("sensitive_data_justified", False)
        evidence["sensitive_data_justified"] = sensitive_data
        if context.get("collects_sensitive_data", False) and not sensitive_data:
            passed = False
            remediation = (
                (remediation or "")
                + " Document justification for sensitive data collection."
            )

        return GDPRFinding(
            requirement_id=req.id,
            article=req.article,
            principle=req.principle,
            data_subject_right=req.data_subject_right,
            passed=passed,
            title=req.title,
            description=req.description,
            evidence=evidence,
            remediation=remediation,
        )

    async def check_retention(self, context: dict[str, Any]) -> GDPRFinding:
        """Check storage limitation (Article 5(1)(e))."""
        req = self.requirements["ART5.1.E"]
        passed = True
        evidence = {}
        remediation = None

        # Check retention policy
        retention_policy = context.get("retention_policy_exists", False)
        evidence["retention_policy_exists"] = retention_policy
        if not retention_policy:
            passed = False
            remediation = "Define data retention policy."

        # Check automated deletion
        auto_deletion = context.get("automated_deletion_enabled", False)
        evidence["automated_deletion_enabled"] = auto_deletion
        if not auto_deletion:
            passed = False
            remediation = (
                (remediation or "")
                + " Implement automated data deletion based on retention schedule."
            )

        # Check deletion logs
        deletion_logs = context.get("deletion_logs_maintained", False)
        evidence["deletion_logs_maintained"] = deletion_logs
        if not deletion_logs:
            passed = False
            remediation = (remediation or "") + " Maintain logs of data deletion."

        return GDPRFinding(
            requirement_id=req.id,
            article=req.article,
            principle=req.principle,
            data_subject_right=req.data_subject_right,
            passed=passed,
            title=req.title,
            description=req.description,
            evidence=evidence,
            remediation=remediation,
        )

    async def check_security(self, context: dict[str, Any]) -> GDPRFinding:
        """Check security of processing (Article 32)."""
        req = self.requirements["ART32"]
        passed = True
        evidence = {}
        remediation = None

        # Check encryption
        encryption = context.get("encryption_enabled", False)
        evidence["encryption_enabled"] = encryption
        if not encryption:
            passed = False
            remediation = "Enable encryption for personal data."

        # Check pseudonymization
        pseudonymization = context.get("pseudonymization_available", False)
        evidence["pseudonymization_available"] = pseudonymization

        # Check access controls
        access_controls = context.get("access_controls_implemented", False)
        evidence["access_controls_implemented"] = access_controls
        if not access_controls:
            passed = False
            remediation = (remediation or "") + " Implement access controls."

        # Check regular testing
        security_testing = context.get("regular_security_testing", False)
        evidence["regular_security_testing"] = security_testing
        if not security_testing:
            passed = False
            remediation = (remediation or "") + " Conduct regular security testing."

        return GDPRFinding(
            requirement_id=req.id,
            article=req.article,
            principle=req.principle,
            data_subject_right=req.data_subject_right,
            passed=passed,
            title=req.title,
            description=req.description,
            evidence=evidence,
            remediation=remediation,
        )

    async def check_right_of_access(self, context: dict[str, Any]) -> GDPRFinding:
        """Check right of access (Article 15)."""
        req = self.requirements["ART15"]
        passed = True
        evidence = {}
        remediation = None

        # Check access request procedure
        access_procedure = context.get("access_request_procedure", False)
        evidence["access_request_procedure"] = access_procedure
        if not access_procedure:
            passed = False
            remediation = "Document data subject access request procedure."

        # Check export capability
        export_capability = context.get("data_export_capability", False)
        evidence["data_export_capability"] = export_capability
        if not export_capability:
            passed = False
            remediation = (remediation or "") + " Implement data export capability."

        # Check response time
        response_time = context.get("access_request_response_days", 60)
        evidence["access_request_response_days"] = response_time
        if response_time > 30:
            passed = False
            remediation = (
                (remediation or "") + " Ensure access requests handled within 30 days."
            )

        return GDPRFinding(
            requirement_id=req.id,
            article=req.article,
            principle=req.principle,
            data_subject_right=req.data_subject_right,
            passed=passed,
            title=req.title,
            description=req.description,
            evidence=evidence,
            remediation=remediation,
        )

    async def check_right_to_erasure(self, context: dict[str, Any]) -> GDPRFinding:
        """Check right to erasure (Article 17)."""
        req = self.requirements["ART17"]
        passed = True
        evidence = {}
        remediation = None

        # Check deletion capability
        deletion_capability = context.get("deletion_capability", False)
        evidence["deletion_capability"] = deletion_capability
        if not deletion_capability:
            passed = False
            remediation = "Implement data deletion capability."

        # Check cascading deletion
        cascading_deletion = context.get("cascading_deletion", False)
        evidence["cascading_deletion"] = cascading_deletion
        if not cascading_deletion:
            passed = False
            remediation = (
                (remediation or "")
                + " Ensure deletion cascades to all data stores and processors."
            )

        # Check deletion verification
        deletion_verification = context.get("deletion_verification", False)
        evidence["deletion_verification"] = deletion_verification
        if not deletion_verification:
            passed = False
            remediation = (remediation or "") + " Implement deletion verification."

        return GDPRFinding(
            requirement_id=req.id,
            article=req.article,
            principle=req.principle,
            data_subject_right=req.data_subject_right,
            passed=passed,
            title=req.title,
            description=req.description,
            evidence=evidence,
            remediation=remediation,
        )

    async def check_breach_notification(self, context: dict[str, Any]) -> GDPRFinding:
        """Check breach notification (Article 33)."""
        req = self.requirements["ART33"]
        passed = True
        evidence = {}
        remediation = None

        # Check breach detection
        breach_detection = context.get("breach_detection_capability", False)
        evidence["breach_detection_capability"] = breach_detection
        if not breach_detection:
            passed = False
            remediation = "Implement breach detection mechanisms."

        # Check notification procedure
        notification_procedure = context.get("breach_notification_procedure", False)
        evidence["breach_notification_procedure"] = notification_procedure
        if not notification_procedure:
            passed = False
            remediation = (
                (remediation or "")
                + " Document 72-hour breach notification procedure."
            )

        # Check incident response
        incident_response = context.get("incident_response_plan", False)
        evidence["incident_response_plan"] = incident_response
        if not incident_response:
            passed = False
            remediation = (
                (remediation or "") + " Create incident response plan for breaches."
            )

        return GDPRFinding(
            requirement_id=req.id,
            article=req.article,
            principle=req.principle,
            data_subject_right=req.data_subject_right,
            passed=passed,
            title=req.title,
            description=req.description,
            evidence=evidence,
            remediation=remediation,
        )

    async def run_all_checks(self, context: dict[str, Any]) -> list[GDPRFinding]:
        """Run all GDPR compliance checks."""
        logger.info(f"Running GDPR compliance checks for {self.data_controller}")
        findings = []

        findings.append(await self.check_lawful_basis(context))
        findings.append(await self.check_data_minimization(context))
        findings.append(await self.check_retention(context))
        findings.append(await self.check_security(context))
        findings.append(await self.check_right_of_access(context))
        findings.append(await self.check_right_to_erasure(context))
        findings.append(await self.check_breach_notification(context))

        return findings

    async def generate_report(
        self,
        context: dict[str, Any],
        processing_activities: list[str] | None = None,
    ) -> GDPRReport:
        """Generate a complete GDPR compliance report."""
        import uuid

        findings = await self.run_all_checks(context)

        # Calculate overall score
        total_passed = sum(1 for f in findings if f.passed)
        overall_score = total_passed / len(findings) if findings else 0.0

        # Calculate principle scores
        principle_scores = {}
        for principle in GDPRPrinciple:
            p_findings = [f for f in findings if f.principle == principle]
            if p_findings:
                p_passed = sum(1 for f in p_findings if f.passed)
                principle_scores[principle] = p_passed / len(p_findings)
            else:
                principle_scores[principle] = 1.0

        # Calculate rights scores
        rights_scores = {}
        for right in DataSubjectRight:
            r_findings = [f for f in findings if f.data_subject_right == right]
            if r_findings:
                r_passed = sum(1 for f in r_findings if f.passed)
                rights_scores[right] = r_passed / len(r_findings)
            else:
                rights_scores[right] = 1.0

        return GDPRReport(
            report_id=str(uuid.uuid4()),
            generated_at=datetime.utcnow(),
            data_controller=self.data_controller,
            data_processor=self.data_processor,
            findings=findings,
            overall_score=overall_score,
            principle_scores=principle_scores,
            rights_scores=rights_scores,
            processing_activities=processing_activities or [],
            dpo_contact=context.get("dpo_contact"),
            supervisory_authority=context.get("supervisory_authority"),
        )
