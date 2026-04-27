# Security & Compliance Fault Scenarios - Progress Report

**Generated:** 2025-01-21
**Total Scenarios:** 50
**Status:** ✅ COMPLETE

## Summary

All 50 security and compliance fault scenarios have been created for the OpenSRE demo bookstore application.

## Categories

### 1. Authentication/Authorization (10 scenarios) ✅

| # | File | Description |
|---|------|-------------|
| 1 | `rbac-permission-denied.yaml` | Service account lacks RBAC permissions |
| 2 | `token-expired.yaml` | JWT/service token has expired |
| 3 | `certificate-expired.yaml` | mTLS certificate expired |
| 4 | `certificate-revoked.yaml` | Certificate in revocation list |
| 5 | `oidc-provider-down.yaml` | Identity provider unavailable |
| 6 | `api-key-invalid.yaml` | Bad API credentials |
| 7 | `jwt-signature-invalid.yaml` | Tampered or invalid JWT |
| 8 | `mfa-service-down.yaml` | 2FA service unavailable |
| 9 | `session-hijacking-detected.yaml` | Anomalous session activity |
| 10 | `brute-force-detected.yaml` | Rate limiting from attack |

### 2. Secrets Management (10 scenarios) ✅

| # | File | Description |
|---|------|-------------|
| 11 | `secret-rotation-failed.yaml` | Credential rotation failed |
| 12 | `vault-unsealed-error.yaml` | HashiCorp Vault sealed |
| 13 | `vault-connection-failed.yaml` | Secrets backend unreachable |
| 14 | `secret-access-denied.yaml` | Vault policy violation |
| 15 | `encryption-key-missing.yaml` | Cannot decrypt data |
| 16 | `kms-unavailable.yaml` | Cloud KMS down |
| 17 | `secret-version-mismatch.yaml` | Wrong secret version |
| 18 | `env-secret-exposed.yaml` | Secret leaked to logs |
| 19 | `secret-not-mounted.yaml` | Volume mount missing |
| 20 | `sealed-secret-decrypt-failed.yaml` | Bitnami sealed secrets error |

### 3. Network Security (10 scenarios) ✅

| # | File | Description |
|---|------|-------------|
| 21 | `network-policy-too-restrictive.yaml` | Blocking legitimate traffic |
| 22 | `firewall-rule-missing.yaml` | Traffic dropped by firewall |
| 23 | `ddos-attack-detected.yaml` | DDoS attack traffic spike |
| 24 | `port-scan-detected.yaml` | Reconnaissance detected |
| 25 | `ssl-stripping-attempt.yaml` | MITM/downgrade attack |
| 26 | `certificate-chain-incomplete.yaml` | Missing intermediate certs |
| 27 | `cipher-suite-weak.yaml` | Deprecated cipher in use |
| 28 | `hsts-missing.yaml` | No HSTS header |
| 29 | `cors-misconfigured.yaml` | Overly permissive CORS |
| 30 | `egress-blocked.yaml` | Can't reach external service |

### 4. Container Security (10 scenarios) ✅

| # | File | Description |
|---|------|-------------|
| 31 | `privileged-container-detected.yaml` | Container running privileged |
| 32 | `root-user-container.yaml` | Running as root |
| 33 | `capabilities-added.yaml` | Excessive Linux capabilities |
| 34 | `host-network-enabled.yaml` | Using host network namespace |
| 35 | `host-path-mounted.yaml` | Host filesystem mounted |
| 36 | `image-vulnerability-critical.yaml` | Critical CVE detected |
| 37 | `image-not-signed.yaml` | Unsigned container image |
| 38 | `image-registry-unauthorized.yaml` | Pull secret missing |
| 39 | `seccomp-violation.yaml` | Syscall blocked by seccomp |
| 40 | `apparmor-denied.yaml` | LSM blocking operation |

### 5. Compliance (10 scenarios) ✅

| # | File | Description |
|---|------|-------------|
| 41 | `pci-violation-detected.yaml` | Cardholder data exposed |
| 42 | `gdpr-data-leak.yaml` | PII in logs |
| 43 | `hipaa-violation.yaml` | PHI mishandled |
| 44 | `audit-log-gap.yaml` | Missing audit records |
| 45 | `encryption-at-rest-disabled.yaml` | Unencrypted storage |
| 46 | `backup-retention-violation.yaml` | Backups too old |
| 47 | `password-policy-violation.yaml` | Weak credentials |
| 48 | `access-review-overdue.yaml` | Stale permissions |
| 49 | `data-residency-violation.yaml` | Data in wrong region |
| 50 | `license-compliance-failed.yaml` | Software license issue |

## Scenario Structure

Each scenario includes:

- **Metadata**: Labels for category, subcategory, severity, service
- **Description**: What the fault represents
- **Symptoms**: How the fault manifests (errors, logs, metrics, alerts)
- **Root Cause**: Why this happens
- **Detection**: How to identify this fault
- **Remediation**: Steps to fix (automated and manual)
- **Prevention**: How to prevent recurrence
- **Verification**: How to confirm the fix worked
- **References**: Links to relevant documentation

## File Statistics

```
Total files: 50
Total size: ~300KB
Average file size: ~6KB
Location: ~/clawd/projects/opensre/examples/bookstore/faults/
```

## Usage

These scenarios can be used with OpenSRE to:

1. **Train AI models** on security fault diagnosis
2. **Test runbooks** for incident response
3. **Validate monitoring** configurations
4. **Demonstrate** OpenSRE capabilities
5. **Create exercises** for SRE teams

## Next Steps

- [ ] Review scenarios for accuracy
- [ ] Add scenarios to OpenSRE demo
- [ ] Create corresponding remediation runbooks
- [ ] Test scenario injection scripts
- [ ] Generate synthetic telemetry for each scenario
