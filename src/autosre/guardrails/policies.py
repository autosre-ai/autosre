"""
Safety Policies for AI Operations

Provides policy-based safety controls for AI agent actions:
- Risk assessment framework
- Action restrictions and permissions
- Rate limiting and quotas
- Context-aware policy enforcement
"""

import hashlib
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, UTC, timezone
from enum import Enum
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    """Risk levels for AI actions."""
    
    NEGLIGIBLE = "negligible"  # No risk, always allow
    LOW = "low"               # Minor risk, allow with logging
    MEDIUM = "medium"         # Moderate risk, require confirmation
    HIGH = "high"             # Significant risk, require approval
    CRITICAL = "critical"     # Severe risk, require multi-approval
    PROHIBITED = "prohibited" # Never allow


class PolicyAction(str, Enum):
    """Actions a policy can take."""
    
    ALLOW = "allow"               # Allow the action
    ALLOW_WITH_LOGGING = "allow_with_logging"  # Allow but log extensively
    REQUIRE_CONFIRMATION = "require_confirmation"  # User must confirm
    REQUIRE_APPROVAL = "require_approval"  # Approver must approve
    REQUIRE_MULTI_APPROVAL = "require_multi_approval"  # Multiple approvers
    DENY = "deny"                 # Deny the action
    ESCALATE = "escalate"         # Escalate to human operator


class PolicyScope(str, Enum):
    """Scope of policy application."""
    
    GLOBAL = "global"           # Applies to all tenants/users
    TENANT = "tenant"           # Applies to specific tenant
    WORKSPACE = "workspace"     # Applies to specific workspace
    USER = "user"               # Applies to specific user
    SESSION = "session"         # Applies to specific session


class ActionCategory(str, Enum):
    """Categories of AI agent actions."""
    
    READ = "read"               # Reading data/state
    QUERY = "query"             # Running queries
    ANALYZE = "analyze"         # Analysis operations
    RECOMMEND = "recommend"     # Making recommendations
    MODIFY = "modify"           # Modifying state
    CREATE = "create"           # Creating resources
    DELETE = "delete"           # Deleting resources
    EXECUTE = "execute"         # Executing commands
    DEPLOY = "deploy"           # Deployment operations
    ROLLBACK = "rollback"       # Rollback operations
    RESTART = "restart"         # Restarting services
    SCALE = "scale"             # Scaling resources
    CONFIGURE = "configure"     # Configuration changes


class DataClassification(str, Enum):
    """Classification levels for data."""
    
    PUBLIC = "public"           # Publicly available
    INTERNAL = "internal"       # Internal use only
    CONFIDENTIAL = "confidential"  # Restricted access
    SECRET = "secret"           # Highly restricted
    TOP_SECRET = "top_secret"   # Most restricted


class RateLimitScope(str, Enum):
    """Scope for rate limiting."""
    
    GLOBAL = "global"
    TENANT = "tenant"
    USER = "user"
    SESSION = "session"
    ACTION = "action"


class RiskFactor(BaseModel):
    """A factor contributing to risk assessment."""
    
    id: str
    name: str
    description: str = ""
    
    # Weight and scoring
    weight: float = Field(default=1.0, ge=0.0, le=10.0)
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # Metadata
    category: str = "general"
    source: str = ""


class RiskThreshold(BaseModel):
    """Thresholds for risk level classification."""
    
    negligible_max: float = Field(default=0.1, ge=0.0, le=1.0)
    low_max: float = Field(default=0.3, ge=0.0, le=1.0)
    medium_max: float = Field(default=0.5, ge=0.0, le=1.0)
    high_max: float = Field(default=0.7, ge=0.0, le=1.0)
    critical_max: float = Field(default=0.9, ge=0.0, le=1.0)
    # Above critical_max is PROHIBITED


