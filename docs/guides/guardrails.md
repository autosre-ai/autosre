# AI Guardrails Guide

AutoSRE includes enterprise-grade AI safety guardrails to ensure responsible and secure AI operations. This guide covers input/output validation, safety policies, human approval workflows, and comprehensive audit trails.

## Overview

The guardrails module provides four core components:

1. **Validators** - Input sanitization, output filtering, prompt injection detection
2. **Policies** - Risk-based safety policies, action restrictions, rate limiting
3. **Approval** - Human-in-the-loop approval workflows for high-risk actions
4. **Audit** - Immutable audit trails with cryptographic verification

## Quick Start

```python
from autosre.guardrails import (
    # Validators
    InputValidator,
    OutputValidator,
    PromptInjectionDetector,
    
    # Policies
    SafetyPolicy,
    PolicyEngine,
    RiskLevel,
    ActionCategory,
    
    # Approval
    ApprovalWorkflow,
    ApprovalPolicy,
    Approver,
    
    # Audit
    AuditTrail,
    AuditCategory,
)

# Initialize guardrails
input_validator = InputValidator()
policy_engine = PolicyEngine()
approval_workflow = ApprovalWorkflow()
audit_trail = AuditTrail()
```

## Input Validation

### Basic Input Validation

```python
from autosre.guardrails import InputValidator, InputValidationConfig

config = InputValidationConfig(
    max_length=50000,
    detect_injections=True,
    injection_sensitivity=0.7,
    block_code_execution=True,
)

validator = InputValidator(config=config)

# Validate user input
result = await validator.validate(user_input)

if not result.valid:
    print(f"Validation failed: {result.message}")
    print(f"Category: {result.category}")
    print(f"Suggested action: {result.suggested_action}")
else:
    # Safe to process
    sanitized_input = result.sanitized_content or user_input
```

### Prompt Injection Detection

AutoSRE includes robust detection for various injection attacks:

```python
from autosre.guardrails import PromptInjectionDetector, InjectionType

detector = PromptInjectionDetector(sensitivity=0.8)

is_injection, detections = detector.detect(content)

if is_injection:
    for detection in detections:
        print(f"Type: {detection['type']}")
        print(f"Confidence: {detection['confidence']}")
        print(f"Pattern: {detection['pattern']}")
```

Detected injection types:
- `DIRECT` - Direct instruction override attempts
- `JAILBREAK` - Bypass restriction attempts
- `DELIMITER` - Delimiter confusion attacks
- `EXTRACTION` - System prompt extraction
- `ROLEPLAY` - Role manipulation
- `ENCODING` - Encoded malicious content
- `CONTEXT_SWITCH` - Context switching attacks

### Input Sanitization

```python
from autosre.guardrails import (
    InputSanitizer,
    SanitizationRule,
    SanitizationType,
)

rules = [
    SanitizationRule(
        id="mask_creds",
        name="Mask Credentials",
        type=SanitizationType.MASK_CREDENTIALS,
        enabled=True,
    ),
    SanitizationRule(
        id="mask_pii",
        name="Mask PII",
        type=SanitizationType.MASK_PII,
        enabled=True,
    ),
    SanitizationRule(
        id="normalize",
        name="Normalize Unicode",
        type=SanitizationType.NORMALIZE_UNICODE,
    ),
]

sanitizer = InputSanitizer(rules=rules)
sanitized, changes = sanitizer.sanitize(content)

print(f"Made {len(changes)} sanitization changes")
```

## Output Validation

### Content Filtering

```python
from autosre.guardrails import (
    OutputValidator,
    OutputValidationConfig,
    ContentCategory,
)

config = OutputValidationConfig(
    filter_sensitive_data=True,
    filter_pii=True,
    filter_credentials=True,
    max_response_length=100000,
    block_categories=[
        ContentCategory.MALICIOUS,
        ContentCategory.TOXIC,
    ],
)

validator = OutputValidator(config=config)
result = await validator.validate(ai_response)

if result.sanitized_content:
    # Use sanitized version
    safe_response = result.sanitized_content
```

