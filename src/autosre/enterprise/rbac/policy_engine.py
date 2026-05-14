"""Policy Engine for AutoSRE V2 RBAC.

Provides Attribute-Based Access Control (ABAC):
- Policy definition and management
- Condition evaluation
- Policy combination algorithms
- Context-aware authorization
"""

from __future__ import annotations

import asyncio
import operator
import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Union
from uuid import uuid4

from pydantic import BaseModel, Field

from autosre.utils.logging import get_logger

logger = get_logger(__name__)


class PolicyEffect(str, Enum):
    """Effect of a policy when conditions are met."""
    
    ALLOW = "allow"
    DENY = "deny"


class ConditionOperator(str, Enum):
    """Operators for condition evaluation."""
    
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN = "less_than"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    MATCHES = "matches"  # Regex
    EXISTS = "exists"
    NOT_EXISTS = "not_exists"
    
    # Time-based
    WITHIN_TIME_RANGE = "within_time_range"
    DAY_OF_WEEK = "day_of_week"
    HOUR_OF_DAY = "hour_of_day"


class ConditionType(str, Enum):
    """Types of conditions."""
    
    SUBJECT = "subject"  # About the user/actor
    RESOURCE = "resource"  # About the resource
    ACTION = "action"  # About the action
    ENVIRONMENT = "environment"  # About the environment/context


