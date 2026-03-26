# Certificate Expiry Checker Agent

Daily scan for expiring SSL/TLS certificates with tiered alerts at 30/14/7 days before expiry.

## Overview

This agent monitors SSL certificates across multiple sources and:
1. Scans Kubernetes TLS secrets
2. Checks external endpoints
3. Queries AWS ACM certificates
4. Categorizes by expiry urgency
5. Sends tiered alerts based on days remaining
6. Optionally triggers auto-renewal for supported certificates

## Triggers

### Scheduled (Primary)
- **Cron:** `0 8 * * *` (Daily at 8 AM UTC)

### Manual Webhook
- **Path:** `/webhook/cert-check`
- **Use:** On-demand certificate audit

## Configuration

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `slack_channel` | string | `#security-alerts` | Alert channel |
| `alert_thresholds_days` | list | `[30, 14, 7, 3, 1]` | Days before expiry to alert |
| `critical_threshold_days` | int | `7` | Days considered critical |
| `sources` | list | See below | Certificate sources |
| `auto_renew_enabled` | bool | `false` | Auto-renew ACM certs |
| `pagerduty_on_critical` | bool | `true` | Page on critical/expired |

### Sources Configuration
```yaml
sources:
  - type: kubernetes
    namespaces: ["*"]  # All namespaces
    secret_types: ["kubernetes.io/tls"]
  - type: endpoints
    urls:
      - https://api.example.com
      - https://www.example.com
  - type: acm
    regions: ["us-east-1", "us-west-2"]
  - type: files
    paths:
      - /etc/ssl/certs/custom.pem
```

## Required Skills

- **ssl** - Certificate parsing and endpoint checks
- **kubernetes** - TLS secret scanning
- **slack** - Notifications
- **pagerduty** - Critical alerts
- **jira** - Renewal tickets
- **aws** - ACM certificate listing

## Workflow

```
┌─────────────────────┐
│  Daily Schedule     │
│  (8 AM UTC)         │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Scan Sources       │
│  - K8s Secrets      │
│  - Endpoints        │
│  - AWS ACM          │
│  - Files            │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Aggregate &        │
│  Parse Certs        │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Categorize by      │
│  Days Remaining     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│              Tiered Alerts              │
├─────────┬─────────┬─────────┬───────────┤
│ Expired │Critical │ Warning │ Attention │
│ 🚨      │ ⚠️ ≤7d  │ 📋 8-14d│ 📅 15-30d │
└────┬────┴────┬────┴────┬────┴─────┬─────┘
     │         │         │          │
     ▼         ▼         ▼          ▼
┌────────┐┌─────────┐┌───────┐┌──────────┐
│PagerDuty││Jira     ││Slack  ││Slack     │
│Page    ││Tickets  ││Alert  ││Notice    │
└────────┘└─────────┘└───────┘└──────────┘
```

## Alert Tiers

| Category | Days Remaining | Actions |
|----------|---------------|---------|
| Expired | < 0 | Slack (urgent), PagerDuty |
| Critical | 0-7 | Slack (warning), PagerDuty, Jira ticket |
| Warning | 8-14 | Slack notification |
| Attention | 15-30 | Slack notice |
| Healthy | > 30 | No alert (metrics only) |

## Certificate Sources

### Kubernetes TLS Secrets
Scans all namespaces for secrets of type `kubernetes.io/tls`:
```yaml
apiVersion: v1
kind: Secret
type: kubernetes.io/tls
data:
  tls.crt: <base64>
  tls.key: <base64>
```

### External Endpoints
Connects to HTTPS endpoints and extracts certificate info:
- Common Name
- Issuer
- Expiry Date
- Subject Alternative Names

### AWS ACM
Lists certificates from AWS Certificate Manager:
- Issued certificates
- Pending validation certificates

## Auto-Renewal

When `auto_renew_enabled: true`:
- ACM certificates are automatically requested for renewal
- Kubernetes cert-manager certificates trigger renewal annotation
- Manual certificates are flagged for attention

## Metrics

Pushed to Prometheus:
- `opensre_cert_total` - Total certificates scanned
- `opensre_cert_expired` - Expired count
- `opensre_cert_critical` - Critical count (≤7 days)
- `opensre_cert_warning` - Warning count (8-14 days)
- `opensre_cert_healthy` - Healthy count (>30 days)

## Testing

```bash
# Run unit tests
pytest test_agent.py -v

# Manual trigger
curl -X POST http://localhost:8080/webhook/cert-check

# Check specific endpoint
openssl s_client -connect example.com:443 -servername example.com 2>/dev/null | \
  openssl x509 -noout -dates
```

## Example Output

### Critical Alert
```
⚠️ Certificates Expiring Within 7 Days

3 certificate(s) expiring soon:

• api.example.com - 5 days remaining
  Expires: 2024-01-20
  Source: kubernetes

• www.example.com - 3 days remaining
  Expires: 2024-01-18
  Source: endpoints

• *.internal.example.com - 7 days remaining
  Expires: 2024-01-22
  Source: acm

[🔄 Renew Now]
```

### Daily Summary (No Issues)
```
✅ Certificate Check Complete - 2024-01-15

All 45 certificates healthy (>30 days until expiry)
Next check: 2024-01-16 08:00 UTC
```
