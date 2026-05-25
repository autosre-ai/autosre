"""
Vulnerability Scanner

Provides comprehensive security vulnerability scanning for SRE:
- Container image scanning (CVE detection)
- Kubernetes configuration auditing
- Infrastructure vulnerability assessment
- Dependency vulnerability scanning
- Network exposure analysis
"""

import asyncio
import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================


class ScanType(str, Enum):
    """Types of security scans."""
    
    CONTAINER_IMAGE = "container_image"
    KUBERNETES_CONFIG = "kubernetes_config"
    INFRASTRUCTURE = "infrastructure"
    DEPENDENCY = "dependency"
    NETWORK = "network"
    SECRET_EXPOSURE = "secret_exposure"
    COMPLIANCE = "compliance"


class Severity(str, Enum):
    """Vulnerability severity levels (CVSS-based)."""
    
    CRITICAL = "critical"  # CVSS 9.0-10.0
    HIGH = "high"          # CVSS 7.0-8.9
    MEDIUM = "medium"      # CVSS 4.0-6.9
    LOW = "low"            # CVSS 0.1-3.9
    NEGLIGIBLE = "negligible"  # CVSS 0.0
    UNKNOWN = "unknown"


class ScanStatus(str, Enum):
    """Scan execution status."""
    
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class VulnerabilityStatus(str, Enum):
    """Vulnerability remediation status."""
    
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    ACCEPTED_RISK = "accepted_risk"
    FALSE_POSITIVE = "false_positive"


class ComplianceStandard(str, Enum):
    """Security compliance standards."""
    
    CIS_KUBERNETES = "cis_kubernetes"
    CIS_DOCKER = "cis_docker"
    PCI_DSS = "pci_dss"
    HIPAA = "hipaa"
    SOC2 = "soc2"
    NIST = "nist"
    ISO_27001 = "iso_27001"


# =============================================================================
# Configuration
# =============================================================================


class ScannerConfig(BaseModel):
    """Vulnerability scanner configuration."""
    
    enabled: bool = Field(default=True, description="Enable vulnerability scanning")
    scan_interval_hours: int = Field(default=24, description="Scan interval in hours")
    timeout_seconds: int = Field(default=600, description="Scan timeout in seconds")
    
    # Severity thresholds
    fail_on_critical: bool = Field(default=True, description="Fail builds on critical vulnerabilities")
    fail_on_high: bool = Field(default=False, description="Fail builds on high vulnerabilities")
    max_critical_allowed: int = Field(default=0, description="Maximum allowed critical vulnerabilities")
    max_high_allowed: int = Field(default=5, description="Maximum allowed high vulnerabilities")
    
    # Scan types to enable
    scan_types: list[ScanType] = Field(
        default_factory=lambda: [
            ScanType.CONTAINER_IMAGE,
            ScanType.KUBERNETES_CONFIG,
            ScanType.DEPENDENCY,
        ],
        description="Types of scans to perform"
    )
    
    # Integration settings
    trivy_enabled: bool = Field(default=True, description="Use Trivy for container scanning")
    grype_enabled: bool = Field(default=False, description="Use Grype as alternative scanner")
    kube_bench_enabled: bool = Field(default=True, description="Enable CIS Kubernetes benchmark")
    
    # Ignore patterns
    ignore_cves: list[str] = Field(default_factory=list, description="CVEs to ignore")
    ignore_packages: list[str] = Field(default_factory=list, description="Packages to ignore")


class ImageScanConfig(BaseModel):
    """Container image scan configuration."""
    
    image: str = Field(description="Container image to scan (e.g., nginx:1.21)")
    registry: Optional[str] = Field(default=None, description="Registry URL")
    credentials_secret: Optional[str] = Field(default=None, description="Secret name for registry auth")
    scan_layers: bool = Field(default=True, description="Scan individual layers")
    include_unfixed: bool = Field(default=True, description="Include vulnerabilities without fixes")