class PolicyCondition(BaseModel):
    """A condition that must be met for a policy to apply."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: Optional[str] = None
    description: Optional[str] = None
    
    # Condition definition
    condition_type: ConditionType
    attribute: str  # Attribute path (e.g., "subject.role", "resource.severity")
    operator: ConditionOperator
    value: Any  # Expected value
    
    # For nested attributes
    attribute_path: List[str] = Field(default_factory=list)
    
    def __init__(self, **data):
        super().__init__(**data)
        if not self.attribute_path and self.attribute:
            self.attribute_path = self.attribute.split('.')
    
    def evaluate(self, context: "PolicyEvaluationContext") -> bool:
        """Evaluate this condition against a context.
        
        Args:
            context: Evaluation context
            
        Returns:
            True if condition is met
        """
        # Get the attribute value from context
        actual_value = self._get_attribute_value(context)
        
        # Evaluate based on operator
        return self._evaluate_operator(actual_value, self.value)
    
    def _get_attribute_value(self, context: "PolicyEvaluationContext") -> Any:
        """Extract attribute value from context."""
        if not self.attribute_path:
            return None
        
        # Get the base object
        base_type = self.attribute_path[0]
        if base_type == "subject":
            obj = context.subject
        elif base_type == "resource":
            obj = context.resource
        elif base_type == "action":
            obj = context.action
        elif base_type == "environment":
            obj = context.environment
        else:
            return None
        
        # Navigate the path
        for key in self.attribute_path[1:]:
            if isinstance(obj, dict):
                obj = obj.get(key)
            elif hasattr(obj, key):
                obj = getattr(obj, key)
            else:
                return None
            
            if obj is None:
                return None
        
        return obj
    
    def _evaluate_operator(self, actual: Any, expected: Any) -> bool:
        """Evaluate the operator."""
        try:
            if self.operator == ConditionOperator.EQUALS:
                return actual == expected
            
            elif self.operator == ConditionOperator.NOT_EQUALS:
                return actual != expected
            
            elif self.operator == ConditionOperator.GREATER_THAN:
                return actual > expected
            
            elif self.operator == ConditionOperator.GREATER_THAN_OR_EQUAL:
                return actual >= expected
            
            elif self.operator == ConditionOperator.LESS_THAN:
                return actual < expected
            
            elif self.operator == ConditionOperator.LESS_THAN_OR_EQUAL:
                return actual <= expected
            
            elif self.operator == ConditionOperator.IN:
                return actual in expected
            
            elif self.operator == ConditionOperator.NOT_IN:
                return actual not in expected
            
            elif self.operator == ConditionOperator.CONTAINS:
                return expected in actual
            
            elif self.operator == ConditionOperator.NOT_CONTAINS:
                return expected not in actual
            
            elif self.operator == ConditionOperator.STARTS_WITH:
                return str(actual).startswith(str(expected))
            
            elif self.operator == ConditionOperator.ENDS_WITH:
                return str(actual).endswith(str(expected))
            
            elif self.operator == ConditionOperator.MATCHES:
                return bool(re.match(str(expected), str(actual)))
            
            elif self.operator == ConditionOperator.EXISTS:
                return actual is not None
            
            elif self.operator == ConditionOperator.NOT_EXISTS:
                return actual is None
            
            elif self.operator == ConditionOperator.WITHIN_TIME_RANGE:
                # expected should be {"start": "HH:MM", "end": "HH:MM"}
                now = datetime.now(timezone.utc)
                current_time = now.strftime("%H:%M")
                return expected.get("start", "00:00") <= current_time <= expected.get("end", "23:59")
            
            elif self.operator == ConditionOperator.DAY_OF_WEEK:
                # expected is list of day numbers (0=Monday, 6=Sunday)
                now = datetime.now(timezone.utc)
                return now.weekday() in expected
            
            elif self.operator == ConditionOperator.HOUR_OF_DAY:
                # expected is list of hours (0-23)
                now = datetime.now(timezone.utc)
                return now.hour in expected
            
        except (TypeError, ValueError):
            return False
        
        return False


class ConditionSet(BaseModel):
    """A set of conditions with logical operators."""
    
    conditions: List[PolicyCondition] = Field(default_factory=list)
    condition_sets: List["ConditionSet"] = Field(default_factory=list)
    operator: str = "AND"  # AND, OR
    
    def evaluate(self, context: "PolicyEvaluationContext") -> bool:
        """Evaluate all conditions in this set.
        
        Args:
            context: Evaluation context
            
        Returns:
            True if conditions are met according to operator
        """
        results = []
        
        # Evaluate direct conditions
        for condition in self.conditions:
            results.append(condition.evaluate(context))
        
        # Evaluate nested condition sets
        for cond_set in self.condition_sets:
            results.append(cond_set.evaluate(context))
        
        if not results:
            return True
        
        if self.operator == "AND":
            return all(results)
        elif self.operator == "OR":
            return any(results)
        
        return False


class Policy(BaseModel):
    """An ABAC policy defining access rules."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: Optional[str] = None
    
    # Scope
    tenant_id: Optional[str] = None  # None = global policy
    
    # Target
    target_resources: List[str] = Field(default_factory=list)  # Resource types
    target_actions: List[str] = Field(default_factory=list)  # Actions
    
    # Effect
    effect: PolicyEffect = PolicyEffect.ALLOW
    
    # Conditions
    condition_set: Optional[ConditionSet] = None
    
    # Priority and combination
    priority: int = 0  # Higher = evaluated first
    combine_with: str = "permit-unless-deny"  # Policy combination algorithm
    
    # Obligations (actions to take when policy applies)
    obligations: Dict[str, Any] = Field(default_factory=dict)
    
    # Status
    enabled: bool = True
    
    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: Optional[str] = None
    version: int = 1
    
    def matches_target(
        self,
        resource_type: str,
        action: str,
    ) -> bool:
        """Check if policy applies to given resource and action."""
        # Check resource type
        if self.target_resources:
            if resource_type not in self.target_resources and "*" not in self.target_resources:
                return False
        
        # Check action
        if self.target_actions:
            if action not in self.target_actions and "*" not in self.target_actions:
                return False
        
        return True
    
    def evaluate(self, context: "PolicyEvaluationContext") -> Optional[PolicyEffect]:
        """Evaluate this policy against a context.
        
        Args:
            context: Evaluation context
            
        Returns:
            PolicyEffect if policy applies, None if not applicable
        """
        if not self.enabled:
            return None
        
        # Check target
        if not self.matches_target(context.resource_type, context.action_name):
            return None
        
        # Check conditions
        if self.condition_set:
            if not self.condition_set.evaluate(context):
                return None
        
        return self.effect


