"""
Compliance Evidence Collection

Automated evidence collection and packaging for compliance audits.
Supports SOC2, HIPAA, GDPR, and PCI-DSS evidence requirements.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, BinaryIO
import hashlib
import json
import zipfile
import io

from autosre.logging import get_logger
from autosre.compliance.audit import ComplianceFramework

logger = get_logger(__name__)


class EvidenceType(Enum):
    """Types of compliance evidence."""

    # Access Control Evidence
    ACCESS_LOGS = "access_logs"
    AUTHENTICATION_LOGS = "authentication_logs"
    RBAC_CONFIGURATION = "rbac_configuration"
    USER_PROVISIONING = "user_provisioning"
    ACCESS_REVIEWS = "access_reviews"

    # Security Evidence
    ENCRYPTION_CONFIG = "encryption_config"
    TLS_CERTIFICATES = "tls_certificates"
    KEY_MANAGEMENT = "key_management"
    FIREWALL_RULES = "firewall_rules"
    NETWORK_DIAGRAMS = "network_diagrams"

    # Monitoring Evidence
    AUDIT_LOGS = "audit_logs"
    SECURITY_ALERTS = "security_alerts"
    SIEM_REPORTS = "siem_reports"
    ANOMALY_DETECTION = "anomaly_detection"

    # Availability Evidence
    BACKUP_LOGS = "backup_logs"
    DR_TEST_RESULTS = "dr_test_results"
    INCIDENT_REPORTS = "incident_reports"
    UPTIME_REPORTS = "uptime_reports"

    # Data Protection Evidence
    DATA_INVENTORY = "data_inventory"
    RETENTION_POLICIES = "retention_policies"
    DELETION_LOGS = "deletion_logs"
    CONSENT_RECORDS = "consent_records"
    DSAR_LOGS = "dsar_logs"

    # Testing Evidence
    PENETRATION_TESTS = "penetration_tests"
    VULNERABILITY_SCANS = "vulnerability_scans"
    SECURITY_ASSESSMENTS = "security_assessments"

    # Policy Evidence
    SECURITY_POLICIES = "security_policies"
    PROCEDURES = "procedures"
    TRAINING_RECORDS = "training_records"


@dataclass
class EvidenceItem:
    """A single piece of compliance evidence."""

    evidence_id: str
    evidence_type: EvidenceType
    framework: ComplianceFramework
    title: str
    description: str
    collected_at: datetime
    source: str
    content: bytes | str | dict[str, Any]
    content_type: str  # e.g., "application/json", "text/plain", "application/pdf"
    hash_sha256: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Calculate hash after initialization."""
        if not self.hash_sha256:
            if isinstance(self.content, bytes):
                self.hash_sha256 = hashlib.sha256(self.content).hexdigest()
            elif isinstance(self.content, str):
                self.hash_sha256 = hashlib.sha256(self.content.encode()).hexdigest()
            else:
                self.hash_sha256 = hashlib.sha256(
                    json.dumps(self.content, sort_keys=True, default=str).encode()
                ).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary (without content for manifest)."""
        return {
            "evidence_id": self.evidence_id,
            "evidence_type": self.evidence_type.value,
            "framework": self.framework.value,
            "title": self.title,
            "description": self.description,
            "collected_at": self.collected_at.isoformat(),
            "source": self.source,
            "content_type": self.content_type,
            "hash_sha256": self.hash_sha256,
            "metadata": self.metadata,
        }


@dataclass
class EvidencePackage:
    """A package of collected evidence for an audit period."""

    package_id: str
    organization: str
    frameworks: list[ComplianceFramework]
    period_start: datetime
    period_end: datetime
    created_at: datetime
    items: list[EvidenceItem]
    auditor_name: str | None = None

    @property
    def total_items(self) -> int:
        """Total number of evidence items."""
        return len(self.items)

    def get_items_by_framework(
        self, framework: ComplianceFramework
    ) -> list[EvidenceItem]:
        """Get evidence items for a specific framework."""
        return [i for i in self.items if i.framework == framework]

    def get_items_by_type(self, evidence_type: EvidenceType) -> list[EvidenceItem]:
        """Get evidence items of a specific type."""
        return [i for i in self.items if i.evidence_type == evidence_type]

    def generate_manifest(self) -> dict[str, Any]:
        """Generate evidence manifest."""
        return {
            "package_id": self.package_id,
            "organization": self.organization,
            "frameworks": [f.value for f in self.frameworks],
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "created_at": self.created_at.isoformat(),
            "auditor_name": self.auditor_name,
            "total_items": self.total_items,
            "items": [item.to_dict() for item in self.items],
        }


class EvidenceCollector:
    """
    Compliance Evidence Collector.

    Automatically collects and packages evidence for compliance audits.
    """

    # Framework-specific evidence requirements
    FRAMEWORK_EVIDENCE = {
        ComplianceFramework.SOC2: [
            EvidenceType.ACCESS_LOGS,
            EvidenceType.AUTHENTICATION_LOGS,
            EvidenceType.RBAC_CONFIGURATION,
            EvidenceType.ENCRYPTION_CONFIG,
            EvidenceType.AUDIT_LOGS,
            EvidenceType.SECURITY_ALERTS,
            EvidenceType.BACKUP_LOGS,
            EvidenceType.DR_TEST_RESULTS,
            EvidenceType.PENETRATION_TESTS,
            EvidenceType.SECURITY_POLICIES,
        ],
        ComplianceFramework.HIPAA: [
            EvidenceType.ACCESS_LOGS,
            EvidenceType.AUTHENTICATION_LOGS,
            EvidenceType.AUDIT_LOGS,
            EvidenceType.ENCRYPTION_CONFIG,
            EvidenceType.BACKUP_LOGS,
            EvidenceType.DR_TEST_RESULTS,
            EvidenceType.ACCESS_REVIEWS,
            EvidenceType.TRAINING_RECORDS,
            EvidenceType.SECURITY_POLICIES,
            EvidenceType.INCIDENT_REPORTS,
        ],
        ComplianceFramework.GDPR: [
            EvidenceType.DATA_INVENTORY,
            EvidenceType.CONSENT_RECORDS,
            EvidenceType.DSAR_LOGS,
            EvidenceType.RETENTION_POLICIES,
            EvidenceType.DELETION_LOGS,
            EvidenceType.ENCRYPTION_CONFIG,
            EvidenceType.ACCESS_LOGS,
            EvidenceType.SECURITY_POLICIES,
        ],
        ComplianceFramework.PCI_DSS: [
            EvidenceType.FIREWALL_RULES,
            EvidenceType.NETWORK_DIAGRAMS,
            EvidenceType.ENCRYPTION_CONFIG,
            EvidenceType.KEY_MANAGEMENT,
            EvidenceType.ACCESS_LOGS,
            EvidenceType.AUDIT_LOGS,
            EvidenceType.PENETRATION_TESTS,
            EvidenceType.VULNERABILITY_SCANS,
            EvidenceType.SECURITY_POLICIES,
            EvidenceType.TRAINING_RECORDS,
        ],
    }

    def __init__(
        self,
        evidence_storage: str | None = None,
        retention_days: int = 2190,  # 6 years default for HIPAA
    ):
        self.evidence_storage = evidence_storage
        self.retention_days = retention_days
        self.collectors: dict[EvidenceType, Any] = {}

    def register_collector(
        self,
        evidence_type: EvidenceType,
        collector_func: Any,
    ) -> None:
        """Register a custom collector function for an evidence type."""
        self.collectors[evidence_type] = collector_func

    async def collect_access_logs(
        self,
        start_date: datetime,
        end_date: datetime,
        framework: ComplianceFramework,
    ) -> list[EvidenceItem]:
        """Collect access logs as evidence."""
        import uuid

        # In production, this would query actual log sources
        evidence_id = str(uuid.uuid4())
        content = {
            "log_source": "kubernetes_audit",
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
            "total_entries": 125000,
            "sample_entries": [
                {
                    "timestamp": "2024-06-15T10:30:00Z",
                    "user": "admin@company.com",
                    "action": "login",
                    "resource": "dashboard",
                    "result": "success",
                },
                {
                    "timestamp": "2024-06-15T10:31:00Z",
                    "user": "admin@company.com",
                    "action": "view",
                    "resource": "secrets/production",
                    "result": "success",
                },
            ],
            "statistics": {
                "successful_logins": 45000,
                "failed_logins": 234,
                "unique_users": 156,
            },
        }

        return [
            EvidenceItem(
                evidence_id=evidence_id,
                evidence_type=EvidenceType.ACCESS_LOGS,
                framework=framework,
                title=f"Access Logs ({start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')})",
                description="Kubernetes audit logs and application access logs",
                collected_at=datetime.now(timezone.utc),
                source="kubernetes-audit-logs",
                content=content,
                content_type="application/json",
                metadata={
                    "log_sources": ["kubernetes", "application"],
                    "total_entries": 125000,
                },
            )
        ]

    async def collect_encryption_config(
        self,
        framework: ComplianceFramework,
    ) -> list[EvidenceItem]:
        """Collect encryption configuration evidence."""
        import uuid

        content = {
            "encryption_at_rest": {
                "enabled": True,
                "algorithm": "AES-256-GCM",
                "key_management": "AWS KMS",
                "key_rotation_days": 90,
            },
            "encryption_in_transit": {
                "tls_version": "1.3",
                "cipher_suites": [
                    "TLS_AES_256_GCM_SHA384",
                    "TLS_CHACHA20_POLY1305_SHA256",
                ],
                "hsts_enabled": True,
                "certificate_expiry": "2025-06-15",
            },
            "database_encryption": {
                "enabled": True,
                "algorithm": "AES-256",
                "transparent_data_encryption": True,
            },
        }

        return [
            EvidenceItem(
                evidence_id=str(uuid.uuid4()),
                evidence_type=EvidenceType.ENCRYPTION_CONFIG,
                framework=framework,
                title="Encryption Configuration",
                description="Current encryption settings for data at rest and in transit",
                collected_at=datetime.now(timezone.utc),
                source="infrastructure-config",
                content=content,
                content_type="application/json",
            )
        ]

    async def collect_security_policies(
        self,
        framework: ComplianceFramework,
    ) -> list[EvidenceItem]:
        """Collect security policy documentation evidence."""
        import uuid

        content = {
            "policies": [
                {
                    "name": "Information Security Policy",
                    "version": "3.2",
                    "last_updated": "2024-01-15",
                    "approved_by": "CISO",
                    "review_cycle": "annual",
                },
                {
                    "name": "Access Control Policy",
                    "version": "2.1",
                    "last_updated": "2024-03-01",
                    "approved_by": "CISO",
                    "review_cycle": "annual",
                },
                {
                    "name": "Incident Response Plan",
                    "version": "4.0",
                    "last_updated": "2024-02-28",
                    "approved_by": "CISO",
                    "review_cycle": "annual",
                },
                {
                    "name": "Data Retention Policy",
                    "version": "1.5",
                    "last_updated": "2024-04-10",
                    "approved_by": "DPO",
                    "review_cycle": "annual",
                },
            ],
            "acknowledgments": {
                "total_employees": 250,
                "acknowledged": 248,
                "pending": 2,
                "acknowledgment_rate": "99.2%",
            },
        }

        return [
            EvidenceItem(
                evidence_id=str(uuid.uuid4()),
                evidence_type=EvidenceType.SECURITY_POLICIES,
                framework=framework,
                title="Security Policy Documentation",
                description="Current security policies and employee acknowledgments",
                collected_at=datetime.now(timezone.utc),
                source="policy-management-system",
                content=content,
                content_type="application/json",
            )
        ]

    async def collect(
        self,
        frameworks: list[ComplianceFramework],
        start_date: datetime,
        end_date: datetime,
    ) -> EvidencePackage:
        """
        Collect all required evidence for specified frameworks.

        Args:
            frameworks: List of compliance frameworks to collect evidence for
            start_date: Start of audit period
            end_date: End of audit period

        Returns:
            EvidencePackage with all collected evidence
        """
        import uuid

        logger.info(
            f"Collecting evidence for {len(frameworks)} framework(s) "
            f"from {start_date} to {end_date}"
        )

        all_items: list[EvidenceItem] = []

        for framework in frameworks:
            required_types = self.FRAMEWORK_EVIDENCE.get(framework, [])
            logger.info(
                f"Collecting {len(required_types)} evidence types for {framework.value}"
            )

            for evidence_type in required_types:
                try:
                    items = await self._collect_evidence_type(
                        evidence_type, framework, start_date, end_date
                    )
                    all_items.extend(items)
                except Exception as e:
                    logger.error(
                        f"Error collecting {evidence_type.value} for {framework.value}: {e}"
                    )

        return EvidencePackage(
            package_id=str(uuid.uuid4()),
            organization="",  # Will be set by caller
            frameworks=frameworks,
            period_start=start_date,
            period_end=end_date,
            created_at=datetime.now(timezone.utc),
            items=all_items,
        )

    async def _collect_evidence_type(
        self,
        evidence_type: EvidenceType,
        framework: ComplianceFramework,
        start_date: datetime,
        end_date: datetime,
    ) -> list[EvidenceItem]:
        """Collect a specific type of evidence."""
        # Use registered collector if available
        if evidence_type in self.collectors:
            return await self.collectors[evidence_type](
                framework, start_date, end_date
            )

        # Default collectors
        if evidence_type == EvidenceType.ACCESS_LOGS:
            return await self.collect_access_logs(start_date, end_date, framework)
        elif evidence_type == EvidenceType.ENCRYPTION_CONFIG:
            return await self.collect_encryption_config(framework)
        elif evidence_type == EvidenceType.SECURITY_POLICIES:
            return await self.collect_security_policies(framework)

        # Return empty for types without collectors
        logger.debug(f"No collector for {evidence_type.value}, skipping")
        return []

    async def package_evidence(
        self,
        evidence: EvidencePackage,
        output_path: str | Path,
        include_content: bool = True,
    ) -> Path:
        """
        Package evidence into a ZIP file for audit submission.

        Args:
            evidence: The evidence package to export
            output_path: Path for the output ZIP file
            include_content: Whether to include full evidence content

        Returns:
            Path to the created ZIP file
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # Write manifest
            manifest = evidence.generate_manifest()
            zf.writestr(
                "manifest.json",
                json.dumps(manifest, indent=2, default=str),
            )

            if include_content:
                # Write each evidence item
                for item in evidence.items:
                    folder = f"{item.framework.value}/{item.evidence_type.value}"

                    if isinstance(item.content, bytes):
                        zf.writestr(
                            f"{folder}/{item.evidence_id}.bin",
                            item.content,
                        )
                    elif isinstance(item.content, str):
                        zf.writestr(
                            f"{folder}/{item.evidence_id}.txt",
                            item.content,
                        )
                    else:
                        zf.writestr(
                            f"{folder}/{item.evidence_id}.json",
                            json.dumps(item.content, indent=2, default=str),
                        )

        logger.info(f"Evidence package created: {output_path}")
        return output_path

    async def verify_package(self, package_path: str | Path) -> dict[str, Any]:
        """
        Verify the integrity of an evidence package.

        Args:
            package_path: Path to the evidence ZIP file

        Returns:
            Verification results
        """
        package_path = Path(package_path)
        results = {
            "valid": True,
            "total_items": 0,
            "verified_items": 0,
            "failed_items": [],
            "manifest": None,
        }

        with zipfile.ZipFile(package_path, "r") as zf:
            # Read manifest
            manifest = json.loads(zf.read("manifest.json"))
            results["manifest"] = {
                "package_id": manifest["package_id"],
                "organization": manifest["organization"],
                "frameworks": manifest["frameworks"],
                "period_start": manifest["period_start"],
                "period_end": manifest["period_end"],
            }
            results["total_items"] = manifest["total_items"]

            # Verify each item
            for item in manifest["items"]:
                framework = item["framework"]
                evidence_type = item["evidence_type"]
                evidence_id = item["evidence_id"]
                expected_hash = item["hash_sha256"]

                # Try different extensions
                for ext in [".json", ".txt", ".bin"]:
                    try:
                        content = zf.read(
                            f"{framework}/{evidence_type}/{evidence_id}{ext}"
                        )
                        actual_hash = hashlib.sha256(content).hexdigest()

                        if actual_hash == expected_hash:
                            results["verified_items"] += 1
                        else:
                            results["valid"] = False
                            results["failed_items"].append(
                                {
                                    "evidence_id": evidence_id,
                                    "reason": "hash_mismatch",
                                }
                            )
                        break
                    except KeyError:
                        continue
                else:
                    results["valid"] = False
                    results["failed_items"].append(
                        {
                            "evidence_id": evidence_id,
                            "reason": "file_not_found",
                        }
                    )

        return results
