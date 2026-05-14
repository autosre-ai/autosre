"""
AutoSRE V2 Kubernetes Operators.

This module provides specialized operators for Kubernetes remediation:
- PodRestarter: Smart pod restart with health checks
- ScaleManager: HPA override and manual scaling
- ResourceTuner: CPU/memory limit adjustments
- DrainManager: Safe node draining
- DeploymentRollback: Automated rollback to last good version

Example:
    from autosre.operators import PodRestarter, ScaleManager
    
    restarter = PodRestarter(k8s_client)
    result = await restarter.restart_pod("production", "api-server-abc")
    
    scaler = ScaleManager(k8s_client)
    result = await scaler.scale_deployment("production", "api", replicas=5)
"""

from autosre.operators.base import (
    BaseOperator,
    OperatorResult,
    OperatorStatus,
    OperatorConfig,
)

from autosre.operators.pod_restarter import (
    PodRestarter,
    RestartStrategy,
    RestartResult,
)

from autosre.operators.scale_manager import (
    ScaleManager,
    ScaleMode,
    ScaleResult,
    HPAOverride,
)

from autosre.operators.resource_tuner import (
    ResourceTuner,
    ResourceSpec,
    TuningResult,
    ResourceRecommendation,
)

from autosre.operators.drain_manager import (
    DrainManager,
    DrainConfig,
    DrainResult,
    DrainStatus,
)

from autosre.operators.deployment_rollback import (
    DeploymentRollback,
    RollbackConfig,
    RollbackResult,
    RevisionInfo,
)

__all__ = [
    # Base
    "BaseOperator",
    "OperatorResult",
    "OperatorStatus",
    "OperatorConfig",
    # Pod Restarter
    "PodRestarter",
    "RestartStrategy",
    "RestartResult",
    # Scale Manager
    "ScaleManager",
    "ScaleMode",
    "ScaleResult",
    "HPAOverride",
    # Resource Tuner
    "ResourceTuner",
    "ResourceSpec",
    "TuningResult",
    "ResourceRecommendation",
    # Drain Manager
    "DrainManager",
    "DrainConfig",
    "DrainResult",
    "DrainStatus",
    # Deployment Rollback
    "DeploymentRollback",
    "RollbackConfig",
    "RollbackResult",
    "RevisionInfo",
]
