"""
Deployment Rollback Operator.

Provides automated rollback capabilities:
- Revision history management
- Health-based rollback decisions
- Progressive rollback
- Rollback verification
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from autosre.utils.logging import get_logger

from .base import BaseOperator, OperatorConfig, OperatorResult, OperatorStatus

logger = get_logger(__name__)


class RollbackTrigger(str, Enum):
    """What triggered the rollback."""
    
    MANUAL = "manual"               # Manual request
    AUTO_HEALTH = "auto_health"     # Automatic due to health check failure
    AUTO_ERROR = "auto_error"       # Automatic due to error rate
    AUTO_LATENCY = "auto_latency"   # Automatic due to latency
    AUTO_CRASH = "auto_crash"       # Automatic due to crash loop
    INCIDENT = "incident"           # Part of incident response


class RevisionInfo(BaseModel):
    """Information about a deployment revision."""
    
    revision: int
    image: str | None = None
    replicas: int = 0
    
    # Timing
    created_at: datetime | None = None
    deployed_at: datetime | None = None
    
    # Change info
    change_cause: str | None = None
    changed_by: str | None = None
    
    # Labels
    labels: dict[str, str] = Field(default_factory=dict)
    
    # Health at deployment
    was_healthy: bool | None = None
    health_check_passed: bool | None = None


class RollbackConfig(OperatorConfig):
    """Configuration for deployment rollback."""
    
    # Revision selection
    prefer_last_healthy: bool = Field(True, description="Prefer last healthy revision")
    max_revision_age_hours: int = Field(168, description="Max age of revision to rollback to")
    
    # Health checking
    verify_after_rollback: bool = Field(True, description="Verify health after rollback")
    health_check_timeout_seconds: int = Field(120, description="Health check timeout")
    health_check_interval_seconds: float = Field(5.0)
    
    # Auto-rollback
    enable_auto_rollback: bool = Field(False, description="Enable automatic rollback")
    auto_rollback_error_threshold: float = Field(0.1, description="Error rate to trigger")
    auto_rollback_latency_threshold_ms: int = Field(5000, description="P99 latency threshold")
    auto_rollback_window_seconds: int = Field(300, description="Monitoring window")
    
    # Safety
    min_time_between_rollbacks_seconds: int = Field(300, description="Cooldown between rollbacks")


class RollbackResult(OperatorResult):
    """Result of a rollback operation."""
    
    # Trigger
    trigger: RollbackTrigger = RollbackTrigger.MANUAL
    
    # Revisions
    from_revision: int | None = None
    to_revision: int | None = None
    
    # Revision details
    from_revision_info: RevisionInfo | None = None
    to_revision_info: RevisionInfo | None = None
    
    # Health
    health_verified: bool = False
    health_check_attempts: int = 0
    
    # Timing
    rollback_started_at: datetime | None = None
    rollback_completed_at: datetime | None = None
    
    @property
    def rollback_duration_seconds(self) -> float | None:
        if self.rollback_started_at and self.rollback_completed_at:
            return (self.rollback_completed_at - self.rollback_started_at).total_seconds()
        return None


class DeploymentRollback(BaseOperator[RollbackResult]):
    """
    Automated deployment rollback operator.
    
    Features:
    - Revision history tracking
    - Intelligent rollback target selection
    - Health verification
    - Auto-rollback support
    
    Example:
        rollback = DeploymentRollback(k8s_client)
        
        # Rollback to previous revision
        result = await rollback.rollback_deployment("prod", "api")
        
        # Rollback to specific revision
        result = await rollback.rollback_deployment(
            "prod", "api",
            target_revision=5
        )
        
        # List available revisions
        revisions = await rollback.get_revisions("prod", "api")
    """
    
    def __init__(
        self,
        k8s_client: Any,
        config: RollbackConfig | None = None,
    ):
        super().__init__(k8s_client, config or RollbackConfig())
        
        # Track last rollback time per deployment
        self._last_rollback: dict[str, datetime] = {}
        
        # Track revision health
        self._revision_health: dict[str, dict[int, bool]] = {}
    
    @property
    def name(self) -> str:
        return "DeploymentRollback"
    
    @property
    def rollback_config(self) -> RollbackConfig:
        return self._config  # type: ignore
    
    async def health_check(self) -> bool:
        """Verify operator can perform rollbacks."""
        try:
            await self._k8s.list_deployments("default", limit=1)
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    async def rollback_deployment(
        self,
        namespace: str,
        deployment_name: str,
        target_revision: int | None = None,
        trigger: RollbackTrigger = RollbackTrigger.MANUAL,
        verify_health: bool | None = None,
        dry_run: bool = False,
    ) -> RollbackResult:
        """
        Rollback a deployment to a previous revision.
        
        Args:
            namespace: Kubernetes namespace
            deployment_name: Deployment name
            target_revision: Specific revision to rollback to (None = previous)
            trigger: What triggered the rollback
            verify_health: Verify health after rollback
            dry_run: Dry run mode
            
        Returns:
            Rollback result
        """
        dry_run = dry_run or self._config.dry_run
        verify_health = verify_health if verify_health is not None else self.rollback_config.verify_after_rollback
        
        result = RollbackResult(
            operation="rollback_deployment",
            resource_type="deployment",
            resource_name=deployment_name,
            namespace=namespace,
            trigger=trigger,
        )
        
        deployment_key = f"{namespace}/{deployment_name}"
        
        try:
            # Check cooldown
            if not self._check_cooldown(deployment_key):
                result.fail(
                    f"Rollback in cooldown (wait {self.rollback_config.min_time_between_rollbacks_seconds}s)",
                    "CooldownViolation",
                )
                return result
            
            # Get deployment
            deployment = await self._k8s._request(
                "GET",
                f"/apis/apps/v1/namespaces/{namespace}/deployments/{deployment_name}",
            )
            
            current_revision = int(
                deployment.get("metadata", {})
                .get("annotations", {})
                .get("deployment.kubernetes.io/revision", "0")
            )
            result.from_revision = current_revision
            
            # Get revision history
            revisions = await self.get_revisions(namespace, deployment_name)
            
            if len(revisions) < 2:
                result.fail("No previous revisions available", "NoRevisions")
                return result
            
            # Determine target revision
            if target_revision is not None:
                target = next((r for r in revisions if r.revision == target_revision), None)
                if not target:
                    result.fail(f"Revision {target_revision} not found", "RevisionNotFound")
                    return result
            else:
                # Select best target revision
                target = self._select_target_revision(revisions, current_revision)
            
            result.to_revision = target.revision
            result.to_revision_info = target
            
            logger.info(
                f"Rolling back {deployment_key} from revision {current_revision} "
                f"to revision {target.revision} (trigger={trigger.value})"
            )
            
            if dry_run:
                result.complete(
                    success=True,
                    message=f"Dry run - would rollback from {current_revision} to {target.revision}",
                )
                return result
            
            # Perform rollback
            result.status = OperatorStatus.EXECUTING
            result.rollback_started_at = datetime.utcnow()
            
            # Get the ReplicaSet for the target revision
            rs_name = await self._get_replicaset_for_revision(
                namespace, deployment_name, target.revision
            )
            
            if not rs_name:
                result.fail(f"ReplicaSet for revision {target.revision} not found")
                return result
            
            # Rollback by patching deployment with target RS template
            await self._perform_rollback(namespace, deployment_name, rs_name, target.revision)
            
            result.add_change(
                "revision",
                current_revision,
                target.revision,
                f"Rolled back to revision {target.revision}",
            )
            
            # Wait for rollout
            result.status = OperatorStatus.WAITING
            await self._wait_for_rollout(namespace, deployment_name)
            
            result.rollback_completed_at = datetime.utcnow()
            
            # Verify health
            if verify_health:
                healthy = await self._verify_deployment_health(
                    namespace, deployment_name, result
                )
                result.health_verified = healthy
                
                if not healthy:
                    result.fail("Health check failed after rollback")
                    return result
            
            # Update cooldown
            self._last_rollback[deployment_key] = datetime.utcnow()
            
            result.complete(
                success=True,
                message=f"Rolled back from revision {current_revision} to {target.revision}",
            )
            
        except Exception as e:
            result.fail(str(e), type(e).__name__)
            logger.error(f"Rollback failed: {e}", exc_info=True)
        
        self._record_operation(result)
        return result
    
    async def get_revisions(
        self,
        namespace: str,
        deployment_name: str,
        limit: int = 10,
    ) -> list[RevisionInfo]:
        """
        Get revision history for a deployment.
        
        Args:
            namespace: Kubernetes namespace
            deployment_name: Deployment name
            limit: Maximum revisions to return
            
        Returns:
            List of revisions (newest first)
        """
        revisions = []
        
        try:
            # Get deployment
            deployment = await self._k8s._request(
                "GET",
                f"/apis/apps/v1/namespaces/{namespace}/deployments/{deployment_name}",
            )
            
            selector = deployment.get("spec", {}).get("selector", {}).get("matchLabels", {})
            label_selector = ",".join(f"{k}={v}" for k, v in selector.items())
            
            # Get ReplicaSets
            rs_list = await self._k8s._request(
                "GET",
                f"/apis/apps/v1/namespaces/{namespace}/replicasets",
                params={"labelSelector": label_selector},
            )
            
            for rs in rs_list.get("items", []):
                # Check owner reference
                owners = rs.get("metadata", {}).get("ownerReferences", [])
                is_owned = any(
                    o.get("kind") == "Deployment" and o.get("name") == deployment_name
                    for o in owners
                )
                
                if not is_owned:
                    continue
                
                revision = int(
                    rs.get("metadata", {})
                    .get("annotations", {})
                    .get("deployment.kubernetes.io/revision", "0")
                )
                
                # Get image from first container
                containers = rs.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
                image = containers[0].get("image") if containers else None
                
                change_cause = (
                    rs.get("metadata", {})
                    .get("annotations", {})
                    .get("kubernetes.io/change-cause")
                )
                
                created_at = rs.get("metadata", {}).get("creationTimestamp")
                
                revisions.append(RevisionInfo(
                    revision=revision,
                    image=image,
                    replicas=rs.get("spec", {}).get("replicas", 0),
                    created_at=datetime.fromisoformat(created_at.rstrip("Z")) if created_at else None,
                    change_cause=change_cause,
                    labels=rs.get("metadata", {}).get("labels", {}),
                ))
            
            # Sort by revision (newest first)
            revisions.sort(key=lambda r: r.revision, reverse=True)
            
            return revisions[:limit]
            
        except Exception as e:
            logger.error(f"Failed to get revisions: {e}", exc_info=True)
            return []
    
    async def get_last_healthy_revision(
        self,
        namespace: str,
        deployment_name: str,
    ) -> RevisionInfo | None:
        """
        Get the last known healthy revision.
        
        Args:
            namespace: Kubernetes namespace
            deployment_name: Deployment name
            
        Returns:
            Last healthy revision or None
        """
        deployment_key = f"{namespace}/{deployment_name}"
        health_map = self._revision_health.get(deployment_key, {})
        
        revisions = await self.get_revisions(namespace, deployment_name)
        
        for rev in revisions:
            if health_map.get(rev.revision, False):
                return rev
        
        return None
    
    async def mark_revision_healthy(
        self,
        namespace: str,
        deployment_name: str,
        revision: int,
        healthy: bool = True,
    ) -> None:
        """
        Mark a revision as healthy or unhealthy.
        
        Args:
            namespace: Kubernetes namespace
            deployment_name: Deployment name
            revision: Revision number
            healthy: Whether revision is healthy
        """
        deployment_key = f"{namespace}/{deployment_name}"
        
        if deployment_key not in self._revision_health:
            self._revision_health[deployment_key] = {}
        
        self._revision_health[deployment_key][revision] = healthy
        logger.info(f"Marked {deployment_key} revision {revision} as {'healthy' if healthy else 'unhealthy'}")
    
    async def should_auto_rollback(
        self,
        namespace: str,
        deployment_name: str,
        current_error_rate: float | None = None,
        current_p99_latency_ms: float | None = None,
        crash_loop_detected: bool = False,
    ) -> tuple[bool, RollbackTrigger | None, str]:
        """
        Determine if auto-rollback should be triggered.
        
        Args:
            namespace: Kubernetes namespace
            deployment_name: Deployment name
            current_error_rate: Current error rate (0-1)
            current_p99_latency_ms: Current P99 latency in ms
            crash_loop_detected: Whether crash loop was detected
            
        Returns:
            Tuple of (should_rollback, trigger, reason)
        """
        if not self.rollback_config.enable_auto_rollback:
            return False, None, "Auto-rollback disabled"
        
        # Check crash loop
        if crash_loop_detected:
            return True, RollbackTrigger.AUTO_CRASH, "Crash loop detected"
        
        # Check error rate
        if current_error_rate is not None:
            if current_error_rate > self.rollback_config.auto_rollback_error_threshold:
                return True, RollbackTrigger.AUTO_ERROR, f"Error rate {current_error_rate:.2%} exceeds threshold"
        
        # Check latency
        if current_p99_latency_ms is not None:
            if current_p99_latency_ms > self.rollback_config.auto_rollback_latency_threshold_ms:
                return True, RollbackTrigger.AUTO_LATENCY, f"P99 latency {current_p99_latency_ms}ms exceeds threshold"
        
        return False, None, "No auto-rollback conditions met"
    
    def _check_cooldown(self, deployment_key: str) -> bool:
        """Check if deployment is in rollback cooldown."""
        last_rollback = self._last_rollback.get(deployment_key)
        if not last_rollback:
            return True
        
        cooldown = timedelta(seconds=self.rollback_config.min_time_between_rollbacks_seconds)
        return datetime.utcnow() > last_rollback + cooldown
    
    def _select_target_revision(
        self,
        revisions: list[RevisionInfo],
        current_revision: int,
    ) -> RevisionInfo:
        """Select the best revision to rollback to."""
        # Filter out current revision
        candidates = [r for r in revisions if r.revision != current_revision]
        
        if not candidates:
            raise ValueError("No candidate revisions")
        
        # If prefer last healthy, check health map
        if self.rollback_config.prefer_last_healthy:
            for rev in candidates:
                if rev.was_healthy:
                    return rev
        
        # Check revision age
        max_age = timedelta(hours=self.rollback_config.max_revision_age_hours)
        now = datetime.utcnow()
        
        valid_candidates = [
            r for r in candidates
            if r.created_at is None or (now - r.created_at) <= max_age
        ]
        
        if not valid_candidates:
            valid_candidates = candidates
        
        # Return highest revision number (most recent)
        return max(valid_candidates, key=lambda r: r.revision)
    
    async def _get_replicaset_for_revision(
        self,
        namespace: str,
        deployment_name: str,
        revision: int,
    ) -> str | None:
        """Get ReplicaSet name for a specific revision."""
        deployment = await self._k8s._request(
            "GET",
            f"/apis/apps/v1/namespaces/{namespace}/deployments/{deployment_name}",
        )
        
        selector = deployment.get("spec", {}).get("selector", {}).get("matchLabels", {})
        label_selector = ",".join(f"{k}={v}" for k, v in selector.items())
        
        rs_list = await self._k8s._request(
            "GET",
            f"/apis/apps/v1/namespaces/{namespace}/replicasets",
            params={"labelSelector": label_selector},
        )
        
        for rs in rs_list.get("items", []):
            rs_revision = int(
                rs.get("metadata", {})
                .get("annotations", {})
                .get("deployment.kubernetes.io/revision", "0")
            )
            
            if rs_revision == revision:
                return rs.get("metadata", {}).get("name")
        
        return None
    
    async def _perform_rollback(
        self,
        namespace: str,
        deployment_name: str,
        rs_name: str,
        target_revision: int,
    ) -> None:
        """Perform the actual rollback."""
        # Get the target ReplicaSet
        rs = await self._k8s._request(
            "GET",
            f"/apis/apps/v1/namespaces/{namespace}/replicasets/{rs_name}",
        )
        
        # Extract template from RS
        template = rs.get("spec", {}).get("template", {})
        
        # Patch deployment with new template
        patch = {
            "spec": {
                "template": template,
            },
            "metadata": {
                "annotations": {
                    "kubernetes.io/change-cause": f"Rollback to revision {target_revision}",
                },
            },
        }
        
        await self._k8s._request(
            "PATCH",
            f"/apis/apps/v1/namespaces/{namespace}/deployments/{deployment_name}",
            json=patch,
            headers={"Content-Type": "application/strategic-merge-patch+json"},
        )
        
        logger.info(f"Initiated rollback of {namespace}/{deployment_name} to revision {target_revision}")
    
    async def _wait_for_rollout(
        self,
        namespace: str,
        deployment_name: str,
    ) -> bool:
        """Wait for rollout to complete."""
        timeout = self._config.operation_timeout_seconds
        interval = 5.0
        
        start_time = datetime.utcnow()
        
        while (datetime.utcnow() - start_time).total_seconds() < timeout:
            try:
                deployment = await self._k8s.get_deployment(namespace, deployment_name)
                
                if (
                    deployment.ready_replicas == deployment.replicas
                    and deployment.updated_replicas == deployment.replicas
                    and deployment.available_replicas == deployment.replicas
                ):
                    logger.info(f"Rollout complete for {namespace}/{deployment_name}")
                    return True
                
                logger.debug(
                    f"Rollout progress: {deployment.ready_replicas}/{deployment.replicas} ready"
                )
                
            except Exception as e:
                logger.warning(f"Error checking rollout: {e}")
            
            await asyncio.sleep(interval)
        
        logger.warning(f"Rollout did not complete in time")
        return False
    
    async def _verify_deployment_health(
        self,
        namespace: str,
        deployment_name: str,
        result: RollbackResult,
    ) -> bool:
        """Verify deployment is healthy after rollback."""
        timeout = self.rollback_config.health_check_timeout_seconds
        interval = self.rollback_config.health_check_interval_seconds
        
        start_time = datetime.utcnow()
        
        while (datetime.utcnow() - start_time).total_seconds() < timeout:
            result.health_check_attempts += 1
            
            try:
                deployment = await self._k8s.get_deployment(namespace, deployment_name)
                
                # Check if all replicas are ready
                if deployment.is_available:
                    # Check for any warning events
                    events = await self._k8s.list_events(
                        namespace,
                        involved_object_kind="Deployment",
                        involved_object_name=deployment_name,
                    )
                    
                    warning_events = [e for e in events if e.type.value == "Warning"]
                    recent_warnings = [
                        e for e in warning_events
                        if e.last_timestamp and (datetime.utcnow() - e.last_timestamp).total_seconds() < 60
                    ]
                    
                    if not recent_warnings:
                        logger.info(f"Deployment {namespace}/{deployment_name} is healthy")
                        return True
                
            except Exception as e:
                logger.warning(f"Health check error: {e}")
            
            await asyncio.sleep(interval)
        
        logger.warning(f"Health verification timed out for {namespace}/{deployment_name}")
        return False