@dataclass
class RiskAssessment:
    """Result of a risk assessment."""
    
    level: RiskLevel
    score: float  # 0.0 to 1.0
    
    # Contributing factors
    factors: list[RiskFactor] = field(default_factory=list)
    
    # Context
    action: str = ""
    target: str = ""
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    
    # Metadata
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    assessment_id: str = ""
    
    # Mitigations
    required_mitigations: list[str] = field(default_factory=list)
    applied_mitigations: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "level": self.level.value,
            "score": self.score,
            "factors": [f.model_dump() for f in self.factors],
            "action": self.action,
            "target": self.target,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "timestamp": self.timestamp.isoformat(),
            "assessment_id": self.assessment_id,
            "required_mitigations": self.required_mitigations,
            "applied_mitigations": self.applied_mitigations,
        }


class ActionRestriction(BaseModel):
    """Restriction on a specific action."""
    
    action: ActionCategory
    
    # Restrictions
    allowed: bool = True
    max_per_hour: Optional[int] = None
    max_per_day: Optional[int] = None
    
    # Requirements
    requires_confirmation: bool = False
    requires_approval: bool = False
    requires_justification: bool = False
    
    # Scope
    allowed_targets: list[str] = Field(default_factory=list)
    blocked_targets: list[str] = Field(default_factory=list)
    allowed_environments: list[str] = Field(
        default_factory=lambda: ["development", "staging", "production"]
    )
    
    # Conditions
    time_restrictions: Optional[tuple[int, int]] = None  # Allowed hours (24h)
    day_restrictions: list[int] = Field(default_factory=list)  # Blocked days
    
    # Risk
    base_risk_level: RiskLevel = RiskLevel.LOW


class AllowedAction(BaseModel):
    """An explicitly allowed action."""
    
    action: ActionCategory
    targets: list[str] = Field(default_factory=list)
    
    # Permissions
    permission_level: str = "standard"  # standard, elevated, admin
    
    # Constraints
    max_blast_radius: int = Field(default=10, ge=1)
    max_duration_minutes: int = Field(default=60, ge=1)
    require_rollback_plan: bool = False
    
    # Metadata
    description: str = ""
    owner: str = ""


class ActionPolicy(BaseModel):
    """Policy for controlling AI agent actions."""
    
    id: str
    name: str
    description: str = ""
    enabled: bool = True
    
    # Scope
    scope: PolicyScope = PolicyScope.GLOBAL
    scope_value: Optional[str] = None  # tenant_id, user_id, etc.
    
    # Default behavior
    default_action: PolicyAction = PolicyAction.ALLOW_WITH_LOGGING
    default_risk_level: RiskLevel = RiskLevel.LOW
    
    # Restrictions
    restrictions: list[ActionRestriction] = Field(default_factory=list)
    allowed_actions: list[AllowedAction] = Field(default_factory=list)
    
    # Blocked actions
    blocked_actions: list[ActionCategory] = Field(default_factory=list)
    blocked_targets: list[str] = Field(default_factory=list)
    
    # Priority (higher = evaluated first)
    priority: int = Field(default=100, ge=0)
    
    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = Field(default=1, ge=1)


class RateLimitConfig(BaseModel):
    """Configuration for rate limiting."""
    
    id: str
    name: str
    enabled: bool = True
    
    # Limits
    requests_per_second: Optional[int] = None
    requests_per_minute: Optional[int] = None
    requests_per_hour: Optional[int] = None
    requests_per_day: Optional[int] = None
    
    # Token limits (for LLM calls)
    tokens_per_minute: Optional[int] = None
    tokens_per_hour: Optional[int] = None
    
    # Cost limits
    cost_per_hour: Optional[float] = None
    cost_per_day: Optional[float] = None
    
    # Scope
    scope: RateLimitScope = RateLimitScope.USER
    
    # Behavior
    burst_multiplier: float = Field(default=1.5, ge=1.0, le=5.0)
    soft_limit_percentage: float = Field(default=0.8, ge=0.0, le=1.0)
    
    # Actions
    on_soft_limit: PolicyAction = PolicyAction.ALLOW_WITH_LOGGING
    on_hard_limit: PolicyAction = PolicyAction.DENY