### Schema Validation

```python
from autosre.guardrails import SchemaValidator, ResponseSchemaConfig

config = ResponseSchemaConfig(
    schema={
        "type": "object",
        "required": ["action", "target", "justification"],
        "properties": {
            "action": {"type": "string"},
            "target": {"type": "string"},
            "justification": {"type": "string"},
        },
    },
    strict=True,
    allow_extra_fields=False,
)

validator = SchemaValidator(config=config)
result = await validator.validate(json_response)
```

## Safety Policies

### Policy Configuration

```python
from autosre.guardrails import (
    SafetyPolicy,
    PolicyEngine,
    ActionPolicy,
    ActionRestriction,
    ActionCategory,
    RiskLevel,
    RateLimitConfig,
)

# Create action restrictions
restrictions = [
    ActionRestriction(
        action=ActionCategory.DELETE,
        requires_approval=True,
        requires_justification=True,
        blocked_targets=["production-database"],
        base_risk_level=RiskLevel.HIGH,
    ),
    ActionRestriction(
        action=ActionCategory.DEPLOY,
        requires_approval=True,
        allowed_environments=["staging", "production"],
        time_restrictions=(9, 17),  # Only during business hours
    ),
    ActionRestriction(
        action=ActionCategory.SCALE,
        requires_confirmation=True,
        max_per_hour=10,
    ),
]

# Create policy
policy = SafetyPolicy(
    id="production-policy",
    name="Production Safety Policy",
    action_policies=[
        ActionPolicy(
            id="default",
            name="Default Action Policy",
            restrictions=restrictions,
            blocked_actions=[ActionCategory.DELETE],  # Block all deletes
        ),
    ],
    rate_limits=[
        RateLimitConfig(
            id="api-limit",
            name="API Rate Limit",
            requests_per_minute=60,
            requests_per_hour=1000,
        ),
    ],
    require_approval_for_risk=RiskLevel.HIGH,
    require_justification_for_risk=RiskLevel.MEDIUM,
)
```

### Policy Evaluation

```python
from autosre.guardrails import PolicyEngine, ActionCategory

engine = PolicyEngine(policy=policy)

# Evaluate an action
result = await engine.evaluate(
    action=ActionCategory.DELETE,
    target="user-service-pod",
    context={
        "user_id": "user-123",
        "tenant_id": "acme",
        "environment": "production",
    },
)

print(f"Action: {result.action}")  # ALLOW, DENY, REQUIRE_APPROVAL, etc.
print(f"Reason: {result.reason}")
print(f"Risk Level: {result.risk_assessment.level}")
print(f"Requires Approval: {result.requires_approval}")

if result.action == PolicyAction.REQUIRE_APPROVAL:
    # Trigger approval workflow
    pass
```

### Risk Assessment

```python
# The policy engine performs automatic risk assessment
risk = result.risk_assessment

print(f"Risk Score: {risk.score}")
print(f"Risk Level: {risk.level}")

for factor in risk.factors:
    print(f"  - {factor.name}: {factor.score} (weight: {factor.weight})")
```

Risk factors considered:
- Action type (read vs. modify vs. delete)
- Target environment (development, staging, production)
- Target sensitivity (database, critical service)
- Time of day and day of week
- User permissions and history

## Human Approval Workflows

### Setting Up Approvers

```python
from autosre.guardrails import (
    ApprovalWorkflow,
    ApprovalPolicy,
    Approver,
    ApproverGroup,
    ApprovalLevel,
    ApprovalStrategy,
)

# Register approvers
workflow = ApprovalWorkflow()

workflow.register_approver(Approver(
    id="alice",
    name="Alice Smith",
    email="alice@example.com",
    approval_level=ApprovalLevel.TEAM_LEAD,
    team="platform",
))

workflow.register_approver(Approver(
    id="bob",
    name="Bob Jones",
    email="bob@example.com",
    approval_level=ApprovalLevel.MANAGER,
    team="sre",
))

# Create approver groups
workflow.register_group(ApproverGroup(
    id="sre-leads",
    name="SRE Team Leads",
    members=["alice", "bob"],
    strategy=ApprovalStrategy.ANY,  # Any one can approve
))
```

