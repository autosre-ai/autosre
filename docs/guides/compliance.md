# Enterprise Compliance Framework Guide

AutoSRE provides comprehensive enterprise compliance automation for the most demanding regulatory requirements. This guide covers setting up and using compliance checks for SOC2 Type II, HIPAA, GDPR, and PCI-DSS frameworks.

## Overview

The compliance module provides:

- **Automated compliance checks** - Continuous monitoring against regulatory controls
- **Evidence collection** - Automatic gathering of compliance evidence
- **Unified reporting** - Cross-framework audit reports
- **Remediation guidance** - Actionable steps to address findings
- **Dashboard integration** - Real-time compliance visibility

## Quick Start

```python
from autosre.compliance import (
    ComplianceAuditor,
    SOC2Checker,
    HIPAAChecker,
    GDPRChecker,
    PCIChecker,
    generate_compliance_dashboard,
)
from datetime import datetime, timedelta

# Initialize the unified auditor
auditor = ComplianceAuditor(
    organization="Acme Corp",
    soc2_enabled=True,
    hipaa_enabled=True,
    gdpr_enabled=True,
    pci_enabled=True,
)

# Define your compliance context
context = {
    # Security controls
    "rbac_enabled": True,
    "mfa_enforced": True,
    "encryption_at_rest": True,
    "tls_version": "1.3",
    
    # Logging and monitoring
    "centralized_logging": True,
    "log_retention_days": 365,
    "audit_logging_enabled": True,
    
    # Additional context...
}

# Run full compliance audit
report = await auditor.run_full_audit(
    context=context,
    period_start=datetime.now() - timedelta(days=90),
    period_end=datetime.now(),
)

# Generate dashboard data
dashboard = generate_compliance_dashboard(report)
print(f"Overall Status: {report.overall_status.value}")
print(f"Critical Findings: {len(report.critical_findings)}")
```

---

## SOC2 Type II Compliance

SOC2 Type II audits focus on the Trust Services Criteria (TSC) for service organizations.

### Trust Services Categories

| Category | Code | Description |
|----------|------|-------------|
| Security | CC | Common Criteria - protection against unauthorized access |
| Availability | A | System availability for operation and use |
| Processing Integrity | PI | System processing is complete, valid, accurate |
| Confidentiality | C | Information designated confidential is protected |
| Privacy | P | Personal information is collected, used, retained properly |

### Setting Up SOC2 Checks

```python
from autosre.compliance import SOC2Checker, SOC2Category

checker = SOC2Checker()

# Define SOC2 compliance context
soc2_context = {
    # CC6.1 - Access Controls
    "rbac_enabled": True,
    "mfa_enforced": True,
    "password_policy": {
        "min_length": 14,
        "complexity_required": True,
        "max_age_days": 90,
    },
    
    # CC6.7 - Encryption
    "tls_version": "1.3",
    "encryption_at_rest": True,
    "key_rotation_days": 90,
    
    # CC7.2 - Security Monitoring
    "centralized_logging": True,
    "security_alerts_configured": True,
    "log_retention_days": 365,
    
    # A1.2 - Availability
    "automated_backups": True,
    "dr_plan_tested_recently": True,
    "rto_hours": 4,
    "rpo_hours": 1,
}

# Run SOC2 checks
report = await checker.generate_report(
    context=soc2_context,
    period_start=datetime(2024, 1, 1),
    period_end=datetime(2024, 12, 31),
)

print(f"SOC2 Score: {report.overall_score:.1%}")
print(f"Passed: {report.passed}")

# Review category scores
for category, score in report.category_scores.items():
    print(f"  {category.value}: {score:.1%}")
```

### Key SOC2 Controls

#### CC6.1 - Logical and Physical Access Controls

```python
# Required context parameters
access_control_context = {
    "rbac_enabled": True,              # Role-based access control
    "mfa_enforced": True,              # Multi-factor authentication
    "password_policy": {
        "min_length": 12,              # Minimum password length
        "complexity_required": True,   # Special chars, numbers, etc.
        "history_count": 12,           # Password history
        "max_age_days": 90,            # Password expiration
    },
}
```

#### CC6.7 - Transmission Security