class SensitiveDataPolicy(BaseModel):
    """Policy for handling sensitive data."""
    
    id: str
    name: str
    enabled: bool = True
    
    # Data classification
    classification: DataClassification
    
    # Access control
    allowed_roles: list[str] = Field(default_factory=list)
    denied_roles: list[str] = Field(default_factory=list)
    
    # Handling
    allow_in_prompts: bool = False
    allow_in_responses: bool = False
    mask_in_logs: bool = True
    mask_in_audit: bool = False
    
    # Detection patterns
    patterns: list[str] = Field(default_factory=list)
    
    # Actions
    on_detection: PolicyAction = PolicyAction.DENY
    
    # Retention
    retention_days: int = Field(default=90, ge=1)


class ContextPolicy(BaseModel):
    """Context-aware policy configuration."""
    
    id: str
    name: str
    enabled: bool = True
    
    # Context conditions
    environments: list[str] = Field(default_factory=list)
    time_ranges: list[tuple[int, int]] = Field(default_factory=list)
    incident_states: list[str] = Field(default_factory=list)  # active, resolved, etc.
    
    # Risk modifiers
    risk_multiplier: float = Field(default=1.0, ge=0.0, le=10.0)
    
    # Overrides
    force_approval: bool = False
    force_logging: bool = True
    
    # Metadata
    description: str = ""


@dataclass
class PolicyResult:
    """Result of policy evaluation."""
    
    action: PolicyAction
    reason: str
    
    # Risk assessment
    risk_assessment: Optional[RiskAssessment] = None
    
    # Policy details
    policy_id: str = ""
    policy_name: str = ""
    
    # Requirements
    requires_approval: bool = False
    requires_justification: bool = False
    approval_level: Optional[str] = None
    
    # Context
    evaluated_policies: list[str] = field(default_factory=list)
    matched_restrictions: list[str] = field(default_factory=list)
    
    # Metadata
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    evaluation_time_ms: float = 0.0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "action": self.action.value,
            "reason": self.reason,
            "risk_assessment": self.risk_assessment.to_dict() if self.risk_assessment else None,
            "policy_id": self.policy_id,
            "policy_name": self.policy_name,
            "requires_approval": self.requires_approval,
            "requires_justification": self.requires_justification,
            "approval_level": self.approval_level,
            "evaluated_policies": self.evaluated_policies,
            "matched_restrictions": self.matched_restrictions,
            "timestamp": self.timestamp.isoformat(),
            "evaluation_time_ms": self.evaluation_time_ms,
        }


