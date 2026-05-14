"""
AutoSRE V2 Remediation Framework.

This module provides automated remediation capabilities:
- RemediationEngine: Orchestrates remediation workflows
- ActionRegistry: Registers and manages safe, reversible actions
- RollbackManager: Automatic rollback on failure
- SafetyChecker: Pre-flight checks and blast radius assessment
- ApprovalWorkflow: Human-in-the-loop for dangerous operations

Example:
    from autosre.remediation import RemediationEngine, Action
    
    engine = RemediationEngine()
    
    # Register an action
    @engine.register_action("restart_pod")
    async def restart_pod(namespace: str, pod: str) -> ActionResult:
        ...
    
    # Execute remediation
    result = await engine.execute(
        action="restart_pod",
        parameters={"namespace": "default", "pod": "api-server-123"},
        dry_run=False,
    )
"""

from autosre.remediation.models import (
    RemediationAction,
    RemediationPlan,
    RemediationResult,
    RemediationStatus,
    ActionDefinition,
    ActionParameter,
    ActionType,
    RiskLevel,
    RollbackStrategy,
    ApprovalStatus,
    ApprovalRequest,
    SafetyCheckResult,
    SafetyCheckType,
    BlastRadius,
)

from autosre.remediation.engine import RemediationEngine, EngineConfig
from autosre.remediation.registry import (
    ActionRegistry,
    ActionNotFoundError,
    ActionValidationError,
    ActionCooldownError,
    get_registry,
)
from autosre.remediation.rollback import RollbackManager, RollbackState
from autosre.remediation.safety import SafetyChecker, SafetyPolicy
from autosre.remediation.approval import ApprovalWorkflow, ApprovalPolicy

__all__ = [
    # Models
    "RemediationAction",
    "RemediationPlan",
    "RemediationResult",
    "RemediationStatus",
    "ActionDefinition",
    "ActionParameter",
    "ActionType",
    "RiskLevel",
    "RollbackStrategy",
    "ApprovalStatus",
    "ApprovalRequest",
    "SafetyCheckResult",
    "SafetyCheckType",
    "BlastRadius",
    # Engine
    "RemediationEngine",
    "EngineConfig",
    # Registry
    "ActionRegistry",
    "ActionNotFoundError",
    "ActionValidationError",
    "ActionCooldownError",
    "get_registry",
    # Rollback
    "RollbackManager",
    "RollbackState",
    # Safety
    "SafetyChecker",
    "SafetyPolicy",
    # Approval
    "ApprovalWorkflow",
    "ApprovalPolicy",
]
