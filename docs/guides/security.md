# Security Module Guide

AutoSRE includes an enterprise-grade security module designed for SRE teams to maintain a strong security posture while managing production infrastructure. This guide covers vulnerability scanning, security audit logging, and secrets management.

## Overview

The security module provides three core components:

1. **Vulnerability Scanner** - Container image scanning, Kubernetes configuration auditing, compliance checks
2. **Security Audit Logger** - Tamper-evident audit trails, anomaly detection, compliance reporting
3. **Secrets Manager** - Multi-backend secrets storage, automatic rotation, access control

## Quick Start

```python
from autosre.security import (
    # Vulnerability Scanning
    VulnerabilityScanner,
    ScannerConfig,
    Severity,
    
    # Security Audit
    SecurityAuditLogger,
    SecurityEventType,
    Actor,
    
    # Secrets Management
    SecretsManager,
    SecretsConfig,
    SecretBackend,
    SecretType,
)

# Initialize components
scanner = VulnerabilityScanner()
audit_logger = SecurityAuditLogger()
secrets_manager = SecretsManager(SecretsConfig(backend=SecretBackend.HASHICORP_VAULT))
```

## Vulnerability Scanning

### Container Image Scanning

Scan container images for known CVEs and vulnerabilities:

```python
from autosre.security import (
    VulnerabilityScanner,
    ScannerConfig,
    ImageScanConfig,
    Severity,
)

# Configure scanner
config = ScannerConfig(
    fail_on_critical=True,
    fail_on_high=False,
    max_critical_allowed=0,
    max_high_allowed=5,
    trivy_enabled=True,
)

scanner = VulnerabilityScanner(config)

# Scan a container image
result = await scanner.scan_image("nginx:1.21")

print(f"Image: {result.image}")
print(f"Total vulnerabilities: {result.total_vulnerabilities}")
print(f"Critical: {result.critical_count}")
print(f"High: {result.high_count}")

# Get critical vulnerabilities
for vuln in result.vulnerabilities_by_severity(Severity.CRITICAL):
    print(f"- {vuln.id}: {vuln.title}")
    print(f"  Package: {vuln.package_name} {vuln.installed_version}")
    if vuln.fixed_version:
        print(f"  Fix available: {vuln.fixed_version}")
```

### Kubernetes Security Scanning

Audit Kubernetes configurations against CIS benchmarks:

```python
from autosre.security import (
    VulnerabilityScanner,
    KubernetesScanConfig,
    ComplianceStandard,
)

scanner = VulnerabilityScanner()

# Configure Kubernetes scan
k8s_config = KubernetesScanConfig(
    namespaces=["production", "staging"],
    resource_types=["Deployment", "Pod", "Service", "ConfigMap"],
    compliance_standards=[
        ComplianceStandard.CIS_KUBERNETES,
        ComplianceStandard.PCI_DSS,
    ],
)

result = await scanner.scan_kubernetes(k8s_config)

# Check compliance scores
for standard, score in result.compliance_scores.items():
    status = "✓" if score >= 80 else "✗"
    print(f"{status} {standard}: {score:.1f}%")

# Review findings
for finding in result.findings:
    print(f"\n[{finding.severity.value.upper()}] {finding.title}")
    print(f"  Resource: {finding.resource_type}/{finding.resource_name}")
    print(f"  Remediation: {finding.remediation}")

# Check network exposures
for exposure in result.network_exposures:
    if exposure.is_public:
        print(f"⚠ Public exposure: {exposure.service_name}:{exposure.port}")
        print(f"  Recommendation: {exposure.recommendation}")
```

### Full Security Scan

Run a comprehensive security scan:

```python
from autosre.security import VulnerabilityScanner, ScanType

config = ScannerConfig(
    scan_types=[
        ScanType.CONTAINER_IMAGE,
        ScanType.KUBERNETES_CONFIG,
        ScanType.DEPENDENCY,
    ],
)

scanner = VulnerabilityScanner(config)

# Run full scan
summary = await scanner.full_scan(
    images=["app:v1.2.3", "worker:v1.2.3", "nginx:1.21"]
)

print(f"Scan ID: {summary.scan_id}")
print(f"Status: {summary.status.value}")
print(f"Risk Score: {summary.risk_score:.1f}/100")
print(f"Policy Passed: {'✓' if summary.passed_policy else '✗'}")

if not summary.passed_policy:
    print("\nPolicy Violations:")
    for violation in summary.policy_violations:
        print(f"  - {violation}")
```