class RateLimiter:
    """Rate limiter with sliding window algorithm."""
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self._windows: dict[str, dict[str, list[float]]] = defaultdict(
            lambda: defaultdict(list)
        )
    
    def check(
        self,
        key: str,
        tokens: int = 1,
        cost: float = 0.0,
    ) -> tuple[bool, Optional[str]]:
        """Check if request is allowed.
        
        Returns (allowed, reason_if_denied).
        """
        now = time.time()
        scope_key = f"{self.config.scope.value}:{key}"
        
        # Check each limit
        limits = [
            ("requests_per_second", 1, self.config.requests_per_second),
            ("requests_per_minute", 60, self.config.requests_per_minute),
            ("requests_per_hour", 3600, self.config.requests_per_hour),
            ("requests_per_day", 86400, self.config.requests_per_day),
        ]
        
        for name, window_seconds, limit in limits:
            if limit is None:
                continue
            
            window = self._windows[scope_key][name]
            
            # Clean old entries
            cutoff = now - window_seconds
            self._windows[scope_key][name] = [t for t in window if t > cutoff]
            window = self._windows[scope_key][name]
            
            # Check limit
            if len(window) >= limit:
                return False, f"Rate limit exceeded: {name} ({len(window)}/{limit})"
            
            # Check soft limit (warning)
            soft_limit = int(limit * self.config.soft_limit_percentage)
            if len(window) >= soft_limit:
                # Allow but should log warning
                pass
        
        # Record request
        for name, _, _ in limits:
            self._windows[scope_key][name].append(now)
        
        return True, None
    
    def record(self, key: str, tokens: int = 1, cost: float = 0.0) -> None:
        """Record a request after it completes."""
        # Additional tracking for tokens and cost could be added here
        pass
    
    def get_usage(self, key: str) -> dict[str, Any]:
        """Get current usage for a key."""
        now = time.time()
        scope_key = f"{self.config.scope.value}:{key}"
        
        usage = {}
        
        limits = [
            ("requests_per_minute", 60, self.config.requests_per_minute),
            ("requests_per_hour", 3600, self.config.requests_per_hour),
        ]
        
        for name, window_seconds, limit in limits:
            if limit is None:
                continue
            
            window = self._windows[scope_key][name]
            cutoff = now - window_seconds
            current = len([t for t in window if t > cutoff])
            
            usage[name] = {
                "current": current,
                "limit": limit,
                "percentage": (current / limit) * 100 if limit else 0,
            }
        
        return usage
    
    def reset(self, key: str) -> None:
        """Reset rate limit counters for a key."""
        scope_key = f"{self.config.scope.value}:{key}"
        if scope_key in self._windows:
            del self._windows[scope_key]


class SafetyPolicy(BaseModel):
    """Comprehensive safety policy for AI operations."""
    
    id: str
    name: str
    description: str = ""
    version: str = "1.0.0"
    enabled: bool = True
    
    # Risk thresholds
    risk_thresholds: RiskThreshold = Field(default_factory=RiskThreshold)
    
    # Action policies
    action_policies: list[ActionPolicy] = Field(default_factory=list)
    
    # Rate limits
    rate_limits: list[RateLimitConfig] = Field(default_factory=list)
    
    # Data policies
    sensitive_data_policies: list[SensitiveDataPolicy] = Field(default_factory=list)
    
    # Context policies
    context_policies: list[ContextPolicy] = Field(default_factory=list)
    
    # Global settings
    require_audit_trail: bool = True
    require_justification_for_risk: RiskLevel = RiskLevel.MEDIUM
    require_approval_for_risk: RiskLevel = RiskLevel.HIGH
    
    # Environments
    production_restrictions: bool = True
    allowed_environments: list[str] = Field(
        default_factory=lambda: ["development", "staging", "production"]
    )
    
    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    owner: str = ""
    
    def get_action_policy(self, action: ActionCategory) -> Optional[ActionPolicy]:
        """Get the applicable action policy for an action."""
        for policy in sorted(self.action_policies, key=lambda p: -p.priority):
            if not policy.enabled:
                continue
            
            # Check if action is blocked
            if action in policy.blocked_actions:
                return policy
            
            # Check restrictions
            for restriction in policy.restrictions:
                if restriction.action == action:
                    return policy
        
        return None


