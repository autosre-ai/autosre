"""
PCI-DSS Compliance Checker

Implements Payment Card Industry Data Security Standard checks:
- Build and Maintain a Secure Network and Systems (Req 1-2)
- Protect Cardholder Data (Req 3-4)
- Maintain a Vulnerability Management Program (Req 5-6)
- Implement Strong Access Control Measures (Req 7-9)
- Regularly Monitor and Test Networks (Req 10-11)
- Maintain an Information Security Policy (Req 12)
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

from autosre.logging import get_logger

logger = get_logger(__name__)


class PCILevel(Enum):
    """PCI-DSS Compliance Levels based on transaction volume."""

    LEVEL_1 = "level_1"  # > 6M transactions/year
    LEVEL_2 = "level_2"  # 1M - 6M transactions/year
    LEVEL_3 = "level_3"  # 20K - 1M e-commerce transactions/year
    LEVEL_4 = "level_4"  # < 20K e-commerce or < 1M other transactions/year


class PCICategory(Enum):
    """PCI-DSS Requirement Categories."""

    NETWORK_SECURITY = "network_security"  # Req 1-2
    CARDHOLDER_DATA = "cardholder_data"  # Req 3-4
    VULNERABILITY_MGMT = "vulnerability_management"  # Req 5-6
    ACCESS_CONTROL = "access_control"  # Req 7-9
    MONITORING = "monitoring"  # Req 10-11
    SECURITY_POLICY = "security_policy"  # Req 12


@dataclass
class PCIRequirement:
    """Represents a PCI-DSS requirement."""

    id: str  # e.g., "1.1", "3.4"
    category: PCICategory
    title: str
    description: str
    sub_requirements: list[str] = field(default_factory=list)
    check_function: Callable[..., bool] | None = None
    evidence_required: list[str] = field(default_factory=list)


@dataclass
class PCIFinding:
    """A finding from PCI-DSS compliance check."""

    requirement_id: str
    category: PCICategory
    passed: bool
    title: str
    description: str
    evidence: dict[str, Any] = field(default_factory=dict)
    remediation: str | None = None
    compensating_controls: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class PCIReport:
    """Complete PCI-DSS compliance report."""

    report_id: str
    generated_at: datetime
    merchant_id: str
    pci_level: PCILevel
    findings: list[PCIFinding]
    overall_score: float
    category_scores: dict[PCICategory, float]
    saq_type: str | None = None
    last_pen_test: datetime | None = None
    last_vulnerability_scan: datetime | None = None
    qsa_name: str | None = None

    @property
    def compliant(self) -> bool:
        """Check if PCI-DSS compliant (all requirements passed)."""
        return all(f.passed for f in self.findings)

    def get_violations(self) -> list[PCIFinding]:
        """Get all failed requirements."""
        return [f for f in self.findings if not f.passed]

    def get_critical_violations(self) -> list[PCIFinding]:
        """Get violations in critical categories."""
        critical_categories = {
            PCICategory.CARDHOLDER_DATA,
            PCICategory.ACCESS_CONTROL,
        }
        return [
            f
            for f in self.findings
            if not f.passed and f.category in critical_categories
        ]


class PCIChecker:
    """
    PCI-DSS Compliance Checker.

    Performs automated checks against PCI-DSS requirements
    for protecting cardholder data.
    """

    def __init__(self, merchant_id: str, pci_level: PCILevel = PCILevel.LEVEL_4):
        self.merchant_id = merchant_id
        self.pci_level = pci_level
        self.requirements: dict[str, PCIRequirement] = {}
        self._register_default_requirements()

    def _register_default_requirements(self) -> None:
        """Register default PCI-DSS requirements."""
        # Requirement 1: Install and maintain network security controls
        self._add_requirement(
            PCIRequirement(
                id="1.1",
                category=PCICategory.NETWORK_SECURITY,
                title="Network Security Controls Configuration",
                description="Processes and mechanisms for network security controls "
                "are defined and understood.",
                sub_requirements=[
                    "1.1.1",
                    "1.1.2",
                    "1.1.3",
                    "1.1.4",
                    "1.1.5",
                    "1.1.6",
                    "1.1.7",
                    "1.1.8",
                ],
                evidence_required=["firewall_rules", "network_diagram", "change_logs"],
            )
        )
        self._add_requirement(
            PCIRequirement(
                id="1.2",
                category=PCICategory.NETWORK_SECURITY,
                title="Network Security Controls Implementation",
                description="Network security controls are configured and maintained.",
                evidence_required=[
                    "firewall_config",
                    "ingress_rules",
                    "egress_rules",
                ],
            )
        )
        self._add_requirement(
            PCIRequirement(
                id="1.3",
                category=PCICategory.NETWORK_SECURITY,
                title="Network Access Restrictions",
                description="Network access to and from the CDE is restricted.",
                evidence_required=["cde_network_diagram", "access_restrictions"],
            )
        )

        # Requirement 2: Apply Secure Configurations
        self._add_requirement(
            PCIRequirement(
                id="2.1",
                category=PCICategory.NETWORK_SECURITY,
                title="Secure Configuration Standards",
                description="Processes and mechanisms for secure configurations "
                "are defined and understood.",
                evidence_required=[
                    "config_standards",
                    "baseline_configs",
                    "hardening_guides",
                ],
            )
        )
        self._add_requirement(
            PCIRequirement(
                id="2.2",
                category=PCICategory.NETWORK_SECURITY,
                title="System Component Security",
                description="System components are configured and managed securely.",
                evidence_required=[
                    "system_inventory",
                    "config_audit",
                    "default_credential_check",
                ],
            )
        )

        # Requirement 3: Protect Stored Account Data
        self._add_requirement(
            PCIRequirement(
                id="3.1",
                category=PCICategory.CARDHOLDER_DATA,
                title="Account Data Storage Policies",
                description="Processes and mechanisms for protecting stored "
                "account data are defined and understood.",
                evidence_required=[
                    "data_retention_policy",
                    "storage_locations",
                    "data_inventory",
                ],
            )
        )
        self._add_requirement(
            PCIRequirement(
                id="3.4",
                category=PCICategory.CARDHOLDER_DATA,
                title="PAN Protection",
                description="PAN is rendered unreadable anywhere it is stored.",
                evidence_required=[
                    "encryption_config",
                    "tokenization_config",
                    "masking_rules",
                ],
            )
        )
        self._add_requirement(
            PCIRequirement(
                id="3.5",
                category=PCICategory.CARDHOLDER_DATA,
                title="Cryptographic Key Management",
                description="Cryptographic keys used to protect stored account "
                "data are secured.",
                evidence_required=[
                    "key_management_procedures",
                    "key_inventory",
                    "key_rotation_logs",
                ],
            )
        )

        # Requirement 4: Protect Cardholder Data in Transit
        self._add_requirement(
            PCIRequirement(
                id="4.1",
                category=PCICategory.CARDHOLDER_DATA,
                title="Transmission Encryption",
                description="Processes and mechanisms for protecting cardholder "
                "data during transmission are defined and understood.",
                evidence_required=[
                    "tls_config",
                    "certificate_inventory",
                    "transmission_policy",
                ],
            )
        )
        self._add_requirement(
            PCIRequirement(
                id="4.2",
                category=PCICategory.CARDHOLDER_DATA,
                title="Strong Cryptography for Transmission",
                description="PAN is protected with strong cryptography "
                "during transmission.",
                evidence_required=["tls_version", "cipher_suites", "hsts_config"],
            )
        )

        # Requirement 5: Protect Systems with Anti-Malware
        self._add_requirement(
            PCIRequirement(
                id="5.1",
                category=PCICategory.VULNERABILITY_MGMT,
                title="Anti-Malware Deployment",
                description="Processes and mechanisms for protecting systems "
                "against malware are defined and understood.",
                evidence_required=[
                    "antimalware_policy",
                    "deployment_coverage",
                    "update_logs",
                ],
            )
        )
        self._add_requirement(
            PCIRequirement(
                id="5.2",
                category=PCICategory.VULNERABILITY_MGMT,
                title="Anti-Malware Maintenance",
                description="Malware is prevented or detected and addressed.",
                evidence_required=[
                    "scan_reports",
                    "detection_logs",
                    "remediation_records",
                ],
            )
        )

        # Requirement 6: Develop Secure Systems
        self._add_requirement(
            PCIRequirement(
                id="6.1",
                category=PCICategory.VULNERABILITY_MGMT,
                title="Secure Development Processes",
                description="Processes and mechanisms for developing and "
                "maintaining secure systems are defined and understood.",
                evidence_required=[
                    "sdlc_documentation",
                    "security_requirements",
                    "coding_standards",
                ],
            )
        )
        self._add_requirement(
            PCIRequirement(
                id="6.2",
                category=PCICategory.VULNERABILITY_MGMT,
                title="Vulnerability Management",
                description="Bespoke and custom software is developed securely.",
                evidence_required=[
                    "vulnerability_scans",
                    "patch_management",
                    "remediation_timeline",
                ],
            )
        )

        # Requirement 7: Restrict Access to System Components
        self._add_requirement(
            PCIRequirement(
                id="7.1",
                category=PCICategory.ACCESS_CONTROL,
                title="Access Control Policies",
                description="Processes and mechanisms for restricting access "
                "to system components are defined and understood.",
                evidence_required=["access_policy", "role_definitions", "access_matrix"],
            )
        )
        self._add_requirement(
            PCIRequirement(
                id="7.2",
                category=PCICategory.ACCESS_CONTROL,
                title="Role-Based Access Control",
                description="Access to system components and data is appropriately "
                "defined and assigned.",
                evidence_required=["rbac_config", "user_roles", "access_reviews"],
            )
        )

        # Requirement 8: Identify Users and Authenticate Access
        self._add_requirement(
            PCIRequirement(
                id="8.1",
                category=PCICategory.ACCESS_CONTROL,
                title="User Identification",
                description="Processes and mechanisms for identifying users "
                "and authenticating access are defined and understood.",
                evidence_required=[
                    "authentication_policy",
                    "unique_ids",
                    "account_management",
                ],
            )
        )
        self._add_requirement(
            PCIRequirement(
                id="8.3",
                category=PCICategory.ACCESS_CONTROL,
                title="Strong Authentication",
                description="Strong authentication is established for users "
                "and administrators.",
                evidence_required=[
                    "mfa_config",
                    "password_policy",
                    "authentication_logs",
                ],
            )
        )

        # Requirement 10: Log and Monitor All Access
        self._add_requirement(
            PCIRequirement(
                id="10.1",
                category=PCICategory.MONITORING,
                title="Audit Logging Processes",
                description="Processes and mechanisms for logging and monitoring "
                "all access are defined and understood.",
                evidence_required=["logging_policy", "audit_config", "log_retention"],
            )
        )
        self._add_requirement(
            PCIRequirement(
                id="10.2",
                category=PCICategory.MONITORING,
                title="Audit Log Implementation",
                description="Audit logs are implemented to support detection "
                "of anomalies and suspicious activity.",
                evidence_required=["log_events", "timestamps", "user_attribution"],
            )
        )

        # Requirement 11: Test Security Regularly
        self._add_requirement(
            PCIRequirement(
                id="11.3",
                category=PCICategory.MONITORING,
                title="Penetration Testing",
                description="External and internal penetration testing is "
                "regularly performed.",
                evidence_required=["pentest_reports", "remediation_evidence", "schedule"],
            )
        )
        self._add_requirement(
            PCIRequirement(
                id="11.4",
                category=PCICategory.MONITORING,
                title="Intrusion Detection",
                description="Network intrusion detection and/or prevention "
                "techniques are employed.",
                evidence_required=["ids_config", "ips_config", "alert_logs"],
            )
        )

        # Requirement 12: Support Information Security with Policies
        self._add_requirement(
            PCIRequirement(
                id="12.1",
                category=PCICategory.SECURITY_POLICY,
                title="Information Security Policy",
                description="A comprehensive information security policy "
                "is established and disseminated.",
                evidence_required=[
                    "security_policy",
                    "distribution_records",
                    "acknowledgments",
                ],
            )
        )

    def _add_requirement(self, requirement: PCIRequirement) -> None:
        """Add a requirement to the checker."""
        self.requirements[requirement.id] = requirement

    async def check_network_security(self, context: dict[str, Any]) -> PCIFinding:
        """Check network security controls (Requirement 1)."""
        req = self.requirements["1.1"]
        passed = True
        evidence = {}
        remediation = None

        # Check firewall
        firewall_enabled = context.get("firewall_enabled", False)
        evidence["firewall_enabled"] = firewall_enabled
        if not firewall_enabled:
            passed = False
            remediation = "Enable and configure firewall for CDE."

        # Check network segmentation
        network_segmented = context.get("cde_segmented", False)
        evidence["cde_segmented"] = network_segmented
        if not network_segmented:
            passed = False
            remediation = (
                (remediation or "") + " Implement CDE network segmentation."
            )

        # Check ingress/egress rules
        ingress_rules = context.get("ingress_rules_documented", False)
        evidence["ingress_rules_documented"] = ingress_rules
        if not ingress_rules:
            passed = False
            remediation = (remediation or "") + " Document all ingress rules."

        return PCIFinding(
            requirement_id=req.id,
            category=req.category,
            passed=passed,
            title=req.title,
            description=req.description,
            evidence=evidence,
            remediation=remediation,
        )

    async def check_pan_protection(self, context: dict[str, Any]) -> PCIFinding:
        """Check PAN protection (Requirement 3.4)."""
        req = self.requirements["3.4"]
        passed = True
        evidence = {}
        remediation = None

        # Check PAN storage
        pan_encrypted = context.get("pan_encrypted_at_rest", False)
        evidence["pan_encrypted_at_rest"] = pan_encrypted
        if not pan_encrypted:
            passed = False
            remediation = "Encrypt or tokenize PAN at rest."

        # Check tokenization
        tokenization = context.get("tokenization_enabled", False)
        evidence["tokenization_enabled"] = tokenization

        # Check masking
        pan_masked = context.get("pan_masked_in_display", False)
        evidence["pan_masked_in_display"] = pan_masked
        if not pan_masked:
            passed = False
            remediation = (remediation or "") + " Mask PAN when displayed."

        # Check key management
        key_rotation = context.get("encryption_key_rotation_days", 365)
        evidence["encryption_key_rotation_days"] = key_rotation
        if key_rotation > 365:
            passed = False
            remediation = (remediation or "") + " Rotate encryption keys annually."

        return PCIFinding(
            requirement_id=req.id,
            category=req.category,
            passed=passed,
            title=req.title,
            description=req.description,
            evidence=evidence,
            remediation=remediation,
        )

    async def check_transmission_encryption(
        self, context: dict[str, Any]
    ) -> PCIFinding:
        """Check transmission encryption (Requirement 4.2)."""
        req = self.requirements["4.2"]
        passed = True
        evidence = {}
        remediation = None

        # Check TLS
        tls_version = context.get("tls_version", "1.0")
        evidence["tls_version"] = tls_version
        if tls_version < "1.2":
            passed = False
            remediation = "Upgrade to TLS 1.2 or higher."

        # Check certificate validity
        cert_valid = context.get("certificates_valid", False)
        evidence["certificates_valid"] = cert_valid
        if not cert_valid:
            passed = False
            remediation = (remediation or "") + " Ensure all certificates are valid."

        # Check HSTS
        hsts_enabled = context.get("hsts_enabled", False)
        evidence["hsts_enabled"] = hsts_enabled
        if not hsts_enabled:
            passed = False
            remediation = (remediation or "") + " Enable HSTS headers."

        return PCIFinding(
            requirement_id=req.id,
            category=req.category,
            passed=passed,
            title=req.title,
            description=req.description,
            evidence=evidence,
            remediation=remediation,
        )

    async def check_access_control(self, context: dict[str, Any]) -> PCIFinding:
        """Check access control (Requirement 7.2)."""
        req = self.requirements["7.2"]
        passed = True
        evidence = {}
        remediation = None

        # Check RBAC
        rbac_enabled = context.get("rbac_enabled", False)
        evidence["rbac_enabled"] = rbac_enabled
        if not rbac_enabled:
            passed = False
            remediation = "Implement role-based access control."

        # Check least privilege
        least_privilege = context.get("least_privilege_enforced", False)
        evidence["least_privilege_enforced"] = least_privilege
        if not least_privilege:
            passed = False
            remediation = (remediation or "") + " Enforce least privilege principle."

        # Check access reviews
        access_reviews = context.get("quarterly_access_reviews", False)
        evidence["quarterly_access_reviews"] = access_reviews
        if not access_reviews:
            passed = False
            remediation = (remediation or "") + " Conduct quarterly access reviews."

        return PCIFinding(
            requirement_id=req.id,
            category=req.category,
            passed=passed,
            title=req.title,
            description=req.description,
            evidence=evidence,
            remediation=remediation,
        )

    async def check_authentication(self, context: dict[str, Any]) -> PCIFinding:
        """Check strong authentication (Requirement 8.3)."""
        req = self.requirements["8.3"]
        passed = True
        evidence = {}
        remediation = None

        # Check MFA
        mfa_enabled = context.get("mfa_enabled", False)
        evidence["mfa_enabled"] = mfa_enabled
        if not mfa_enabled:
            passed = False
            remediation = "Enable multi-factor authentication for CDE access."

        # Check password policy
        password_policy = context.get("password_policy", {})
        evidence["password_policy"] = password_policy
        if password_policy.get("min_length", 0) < 12:
            passed = False
            remediation = (
                (remediation or "") + " Require minimum 12 character passwords."
            )
        if password_policy.get("max_age_days", 999) > 90:
            passed = False
            remediation = (remediation or "") + " Require password change every 90 days."

        # Check lockout
        lockout_enabled = context.get("account_lockout_enabled", False)
        evidence["account_lockout_enabled"] = lockout_enabled
        if not lockout_enabled:
            passed = False
            remediation = (
                (remediation or "") + " Enable account lockout after failed attempts."
            )

        return PCIFinding(
            requirement_id=req.id,
            category=req.category,
            passed=passed,
            title=req.title,
            description=req.description,
            evidence=evidence,
            remediation=remediation,
        )

    async def check_audit_logging(self, context: dict[str, Any]) -> PCIFinding:
        """Check audit logging (Requirement 10.2)."""
        req = self.requirements["10.2"]
        passed = True
        evidence = {}
        remediation = None

        # Check logging enabled
        logging_enabled = context.get("audit_logging_enabled", False)
        evidence["audit_logging_enabled"] = logging_enabled
        if not logging_enabled:
            passed = False
            remediation = "Enable comprehensive audit logging."

        # Check log events
        required_events = [
            "user_access",
            "invalid_access",
            "elevation_of_privilege",
            "audit_log_access",
            "security_events",
        ]
        logged_events = context.get("logged_events", [])
        evidence["logged_events"] = logged_events
        missing_events = [e for e in required_events if e not in logged_events]
        if missing_events:
            passed = False
            remediation = (
                (remediation or "") + f" Log required events: {missing_events}."
            )

        # Check log retention
        log_retention = context.get("log_retention_days", 0)
        evidence["log_retention_days"] = log_retention
        if log_retention < 365:
            passed = False
            remediation = (remediation or "") + " Retain audit logs for minimum 1 year."

        return PCIFinding(
            requirement_id=req.id,
            category=req.category,
            passed=passed,
            title=req.title,
            description=req.description,
            evidence=evidence,
            remediation=remediation,
        )

    async def check_penetration_testing(self, context: dict[str, Any]) -> PCIFinding:
        """Check penetration testing (Requirement 11.3)."""
        req = self.requirements["11.3"]
        passed = True
        evidence = {}
        remediation = None

        # Check external pen test
        external_pentest = context.get("external_pentest_performed", False)
        evidence["external_pentest_performed"] = external_pentest
        if not external_pentest:
            passed = False
            remediation = "Perform annual external penetration test."

        # Check internal pen test
        internal_pentest = context.get("internal_pentest_performed", False)
        evidence["internal_pentest_performed"] = internal_pentest
        if not internal_pentest:
            passed = False
            remediation = (remediation or "") + " Perform annual internal penetration test."

        # Check remediation
        pentest_issues_remediated = context.get("pentest_issues_remediated", False)
        evidence["pentest_issues_remediated"] = pentest_issues_remediated
        if not pentest_issues_remediated:
            passed = False
            remediation = (
                (remediation or "") + " Remediate all penetration test findings."
            )

        return PCIFinding(
            requirement_id=req.id,
            category=req.category,
            passed=passed,
            title=req.title,
            description=req.description,
            evidence=evidence,
            remediation=remediation,
        )

    async def run_all_checks(self, context: dict[str, Any]) -> list[PCIFinding]:
        """Run all PCI-DSS compliance checks."""
        logger.info(f"Running PCI-DSS compliance checks for merchant {self.merchant_id}")
        findings = []

        findings.append(await self.check_network_security(context))
        findings.append(await self.check_pan_protection(context))
        findings.append(await self.check_transmission_encryption(context))
        findings.append(await self.check_access_control(context))
        findings.append(await self.check_authentication(context))
        findings.append(await self.check_audit_logging(context))
        findings.append(await self.check_penetration_testing(context))

        return findings

    async def generate_report(
        self,
        context: dict[str, Any],
        saq_type: str | None = None,
    ) -> PCIReport:
        """Generate a complete PCI-DSS compliance report."""
        import uuid

        findings = await self.run_all_checks(context)

        # Calculate overall score
        total_passed = sum(1 for f in findings if f.passed)
        overall_score = total_passed / len(findings) if findings else 0.0

        # Calculate category scores
        category_scores = {}
        for category in PCICategory:
            cat_findings = [f for f in findings if f.category == category]
            if cat_findings:
                cat_passed = sum(1 for f in cat_findings if f.passed)
                category_scores[category] = cat_passed / len(cat_findings)
            else:
                category_scores[category] = 1.0

        return PCIReport(
            report_id=str(uuid.uuid4()),
            generated_at=datetime.now(timezone.utc),
            merchant_id=self.merchant_id,
            pci_level=self.pci_level,
            findings=findings,
            overall_score=overall_score,
            category_scores=category_scores,
            saq_type=saq_type,
            last_pen_test=context.get("last_pen_test"),
            last_vulnerability_scan=context.get("last_vulnerability_scan"),
            qsa_name=context.get("qsa_name"),
        )