## Security Audit Logging

### Basic Event Logging

Log security events with tamper-evident audit trails:

```python
from autosre.security import (
    SecurityAuditLogger,
    SecurityAuditConfig,
    SecurityEventType,
    Actor,
    Resource,
)

config = SecurityAuditConfig(
    enable_hmac=True,
    enable_chain_verification=True,
    alert_on_critical=True,
    compliance_frameworks=["soc2", "pci_dss"],
)

logger = SecurityAuditLogger(config)

# Log a login event
await logger.log_event(
    event_type=SecurityEventType.LOGIN_SUCCESS,
    actor=Actor(
        id="user-123",
        type="user",
        name="Alice Smith",
        email="alice@company.com",
        ip_address="192.168.1.100",
    ),
    action="User logged in via SSO",
    context={
        "method": "oauth2",
        "provider": "okta",
        "session_id": "sess-abc123",
    },
)

# Log resource access
await logger.log_event(
    event_type=SecurityEventType.SECRET_ACCESS,
    actor=Actor(
        id="service-account-api",
        type="service",
        name="API Service",
    ),
    action="Accessed database credentials",
    resource=Resource(
        type="secret",
        id="production/database/credentials",
        name="Database Credentials",
        namespace="production",
    ),
)
```

### Querying Audit Logs

Search and filter audit events:

```python
from autosre.security import (
    SecurityAuditLogger,
    AuditQuery,
    SecurityEventType,
    EventSeverity,
)
from datetime import datetime, timedelta

logger = SecurityAuditLogger()

# Query recent high-severity events
query = AuditQuery(
    start_time=datetime.utcnow() - timedelta(hours=24),
    event_types=[
        SecurityEventType.ACCESS_DENIED,
        SecurityEventType.LOGIN_FAILURE,
        SecurityEventType.BRUTE_FORCE_DETECTED,
    ],
    severities=[EventSeverity.HIGH, EventSeverity.CRITICAL],
    limit=100,
)

result = await logger.query(query)

print(f"Found {result.total_count} events")
for event in result.events:
    print(f"[{event.timestamp}] {event.event_type.value}")
    print(f"  Actor: {event.actor.id} from {event.actor.ip_address}")
    print(f"  Action: {event.action}")
```

### Compliance Reporting

Generate compliance audit reports:

```python
from autosre.security import (
    SecurityAuditLogger,
    ComplianceFramework,
)
from datetime import datetime

logger = SecurityAuditLogger()

# Generate SOC2 compliance report
report = await logger.generate_compliance_report(
    framework=ComplianceFramework.SOC2,
    period_start=datetime(2024, 1, 1),
    period_end=datetime(2024, 3, 31),
)

print(f"Report ID: {report.report_id}")
print(f"Framework: {report.framework.value}")
print(f"Period: {report.period_start} to {report.period_end}")
print(f"Compliance Score: {report.compliance_score:.1f}%")
print(f"Status: {'Compliant' if report.is_compliant else 'Non-Compliant'}")

print(f"\nControls Checked: {report.controls_checked}")
print(f"Controls Passed: {report.controls_passed}")
print(f"Controls Failed: {report.controls_failed}")

if report.findings:
    print("\nFindings:")
    for finding in report.findings:
        print(f"  - {finding['control_id']}: {finding['finding']}")
```

### Integrity Verification

Verify the integrity of audit logs:

```python
from autosre.security import SecurityAuditLogger

logger = SecurityAuditLogger()

# Verify hash chain integrity
is_valid, errors = await logger.verify_chain_integrity()

if is_valid:
    print("✓ Audit log integrity verified")
else:
    print("✗ Integrity verification failed:")
    for error in errors:
        print(f"  - {error}")
```

## Secrets Management

### Storing Secrets

Store secrets with automatic rotation:

```python
from autosre.security import (
    SecretsManager,
    SecretsConfig,
    SecretBackend,
    SecretType,
    RotationConfig,
)

config = SecretsConfig(
    backend=SecretBackend.HASHICORP_VAULT,
    vault_address="https://vault.company.com",
    auto_rotation_enabled=True,
)

manager = SecretsManager(config)

# Store a database credential
metadata = await manager.put_secret(
    name="production/database/password",
    value="super-secret-password",
    secret_type=SecretType.DATABASE_CREDENTIAL,
    description="Production PostgreSQL password",
    rotation_config=RotationConfig(
        enabled=True,
        rotation_days=30,
        auto_rotate=True,
        notify_before_days=[14, 7, 1],
        notification_emails=["oncall@company.com"],
    ),
    tags={
        "environment": "production",
        "service": "api",
        "team": "platform",
    },
    owner="platform-team",
)

print(f"Secret stored: {metadata.name}")
print(f"Version: {metadata.current_version}")
print(f"Next rotation: {metadata.next_rotation_at}")
```

### Retrieving Secrets

Retrieve secrets securely:

```python
from autosre.security import SecretsManager

manager = SecretsManager(config)

# Get a secret
secret = await manager.get_secret(
    name="production/database/password",
    accessor="api-service",
)

# Use the secret value
password = secret.reveal()

# Check metadata
print(f"Type: {secret.metadata.secret_type}")
print(f"Created: {secret.metadata.created_at}")
print(f"Days until rotation: {secret.metadata.days_until_rotation}")
```

### Secret Rotation

Rotate secrets automatically or manually:

```python
from autosre.security import SecretsManager, RotationStatus

manager = SecretsManager(config)

# Check secrets due for rotation
due_secrets = await manager.get_rotation_due(days_ahead=14)

print(f"Secrets due for rotation in next 14 days:")
for metadata in due_secrets:
    print(f"  - {metadata.name}: due {metadata.next_rotation_at}")

# Manually rotate a secret
result = await manager.rotate_secret(
    name="production/database/password",
    rotated_by="oncall-engineer",
)

if result.status == RotationStatus.COMPLETED:
    print(f"✓ Rotated from {result.previous_version} to {result.new_version}")
else:
    print(f"✗ Rotation failed: {result.error_message}")
```

### Generating Secrets

Generate secure secrets:

```python
from autosre.security import SecretGenerator

# Generate a strong password
password = SecretGenerator.generate_password(
    length=32,
    include_special=True,
)

# Generate an API key
api_key = SecretGenerator.generate_api_key(prefix="sk")

# Generate a database-safe password (no special chars)
db_password = SecretGenerator.generate_database_password()

# Generate an encryption key
encryption_key = SecretGenerator.generate_encryption_key(bits=256)
```

### Secret Scanning

Scan for exposed secrets in code or logs:

```python
from autosre.security import SecretsManager

manager = SecretsManager(config)

# Scan content for exposed secrets
content = '''
config = {
    "api_key": "YOUR_API_KEY_HERE",
    "password": "super-secret-password-123",
    "database_url": "postgres://user:pass@host/db",
}
'''

result = await manager.scan_for_secrets(content, scan_type="code")

print(f"Secrets found: {result.secrets_found}")
print(f"High risk: {result.high_risk_count}")

for finding in result.findings:
    print(f"  [{finding['risk']}] {finding['type']} on line {finding['line']}")
```

## Integration Examples

### CI/CD Pipeline Integration

```python
from autosre.security import (
    VulnerabilityScanner,
    ScannerConfig,
    Severity,
)

async def security_gate(image: str) -> bool:
    """Security gate for CI/CD pipeline."""
    
    config = ScannerConfig(
        fail_on_critical=True,
        max_critical_allowed=0,
        max_high_allowed=5,
    )
    
    scanner = VulnerabilityScanner(config)
    result = await scanner.scan_image(image)
    
    # Generate report
    print(f"Security Scan Report for {image}")
    print("=" * 50)
    print(f"Critical: {result.critical_count}")
    print(f"High: {result.high_count}")
    print(f"Medium: {result.medium_count}")
    print(f"Low: {result.low_count}")
    
    # List critical vulnerabilities
    if result.critical_count > 0:
        print("\nCritical Vulnerabilities:")
        for vuln in result.vulnerabilities_by_severity(Severity.CRITICAL):
            print(f"  - {vuln.id}: {vuln.package_name}")
            if vuln.fixed_version:
                print(f"    Fix: upgrade to {vuln.fixed_version}")
    
    # Check policy
    passed = result.critical_count == 0
    
    if passed:
        print("\n✓ Security gate PASSED")
    else:
        print("\n✗ Security gate FAILED")
    
    return passed
```

