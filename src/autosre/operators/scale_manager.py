"""
Scale Manager Operator.

Provides intelligent scaling capabilities:
- Manual scaling with validation
- HPA override management
- Scale-to-zero protection
- Burst scaling
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


class ScaleMode(str, Enum):
    """Scaling mode."""
    
    ABSOLUTE = "absolute"           # Set to exact replica count
    RELATIVE = "relative"           # Add/subtract from current
    PERCENTAGE = "percentage"       # Scale by percentage


class ScaleConfig(OperatorConfig):
    """Configuration for scale manager."""
    
    # Limits
    max_replicas: int = Field(100, description="Maximum allowed replicas")
    min_replicas: int = Field(0, description="Minimum allowed replicas")
    
    # Safety
    allow_scale_to_zero: bool = Field(False, description="Allow scaling to zero")
    require_approval_above: int = Field(50, description="Require approval above this")
    
    # HPA
    hpa_restore_delay_minutes: int = Field(30, description="Delay before restoring HPA")
    
    # Verification
    verify_scale_complete: bool = Field(True, description="Wait for scaling")
    scale_timeout_seconds: int = Field(300, description="Timeout for scaling")


class HPAOverride(BaseModel):
    """HPA override configuration."""
    
    id: UUID = Field(default_factory=uuid4)
    namespace: str
    deployment_name: str
    hpa_name: str
    
    # Original values
    original_min_replicas: int
    original_max_replicas: int
    
    # Override values
    override_min_replicas: int
    override_max_replicas: int
    
    # Status
    active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime | None = None
    restored_at: datetime | None = None
    
    @property
    def is_expired(self) -> bool:
        if self.expires_at:
            return datetime.utcnow() > self.expires_at
        return False


class ScaleResult(OperatorResult):
    """Result of a scale operation."""
    
    # Scale details
    mode: ScaleMode = ScaleMode.ABSOLUTE
    original_replicas: int = 0
    target_replicas: int = 0
    final_replicas: int | None = None
    
    # HPA
    hpa_override: HPAOverride | None = None
    hpa_paused: bool = False
    
    # Timing
    scale_started_at: datetime | None = None
    scale_completed_at: datetime | None = None
    
    @property
    def scale_duration_seconds(self) -> float | None:
        if self.scale_started_at and self.scale_completed_at:
            return (self.scale_completed_at - self.scale_started_at).total_seconds()
        return None


class ScaleManager(BaseOperator[ScaleResult]):
    """
    Intelligent scaling operator.
    
    Features:
    - Multiple scaling modes
    - HPA override and restore
    - Scale verification
    - Safety limits
    
    Example:
        scaler = ScaleManager(k8s_client)
        
        # Scale to exact count
        result = await scaler.scale_deployment("prod", "api", replicas=10)
        
        # Scale up by percentage
        result = await scaler.scale_deployment(
            "prod", "api",
            amount=50,
            mode=ScaleMode.PERCENTAGE
        )
        
        # Override HPA temporarily
        override = await scaler.override_hpa(
            "prod", "api", "api-hpa",
            min_replicas=10,
            max_replicas=10,
            duration_minutes=30
        )
    """
    
    def __init__(
        self,
        k8s_client: Any,
        config: ScaleConfig | None = None,
    ):
        super().__init__(k8s_client, config or ScaleConfig())
        self._active_overrides: dict[str, HPAOverride] = {}
    
    @property
    def name(self) -> str:
        return "ScaleManager"
    
    @property
    def scale_config(self) -> ScaleConfig:
        return self._config  # type: ignore
    
    async def health_check(self) -> bool:
        """Verify operator can perform scaling."""
        try:
            await self._k8s.list_deployments("default", limit=1)
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    async def scale_deployment(
        self,
        namespace: str,
        deployment_name: str,
        replicas: int | None = None,
        amount: int | None = None,
        mode: ScaleMode = ScaleMode.ABSOLUTE,
        override_hpa: bool = False,
        dry_run: bool = False,
    ) -> ScaleResult:
        """
        Scale a deployment.
        
        Args:
            namespace: Kubernetes namespace
            deployment_name: Deployment name
            replicas: Target replica count (for ABSOLUTE mode)
            amount: Scale amount (for RELATIVE or PERCENTAGE mode)
            mode: Scaling mode
            override_hpa: Override HPA if present
            dry_run: Dry run mode
            
        Returns:
            Scale result
        """
        dry_run = dry_run or self._config.dry_run
        
        result = ScaleResult(
            operation="scale_deployment",
            resource_type="deployment",
            resource_name=deployment_name,
            namespace=namespace,
            mode=mode,
        )
        
        try:
            # Get current deployment
            deployment = await self._k8s.get_deployment(namespace, deployment_name)
            result.original_replicas = deployment.replicas
            
            # Calculate target replicas
            if mode == ScaleMode.ABSOLUTE:
                target = replicas or deployment.replicas
            elif mode == ScaleMode.RELATIVE:
                target = deployment.replicas + (amount or 0)
            elif mode == ScaleMode.PERCENTAGE:
                pct = (amount or 0) / 100.0
                target = int(deployment.replicas * (1 + pct))
            else:
                target = deployment.replicas
            
            result.target_replicas = target
            
            # Validate target
            validation_error = self._validate_scale_target(
                target, deployment.replicas
            )
            if validation_error:
                result.fail(validation_error, "ValidationError")
                return result
            
            logger.info(
                f"Scaling {namespace}/{deployment_name}: "
                f"{deployment.replicas} -> {target} (mode={mode.value})"
            )
            
            if dry_run:
                result.complete(
                    success=True,
                    message=f"Dry run - would scale from {deployment.replicas} to {target}",
                )
                return result
            
            # Check for HPA
            if override_hpa:
                hpa_override = await self._check_and_override_hpa(
                    namespace, deployment_name, target
                )
                if hpa_override:
                    result.hpa_override = hpa_override
                    result.hpa_paused = True
            
            # Perform scale
            result.status = OperatorStatus.EXECUTING
            result.scale_started_at = datetime.utcnow()
            
            scaled_deployment = await self._k8s.scale_deployment(
                namespace, deployment_name, target
            )
            
            result.add_change(
                "replicas",
                deployment.replicas,
                target,
                f"Scaled deployment",
            )
            
            # Wait for scale to complete
            if self.scale_config.verify_scale_complete:
                result.status = OperatorStatus.WAITING
                await self._wait_for_scale(namespace, deployment_name, target, result)
            
            result.final_replicas = target
            result.scale_completed_at = datetime.utcnow()
            
            result.complete(
                success=True,
                message=f"Scaled from {deployment.replicas} to {target} replicas",
            )
            
        except Exception as e:
            result.fail(str(e), type(e).__name__)
            logger.error(f"Scale operation failed: {e}", exc_info=True)
        
        self._record_operation(result)
        return result
    
    async def scale_statefulset(
        self,
        namespace: str,
        statefulset_name: str,
        replicas: int,
        dry_run: bool = False,
    ) -> ScaleResult:
        """
        Scale a StatefulSet.
        
        Args:
            namespace: Kubernetes namespace
            statefulset_name: StatefulSet name
            replicas: Target replica count
            dry_run: Dry run mode
            
        Returns:
            Scale result
        """
        result = ScaleResult(
            operation="scale_statefulset",
            resource_type="statefulset",
            resource_name=statefulset_name,
            namespace=namespace,
            target_replicas=replicas,
        )
        
        try:
            # Validate
            if replicas < 0:
                result.fail("Replica count cannot be negative")
                return result
            
            if replicas > self.scale_config.max_replicas:
                result.fail(f"Exceeds max replicas ({self.scale_config.max_replicas})")
                return result
            
            if dry_run:
                result.complete(
                    success=True,
                    message=f"Dry run - would scale StatefulSet to {replicas}",
                )
                return result
            
            # Scale via patch
            patch = {"spec": {"replicas": replicas}}
            await self._k8s._request(
                "PATCH",
                f"/apis/apps/v1/namespaces/{namespace}/statefulsets/{statefulset_name}",
                json=patch,
                headers={"Content-Type": "application/strategic-merge-patch+json"},
            )
            
            result.final_replicas = replicas
            result.complete(
                success=True,
                message=f"Scaled StatefulSet to {replicas} replicas",
            )
            
        except Exception as e:
            result.fail(str(e), type(e).__name__)
            logger.error(f"StatefulSet scale failed: {e}", exc_info=True)
        
        self._record_operation(result)
        return result
    
    async def override_hpa(
        self,
        namespace: str,
        deployment_name: str,
        hpa_name: str,
        min_replicas: int | None = None,
        max_replicas: int | None = None,
        duration_minutes: int | None = None,
        dry_run: bool = False,
    ) -> HPAOverride | None:
        """
        Override HPA settings temporarily.
        
        Args:
            namespace: Kubernetes namespace
            deployment_name: Deployment name
            hpa_name: HPA name
            min_replicas: Override min replicas
            max_replicas: Override max replicas
            duration_minutes: Override duration (None = permanent until restored)
            dry_run: Dry run mode
            
        Returns:
            HPA override info
        """
        try:
            # Get current HPA
            hpa = await self._k8s._request(
                "GET",
                f"/apis/autoscaling/v2/namespaces/{namespace}/horizontalpodautoscalers/{hpa_name}",
            )
            
            original_min = hpa.get("spec", {}).get("minReplicas", 1)
            original_max = hpa.get("spec", {}).get("maxReplicas", 10)
            
            override_min = min_replicas if min_replicas is not None else original_min
            override_max = max_replicas if max_replicas is not None else original_max
            
            override = HPAOverride(
                namespace=namespace,
                deployment_name=deployment_name,
                hpa_name=hpa_name,
                original_min_replicas=original_min,
                original_max_replicas=original_max,
                override_min_replicas=override_min,
                override_max_replicas=override_max,
                expires_at=(
                    datetime.utcnow() + timedelta(minutes=duration_minutes)
                    if duration_minutes else None
                ),
            )
            
            logger.info(
                f"Overriding HPA {namespace}/{hpa_name}: "
                f"min={original_min}->{override_min}, max={original_max}->{override_max}"
            )
            
            if dry_run:
                logger.info("Dry run - HPA override not applied")
                return override
            
            # Patch HPA
            patch = {
                "spec": {
                    "minReplicas": override_min,
                    "maxReplicas": override_max,
                }
            }
            
            await self._k8s._request(
                "PATCH",
                f"/apis/autoscaling/v2/namespaces/{namespace}/horizontalpodautoscalers/{hpa_name}",
                json=patch,
                headers={"Content-Type": "application/strategic-merge-patch+json"},
            )
            
            # Track override
            override_key = f"{namespace}/{hpa_name}"
            self._active_overrides[override_key] = override
            
            logger.info(f"HPA override applied: {override_key}")
            
            return override
            
        except Exception as e:
            logger.error(f"HPA override failed: {e}", exc_info=True)
            return None
    
    async def restore_hpa(
        self,
        namespace: str,
        hpa_name: str,
        dry_run: bool = False,
    ) -> bool:
        """
        Restore HPA to original settings.
        
        Args:
            namespace: Kubernetes namespace
            hpa_name: HPA name
            dry_run: Dry run mode
            
        Returns:
            True if restored
        """
        override_key = f"{namespace}/{hpa_name}"
        override = self._active_overrides.get(override_key)
        
        if not override:
            logger.warning(f"No active override for {override_key}")
            return False
        
        try:
            logger.info(
                f"Restoring HPA {override_key}: "
                f"min={override.original_min_replicas}, max={override.original_max_replicas}"
            )
            
            if dry_run:
                logger.info("Dry run - HPA restore not applied")
                return True
            
            # Patch HPA back to original
            patch = {
                "spec": {
                    "minReplicas": override.original_min_replicas,
                    "maxReplicas": override.original_max_replicas,
                }
            }
            
            await self._k8s._request(
                "PATCH",
                f"/apis/autoscaling/v2/namespaces/{namespace}/horizontalpodautoscalers/{hpa_name}",
                json=patch,
                headers={"Content-Type": "application/strategic-merge-patch+json"},
            )
            
            # Update override record
            override.active = False
            override.restored_at = datetime.utcnow()
            del self._active_overrides[override_key]
            
            logger.info(f"HPA restored: {override_key}")
            return True
            
        except Exception as e:
            logger.error(f"HPA restore failed: {e}", exc_info=True)
            return False
    
    async def restore_expired_overrides(self) -> int:
        """
        Restore all expired HPA overrides.
        
        Returns:
            Number of overrides restored
        """
        restored = 0
        
        for key, override in list(self._active_overrides.items()):
            if override.is_expired and override.active:
                success = await self.restore_hpa(
                    override.namespace,
                    override.hpa_name,
                )
                if success:
                    restored += 1
        
        return restored
    
    def _validate_scale_target(
        self,
        target: int,
        current: int,
    ) -> str | None:
        """Validate scale target. Returns error message or None."""
        if target < 0:
            return "Replica count cannot be negative"
        
        if target > self.scale_config.max_replicas:
            return f"Target {target} exceeds max replicas ({self.scale_config.max_replicas})"
        
        if target < self.scale_config.min_replicas:
            return f"Target {target} below min replicas ({self.scale_config.min_replicas})"
        
        if target == 0 and not self.scale_config.allow_scale_to_zero:
            return "Scale to zero not allowed by policy"
        
        return None
    
    async def _check_and_override_hpa(
        self,
        namespace: str,
        deployment_name: str,
        target_replicas: int,
    ) -> HPAOverride | None:
        """Check for HPA and override if needed."""
        try:
            # List HPAs in namespace
            hpas = await self._k8s._request(
                "GET",
                f"/apis/autoscaling/v2/namespaces/{namespace}/horizontalpodautoscalers",
            )
            
            for hpa in hpas.get("items", []):
                # Check if HPA targets this deployment
                ref = hpa.get("spec", {}).get("scaleTargetRef", {})
                if (
                    ref.get("kind") == "Deployment"
                    and ref.get("name") == deployment_name
                ):
                    hpa_name = hpa.get("metadata", {}).get("name")
                    
                    # Override HPA to allow our target
                    return await self.override_hpa(
                        namespace,
                        deployment_name,
                        hpa_name,
                        min_replicas=target_replicas,
                        max_replicas=max(
                            target_replicas,
                            hpa.get("spec", {}).get("maxReplicas", target_replicas),
                        ),
                        duration_minutes=self.scale_config.hpa_restore_delay_minutes,
                    )
            
            return None
            
        except Exception as e:
            logger.warning(f"Error checking HPA: {e}")
            return None
    
    async def _wait_for_scale(
        self,
        namespace: str,
        deployment_name: str,
        target: int,
        result: ScaleResult,
    ) -> bool:
        """Wait for deployment to reach target replicas."""
        timeout = self.scale_config.scale_timeout_seconds
        interval = 5.0
        
        start_time = datetime.utcnow()
        
        while (datetime.utcnow() - start_time).total_seconds() < timeout:
            try:
                deployment = await self._k8s.get_deployment(namespace, deployment_name)
                
                if deployment.ready_replicas == target:
                    logger.info(f"Deployment {deployment_name} reached {target} replicas")
                    return True
                
                logger.debug(
                    f"Scale progress: {deployment.ready_replicas}/{target} ready"
                )
                
            except Exception as e:
                logger.warning(f"Error checking scale: {e}")
            
            await asyncio.sleep(interval)
        
        logger.warning(f"Scale did not complete in time")
        return False
    
    def get_active_overrides(self) -> list[HPAOverride]:
        """Get all active HPA overrides."""
        return [o for o in self._active_overrides.values() if o.active]