class PolicyEvaluationContext(BaseModel):
    """Context for policy evaluation."""
    
    # Subject (the actor)
    subject: Dict[str, Any] = Field(default_factory=dict)
    # Expected keys: user_id, tenant_id, roles, groups, attributes
    
    # Resource (what's being accessed)
    resource: Dict[str, Any] = Field(default_factory=dict)
    # Expected keys: type, id, owner, tenant_id, attributes
    
    # Action (what's being done)
    action: Dict[str, Any] = Field(default_factory=dict)
    # Expected keys: name, parameters
    
    # Environment (context)
    environment: Dict[str, Any] = Field(default_factory=dict)
    # Expected keys: ip_address, timestamp, request_id
    
    # Derived fields
    resource_type: str = ""
    action_name: str = ""
    
    def __init__(self, **data):
        super().__init__(**data)
        self.resource_type = self.resource.get("type", "")
        self.action_name = self.action.get("name", "")
    
    @classmethod
    def create(
        cls,
        user_id: str,
        tenant_id: str,
        resource_type: str,
        resource_id: str,
        action: str,
        user_roles: Optional[List[str]] = None,
        user_attributes: Optional[Dict[str, Any]] = None,
        resource_attributes: Optional[Dict[str, Any]] = None,
        environment: Optional[Dict[str, Any]] = None,
    ) -> "PolicyEvaluationContext":
        """Create evaluation context with common fields."""
        return cls(
            subject={
                "user_id": user_id,
                "tenant_id": tenant_id,
                "roles": user_roles or [],
                "attributes": user_attributes or {},
            },
            resource={
                "type": resource_type,
                "id": resource_id,
                "tenant_id": tenant_id,
                "attributes": resource_attributes or {},
            },
            action={
                "name": action,
            },
            environment=environment or {
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )


class PolicyDecision(BaseModel):
    """Decision from policy evaluation."""
    
    allowed: bool
    effect: PolicyEffect
    
    # Which policies contributed to this decision
    matched_policies: List[str] = Field(default_factory=list)
    denied_by: Optional[str] = None
    allowed_by: Optional[str] = None
    
    # Obligations to fulfill
    obligations: Dict[str, Any] = Field(default_factory=dict)
    
    # Evaluation metadata
    policies_evaluated: int = 0
    evaluation_time_ms: float = 0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PolicyEngine:
    """
    Evaluates ABAC policies for authorization decisions.
    
    Supports multiple policy combination algorithms:
    - permit-unless-deny: Allow unless explicitly denied
    - deny-unless-permit: Deny unless explicitly allowed
    - first-applicable: Use first matching policy
    - only-one-applicable: Require exactly one matching policy
    
    Example:
        engine = PolicyEngine()
        
        # Create a policy
        policy = Policy(
            name="only-critical-alerts-after-hours",
            target_resources=["alert"],
            target_actions=["create", "update"],
            effect=PolicyEffect.DENY,
            condition_set=ConditionSet(
                operator="AND",
                conditions=[
                    PolicyCondition(
                        condition_type=ConditionType.RESOURCE,
                        attribute="resource.severity",
                        operator=ConditionOperator.NOT_IN,
                        value=["critical", "high"],
                    ),
                    PolicyCondition(
                        condition_type=ConditionType.ENVIRONMENT,
                        attribute="environment.hour",
                        operator=ConditionOperator.IN,
                        value=[22, 23, 0, 1, 2, 3, 4, 5, 6],
                    ),
                ],
            ),
        )
        
        await engine.add_policy(policy)
        
        # Evaluate
        context = PolicyEvaluationContext.create(
            user_id="user-123",
            tenant_id="tenant-456",
            resource_type="alert",
            resource_id="alert-789",
            action="update",
            resource_attributes={"severity": "low"},
        )
        
        decision = await engine.evaluate(context)
    """
    
    def __init__(
        self,
        default_effect: PolicyEffect = PolicyEffect.DENY,
        combination_algorithm: str = "permit-unless-deny",
    ):
        """Initialize PolicyEngine.
        
        Args:
            default_effect: Default effect when no policies match
            combination_algorithm: How to combine multiple policies
        """
        self.default_effect = default_effect
        self.combination_algorithm = combination_algorithm
        
        self._policies: Dict[str, Policy] = {}
        self._lock = asyncio.Lock()
    
    async def add_policy(self, policy: Policy) -> Policy:
        """Add a policy to the engine.
        
        Args:
            policy: Policy to add
            
        Returns:
            Added policy
        """
        async with self._lock:
            self._policies[policy.id] = policy
            
            logger.info(
                "Added policy",
                policy_id=policy.id,
                name=policy.name,
                effect=policy.effect.value,
            )
            
            return policy
    
    async def get_policy(self, policy_id: str) -> Optional[Policy]:
        """Get a policy by ID."""
        return self._policies.get(policy_id)
    
    async def update_policy(
        self,
        policy_id: str,
        **updates,
    ) -> Policy:
        """Update a policy.
        
        Args:
            policy_id: Policy ID
            **updates: Fields to update
            
        Returns:
            Updated policy
        """
        async with self._lock:
            policy = self._policies.get(policy_id)
            if not policy:
                raise ValueError(f"Policy {policy_id} not found")
            
            for key, value in updates.items():
                if hasattr(policy, key):
                    setattr(policy, key, value)
            
            policy.updated_at = datetime.now(timezone.utc)
            policy.version += 1
            
            return policy
    
    async def delete_policy(self, policy_id: str) -> bool:
        """Delete a policy.
        
        Args:
            policy_id: Policy ID
            
        Returns:
            True if deleted
        """
        async with self._lock:
            if policy_id in self._policies:
                del self._policies[policy_id]
                return True
            return False
    
    async def list_policies(
        self,
        tenant_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        enabled_only: bool = True,
    ) -> List[Policy]:
        """List policies with optional filters.
        
        Args:
            tenant_id: Filter by tenant
            resource_type: Filter by resource type
            enabled_only: Only enabled policies
            
        Returns:
            List of policies
        """
        policies = list(self._policies.values())
        
        if enabled_only:
            policies = [p for p in policies if p.enabled]
        
        if tenant_id:
            policies = [
                p for p in policies
                if p.tenant_id is None or p.tenant_id == tenant_id
            ]
        
        if resource_type:
            policies = [
                p for p in policies
                if not p.target_resources or resource_type in p.target_resources or "*" in p.target_resources
            ]
        
        # Sort by priority (descending)
        policies.sort(key=lambda p: p.priority, reverse=True)
        
        return policies
    
    async def evaluate(
        self,
        context: PolicyEvaluationContext,
        tenant_id: Optional[str] = None,
    ) -> PolicyDecision:
        """Evaluate policies for an authorization decision.
        
        Args:
            context: Evaluation context
            tenant_id: Tenant ID for policy filtering
            
        Returns:
            PolicyDecision
        """
        import time
        start_time = time.time()
        
        # Get applicable policies
        tenant = tenant_id or context.subject.get("tenant_id")
        policies = await self.list_policies(
            tenant_id=tenant,
            resource_type=context.resource_type,
        )
        
        # Evaluate each policy
        matched_policies: List[str] = []
        allow_policies: List[Policy] = []
        deny_policies: List[Policy] = []
        obligations: Dict[str, Any] = {}
        
        for policy in policies:
            effect = policy.evaluate(context)
            
            if effect is not None:
                matched_policies.append(policy.id)
                
                if effect == PolicyEffect.ALLOW:
                    allow_policies.append(policy)
                elif effect == PolicyEffect.DENY:
                    deny_policies.append(policy)
                
                # Collect obligations
                if policy.obligations:
                    obligations.update(policy.obligations)
        
        # Apply combination algorithm
        final_effect = self._combine_effects(allow_policies, deny_policies)
        
        # Build decision
        decision = PolicyDecision(
            allowed=final_effect == PolicyEffect.ALLOW,
            effect=final_effect,
            matched_policies=matched_policies,
            denied_by=deny_policies[0].id if deny_policies else None,
            allowed_by=allow_policies[0].id if allow_policies else None,
            obligations=obligations,
            policies_evaluated=len(policies),
            evaluation_time_ms=(time.time() - start_time) * 1000,
        )
        
        logger.debug(
            "Policy evaluation complete",
            allowed=decision.allowed,
            matched_policies=len(matched_policies),
            resource_type=context.resource_type,
            action=context.action_name,
        )
        
        return decision
    
    async def enforce(
        self,
        context: PolicyEvaluationContext,
        tenant_id: Optional[str] = None,
    ) -> PolicyDecision:
        """Evaluate and enforce policies.
        
        Args:
            context: Evaluation context
            tenant_id: Tenant ID
            
        Returns:
            PolicyDecision
            
        Raises:
            PolicyDeniedError: If access is denied
        """
        decision = await self.evaluate(context, tenant_id)
        
        if not decision.allowed:
            raise PolicyDeniedError(
                message=f"Access denied by policy: {decision.denied_by}",
                policy_id=decision.denied_by,
                context=context,
            )
        
        return decision
    
    def _combine_effects(
        self,
        allow_policies: List[Policy],
        deny_policies: List[Policy],
    ) -> PolicyEffect:
        """Combine policy effects using the configured algorithm.
        
        Args:
            allow_policies: Policies with ALLOW effect
            deny_policies: Policies with DENY effect
            
        Returns:
            Final PolicyEffect
        """
        has_allow = len(allow_policies) > 0
        has_deny = len(deny_policies) > 0
        
        if self.combination_algorithm == "permit-unless-deny":
            # Deny wins, but allow is default if no deny
            if has_deny:
                return PolicyEffect.DENY
            elif has_allow:
                return PolicyEffect.ALLOW
            else:
                return self.default_effect
        
        elif self.combination_algorithm == "deny-unless-permit":
            # Need explicit allow
            if has_allow and not has_deny:
                return PolicyEffect.ALLOW
            else:
                return PolicyEffect.DENY
        
        elif self.combination_algorithm == "first-applicable":
            # Use the highest priority policy that matched
            all_policies = allow_policies + deny_policies
            if all_policies:
                all_policies.sort(key=lambda p: p.priority, reverse=True)
                return all_policies[0].effect
            return self.default_effect
        
        elif self.combination_algorithm == "only-one-applicable":
            # Require exactly one matching policy
            total = len(allow_policies) + len(deny_policies)
            if total == 1:
                return (allow_policies + deny_policies)[0].effect
            elif total > 1:
                # Indeterminate - deny for safety
                return PolicyEffect.DENY
            else:
                return self.default_effect
        
        else:
            return self.default_effect


class PolicyDeniedError(Exception):
    """Raised when a policy denies access."""
    
    def __init__(
        self,
        message: str,
        policy_id: Optional[str] = None,
        context: Optional[PolicyEvaluationContext] = None,
    ):
        super().__init__(message)
        self.policy_id = policy_id
        self.context = context


# Pre-built condition helpers
def subject_has_role(role: str) -> PolicyCondition:
    """Create condition checking if subject has a role."""
    return PolicyCondition(
        condition_type=ConditionType.SUBJECT,
        attribute="subject.roles",
        operator=ConditionOperator.CONTAINS,
        value=role,
    )


def subject_in_tenant(tenant_id: str) -> PolicyCondition:
    """Create condition checking if subject is in a tenant."""
    return PolicyCondition(
        condition_type=ConditionType.SUBJECT,
        attribute="subject.tenant_id",
        operator=ConditionOperator.EQUALS,
        value=tenant_id,
    )


def resource_has_attribute(attribute: str, value: Any) -> PolicyCondition:
    """Create condition checking a resource attribute."""
    return PolicyCondition(
        condition_type=ConditionType.RESOURCE,
        attribute=f"resource.attributes.{attribute}",
        operator=ConditionOperator.EQUALS,
        value=value,
    )


def resource_owner_is_subject() -> PolicyCondition:
    """Create condition checking if subject owns the resource."""
    return PolicyCondition(
        condition_type=ConditionType.RESOURCE,
        attribute="resource.owner",
        operator=ConditionOperator.EQUALS,
        value="${subject.user_id}",  # Variable reference
    )


def during_business_hours() -> PolicyCondition:
    """Create condition for business hours (9 AM - 6 PM, Mon-Fri)."""
    return PolicyCondition(
        condition_type=ConditionType.ENVIRONMENT,
        attribute="environment.timestamp",
        operator=ConditionOperator.WITHIN_TIME_RANGE,
        value={"start": "09:00", "end": "18:00"},
    )


def on_weekdays() -> PolicyCondition:
    """Create condition for weekdays only."""
    return PolicyCondition(
        condition_type=ConditionType.ENVIRONMENT,
        attribute="environment.timestamp",
        operator=ConditionOperator.DAY_OF_WEEK,
        value=[0, 1, 2, 3, 4],  # Monday to Friday
    )