class PolicyEngine:
    """Engine for evaluating safety policies."""
    
    def __init__(
        self,
        policy: Optional[SafetyPolicy] = None,
        risk_assessor: Optional[Callable[[dict], RiskAssessment]] = None,
    ):
        self.policy = policy or SafetyPolicy(id="default", name="Default Policy")
        self.risk_assessor = risk_assessor
        
        # Rate limiters
        self._rate_limiters: dict[str, RateLimiter] = {}
        for config in self.policy.rate_limits:
            self._rate_limiters[config.id] = RateLimiter(config)
    
    async def evaluate(
        self,
        action: ActionCategory,
        target: str,
        context: Optional[dict] = None,
    ) -> PolicyResult:
        """Evaluate if an action is allowed."""
        start_time = datetime.now(UTC)
        context = context or {}
        
        # Extract context values
        user_id = context.get("user_id", "anonymous")
        tenant_id = context.get("tenant_id", "default")
        environment = context.get("environment", "development")
        
        # Check if policy is enabled
        if not self.policy.enabled:
            return PolicyResult(
                action=PolicyAction.ALLOW,
                reason="Policy disabled",
                evaluation_time_ms=0.0,
            )
        
        # Check environment restrictions
        if environment not in self.policy.allowed_environments:
            return PolicyResult(
                action=PolicyAction.DENY,
                reason=f"Environment '{environment}' not allowed",
                policy_id=self.policy.id,
                policy_name=self.policy.name,
            )
        
        # Check rate limits
        for limiter in self._rate_limiters.values():
            allowed, reason = limiter.check(user_id)
            if not allowed:
                return PolicyResult(
                    action=PolicyAction.DENY,
                    reason=reason or "Rate limit exceeded",
                    policy_id=self.policy.id,
                    policy_name=self.policy.name,
                )
        
        # Find applicable action policy
        action_policy = self.policy.get_action_policy(action)
        
        # Check if action is blocked
        if action_policy and action in action_policy.blocked_actions:
            return PolicyResult(
                action=PolicyAction.DENY,
                reason=f"Action '{action.value}' is blocked by policy",
                policy_id=action_policy.id,
                policy_name=action_policy.name,
            )
        
        # Check target restrictions
        if action_policy:
            for restriction in action_policy.restrictions:
                if restriction.action == action:
                    # Check blocked targets
                    if target in restriction.blocked_targets:
                        return PolicyResult(
                            action=PolicyAction.DENY,
                            reason=f"Target '{target}' is blocked",
                            policy_id=action_policy.id,
                            policy_name=action_policy.name,
                            matched_restrictions=[restriction.action.value],
                        )
                    
                    # Check allowed targets (if specified)
                    if restriction.allowed_targets and target not in restriction.allowed_targets:
                        return PolicyResult(
                            action=PolicyAction.DENY,
                            reason=f"Target '{target}' is not in allowed list",
                            policy_id=action_policy.id,
                            policy_name=action_policy.name,
                            matched_restrictions=[restriction.action.value],
                        )
                    
                    # Check environment restrictions
                    if environment not in restriction.allowed_environments:
                        return PolicyResult(
                            action=PolicyAction.DENY,
                            reason=f"Action not allowed in '{environment}'",
                            policy_id=action_policy.id,
                            policy_name=action_policy.name,
                        )
        
        # Perform risk assessment
        risk_assessment = await self._assess_risk(action, target, context)
        
        # Determine required action based on risk
        policy_action = self._risk_to_action(risk_assessment.level)
        
        # Check if approval is required
        requires_approval = (
            risk_assessment.level.value >= self.policy.require_approval_for_risk.value
        )
        
        # Check if justification is required
        requires_justification = (
            risk_assessment.level.value >= self.policy.require_justification_for_risk.value
        )
        
        # Check context policies
        context_result = await self._evaluate_context_policies(action, target, context)
        if context_result:
            if context_result.action == PolicyAction.DENY:
                return context_result
            if context_result.force_approval:
                requires_approval = True
        
        # Calculate evaluation time
        evaluation_time = (datetime.now(UTC) - start_time).total_seconds() * 1000
        
        return PolicyResult(
            action=policy_action,
            reason=f"Risk level: {risk_assessment.level.value}",
            risk_assessment=risk_assessment,
            policy_id=self.policy.id,
            policy_name=self.policy.name,
            requires_approval=requires_approval,
            requires_justification=requires_justification,
            approval_level="standard" if requires_approval else None,
            evaluation_time_ms=evaluation_time,
        )
    
    async def _assess_risk(
        self,
        action: ActionCategory,
        target: str,
        context: dict,
    ) -> RiskAssessment:
        """Assess risk of an action."""
        if self.risk_assessor:
            return self.risk_assessor({
                "action": action.value,
                "target": target,
                **context,
            })
        
        # Default risk assessment
        factors: list[RiskFactor] = []
        
        # Action-based risk
        action_risk = {
            ActionCategory.READ: 0.1,
            ActionCategory.QUERY: 0.15,
            ActionCategory.ANALYZE: 0.2,
            ActionCategory.RECOMMEND: 0.2,
            ActionCategory.MODIFY: 0.5,
            ActionCategory.CREATE: 0.4,
            ActionCategory.DELETE: 0.7,
            ActionCategory.EXECUTE: 0.6,
            ActionCategory.DEPLOY: 0.7,
            ActionCategory.ROLLBACK: 0.6,
            ActionCategory.RESTART: 0.5,
            ActionCategory.SCALE: 0.5,
            ActionCategory.CONFIGURE: 0.6,
        }.get(action, 0.5)
        
        factors.append(RiskFactor(
            id="action_type",
            name="Action Type Risk",
            weight=2.0,
            score=action_risk,
            category="action",
        ))
        
        # Environment-based risk
        environment = context.get("environment", "development")
        env_risk = {
            "development": 0.1,
            "staging": 0.3,
            "production": 0.7,
        }.get(environment, 0.5)
        
        factors.append(RiskFactor(
            id="environment",
            name="Environment Risk",
            weight=1.5,
            score=env_risk,
            category="environment",
        ))
        
        # Target-based risk
        target_risk = 0.3
        if "production" in target.lower():
            target_risk = 0.7
        elif "critical" in target.lower():
            target_risk = 0.8
        elif "database" in target.lower() or "db" in target.lower():
            target_risk = 0.6
        
        factors.append(RiskFactor(
            id="target",
            name="Target Risk",
            weight=1.5,
            score=target_risk,
            category="target",
        ))
        
        # Calculate weighted score
        total_weight = sum(f.weight for f in factors)
        weighted_score = sum(f.weight * f.score for f in factors) / total_weight
        
        # Determine risk level
        risk_level = self._score_to_risk_level(weighted_score)
        
        return RiskAssessment(
            level=risk_level,
            score=weighted_score,
            factors=factors,
            action=action.value,
            target=target,
            user_id=context.get("user_id"),
            tenant_id=context.get("tenant_id"),
            assessment_id=hashlib.sha256(
                f"{action.value}:{target}:{datetime.now(UTC).isoformat()}".encode()
            ).hexdigest()[:16],
        )
    
    def _score_to_risk_level(self, score: float) -> RiskLevel:
        """Convert risk score to risk level."""
        thresholds = self.policy.risk_thresholds
        
        if score <= thresholds.negligible_max:
            return RiskLevel.NEGLIGIBLE
        elif score <= thresholds.low_max:
            return RiskLevel.LOW
        elif score <= thresholds.medium_max:
            return RiskLevel.MEDIUM
        elif score <= thresholds.high_max:
            return RiskLevel.HIGH
        elif score <= thresholds.critical_max:
            return RiskLevel.CRITICAL
        else:
            return RiskLevel.PROHIBITED
    
    def _risk_to_action(self, risk_level: RiskLevel) -> PolicyAction:
        """Convert risk level to policy action."""
        return {
            RiskLevel.NEGLIGIBLE: PolicyAction.ALLOW,
            RiskLevel.LOW: PolicyAction.ALLOW_WITH_LOGGING,
            RiskLevel.MEDIUM: PolicyAction.REQUIRE_CONFIRMATION,
            RiskLevel.HIGH: PolicyAction.REQUIRE_APPROVAL,
            RiskLevel.CRITICAL: PolicyAction.REQUIRE_MULTI_APPROVAL,
            RiskLevel.PROHIBITED: PolicyAction.DENY,
        }[risk_level]
    
    async def _evaluate_context_policies(
        self,
        action: ActionCategory,
        target: str,
        context: dict,
    ) -> Optional[Any]:
        """Evaluate context-specific policies."""
        environment = context.get("environment", "development")
        current_hour = datetime.now(UTC).hour
        
        for policy in self.policy.context_policies:
            if not policy.enabled:
                continue
            
            # Check environment
            if policy.environments and environment not in policy.environments:
                continue
            
            # Check time range
            if policy.time_ranges:
                in_range = any(
                    start <= current_hour < end
                    for start, end in policy.time_ranges
                )
                if not in_range:
                    continue
            
            # Policy applies
            return type('ContextResult', (), {
                'action': PolicyAction.ALLOW_WITH_LOGGING,
                'force_approval': policy.force_approval,
            })()
        
        return None
    
    def set_policy(self, policy: SafetyPolicy) -> None:
        """Update the active policy."""
        self.policy = policy
        
        # Recreate rate limiters
        self._rate_limiters.clear()
        for config in self.policy.rate_limits:
            self._rate_limiters[config.id] = RateLimiter(config)
    
    def get_policy(self) -> SafetyPolicy:
        """Get the current policy."""
        return self.policy