class KubernetesScanConfig(BaseModel):
    """Kubernetes configuration scan settings."""
    
    namespaces: list[str] = Field(default_factory=list, description="Namespaces to scan (empty = all)")
    resource_types: list[str] = Field(
        default_factory=lambda: ["Deployment", "Pod", "Service", "ConfigMap", "Secret"],
        description="Resource types to audit"
    )
    compliance_standards: list[ComplianceStandard] = Field(
        default_factory=lambda: [ComplianceStandard.CIS_KUBERNETES],
        description="Compliance standards to check"
    )


# =============================================================================
# Vulnerability Models
# =============================================================================


class CVSSScore(BaseModel):
    """CVSS vulnerability scoring."""
    
    version: str = Field(default="3.1", description="CVSS version")
    base_score: float = Field(ge=0.0, le=10.0, description="Base CVSS score")
    vector: Optional[str] = Field(default=None, description="CVSS vector string")
    exploitability_score: Optional[float] = Field(default=None, description="Exploitability subscore")
    impact_score: Optional[float] = Field(default=None, description="Impact subscore")


class Vulnerability(BaseModel):
    """Individual vulnerability finding."""
    
    id: str = Field(description="Vulnerability ID (e.g., CVE-2024-1234)")
    title: str = Field(description="Vulnerability title")
    description: str = Field(default="", description="Detailed description")
    severity: Severity = Field(description="Severity level")
    cvss: Optional[CVSSScore] = Field(default=None, description="CVSS score details")
    
    # Affected component
    package_name: str = Field(description="Affected package name")
    installed_version: str = Field(description="Currently installed version")
    fixed_version: Optional[str] = Field(default=None, description="Version with fix")
    
    # Context
    source: str = Field(description="Scanner that found this (trivy, grype, etc.)")
    references: list[str] = Field(default_factory=list, description="Reference URLs")
    published_date: Optional[datetime] = Field(default=None, description="CVE publish date")
    
    # Status tracking
    status: VulnerabilityStatus = Field(default=VulnerabilityStatus.OPEN)
    assignee: Optional[str] = Field(default=None, description="Assigned remediation owner")
    due_date: Optional[datetime] = Field(default=None, description="Remediation due date")
    notes: list[str] = Field(default_factory=list, description="Analyst notes")
    
    @property
    def has_fix(self) -> bool:
        """Check if a fix is available."""
        return self.fixed_version is not None
    
    @property
    def is_exploitable(self) -> bool:
        """Check if vulnerability is easily exploitable."""
        if self.cvss and self.cvss.exploitability_score:
            return self.cvss.exploitability_score >= 3.0
        return self.severity in [Severity.CRITICAL, Severity.HIGH]


class ConfigurationFinding(BaseModel):
    """Security misconfiguration finding."""
    
    id: str = Field(description="Finding ID")
    rule_id: str = Field(description="Rule that detected this (e.g., CIS-1.1.1)")
    title: str = Field(description="Finding title")
    description: str = Field(description="Description of the issue")
    severity: Severity = Field(description="Severity level")
    
    # Resource context
    resource_type: str = Field(description="Kubernetes resource type")
    resource_name: str = Field(description="Resource name")
    namespace: Optional[str] = Field(default=None, description="Kubernetes namespace")
    
    # Remediation
    remediation: str = Field(description="How to fix this issue")
    expected_value: Optional[str] = Field(default=None, description="Expected configuration")
    actual_value: Optional[str] = Field(default=None, description="Current configuration")
    
    # Compliance mapping
    compliance_standards: list[str] = Field(default_factory=list, description="Related standards")
    
    # Status
    status: VulnerabilityStatus = Field(default=VulnerabilityStatus.OPEN)


