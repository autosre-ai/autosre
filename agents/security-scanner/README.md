# Security Scanner Agent

Comprehensive security scanning for container images, Kubernetes configurations, and compliance standards.

## Overview

The Security Scanner agent performs daily security scans to detect CVEs in container images, identify Kubernetes misconfigurations, and verify compliance with security standards (CIS, PCI-DSS, HIPAA).

## Features

- **CVE Detection** - Scan running images for known vulnerabilities
- **Severity-based Alerting** - Page on critical, alert on high
- **SLA Tracking** - Monitor remediation SLAs (7 days critical, 30 days high)
- **Compliance Checking** - CIS, PCI-DSS, HIPAA benchmarks
- **Configuration Scanning** - Detect misconfigurations and secrets
- **Auto-ticketing** - Create Jira tickets for critical CVEs
- **AI Prioritization** - Intelligent remediation recommendations

## Configuration

```yaml
config:
  slack_channel: "#security-alerts"
  severity_thresholds:
    page: ["CRITICAL"]
    alert: ["HIGH", "CRITICAL"]
    report: ["MEDIUM", "HIGH", "CRITICAL"]
  scan_targets:
    namespaces:
      - production
      - staging
    registries:
      - "gcr.io/company-project"
  compliance_standards:
    - CIS
    - PCI-DSS
  max_age_days_critical: 7   # SLA for critical CVEs
  max_age_days_high: 30      # SLA for high CVEs
  enable_auto_ticket: true
```

## Scan Types

### Image Vulnerability Scanning
Uses Trivy to scan all running container images:
- Extracts unique images from all pods
- Scans for known CVEs
- Identifies fixed versions available

### Kubernetes Configuration Scanning
Checks for:
- RBAC misconfigurations
- Secrets in environment variables
- Privileged containers
- Host network/PID access
- Missing security contexts

### Compliance Scanning
Validates against:
- **CIS Kubernetes Benchmark** - Best practices
- **PCI-DSS** - Payment card industry
- **HIPAA** - Healthcare data

## Triggers

- **Schedule**: Daily at 2 AM UTC
- **Manual**: `/webhook/security-scan`
- **Registry Push**: `/webhook/image-push`

## Alert Examples

### Critical CVE Alert (Slack)
```
🚨 Critical Vulnerabilities Detected

Critical: 5
High: 23
Scan Date: 2024-01-15
Images Scanned: 47

Top Critical CVEs:
• CVE-2024-1234 - Remote code execution in libxml2
  CVSS: 9.8 | Fix: 2.9.14
• CVE-2024-5678 - SQL injection in postgresql
  CVSS: 9.1 | Fix: 15.4
```

### SLA Violation (PagerDuty)
```
Critical CVE SLA Violation - 3 overdue

- CVE-2024-1111: Buffer overflow
  Published: 2024-01-01
  Days overdue: 14
  Affected: api-server, worker
```

## Jira Integration

When `enable_auto_ticket: true`, creates tickets for critical CVEs:

```yaml
Summary: [CVE-2024-1234] Remote code execution in libxml2
Priority: Blocker
Labels: security, cve, critical, auto-generated
Due Date: 7 days from detection
```

## Metrics

| Metric | Description |
|--------|-------------|
| `opensre_security_vulns_total` | Total vulnerabilities found |
| `opensre_security_vulns_critical` | Critical CVE count |
| `opensre_security_vulns_high` | High CVE count |
| `opensre_security_compliance_score` | Overall compliance score |
| `opensre_security_sla_violations` | CVEs exceeding SLA |

## Prerequisites

- Trivy installed or available as skill
- Kubernetes cluster access
- Container registry credentials
- Slack, PagerDuty, Jira configured

## Usage

```bash
# Full scan
opensre agent run agents/security-scanner/agent.yaml

# Dry run
opensre agent run agents/security-scanner/agent.yaml --dry-run

# Scan specific namespace
opensre agent run agents/security-scanner/agent.yaml \
  -c "config.scan_targets.namespaces=['production']"
```

## Security Considerations

- Agent requires read access to all namespaces
- Registry credentials needed for private images
- Scan results may contain sensitive paths
- Store reports securely

## Related Agents

- [cert-checker](../cert-checker/) - SSL/TLS certificate monitoring
- [change-detector](../change-detector/) - Track security-relevant changes
- [incident-responder](../incident-responder/) - Respond to security incidents
