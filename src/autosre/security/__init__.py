"""
AutoSRE Security Module

Enterprise-grade security capabilities for SRE operations providing:
- Vulnerability scanning for containers, Kubernetes, and infrastructure
- Security audit logging with tamper-evident trails
- Secrets management with multi-backend support
- Compliance reporting (SOC2, PCI-DSS, HIPAA, ISO 27001)

Enables comprehensive security posture management for
incident prevention, compliance, and forensic investigation.

Usage:
    from autosre.security import (
        # Vulnerability Scanning
        VulnerabilityScanner, ScannerConfig, ImageScanConfig,
        Vulnerability, Severity, ScanSummary, ImageScanResult,
        # Security Audit
        SecurityAuditLogger, SecurityAuditConfig,
        SecurityEvent, SecurityEventType, EventSeverity,
        Actor, Resource, AuditQuery, ComplianceReport,
        # Secrets Management
        SecretsManager, SecretsConfig, Secret, SecretMetadata,
        SecretType, RotationConfig, SecretGenerator,
    )
"""

from autosre.security.scanner import (
    # Enums
    ScanType,
    Severity,
    ScanStatus,
    VulnerabilityStatus,
    ComplianceStandard,
    # Configuration
    ScannerConfig,
    ImageScanConfig,
    KubernetesScanConfig,
    # Models
    CVSSScore,
    Vulnerability,
    ConfigurationFinding,
    NetworkExposure,
    # Results
    ImageScanResult,
    KubernetesScanResult,
    ScanSummary,
    # Scanner
    VulnerabilityScanner,
)
from autosre.security.audit import (
    # Enums
    SecurityEventType,
    EventSeverity,
    AuditLogDestination,
    ComplianceFramework,
    # Configuration
    SecurityAuditConfig,
    AlertConfig,
    # Models
    Actor,
    Resource,
    SecurityEvent,
    AuditLogEntry,
    # Query and Reporting
    AuditQuery,
    AuditQueryResult,
    ComplianceReport,
    SecurityAlert,
    # Logger
    SecurityAuditLogger,
)
from autosre.security.secrets import (
    # Enums
    SecretBackend,
    SecretType,
    RotationStatus,
    AccessLevel,
    # Configuration
    SecretsConfig,
    RotationConfig,
    AccessPolicy,
    # Models
    SecretVersion,
    SecretMetadata,
    Secret,
    SecretReference,
    RotationResult,
    SecretScanResult,
    # Generator
    SecretGenerator,
    # Manager
    SecretsManager,
)

__all__ = [
    # Scanner - Enums
    "ScanType",
    "Severity",
    "ScanStatus",
    "VulnerabilityStatus",
    "ComplianceStandard",
    # Scanner - Configuration
    "ScannerConfig",
    "ImageScanConfig",
    "KubernetesScanConfig",
    # Scanner - Models
    "CVSSScore",
    "Vulnerability",
    "ConfigurationFinding",
    "NetworkExposure",
    # Scanner - Results
    "ImageScanResult",
    "KubernetesScanResult",
    "ScanSummary",
    # Scanner - Implementation
    "VulnerabilityScanner",
    # Audit - Enums
    "SecurityEventType",
    "EventSeverity",
    "AuditLogDestination",
    "ComplianceFramework",
    # Audit - Configuration
    "SecurityAuditConfig",
    "AlertConfig",
    # Audit - Models
    "Actor",
    "Resource",
    "SecurityEvent",
    "AuditLogEntry",
    # Audit - Query and Reporting
    "AuditQuery",
    "AuditQueryResult",
    "ComplianceReport",
    "SecurityAlert",
    # Audit - Logger
    "SecurityAuditLogger",
    # Secrets - Enums
    "SecretBackend",
    "SecretType",
    "RotationStatus",
    "AccessLevel",
    # Secrets - Configuration
    "SecretsConfig",
    "RotationConfig",
    "AccessPolicy",
    # Secrets - Models
    "SecretVersion",
    "SecretMetadata",
    "Secret",
    "SecretReference",
    "RotationResult",
    "SecretScanResult",
    # Secrets - Generator
    "SecretGenerator",
    # Secrets - Manager
    "SecretsManager",
]