```python
encryption_context = {
    "tls_version": "1.3",              # TLS 1.2 minimum required
    "encryption_at_rest": True,        # Data encrypted at rest
    "key_rotation_days": 90,           # Key rotation frequency
    "hsts_enabled": True,              # HTTP Strict Transport Security
}
```

#### CC7.2 - Security Monitoring

```python
monitoring_context = {
    "centralized_logging": True,       # Centralized log aggregation
    "security_alerts_configured": True, # Alert rules defined
    "log_retention_days": 365,         # Log retention (min 90 days)
    "siem_deployed": True,             # SIEM solution in place
}
```

### Custom SOC2 Controls

Register custom controls for your specific requirements:

```python
checker.register_control(
    id="CC9.1.CUSTOM",
    category=SOC2Category.SECURITY,
    title="Custom Encryption Verification",
    description="Verify AES-256 encryption for all sensitive data",
    check_function=verify_aes256_encryption,
    evidence_required=["encryption_config", "key_strength_report"],
)
```

---

## HIPAA Compliance

HIPAA compliance protects electronic Protected Health Information (ePHI) through Administrative, Physical, and Technical Safeguards.

### Safeguard Types

| Type | Section | Focus Area |
|------|---------|------------|
| Administrative | §164.308 | Workforce security, risk analysis, incident procedures |
| Physical | §164.310 | Facility access, workstation security, device controls |
| Technical | §164.312 | Access control, audit controls, integrity, transmission |
| Organizational | §164.314 | Business associate agreements, group health plans |
| Policies | §164.316 | Documentation requirements, retention |

### Setting Up HIPAA Checks

```python
from autosre.compliance import HIPAAChecker, SafeguardType

checker = HIPAAChecker(covered_entity="Healthcare Corp")

# Define HIPAA compliance context
hipaa_context = {
    # §164.312(a)(1) - Access Control
    "unique_user_ids_enforced": True,
    "automatic_logoff_enabled": True,
    "emergency_access_procedure": True,
    
    # §164.312(b) - Audit Controls
    "audit_logging_enabled": True,
    "audit_log_retention_days": 2190,  # 6 years required
    "regular_log_review": True,
    
    # §164.312(e)(1) - Transmission Security
    "encryption_in_transit": True,
    "encryption_at_rest": True,
    "tls_version": "1.3",
    
    # §164.312(d) - Authentication
    "mfa_enabled": True,
    "password_policy": {
        "min_length": 14,
        "complexity_required": True,
    },
    
    # §164.308(a)(7) - Contingency Plan
    "data_backup_plan": True,
    "disaster_recovery_plan": True,
    "emergency_mode_operation": True,
    "contingency_testing_performed": True,
}

# Run HIPAA checks
report = await checker.generate_report(
    context=hipaa_context,
    phi_scope=["patient_records", "medical_images", "lab_results"],
)

print(f"HIPAA Compliant: {report.compliant}")
print(f"Required Violations: {len(report.get_required_violations())}")
```

### Critical HIPAA Requirements

#### Access Control (§164.312(a)(1))

```python
access_context = {
    "unique_user_ids_enforced": True,   # Unique user identification
    "automatic_logoff_enabled": True,    # Auto session timeout
    "emergency_access_procedure": True,  # Break-glass procedures
    "audit_trail_maintained": True,      # Access audit trail
}
```

#### Audit Controls (§164.312(b))

```python
audit_context = {
    "audit_logging_enabled": True,       # Comprehensive logging
    "audit_log_retention_days": 2190,    # 6-year retention required
    "regular_log_review": True,          # Regular review process
    "tamper_proof_logs": True,           # Immutable audit trail
}
```

#### Transmission Security (§164.312(e)(1))

```python
transmission_context = {
    "encryption_in_transit": True,       # All ePHI encrypted in transit
    "encryption_at_rest": True,          # All ePHI encrypted at rest
    "tls_version": "1.2",                # TLS 1.2 minimum
    "vpn_for_remote_access": True,       # Secure remote access
}
```

### PHI Handling Best Practices

1. **Minimum Necessary** - Only access ePHI required for the task
2. **Encryption Always** - Encrypt ePHI at rest and in transit
3. **Access Logging** - Log all access to ePHI
4. **6-Year Retention** - Retain audit logs for 6 years
5. **Business Associate Agreements** - Document all third-party access

---

## GDPR Compliance

