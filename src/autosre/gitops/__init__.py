"""
AutoSRE GitOps Integration Module

Enterprise-grade GitOps capabilities providing:
- ArgoCD integration for application deployment and sync management
- Flux CD integration for GitOps automation
- Configuration drift detection and remediation
- GitOps-driven incident response automation

Enables GitOps-driven SRE workflows with automatic drift detection,
sync status monitoring, and incident response integration.

Usage:
    from autosre.gitops import (
        # ArgoCD
        ArgoCDClient, Application, ApplicationStatus, SyncOperation,
        SyncPolicy, HealthStatus, SyncStatus,
        # Flux
        FluxClient, Kustomization, HelmRelease, GitRepository,
        FluxHealthStatus, FluxSyncStatus,
        # Drift Detection
        DriftDetector, DriftReport, DriftType, DriftSeverity,
        DriftRemediator, RemediationAction, RemediationResult,
    )
"""

from autosre.gitops.argocd import (
    ArgoCDClient,
    ArgoCDConfig,
    Application,
    ApplicationStatus,
    ApplicationSource,
    ApplicationDestination,
    SyncOperation,
    SyncOperationResult,
    SyncPolicy,
    SyncStrategy,
    HealthStatus,
    SyncStatus,
    ResourceStatus,
    ResourceHealth,
    ApplicationSet,
    ApplicationSetGenerator,
    Rollout,
    RolloutStrategy,
    ArgoCDWebhook,
    ArgoCDEventType,
)
from autosre.gitops.flux import (
    FluxClient,
    FluxConfig,
    Kustomization,
    KustomizationStatus,
    HelmRelease,
    HelmReleaseStatus,
    HelmChart,
    GitRepository,
    GitRepositoryStatus,
    OCIRepository,
    Bucket,
    FluxHealthStatus,
    FluxSyncStatus,
    FluxCondition,
    SourceRef,
    CrossNamespaceSourceRef,
    FluxReconciler,
    FluxAlert,
    FluxAlertProvider,
)
from autosre.gitops.drift import (
    DriftDetector,
    DriftDetectorConfig,
    DriftReport,
    DriftItem,
    DriftType,
    DriftSeverity,
    DriftSource,
    DriftRemediator,
    RemediationAction,
    RemediationActionType,
    RemediationResult,
    RemediationPolicy,
    DriftNotifier,
    DriftNotificationConfig,
    DriftScheduler,
    DriftIncidentIntegration,
)

__all__ = [
    # ArgoCD
    "ArgoCDClient",
    "ArgoCDConfig",
    "Application",
    "ApplicationStatus",
    "ApplicationSource",
    "ApplicationDestination",
    "SyncOperation",
    "SyncOperationResult",
    "SyncPolicy",
    "SyncStrategy",
    "HealthStatus",
    "SyncStatus",
    "ResourceStatus",
    "ResourceHealth",
    "ApplicationSet",
    "ApplicationSetGenerator",
    "Rollout",
    "RolloutStrategy",
    "ArgoCDWebhook",
    "ArgoCDEventType",
    # Flux
    "FluxClient",
    "FluxConfig",
    "Kustomization",
    "KustomizationStatus",
    "HelmRelease",
    "HelmReleaseStatus",
    "HelmChart",
    "GitRepository",
    "GitRepositoryStatus",
    "OCIRepository",
    "Bucket",
    "FluxHealthStatus",
    "FluxSyncStatus",
    "FluxCondition",
    "SourceRef",
    "CrossNamespaceSourceRef",
    "FluxReconciler",
    "FluxAlert",
    "FluxAlertProvider",
    # Drift Detection
    "DriftDetector",
    "DriftDetectorConfig",
    "DriftReport",
    "DriftItem",
    "DriftType",
    "DriftSeverity",
    "DriftSource",
    "DriftRemediator",
    "RemediationAction",
    "RemediationActionType",
    "RemediationResult",
    "RemediationPolicy",
    "DriftNotifier",
    "DriftNotificationConfig",
    "DriftScheduler",
    "DriftIncidentIntegration",
]
