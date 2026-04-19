# Security

OpenSRE's security model is designed to protect your infrastructure while enabling powerful automation.

## Security Philosophy

1. **Least Privilege** — Agents only get permissions they need
2. **Human-in-the-Loop** — Dangerous actions require approval
3. **Audit Everything** — All actions are logged
4. **Defense in Depth** — Multiple layers of protection

---

## Authentication

### API Authentication

All API requests require authentication:

```bash
# Bearer token authentication
curl -H "Authorization: Bearer <api-key>" \
  http://localhost:8000/api/v1/status
```

Generate API keys:

```bash
opensre auth create-key --name "ci-cd" --expires 30d
```

### Webhook Verification

#### Alertmanager

Configure a shared secret:

```yaml
# alertmanager.yml
receivers:
  - name: opensre
    webhook_configs:
      - url: http://opensre:8000/webhook/alertmanager
        http_config:
          authorization:
            credentials: <shared-secret>
```

#### PagerDuty

OpenSRE verifies PagerDuty webhook signatures:

```yaml
# config/opensre.yaml
pagerduty:
  webhook_secret: ${PAGERDUTY_WEBHOOK_SECRET}
```

#### Slack

Slack requests are verified using signing secrets:

```yaml
slack:
  signing_secret: ${SLACK_SIGNING_SECRET}
```

---

## Authorization

### Role-Based Access Control (RBAC)

Define roles with specific permissions:

```yaml
# config/opensre.yaml
rbac:
  roles:
    viewer:
      permissions:
        - "read:*"
        - "investigate:*"
      
    operator:
      permissions:
        - "read:*"
        - "investigate:*"
        - "execute:safe"
        - "approve:standard"
      
    admin:
      permissions:
        - "*"

  users:
    alice@example.com:
      roles: [admin]
    
    bob@example.com:
      roles: [operator]
```

### Permission Types

| Permission | Description |
|------------|-------------|
| `read:*` | Read any resource |
| `investigate:*` | Trigger investigations |
| `execute:safe` | Execute read-only actions |
| `execute:write` | Execute write actions |
| `approve:standard` | Approve standard actions |
| `approve:critical` | Approve critical actions |
| `admin:*` | Full administrative access |

---

## Action Safety

### Action Classification

Actions are classified by risk level:

| Level | Description | Examples | Approval |
|-------|-------------|----------|----------|
| **safe** | Read-only, no side effects | `prometheus.query`, `kubernetes.get_pods` | Auto-approved |
| **standard** | Minor changes, reversible | `slack.post_message`, `kubernetes.restart` | Configurable |
| **critical** | Major changes, potentially destructive | `kubernetes.delete`, `kubernetes.rollback` | Required |
| **dangerous** | Irreversible operations | `aws.terminate_instance` | Always required |

### Approval Workflow

When an action requires approval:

1. Agent requests action execution
2. OpenSRE posts approval request to Slack
3. Authorized user approves/denies via button
4. Action executes (or is cancelled)
5. Result is posted back

```
╭──────────────────────────────────────────────╮
│ 🔐 Approval Required                          │
├──────────────────────────────────────────────┤
│ Action: kubernetes.rollback                  │
│ Target: checkout-service (production)        │
│ Requested by: incident-responder agent       │
│ Reason: Memory leak detected in v2.4.1       │
│                                              │
│ [✅ Approve]  [❌ Deny]  [👁️ Details]         │
╰──────────────────────────────────────────────╯
```

### Configuring Approvals

```yaml
# config/opensre.yaml
safety:
  # Auto-approve these patterns
  auto_approve:
    - "prometheus.*"
    - "kubernetes.get_*"
    - "kubernetes.describe_*"
    - "slack.post_*"
  
  # Always require approval
  require_approval:
    - "kubernetes.rollback"
    - "kubernetes.delete_*"
    - "kubernetes.scale"
    - "aws.terminate_*"
    - "gcp.delete_*"
  
  # Approval timeout
  approval_timeout: 300  # 5 minutes
  
  # Who can approve
  approvers:
    - group: "@sre-team"
    - user: "alice@example.com"
```

---

## Protected Resources

### Protected Namespaces

Certain namespaces require extra confirmation:

```yaml
safety:
  protected_namespaces:
    - production
    - kube-system
    - monitoring
    - cert-manager
```

Actions on protected namespaces:
- Require explicit approval even if normally auto-approved
- Log with elevated audit level
- Send notifications to security channel

### Resource Allowlists/Blocklists

Control which resources agents can access:

```yaml
safety:
  # Only allow operations on these
  allowlist:
    namespaces:
      - staging
      - production
    services:
      - checkout-*
      - payment-*
  
  # Never operate on these
  blocklist:
    namespaces:
      - kube-system
      - secrets-*
    deployments:
      - prometheus
      - grafana
```

---

## Audit Logging

### What's Logged

Every action includes:

- Timestamp
- User/agent identity
- Action requested
- Parameters
- Target resources
- Approval status
- Result (success/failure)
- Duration

### Log Format