### Requesting Approval

```python
# Create approval request
request = await workflow.request_approval(
    action="scale_down_production",
    target="api-gateway",
    justification="Reducing capacity during maintenance window",
    requester_id="user-123",
    requester_name="John Doe",
    risk_level="high",
    risk_score=0.75,
    risk_factors=["production", "customer-facing"],
    priority="high",
)

print(f"Request ID: {request.id}")
print(f"Status: {request.status}")
print(f"Expires: {request.expires_at}")
```

### Submitting Decisions

```python
from autosre.guardrails import ApprovalStatus

# Approver submits decision
success, message = await workflow.submit_decision(
    request_id=request.id,
    approver_id="alice",
    decision=ApprovalStatus.APPROVED,
    comment="Approved for maintenance window",
    conditions=["Must complete within 2 hours"],
)

if success:
    print(f"Decision recorded: {message}")
```

### Handling Escalation

```python
from autosre.guardrails import EscalationConfig, EscalationRule

# Configure escalation
escalation_config = EscalationConfig(
    enabled=True,
    rules=[
        EscalationRule(
            id="timeout-escalation",
            name="Timeout Escalation",
            timeout_minutes=30,
            escalate_to=ApprovalLevel.MANAGER,
            max_escalations=3,
        ),
    ],
    default_timeout_minutes=60,
    urgent_timeout_minutes=15,
)

workflow = ApprovalWorkflow(
    escalation_config=escalation_config,
)

# Manual escalation
success, message = await workflow.escalate(
    request_id=request.id,
    reason="Urgent: maintenance window starting soon",
)
```

### Approval Callbacks

```python
async def on_approved(request):
    print(f"Request {request.id} approved!")
    # Execute the action
    await execute_action(request.action, request.target)

async def on_denied(request):
    print(f"Request {request.id} denied")
    # Notify requester
    await notify_requester(request)

workflow.set_callbacks(
    on_approved=on_approved,
    on_denied=on_denied,
)
```

## Audit Trail

### Basic Logging

```python
from autosre.guardrails import (
    AuditTrail,
    AuditCategory,
    AuditSeverity,
)

audit = AuditTrail()

# Log an AI action
entry = await audit.log_ai_action(
    action="scale_deployment",
    target="api-gateway",
    user_id="user-123",
    ai_model="autosre-v2",
    risk_level="medium",
    success=True,
    details={
        "replicas_before": 3,
        "replicas_after": 5,
        "reason": "High latency detected",
    },
    tenant_id="acme",
    session_id="session-456",
)

print(f"Audit entry: {entry.id}")
print(f"Hash: {entry.entry_hash}")
```

### Logging AI Requests/Responses

```python
# Log AI request
await audit.log_ai_request(
    request_id="req-123",
    model="gpt-4",
    prompt="Analyze the current system metrics...",
    user_id="user-123",
    tenant_id="acme",
)

# Log AI response
await audit.log_ai_response(
    request_id="req-123",
    model="gpt-4",
    response="Based on the metrics...",
    user_id="user-123",
    tokens_used=1500,
    latency_ms=2500,
)
```

### Querying Audit Logs

```python
from autosre.guardrails import AuditQuery
from datetime import datetime, timedelta

query = AuditQuery(
    start_time=datetime.utcnow() - timedelta(hours=24),
    end_time=datetime.utcnow(),
    categories=[AuditCategory.AI_ACTION],
    severities=[AuditSeverity.WARNING, AuditSeverity.ERROR],
    actor_types=["ai"],
    failure_only=True,
    limit=100,
)

entries = await audit.query(query)

for entry in entries:
    print(f"{entry.timestamp}: {entry.message}")
```

