"""
AI Guardrails Module for AutoSRE

Enterprise-grade AI safety with input/output validation, safety policies,
human approval workflows, and comprehensive audit trails.

Features:
- Input sanitization and validation
- Output content filtering and classification
- Risk-based safety policies
- Human-in-the-loop approval workflows
- Immutable audit trails with cryptographic verification
"""

from autosre.guardrails.validators import (
    # Base classes
    Validator,
    ValidationResult,
    ValidationSeverity,
    # Input validation
    InputValidator,
    InputValidationConfig,
    ContentCategory,
    InputSanitizer,
    SanitizationRule,
    SanitizationType,
    # Output validation
    OutputValidator,
    OutputValidationConfig,
    OutputClassification,
    ContentFilter,
    FilterAction,
    # Prompt validation
    PromptValidator,
    PromptInjectionDetector,
    InjectionType,
    # Schema validation
    SchemaValidator,
    ResponseSchemaConfig,
)

from autosre.guardrails.policies import (
    # Policy framework
    SafetyPolicy,
    PolicyEngine,
    PolicyResult,
    PolicyAction,
    PolicyScope,
    # Risk management
    RiskLevel,
    RiskAssessment,
    RiskFactor,
    RiskThreshold,
    # Action policies
    ActionPolicy,
    ActionRestriction,
    ActionCategory,
    AllowedAction,
    # Rate limiting
    RateLimiter,
    RateLimitConfig,
    RateLimitScope,
    # Context policies
    ContextPolicy,
    SensitiveDataPolicy,
    DataClassification,
)

from autosre.guardrails.approval import (
    # Approval workflow
    ApprovalWorkflow,
    ApprovalRequest,
    ApprovalDecision,
    ApprovalStatus,
    ApprovalLevel,
    # Approvers
    Approver,
    ApproverGroup,
    ApprovalPolicy,
    ApprovalStrategy,
    # Escalation
    EscalationConfig,
    EscalationRule,
    # Notifications
    ApprovalNotifier,
    NotificationConfig,
)

from autosre.guardrails.audit import (
    # Audit trail
    AuditTrail,
    AuditEntry,
    AuditCategory,
    AuditSeverity,
    # Verification
    AuditVerifier,
    IntegrityCheck,
    HashChain,
    # Storage
    AuditStorage,
    AuditQuery,
    AuditReport,
    # Compliance
    ComplianceChecker,
    ComplianceFramework,
    ComplianceReport,
)

__all__ = [
    # Validators
    "Validator",
    "ValidationResult",
    "ValidationSeverity",
    "InputValidator",
    "InputValidationConfig",
    "ContentCategory",
    "InputSanitizer",
    "SanitizationRule",
    "SanitizationType",
    "OutputValidator",
    "OutputValidationConfig",
    "OutputClassification",
    "ContentFilter",
    "FilterAction",
    "PromptValidator",
    "PromptInjectionDetector",
    "InjectionType",
    "SchemaValidator",
    "ResponseSchemaConfig",
    # Policies
    "SafetyPolicy",
    "PolicyEngine",
    "PolicyResult",
    "PolicyAction",
    "PolicyScope",
    "RiskLevel",
    "RiskAssessment",
    "RiskFactor",
    "RiskThreshold",
    "ActionPolicy",
    "ActionRestriction",
    "ActionCategory",
    "AllowedAction",
    "RateLimiter",
    "RateLimitConfig",
    "RateLimitScope",
    "ContextPolicy",
    "SensitiveDataPolicy",
    "DataClassification",
    # Approval
    "ApprovalWorkflow",
    "ApprovalRequest",
    "ApprovalDecision",
    "ApprovalStatus",
    "ApprovalLevel",
    "Approver",
    "ApproverGroup",
    "ApprovalPolicy",
    "ApprovalStrategy",
    "EscalationConfig",
    "EscalationRule",
    "ApprovalNotifier",
    "NotificationConfig",
    # Audit
    "AuditTrail",
    "AuditEntry",
    "AuditCategory",
    "AuditSeverity",
    "AuditVerifier",
    "IntegrityCheck",
    "HashChain",
    "AuditStorage",
    "AuditQuery",
    "AuditReport",
    "ComplianceChecker",
    "ComplianceFramework",
    "ComplianceReport",
]