# Convenience function to create default policies
def create_default_policy(
    environment: str = "production",
    strict: bool = False,
) -> SafetyPolicy:
    """Create a default safety policy."""
    
    # Base action restrictions
    restrictions = [
        ActionRestriction(
            action=ActionCategory.DELETE,
            requires_approval=True,
            requires_justification=True,
            base_risk_level=RiskLevel.HIGH,
        ),
        ActionRestriction(
            action=ActionCategory.DEPLOY,
            requires_approval=True,
            allowed_environments=["staging", "production"],
            base_risk_level=RiskLevel.HIGH,
        ),
        ActionRestriction(
            action=ActionCategory.EXECUTE,
            requires_confirmation=True,
            blocked_targets=["production-database"],
            base_risk_level=RiskLevel.MEDIUM,
        ),
    ]
    
    # Strict mode adds more restrictions
    if strict:
        restrictions.extend([
            ActionRestriction(
                action=ActionCategory.MODIFY,
                requires_approval=True,
                base_risk_level=RiskLevel.MEDIUM,
            ),
            ActionRestriction(
                action=ActionCategory.SCALE,
                requires_approval=True,
                base_risk_level=RiskLevel.MEDIUM,
            ),
        ])
    
    # Create action policy
    action_policy = ActionPolicy(
        id="default-action-policy",
        name="Default Action Policy",
        restrictions=restrictions,
        blocked_actions=[ActionCategory.DELETE] if environment == "production" else [],
    )
    
    # Rate limits
    rate_limits = [
        RateLimitConfig(
            id="default-rate-limit",
            name="Default Rate Limit",
            requests_per_minute=60,
            requests_per_hour=1000,
            tokens_per_minute=100000,
        ),
    ]
    
    # Sensitive data policies
    sensitive_data_policies = [
        SensitiveDataPolicy(
            id="credentials-policy",
            name="Credentials Protection",
            classification=DataClassification.SECRET,
            allow_in_prompts=False,
            allow_in_responses=False,
            mask_in_logs=True,
            patterns=[
                r"(?i)password\s*[:=]",
                r"(?i)api[_-]?key\s*[:=]",
                r"(?i)token\s*[:=]",
            ],
        ),
        SensitiveDataPolicy(
            id="pii-policy",
            name="PII Protection",
            classification=DataClassification.CONFIDENTIAL,
            allow_in_prompts=True,
            allow_in_responses=False,
            mask_in_logs=True,
            patterns=[
                r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
                r"\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b",  # SSN
            ],
        ),
    ]
    
    return SafetyPolicy(
        id=f"default-{environment}",
        name=f"Default {environment.capitalize()} Policy",
        description=f"Default safety policy for {environment} environment",
        action_policies=[action_policy],
        rate_limits=rate_limits,
        sensitive_data_policies=sensitive_data_policies,
        production_restrictions=(environment == "production"),
        require_approval_for_risk=RiskLevel.HIGH if not strict else RiskLevel.MEDIUM,
        require_justification_for_risk=RiskLevel.MEDIUM if not strict else RiskLevel.LOW,
    )