### Integrity Verification

The audit trail uses a cryptographic hash chain for tamper detection:

```python
# Verify integrity
check = await audit.verify_integrity(
    start_time=datetime.utcnow() - timedelta(days=7),
    end_time=datetime.utcnow(),
)

if check.valid:
    print(f"✓ Verified {check.checked_entries} entries")
else:
    print(f"✗ Integrity check failed!")
    print(f"  Invalid entries: {check.invalid_entries}")
    print(f"  Chain broken at: {check.broken_chain_at}")
```

### Compliance Reporting

```python
from autosre.guardrails import ComplianceFramework

# Configure compliance frameworks
audit = AuditTrail(
    compliance_frameworks=[
        ComplianceFramework.SOC2,
        ComplianceFramework.HIPAA,
        ComplianceFramework.GDPR,
    ],
)

# Generate compliance report
report = await audit.generate_report(
    start_time=datetime.utcnow() - timedelta(days=30),
    end_time=datetime.utcnow(),
    name="Monthly Compliance Report",
)

print(f"Total entries: {report.total_entries}")
print(f"Success rate: {report.success_rate:.1f}%")
print(f"Integrity verified: {report.integrity_verified}")

for framework, compliant in report.compliance_status.items():
    status = "✓" if compliant else "✗"
    print(f"  {status} {framework}")
```

### Persistent Storage

```python
from autosre.guardrails import FileAuditStorage

# Use file-based storage with rotation
storage = FileAuditStorage(
    base_path="/var/log/autosre/audit",
    rotation_size_mb=100,
)

audit = AuditTrail(storage=storage)
```

## Integration Example

Here's a complete example integrating all guardrail components:

```python
from autosre.guardrails import (
    InputValidator,
    OutputValidator,
    PolicyEngine,
    ApprovalWorkflow,
    AuditTrail,
    SafetyPolicy,
    PolicyAction,
    AuditCategory,
)

class GuardedAIAgent:
    """AI agent with full guardrails integration."""
    
    def __init__(self):
        self.input_validator = InputValidator()
        self.output_validator = OutputValidator()
        self.policy_engine = PolicyEngine()
        self.approval_workflow = ApprovalWorkflow()
        self.audit = AuditTrail()
    
    async def execute_action(
        self,
        action: str,
        target: str,
        user_input: str,
        user_id: str,
        context: dict,
    ) -> dict:
        request_id = generate_request_id()
        
        # 1. Validate input
        input_result = await self.input_validator.validate(user_input)
        if not input_result.valid:
            await self.audit.log_validation(
                validation_type="input",
                result=False,
                details={"reason": input_result.message},
                request_id=request_id,
            )
            return {"error": "Invalid input", "details": input_result.message}
        
        # 2. Check policy
        policy_result = await self.policy_engine.evaluate(
            action=action,
            target=target,
            context={**context, "user_id": user_id},
        )
        
        await self.audit.log_policy_check(
            policy_id=policy_result.policy_id,
            policy_name=policy_result.policy_name,
            action=action,
            result=policy_result.action.value,
            risk_level=policy_result.risk_assessment.level.value,
            request_id=request_id,
        )
        
        # 3. Handle policy result
        if policy_result.action == PolicyAction.DENY:
            return {"error": "Action denied", "reason": policy_result.reason}
        
        if policy_result.requires_approval:
            # Request approval
            approval = await self.approval_workflow.request_approval(
                action=action,
                target=target,
                justification=user_input,
                requester_id=user_id,
                requester_name=context.get("user_name", "Unknown"),
                risk_level=policy_result.risk_assessment.level.value,
            )
            return {
                "pending_approval": True,
                "approval_id": approval.id,
                "expires_at": approval.expires_at.isoformat(),
            }
        
        # 4. Execute action
        result = await self._execute(action, target)
        
        # 5. Validate output
        output_result = await self.output_validator.validate(
            str(result)
        )
        
        # 6. Log action
        await self.audit.log_ai_action(
            action=action,
            target=target,
            user_id=user_id,
            success=True,
            request_id=request_id,
        )
        
        return result
```