GDPR protects personal data of EU residents through data protection principles and data subject rights.

### Data Protection Principles (Article 5)

| Principle | Article | Description |
|-----------|---------|-------------|
| Lawfulness | 5(1)(a) | Process data lawfully, fairly, transparently |
| Purpose Limitation | 5(1)(b) | Collect for specified, explicit purposes |
| Data Minimization | 5(1)(c) | Adequate, relevant, and limited to necessary |
| Accuracy | 5(1)(d) | Accurate and kept up to date |
| Storage Limitation | 5(1)(e) | Keep only as long as necessary |
| Integrity | 5(1)(f) | Appropriate security measures |
| Accountability | 5(2) | Demonstrate compliance |

### Data Subject Rights (Articles 12-22)

| Right | Article | Description |
|-------|---------|-------------|
| Information | 13-14 | Be informed about data processing |
| Access | 15 | Access their personal data |
| Rectification | 16 | Correct inaccurate data |
| Erasure | 17 | Request deletion (right to be forgotten) |
| Restrict Processing | 18 | Limit processing of data |
| Portability | 20 | Receive data in portable format |
| Object | 21 | Object to processing |
| Automated Decisions | 22 | Not be subject to automated decisions |

### Setting Up GDPR Checks

```python
from autosre.compliance import GDPRChecker, GDPRPrinciple, DataSubjectRight

checker = GDPRChecker(
    data_controller="TechCorp GmbH",
    data_processor="Cloud Provider Inc",
)

# Define GDPR compliance context
gdpr_context = {
    # Article 5(1)(a) - Lawfulness
    "lawful_basis_documented": True,
    "privacy_notices_published": True,
    "consent_mechanism": True,
    "requires_consent": True,
    
    # Article 5(1)(c) - Data Minimization
    "data_inventory_exists": True,
    "data_necessity_reviewed": True,
    "sensitive_data_justified": True,
    "collects_sensitive_data": False,
    
    # Article 5(1)(e) - Storage Limitation
    "retention_policy_exists": True,
    "automated_deletion_enabled": True,
    "deletion_logs_maintained": True,
    
    # Article 32 - Security
    "encryption_enabled": True,
    "pseudonymization_available": True,
    "access_controls_implemented": True,
    "regular_security_testing": True,
    
    # Article 15 - Right of Access
    "access_request_procedure": True,
    "data_export_capability": True,
    "access_request_response_days": 25,  # Must be <= 30
    
    # Article 17 - Right to Erasure
    "deletion_capability": True,
    "cascading_deletion": True,
    "deletion_verification": True,
    
    # Article 33 - Breach Notification
    "breach_detection_capability": True,
    "breach_notification_procedure": True,
    "incident_response_plan": True,
    
    # DPO information
    "dpo_contact": "dpo@techcorp.eu",
    "supervisory_authority": "DE - BfDI",
}

# Run GDPR checks
report = await checker.generate_report(
    context=gdpr_context,
    processing_activities=[
        "customer_account_management",
        "marketing_communications",
        "analytics_processing",
    ],
)

print(f"GDPR Compliant: {report.compliant}")
print(f"Data Controller: {report.data_controller}")

# Review principle compliance
for principle, score in report.principle_scores.items():
    print(f"  {principle.value}: {score:.1%}")
```

### Implementing Data Subject Rights

#### Right of Access (Article 15)

```python
# Context for access request handling
access_right_context = {
    "access_request_procedure": True,    # Documented procedure
    "data_export_capability": True,      # Can export user data
    "access_request_response_days": 25,  # Response within 30 days
    "machine_readable_export": True,     # JSON/CSV export
}
```

#### Right to Erasure (Article 17)

```python
# Context for deletion capability
erasure_context = {
    "deletion_capability": True,         # Can delete user data
    "cascading_deletion": True,          # Deletes from all systems
    "deletion_verification": True,       # Verify deletion complete
    "backup_deletion_policy": True,      # Handle backup deletion
}
```

#### Right to Data Portability (Article 20)

```python
# Context for data portability
portability_context = {
    "portable_export_formats": ["json", "csv", "xml"],
    "api_for_data_export": True,
    "automated_export_capability": True,
}
```

### GDPR Breach Notification

72-hour notification requirement for breaches:

```python
breach_context = {
    "breach_detection_capability": True,     # Can detect breaches
    "breach_notification_procedure": True,   # 72-hour notification process
    "incident_response_plan": True,          # IR plan documented
    "breach_register_maintained": True,      # Record all breaches
    "data_subject_notification": True,       # Notify affected individuals
}
```

---

## PCI-DSS Compliance

PCI-DSS protects cardholder data through 12 requirement categories.

### PCI-DSS Levels

| Level | Criteria | Validation |
|-------|----------|------------|
| Level 1 | > 6M transactions/year | Annual ROC by QSA |
| Level 2 | 1M - 6M transactions/year | Annual SAQ, quarterly scans |
| Level 3 | 20K - 1M e-commerce/year | Annual SAQ, quarterly scans |
| Level 4 | < 20K e-commerce/year | Annual SAQ |

### Requirement Categories

| # | Category | Requirements |
|---|----------|--------------|
| 1-2 | Network Security | Firewalls, secure configurations |
| 3-4 | Cardholder Data | Protect stored data, encrypt transmissions |
| 5-6 | Vulnerability Mgmt | Anti-malware, secure development |
| 7-9 | Access Control | Restrict access, identify users, physical access |
| 10-11 | Monitoring | Logging, security testing |
| 12 | Security Policy | Maintain security policies |

### Setting Up PCI Checks

```python
from autosre.compliance import PCIChecker, PCILevel, PCICategory

checker = PCIChecker(
    merchant_id="MERCHANT-001",
    pci_level=PCILevel.LEVEL_2,
)

# Define PCI-DSS compliance context
pci_context = {
    # Requirement 1 - Network Security
    "firewall_enabled": True,
    "cde_segmented": True,
    "ingress_rules_documented": True,
    
    # Requirement 3.4 - PAN Protection
    "pan_encrypted_at_rest": True,
    "tokenization_enabled": True,
    "pan_masked_in_display": True,
    "encryption_key_rotation_days": 365,
    
    # Requirement 4.2 - Transmission Encryption
    "tls_version": "1.3",
    "certificates_valid": True,
    "hsts_enabled": True,
    
    # Requirement 7.2 - Access Control
    "rbac_enabled": True,
    "least_privilege_enforced": True,
    "quarterly_access_reviews": True,
    
    # Requirement 8.3 - Authentication
    "mfa_enabled": True,
    "password_policy": {
        "min_length": 12,
        "max_age_days": 90,
    },
    "account_lockout_enabled": True,
    
    # Requirement 10.2 - Audit Logging
    "audit_logging_enabled": True,
    "logged_events": [
        "user_access",
        "invalid_access",
        "elevation_of_privilege",
        "audit_log_access",
        "security_events",
    ],
    "log_retention_days": 365,
    
    # Requirement 11.3 - Penetration Testing
    "external_pentest_performed": True,
    "internal_pentest_performed": True,
    "pentest_issues_remediated": True,
    
    # Additional context
    "last_pen_test": datetime(2024, 6, 15),
    "last_vulnerability_scan": datetime(2024, 11, 1),
    "qsa_name": "SecureAudit Inc",
}

# Run PCI-DSS checks
report = await checker.generate_report(
    context=pci_context,
    saq_type="SAQ-A",
)

print(f"PCI-DSS Compliant: {report.compliant}")
print(f"Critical Violations: {len(report.get_critical_violations())}")

# Review category scores
for category, score in report.category_scores.items():
    print(f"  {category.value}: {score:.1%}")
```

### Key PCI Requirements

#### Requirement 3.4 - PAN Protection

```python
pan_context = {
    "pan_encrypted_at_rest": True,        # Encrypt stored PAN
    "tokenization_enabled": True,          # Use tokenization
    "pan_masked_in_display": True,         # Mask PAN in UI
    "encryption_key_rotation_days": 365,   # Annual key rotation
    "full_pan_never_stored": True,         # No full PAN in logs
}
```

#### Requirement 8.3 - Strong Authentication

```python
auth_context = {
    "mfa_enabled": True,                   # MFA for CDE access
    "password_policy": {
        "min_length": 12,                  # Min 12 characters
        "max_age_days": 90,                # 90-day expiration
        "complexity_required": True,       # Alphanumeric + special
    },
    "account_lockout_enabled": True,       # Lockout after failures
    "lockout_threshold": 6,                # Lock after 6 attempts
    "lockout_duration_minutes": 30,        # 30-min lockout
}
```