### Incident Response Integration

```python
from autosre.security import (
    SecurityAuditLogger,
    AuditQuery,
    SecurityEventType,
)
from datetime import datetime, timedelta

async def investigate_incident(
    incident_time: datetime,
    suspicious_ip: str,
) -> dict:
    """Investigate a security incident."""
    
    logger = SecurityAuditLogger()
    
    # Query events around incident time
    window = timedelta(hours=1)
    query = AuditQuery(
        start_time=incident_time - window,
        end_time=incident_time + window,
        limit=1000,
    )
    
    result = await logger.query(query)
    
    # Find events from suspicious IP
    suspicious_events = [
        e for e in result.events
        if e.actor.ip_address == suspicious_ip
    ]
    
    # Analyze patterns
    analysis = {
        "total_events": len(suspicious_events),
        "login_failures": len([e for e in suspicious_events if e.event_type == SecurityEventType.LOGIN_FAILURE]),
        "access_denied": len([e for e in suspicious_events if e.event_type == SecurityEventType.ACCESS_DENIED]),
        "resources_accessed": list(set(e.resource.name for e in suspicious_events if e.resource)),
        "timeline": [(e.timestamp.isoformat(), e.event_type.value) for e in suspicious_events],
    }
    
    return analysis
```

## Best Practices

### Vulnerability Scanning

1. **Scan in CI/CD**: Integrate scanning in your CI/CD pipeline to catch vulnerabilities before deployment
2. **Fail on critical**: Always fail builds on critical vulnerabilities with known exploits
3. **Regular scanning**: Schedule regular scans of production images
4. **Track trends**: Monitor vulnerability trends over time to measure security improvements

### Security Audit Logging

1. **Log everything important**: Log all authentication, authorization, and sensitive data access
2. **Enable integrity checks**: Use HMAC signatures and hash chains for tamper detection
3. **Retain appropriately**: Follow compliance requirements for log retention
4. **Monitor alerts**: Set up alerting for critical security events

### Secrets Management

1. **Never hardcode**: Always use secrets management instead of hardcoding secrets
2. **Rotate regularly**: Enable automatic rotation for all secrets
3. **Least privilege**: Grant minimal access required for each service
4. **Audit access**: Monitor and audit all secret access

## Configuration Reference

### Scanner Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enabled` | bool | true | Enable vulnerability scanning |
| `scan_interval_hours` | int | 24 | Scan interval in hours |
| `fail_on_critical` | bool | true | Fail builds on critical vulnerabilities |
| `fail_on_high` | bool | false | Fail builds on high vulnerabilities |
| `max_critical_allowed` | int | 0 | Maximum allowed critical vulnerabilities |
| `max_high_allowed` | int | 5 | Maximum allowed high vulnerabilities |
| `trivy_enabled` | bool | true | Use Trivy for container scanning |
| `kube_bench_enabled` | bool | true | Enable CIS Kubernetes benchmark |

### Audit Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enabled` | bool | true | Enable security audit logging |
| `enable_hmac` | bool | true | Enable HMAC signatures |
| `enable_chain_verification` | bool | true | Enable hash chain verification |
| `retention_days` | int | 365 | Log retention period |
| `alert_on_critical` | bool | true | Alert on critical events |

### Secrets Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `backend` | SecretBackend | - | Secret storage backend (required) |
| `enable_caching` | bool | true | Enable secret caching |
| `cache_ttl_seconds` | int | 300 | Cache TTL in seconds |
| `auto_rotation_enabled` | bool | true | Enable auto-rotation |
| `default_rotation_days` | int | 90 | Default rotation period |