```json
{
  "timestamp": "2024-03-15T14:32:05.123Z",
  "event_type": "action_executed",
  "agent": "incident-responder",
  "action": "kubernetes.rollback",
  "params": {
    "deployment": "checkout-service",
    "namespace": "production"
  },
  "approval": {
    "required": true,
    "approved_by": "alice@example.com",
    "approved_at": "2024-03-15T14:31:55.000Z"
  },
  "result": {
    "status": "success",
    "duration_ms": 2340
  }
}
```

### Log Destinations

```yaml
audit:
  # Local file
  file:
    enabled: true
    path: /var/log/opensre/audit.log
    rotation: daily
    retention: 90d
  
  # Stdout (for container logs)
  stdout:
    enabled: true
    format: json
  
  # External systems
  elasticsearch:
    enabled: true
    host: elasticsearch:9200
    index: opensre-audit
  
  splunk:
    enabled: false
    hec_url: https://splunk:8088
    token: ${SPLUNK_HEC_TOKEN}
```

---

## Secret Management

### Sensitive Data Handling

- API keys and tokens are never logged
- Secrets are masked in UI outputs
- Memory is cleared after use where possible

### Secret Storage

#### Environment Variables

```bash
export OPENSRE_OPENAI_API_KEY=sk-...
export OPENSRE_SLACK_BOT_TOKEN=xoxb-...
```

#### Kubernetes Secrets

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: opensre-secrets
type: Opaque
stringData:
  openai-api-key: sk-...
  slack-bot-token: xoxb-...
```

#### HashiCorp Vault

```yaml
secrets:
  provider: vault
  vault:
    address: https://vault.example.com
    path: secret/data/opensre
    auth:
      method: kubernetes
      role: opensre
```

#### AWS Secrets Manager

```yaml
secrets:
  provider: aws-secrets-manager
  aws:
    region: us-east-1
    secret_name: opensre/production
```

---

## Network Security

### TLS Configuration

```yaml
server:
  tls:
    enabled: true
    cert_file: /etc/opensre/tls.crt
    key_file: /etc/opensre/tls.key
    min_version: TLS1.2
```

### Network Policies

Kubernetes NetworkPolicy for OpenSRE:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: opensre
  namespace: opensre
spec:
  podSelector:
    matchLabels:
      app: opensre
  policyTypes:
    - Ingress
    - Egress
  ingress:
    # Allow from Alertmanager
    - from:
        - namespaceSelector:
            matchLabels:
              name: monitoring
        - podSelector:
            matchLabels:
              app: alertmanager
      ports:
        - port: 8000
  egress:
    # Allow to Prometheus
    - to:
        - namespaceSelector:
            matchLabels:
              name: monitoring
      ports:
        - port: 9090
    # Allow to Kubernetes API
    - to:
        - ipBlock:
            cidr: 10.0.0.1/32
      ports:
        - port: 443
```

---

## LLM Security

### Data Privacy

By default, OpenSRE sends context to LLMs. Consider:

1. **Use Local LLMs** — Ollama keeps data on your network
2. **Enable Redaction** — Automatically redact sensitive data
3. **Limit Context** — Control what data is sent

```yaml
llm:
  provider: ollama  # Local, no external calls
  
  # OR with redaction for cloud LLMs
  provider: openai
  privacy:
    redact_secrets: true
    redact_patterns:
      - '\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'  # Emails
      - '\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'                # IPs
    exclude_fields:
      - password
      - token
      - secret
      - key
```

### Prompt Injection Protection

OpenSRE sanitizes LLM inputs to prevent prompt injection:

- User inputs are escaped and quoted
- System prompts are protected
- Outputs are validated before execution

---

## Compliance

### SOC 2

OpenSRE supports SOC 2 compliance with:

- Comprehensive audit logging
- Access control (RBAC)
- Encryption in transit (TLS)
- Secure secret management

### GDPR

For GDPR compliance:

- Use local LLMs (Ollama)
- Enable data redaction
- Configure log retention
- Implement right to deletion

### PCI DSS

For PCI DSS environments:

- Deploy in isolated network segment
- Enable all security controls
- Use hardware security modules for secrets
- Enable comprehensive audit logging

---

## Security Checklist

### Production Deployment

- [ ] TLS enabled for all endpoints
- [ ] API keys rotated and secured
- [ ] RBAC configured with least privilege
- [ ] Protected namespaces defined
- [ ] Audit logging enabled
- [ ] Network policies applied
- [ ] Secrets in secret manager (not env vars)
- [ ] Approval workflows configured
- [ ] LLM privacy settings reviewed

### Monitoring

- [ ] Audit logs forwarded to SIEM
- [ ] Failed auth attempts alerted
- [ ] Action approval timeouts monitored
- [ ] API key usage tracked

---

## Reporting Security Issues

Found a security vulnerability? Please report it responsibly:

**Email:** security@opensre.dev

**Do not** open public GitHub issues for security vulnerabilities.

We'll acknowledge receipt within 24 hours and work with you on a fix.

---

## Next Steps

- **[Deployment](DEPLOYMENT.md)** — Secure production deployment
- **[Configuration](CONFIGURATION.md)** — Security settings
- **[API Reference](api-reference.md)** — API security