#### Requirement 11.3 - Penetration Testing

```python
pentest_context = {
    "external_pentest_performed": True,    # Annual external test
    "internal_pentest_performed": True,    # Annual internal test
    "pentest_issues_remediated": True,     # Fix all findings
    "segmentation_tested": True,           # Test network segmentation
    "last_pen_test": datetime(2024, 6, 15),
}
```

---

## Unified Compliance Auditing

Run comprehensive audits across all enabled frameworks:

```python
from autosre.compliance import (
    ComplianceAuditor,
    ComplianceFramework,
    AuditSeverity,
    generate_compliance_dashboard,
)

# Initialize auditor with all frameworks
auditor = ComplianceAuditor(
    organization="Enterprise Corp",
    soc2_enabled=True,
    hipaa_enabled=True,
    gdpr_enabled=True,
    pci_enabled=True,
)

# Comprehensive compliance context
context = {
    # Common security controls
    "rbac_enabled": True,
    "mfa_enforced": True,
    "mfa_enabled": True,
    "encryption_at_rest": True,
    "encryption_in_transit": True,
    "tls_version": "1.3",
    
    # Logging and monitoring
    "centralized_logging": True,
    "audit_logging_enabled": True,
    "log_retention_days": 2190,  # 6 years for HIPAA
    "regular_log_review": True,
    
    # Access management
    "unique_user_ids_enforced": True,
    "automatic_logoff_enabled": True,
    "least_privilege_enforced": True,
    "quarterly_access_reviews": True,
    
    # Data protection
    "data_inventory_exists": True,
    "retention_policy_exists": True,
    "automated_deletion_enabled": True,
    "pan_encrypted_at_rest": True,
    "pan_masked_in_display": True,
    
    # Incident response
    "incident_response_plan": True,
    "breach_notification_procedure": True,
    "contingency_testing_performed": True,
    
    # Password policy
    "password_policy": {
        "min_length": 14,
        "complexity_required": True,
        "max_age_days": 90,
    },
}

# Run full audit
report = await auditor.run_full_audit(
    context=context,
    period_start=datetime.now() - timedelta(days=365),
    period_end=datetime.now(),
    phi_scope=["patient_records"],
    processing_activities=["customer_management"],
    saq_type="SAQ-A",
)

# Analyze results
print(f"Organization: {report.organization}")
print(f"Overall Status: {report.overall_status.value}")
print(f"Frameworks Assessed: {len(report.frameworks_assessed)}")
print(f"Total Findings: {len(report.findings)}")
print(f"Critical Findings: {len(report.critical_findings)}")
print(f"High Findings: {len(report.high_findings)}")

# Framework-specific status
for framework, status in report.framework_status.items():
    print(f"  {framework.value}: {status.value}")

# Get actionable remediations
failed = report.get_failed_findings()
for finding in sorted(failed, key=lambda f: list(AuditSeverity).index(f.severity))[:5]:
    print(f"\n[{finding.severity.value.upper()}] {finding.framework.value} - {finding.requirement_id}")
    print(f"  Title: {finding.title}")
    print(f"  Remediation: {finding.remediation}")
```

### Generating Compliance Dashboard

```python
# Generate dashboard data for visualization
dashboard = generate_compliance_dashboard(report)

print(f"Compliance Percentage: {dashboard['summary']['compliance_percentage']:.1f}%")
print(f"Severity Breakdown: {dashboard['severity_breakdown']}")
print(f"\nTop Remediations:")
for rem in dashboard['top_remediations'][:5]:
    print(f"  - [{rem['severity']}] {rem['title']}")
```

### Scheduling Compliance Checks

Integrate with AutoSRE's scheduling for continuous compliance:

```python
from autosre.operators import ComplianceOperator

# Register compliance operator
operator = ComplianceOperator(
    auditor=auditor,
    schedule="0 2 * * *",  # Daily at 2 AM
    alert_on_critical=True,
    slack_channel="#compliance",
)

# Start continuous compliance monitoring
await operator.start()
```

---

## Compliance Evidence Collection