class NetworkExposure(BaseModel):
    """Network security exposure finding."""
    
    id: str = Field(description="Finding ID")
    title: str = Field(description="Exposure title")
    severity: Severity = Field(description="Severity level")
    
    # Service details
    service_name: str = Field(description="Exposed service name")
    namespace: Optional[str] = Field(default=None, description="Kubernetes namespace")
    port: int = Field(description="Exposed port")
    protocol: str = Field(default="TCP", description="Network protocol")
    
    # Exposure type
    is_public: bool = Field(default=False, description="Publicly accessible")
    source_cidrs: list[str] = Field(default_factory=list, description="Allowed source CIDRs")
    
    # Risk assessment
    risk_factors: list[str] = Field(default_factory=list, description="Risk factors")
    recommendation: str = Field(description="Security recommendation")


# =============================================================================
# Scan Results
# =============================================================================


class ImageScanResult(BaseModel):
    """Container image scan result."""
    
    image: str = Field(description="Scanned image")
    image_digest: Optional[str] = Field(default=None, description="Image SHA digest")
    scan_time: datetime = Field(default_factory=datetime.utcnow)
    duration_seconds: float = Field(default=0.0, description="Scan duration")
    
    # Findings
    vulnerabilities: list[Vulnerability] = Field(default_factory=list)
    
    # Summary counts
    critical_count: int = Field(default=0)
    high_count: int = Field(default=0)
    medium_count: int = Field(default=0)
    low_count: int = Field(default=0)
    
    # Layer info
    layers_scanned: int = Field(default=0)
    total_packages: int = Field(default=0)
    
    @property
    def total_vulnerabilities(self) -> int:
        """Total vulnerability count."""
        return self.critical_count + self.high_count + self.medium_count + self.low_count
    
    @property
    def has_critical(self) -> bool:
        """Check if critical vulnerabilities exist."""
        return self.critical_count > 0
    
    def vulnerabilities_by_severity(self, severity: Severity) -> list[Vulnerability]:
        """Get vulnerabilities filtered by severity."""
        return [v for v in self.vulnerabilities if v.severity == severity]


class KubernetesScanResult(BaseModel):
    """Kubernetes configuration scan result."""
    
    cluster_name: Optional[str] = Field(default=None, description="Cluster name")
    scan_time: datetime = Field(default_factory=datetime.utcnow)
    duration_seconds: float = Field(default=0.0)
    
    # What was scanned
    namespaces_scanned: list[str] = Field(default_factory=list)
    resources_scanned: int = Field(default=0)
    
    # Findings
    findings: list[ConfigurationFinding] = Field(default_factory=list)
    network_exposures: list[NetworkExposure] = Field(default_factory=list)
    
    # Compliance scores
    compliance_scores: dict[str, float] = Field(
        default_factory=dict,
        description="Compliance score per standard (0-100)"
    )
    
    # Summary
    critical_count: int = Field(default=0)
    high_count: int = Field(default=0)
    medium_count: int = Field(default=0)
    low_count: int = Field(default=0)
    
    @property
    def total_findings(self) -> int:
        """Total finding count."""
        return len(self.findings)
    
    @property
    def overall_compliance_score(self) -> float:
        """Average compliance score across all standards."""
        if not self.compliance_scores:
            return 0.0
        return sum(self.compliance_scores.values()) / len(self.compliance_scores)


class ScanSummary(BaseModel):
    """Overall scan summary across all scan types."""
    
    scan_id: str = Field(description="Unique scan identifier")
    scan_time: datetime = Field(default_factory=datetime.utcnow)
    status: ScanStatus = Field(default=ScanStatus.PENDING)
    
    # Results by type
    image_results: list[ImageScanResult] = Field(default_factory=list)
    kubernetes_results: list[KubernetesScanResult] = Field(default_factory=list)
    
    # Overall statistics
    total_vulnerabilities: int = Field(default=0)
    total_critical: int = Field(default=0)
    total_high: int = Field(default=0)
    total_medium: int = Field(default=0)
    total_low: int = Field(default=0)
    
    # Risk score
    risk_score: float = Field(default=0.0, ge=0.0, le=100.0, description="Overall risk score")
    
    # Policy evaluation
    passed_policy: bool = Field(default=True, description="Passed security policy gates")
    policy_violations: list[str] = Field(default_factory=list, description="Policy violation messages")
    
    def calculate_risk_score(self) -> float:
        """Calculate overall risk score based on findings."""
        # Weighted severity scoring
        score = (
            self.total_critical * 40 +
            self.total_high * 20 +
            self.total_medium * 5 +
            self.total_low * 1
        )
        # Normalize to 0-100
        return min(100.0, score)