## Best Practices

### 1. Defense in Depth

Apply multiple layers of validation:

```python
# Layer 1: Input validation
input_result = await input_validator.validate(user_input)

# Layer 2: Policy check
policy_result = await policy_engine.evaluate(action, target, context)

# Layer 3: Schema validation (if applicable)
schema_result = await schema_validator.validate(structured_data)

# Layer 4: Output validation
output_result = await output_validator.validate(ai_response)
```

### 2. Fail Secure

Always default to denying unsafe actions:

```python
try:
    result = await process_with_guardrails(action)
except Exception as e:
    # Log the error
    await audit.log(
        category=AuditCategory.SYSTEM_ERROR,
        event_type="guardrail_failure",
        message=str(e),
        severity=AuditSeverity.ERROR,
    )
    # Fail secure - deny the action
    return {"error": "System error, action denied for safety"}
```

### 3. Audit Everything

Log all significant events for compliance and debugging:

```python
# Log the request
await audit.log_ai_request(...)

# Log policy decisions
await audit.log_policy_check(...)

# Log approvals
await audit.log_approval_decision(...)

# Log the action
await audit.log_ai_action(...)

# Log errors
await audit.log(category=AuditCategory.AI_ERROR, ...)
```

### 4. Regular Integrity Checks

Schedule regular verification of audit trail integrity:

```python
import asyncio
from datetime import datetime, timedelta

async def daily_integrity_check():
    while True:
        check = await audit.verify_integrity(
            start_time=datetime.utcnow() - timedelta(days=1),
            end_time=datetime.utcnow(),
        )
        
        if not check.valid:
            # Alert security team
            await alert_security_team(check)
        
        await asyncio.sleep(86400)  # 24 hours
```

### 5. Environment-Specific Policies

Use different policies for different environments:

```python
from autosre.guardrails import create_default_policy

# Development - more permissive
dev_policy = create_default_policy(
    environment="development",
    strict=False,
)

# Production - strict controls
prod_policy = create_default_policy(
    environment="production",
    strict=True,
)

# Select based on environment
policy = prod_policy if env == "production" else dev_policy
engine = PolicyEngine(policy=policy)
```

## Configuration Reference

### Environment Variables

```bash
# Guardrails settings
AUTOSRE_GUARDRAILS_ENABLED=true
AUTOSRE_INJECTION_SENSITIVITY=0.7
AUTOSRE_MAX_INPUT_LENGTH=100000
AUTOSRE_MAX_OUTPUT_LENGTH=500000

# Approval settings
AUTOSRE_APPROVAL_TIMEOUT_MINUTES=60
AUTOSRE_APPROVAL_ESCALATION_ENABLED=true

# Audit settings
AUTOSRE_AUDIT_STORAGE_PATH=/var/log/autosre/audit
AUTOSRE_AUDIT_ROTATION_SIZE_MB=100
AUTOSRE_AUDIT_RETENTION_DAYS=365
```

### Policy YAML Format

```yaml
# guardrails-policy.yaml
id: production-policy
name: Production Safety Policy
version: "1.0.0"

risk_thresholds:
  negligible_max: 0.1
  low_max: 0.3
  medium_max: 0.5
  high_max: 0.7
  critical_max: 0.9

action_policies:
  - id: default
    name: Default Actions
    restrictions:
      - action: delete
        requires_approval: true
        blocked_targets:
          - production-database
      - action: deploy
        allowed_environments:
          - staging
          - production

rate_limits:
  - id: api-limit
    requests_per_minute: 60
    requests_per_hour: 1000

require_approval_for_risk: high
require_justification_for_risk: medium
```

## See Also

- [Cost Optimization Guide](./cost.md)
- [Communications Guide](./communications.md)
- [Chaos Engineering Guide](./chaos.md)
- [Multi-Tenancy Guide](./tenancy.md)
