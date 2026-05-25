"""
AutoSRE Compliance Framework

Enterprise compliance automation for SOC2, HIPAA, GDPR, and PCI-DSS.
Provides continuous compliance monitoring, automated checks, and audit reporting.
"""

from autosre.compliance.soc2 import (
    SOC2Checker,
    SOC2Control,
    SOC2Category,
    SOC2Finding,
    SOC2Report,
)
from autosre.compliance.hipaa import (
    HIPAAChecker,
    HIPAASafeguard,
    SafeguardType,
    HIPAAFinding,
    HIPAAReport,
)
from autosre.compliance.gdpr import (
    GDPRChecker,
    GDPRPrinciple,
    DataSubjectRight,
    GDPRFinding,
    GDPRReport,
)
from autosre.compliance.pci import (
    PCIChecker,
    PCIRequirement,
    PCILevel,
    PCIFinding,
    PCIReport,
)
from autosre.compliance.audit import (
    ComplianceAuditor,
    AuditReport,
    AuditFinding,
    AuditSeverity,
    ComplianceStatus,
    ComplianceFramework,
    generate_compliance_dashboard,
)
from autosre.compliance.evidence import (
    EvidenceCollector,
    EvidenceItem,
    EvidencePackage,
    EvidenceType,
)
from autosre.compliance.remediation import (
    RemediationTracker,
    RemediationTask,
    RemediationStatus,
    RemediationPriority,
    RemediationProgress,
)

__all__ = [
    # SOC2
    "SOC2Checker",
    "SOC2Control",
    "SOC2Category",
    "SOC2Finding",
    "SOC2Report",
    # HIPAA
    "HIPAAChecker",
    "HIPAASafeguard",
    "SafeguardType",
    "HIPAAFinding",
    "HIPAAReport",
    # GDPR
    "GDPRChecker",
    "GDPRPrinciple",
    "DataSubjectRight",
    "GDPRFinding",
    "GDPRReport",
    # PCI-DSS
    "PCIChecker",
    "PCIRequirement",
    "PCILevel",
    "PCIFinding",
    "PCIReport",
    # Audit
    "ComplianceAuditor",
    "AuditReport",
    "AuditFinding",
    "AuditSeverity",
    "ComplianceStatus",
    "ComplianceFramework",
    "generate_compliance_dashboard",
    # Evidence
    "EvidenceCollector",
    "EvidenceItem",
    "EvidencePackage",
    "EvidenceType",
    # Remediation
    "RemediationTracker",
    "RemediationTask",
    "RemediationStatus",
    "RemediationPriority",
    "RemediationProgress",
]