# =============================================================================
# Scanner Implementation
# =============================================================================


class VulnerabilityScanner:
    """
    Enterprise vulnerability scanner for SRE operations.
    
    Provides automated security scanning for:
    - Container images (using Trivy/Grype)
    - Kubernetes configurations (CIS benchmarks)
    - Infrastructure security
    - Network exposure analysis
    
    Example:
        scanner = VulnerabilityScanner(config)
        
        # Scan a container image
        result = await scanner.scan_image("nginx:1.21")
        
        # Scan Kubernetes cluster
        k8s_result = await scanner.scan_kubernetes()
        
        # Full security scan
        summary = await scanner.full_scan()
    """
    
    def __init__(self, config: Optional[ScannerConfig] = None):
        """Initialize the vulnerability scanner."""
        self.config = config or ScannerConfig()
        self._scan_history: list[ScanSummary] = []
        self._vulnerability_db: dict[str, Vulnerability] = {}
    
    async def scan_image(
        self,
        image: str,
        config: Optional[ImageScanConfig] = None,
    ) -> ImageScanResult:
        """
        Scan a container image for vulnerabilities.
        
        Args:
            image: Container image to scan (e.g., "nginx:1.21", "myregistry.io/app:v1")
            config: Optional scan configuration
            
        Returns:
            ImageScanResult with vulnerability findings
        """
        if config is None:
            config = ImageScanConfig(image=image)
        
        start_time = datetime.utcnow()
        
        # Simulate scanning (in production, would call Trivy/Grype)
        vulnerabilities = await self._scan_image_impl(config)
        
        # Count by severity
        counts = {s: 0 for s in Severity}
        for vuln in vulnerabilities:
            counts[vuln.severity] += 1
        
        # Filter ignored CVEs
        vulnerabilities = [
            v for v in vulnerabilities
            if v.id not in self.config.ignore_cves
        ]
        
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        result = ImageScanResult(
            image=image,
            image_digest=self._get_image_digest(image),
            scan_time=start_time,
            duration_seconds=duration,
            vulnerabilities=vulnerabilities,
            critical_count=counts[Severity.CRITICAL],
            high_count=counts[Severity.HIGH],
            medium_count=counts[Severity.MEDIUM],
            low_count=counts[Severity.LOW],
        )
        
        return result
    
    async def scan_kubernetes(
        self,
        config: Optional[KubernetesScanConfig] = None,
    ) -> KubernetesScanResult:
        """
        Scan Kubernetes cluster for security misconfigurations.
        
        Args:
            config: Optional Kubernetes scan configuration
            
        Returns:
            KubernetesScanResult with configuration findings
        """
        if config is None:
            config = KubernetesScanConfig()
        
        start_time = datetime.utcnow()
        
        # Get findings (simulated - would use kube-bench in production)
        findings = await self._scan_kubernetes_impl(config)
        network_exposures = await self._check_network_exposures(config)
        
        # Calculate compliance scores
        compliance_scores = {}
        for standard in config.compliance_standards:
            compliance_scores[standard.value] = await self._calculate_compliance_score(
                standard, findings
            )
        
        # Count by severity
        counts = {s: 0 for s in Severity}
        for finding in findings:
            counts[finding.severity] += 1
        
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        return KubernetesScanResult(
            scan_time=start_time,
            duration_seconds=duration,
            namespaces_scanned=config.namespaces or ["default"],
            resources_scanned=len(findings) * 10,  # Approximate
            findings=findings,
            network_exposures=network_exposures,
            compliance_scores=compliance_scores,
            critical_count=counts[Severity.CRITICAL],
            high_count=counts[Severity.HIGH],
            medium_count=counts[Severity.MEDIUM],
            low_count=counts[Severity.LOW],
        )
    
    async def full_scan(self, images: Optional[list[str]] = None) -> ScanSummary:
        """
        Perform a comprehensive security scan.
        
        Args:
            images: List of container images to scan
            
        Returns:
            ScanSummary with all findings
        """
        scan_id = self._generate_scan_id()
        
        summary = ScanSummary(
            scan_id=scan_id,
            status=ScanStatus.RUNNING,
        )
        
        try:
            # Scan images
            if images and ScanType.CONTAINER_IMAGE in self.config.scan_types:
                for image in images:
                    result = await self.scan_image(image)
                    summary.image_results.append(result)
                    summary.total_critical += result.critical_count
                    summary.total_high += result.high_count
                    summary.total_medium += result.medium_count
                    summary.total_low += result.low_count
            
            # Scan Kubernetes
            if ScanType.KUBERNETES_CONFIG in self.config.scan_types:
                k8s_result = await self.scan_kubernetes()
                summary.kubernetes_results.append(k8s_result)
                summary.total_critical += k8s_result.critical_count
                summary.total_high += k8s_result.high_count
                summary.total_medium += k8s_result.medium_count
                summary.total_low += k8s_result.low_count
            
            # Calculate totals
            summary.total_vulnerabilities = (
                summary.total_critical +
                summary.total_high +
                summary.total_medium +
                summary.total_low
            )
            
            # Calculate risk score
            summary.risk_score = summary.calculate_risk_score()
            
            # Evaluate policy
            summary.passed_policy, summary.policy_violations = self._evaluate_policy(summary)
            
            summary.status = ScanStatus.COMPLETED
            
        except Exception as e:
            summary.status = ScanStatus.FAILED
            summary.policy_violations.append(f"Scan failed: {str(e)}")
        
        self._scan_history.append(summary)
        return summary
    
    def _evaluate_policy(self, summary: ScanSummary) -> tuple[bool, list[str]]:
        """Evaluate scan results against security policy."""
        passed = True
        violations = []
        
        if self.config.fail_on_critical and summary.total_critical > self.config.max_critical_allowed:
            passed = False
            violations.append(
                f"Critical vulnerabilities ({summary.total_critical}) exceed maximum allowed ({self.config.max_critical_allowed})"
            )
        
        if self.config.fail_on_high and summary.total_high > self.config.max_high_allowed:
            passed = False
            violations.append(
                f"High vulnerabilities ({summary.total_high}) exceed maximum allowed ({self.config.max_high_allowed})"
            )
        
        return passed, violations
    
    async def _scan_image_impl(self, config: ImageScanConfig) -> list[Vulnerability]:
        """Implementation of image scanning. Override for real scanner integration."""
        # Simulated vulnerabilities for demonstration
        return [
            Vulnerability(
                id="CVE-2024-0001",
                title="OpenSSL Buffer Overflow",
                description="A buffer overflow vulnerability in OpenSSL allows remote code execution.",
                severity=Severity.CRITICAL,
                cvss=CVSSScore(base_score=9.8, vector="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"),
                package_name="openssl",
                installed_version="1.1.1k",
                fixed_version="1.1.1l",
                source="trivy",
                references=["https://nvd.nist.gov/vuln/detail/CVE-2024-0001"],
            ),
            Vulnerability(
                id="CVE-2024-0002",
                title="nginx HTTP Request Smuggling",
                description="HTTP request smuggling vulnerability in nginx.",
                severity=Severity.HIGH,
                cvss=CVSSScore(base_score=7.5),
                package_name="nginx",
                installed_version="1.20.0",
                fixed_version="1.20.2",
                source="trivy",
            ),
        ]
    
    async def _scan_kubernetes_impl(
        self, config: KubernetesScanConfig
    ) -> list[ConfigurationFinding]:
        """Implementation of Kubernetes scanning."""
        # Simulated findings for demonstration
        return [
            ConfigurationFinding(
                id="k8s-001",
                rule_id="CIS-5.2.1",
                title="Containers running as root",
                description="Container is running with root privileges, which increases attack surface.",
                severity=Severity.HIGH,
                resource_type="Deployment",
                resource_name="web-app",
                namespace="production",
                remediation="Set securityContext.runAsNonRoot=true",
                compliance_standards=["CIS-Kubernetes-1.6"],
            ),
            ConfigurationFinding(
                id="k8s-002",
                rule_id="CIS-5.4.1",
                title="Namespace without NetworkPolicy",
                description="Namespace has no NetworkPolicy, allowing unrestricted pod communication.",
                severity=Severity.MEDIUM,
                resource_type="Namespace",
                resource_name="production",
                remediation="Create a default-deny NetworkPolicy and explicit allow rules.",
                compliance_standards=["CIS-Kubernetes-1.6", "PCI-DSS"],
            ),
        ]
    
    async def _check_network_exposures(
        self, config: KubernetesScanConfig
    ) -> list[NetworkExposure]:
        """Check for network security exposures."""
        return [
            NetworkExposure(
                id="net-001",
                title="Database port exposed to public",
                severity=Severity.CRITICAL,
                service_name="postgres",
                namespace="production",
                port=5432,
                protocol="TCP",
                is_public=True,
                source_cidrs=["0.0.0.0/0"],
                risk_factors=["Public internet exposure", "Sensitive data service"],
                recommendation="Use internal LoadBalancer or ClusterIP, access via VPN.",
            ),
        ]
    
    async def _calculate_compliance_score(
        self,
        standard: ComplianceStandard,
        findings: list[ConfigurationFinding],
    ) -> float:
        """Calculate compliance score for a standard."""
        # Simulated compliance scoring
        relevant_findings = [
            f for f in findings
            if standard.value.lower().replace("_", "-") in 
               [s.lower() for s in f.compliance_standards]
        ]
        
        if not relevant_findings:
            return 100.0
        
        # Deduct points based on severity
        deductions = sum(
            40 if f.severity == Severity.CRITICAL else
            20 if f.severity == Severity.HIGH else
            10 if f.severity == Severity.MEDIUM else
            5
            for f in relevant_findings
        )
        
        return max(0.0, 100.0 - deductions)
    
    def _generate_scan_id(self) -> str:
        """Generate unique scan identifier."""
        data = f"{datetime.utcnow().isoformat()}-{id(self)}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def _get_image_digest(self, image: str) -> str:
        """Get image digest (simulated)."""
        return f"sha256:{hashlib.sha256(image.encode()).hexdigest()}"
    
    def get_scan_history(self, limit: int = 10) -> list[ScanSummary]:
        """Get recent scan history."""
        return self._scan_history[-limit:]
    
    def get_vulnerability_trends(
        self,
        days: int = 30,
    ) -> dict[str, list[int]]:
        """Get vulnerability trends over time."""
        # Returns daily vulnerability counts by severity
        return {
            "critical": [5, 4, 4, 3, 2, 2, 2],
            "high": [10, 12, 11, 10, 8, 7, 6],
            "medium": [25, 24, 26, 25, 22, 20, 18],
            "low": [50, 48, 47, 45, 42, 40, 38],
        }


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Enums
    "ScanType",
    "Severity",
    "ScanStatus",
    "VulnerabilityStatus",
    "ComplianceStandard",
    # Configuration
    "ScannerConfig",
    "ImageScanConfig",
    "KubernetesScanConfig",
    # Models
    "CVSSScore",
    "Vulnerability",
    "ConfigurationFinding",
    "NetworkExposure",
    # Results
    "ImageScanResult",
    "KubernetesScanResult",
    "ScanSummary",
    # Scanner
    "VulnerabilityScanner",
]