AutoSRE automatically collects compliance evidence:

### Evidence Types

| Framework | Evidence Types |
|-----------|----------------|
| SOC2 | Access logs, security configs, monitoring data |
| HIPAA | PHI access logs, encryption configs, DR tests |
| GDPR | Consent records, DSAR logs, processing records |
| PCI-DSS | Network configs, pen test reports, scan results |

### Automated Evidence Collection

```python
from autosre.compliance.evidence import EvidenceCollector

collector = EvidenceCollector(
    evidence_storage="s3://compliance-evidence/",
    retention_days=2190,  # 6 years
)

# Collect evidence for audit period
evidence = await collector.collect(
    frameworks=[
        ComplianceFramework.SOC2,
        ComplianceFramework.HIPAA,
    ],
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 12, 31),
)

# Generate evidence package
package = await collector.package_evidence(
    evidence=evidence,
    output_path="/audits/2024_evidence.zip",
)
```

---

## Remediation Workflow

### Tracking Findings

```python
from autosre.compliance.remediation import RemediationTracker

tracker = RemediationTracker()

# Assign findings
for finding in report.get_failed_findings():
    await tracker.create_task(
        finding=finding,
        assigned_to="security-team@company.com",
        due_date=datetime.now() + timedelta(days=30),
        priority="high" if finding.severity in [AuditSeverity.CRITICAL, AuditSeverity.HIGH] else "medium",
    )

# Track progress
progress = await tracker.get_progress()
print(f"Open: {progress['open']}")
print(f"In Progress: {progress['in_progress']}")
print(f"Resolved: {progress['resolved']}")
```

### Integration with Issue Trackers

```python
# Jira integration
tracker.configure_jira(
    url="https://company.atlassian.net",
    project="COMPLIANCE",
    api_token=os.environ["JIRA_TOKEN"],
)

# Create Jira issues for findings
await tracker.sync_to_jira(report.get_failed_findings())
```

---

## Best Practices

### 1. Start with Risk Assessment

Before implementing compliance, conduct a risk assessment:

```python
context["risk_assessment_performed"] = True
context["last_risk_assessment"] = datetime(2024, 6, 1)
context["risk_treatment_plan"] = True
```

### 2. Enable All Relevant Frameworks

Don't just focus on one framework - overlap provides stronger controls:

```python
# If you handle health data AND payments, enable both
auditor = ComplianceAuditor(
    organization="Healthcare Payment Processor",
    hipaa_enabled=True,  # For PHI
    pci_enabled=True,    # For card data
)
```

### 3. Continuous Monitoring

Don't wait for annual audits:

```python
# Schedule daily compliance checks
# Alert on any new critical findings
# Track compliance drift over time
```

### 4. Document Everything

Compliance is about demonstrating controls:

```python
context["policies_documented"] = True
context["procedures_documented"] = True
context["training_records_maintained"] = True
context["audit_trail_maintained"] = True
```

### 5. Regular Testing

Test your controls regularly:

```python
context["annual_security_assessment"] = True
context["quarterly_vulnerability_scans"] = True
context["annual_penetration_test"] = True
context["tabletop_exercises_performed"] = True
```

---

## Troubleshooting

### Common Issues

**Finding: RBAC not enabled**
```python
# Ensure Kubernetes RBAC is properly configured
context["rbac_enabled"] = check_kubernetes_rbac()
```

**Finding: Log retention insufficient**
```python
# Configure log retention for compliance requirements
# HIPAA: 6 years, SOC2: 1 year, PCI-DSS: 1 year
context["log_retention_days"] = 2190  # Max requirement
```

**Finding: Encryption key rotation overdue**
```python
# Implement automated key rotation
context["key_rotation_days"] = 90  # Rotate quarterly
```

### Getting Help

- Check the [API Reference](/reference/api.md#compliance) for detailed method documentation
- See [Examples](/examples/compliance/) for real-world implementations
- Join the [AutoSRE Community](https://community.autosre.io) for support

---

## API Reference

See the full [Compliance API Reference](/reference/api.md#compliance) for:

- `SOC2Checker` methods and controls
- `HIPAAChecker` safeguard definitions
- `GDPRChecker` requirement mappings
- `PCIChecker` requirement details
- `ComplianceAuditor` configuration options
- Report and finding data structures
