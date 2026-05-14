"""
Resource Tuner Operator.

Provides intelligent resource adjustment capabilities:
- CPU/memory limit tuning
- Request optimization
- VPA integration
- Resource recommendations
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


class ResourceSpec(BaseModel):
    """Resource specification (CPU/memory)."""
    
    cpu_request: str | None = None
    cpu_limit: str | None = None
    memory_request: str | None = None
    memory_limit: str | None = None
    
    def to_k8s_resources(self) -> dict[str, Any]:
        """Convert to Kubernetes resource format."""
        resources: dict[str, Any] = {"requests": {}, "limits": {}}
        
        if self.cpu_request:
            resources["requests"]["cpu"] = self.cpu_request
        if self.cpu_limit:
            resources["limits"]["cpu"] = self.cpu_limit
        if self.memory_request:
            resources["requests"]["memory"] = self.memory_request
        if self.memory_limit:
            resources["limits"]["memory"] = self.memory_limit
        
        return resources
    
    @classmethod
    def from_k8s_resources(cls, resources: dict[str, Any]) -> "ResourceSpec":
        """Create from Kubernetes resource format."""
        requests = resources.get("requests", {})
        limits = resources.get("limits", {})
        
        return cls(
            cpu_request=requests.get("cpu"),
            cpu_limit=limits.get("cpu"),
            memory_request=requests.get("memory"),
            memory_limit=limits.get("memory"),
        )
    
    def parse_cpu_millicores(self, value: str | None) -> int | None:
        """Parse CPU value to millicores."""
        if not value:
            return None
        
        value = str(value).strip()
        
        if value.endswith("m"):
            return int(value[:-1])
        else:
            return int(float(value) * 1000)
    
    def parse_memory_bytes(self, value: str | None) -> int | None:
        """Parse memory value to bytes."""
        if not value:
            return None
        
        value = str(value).strip()
        
        units = {
            "Ki": 1024,
            "Mi": 1024 ** 2,
            "Gi": 1024 ** 3,
            "Ti": 1024 ** 4,
            "K": 1000,
            "M": 1000 ** 2,
            "G": 1000 ** 3,
            "T": 1000 ** 4,
        }
        
        for unit, multiplier in units.items():
            if value.endswith(unit):
                return int(float(value[:-len(unit)]) * multiplier)
        
        return int(value)


class ResourceRecommendation(BaseModel):
    """Resource recommendation from analysis."""
    
    container_name: str
    current: ResourceSpec
    recommended: ResourceSpec
    
    # Reasoning
    reason: str = ""
    confidence: float = Field(0.5, ge=0, le=1)
    
    # Impact
    cpu_change_percent: float = 0.0
    memory_change_percent: float = 0.0
    estimated_savings_percent: float = 0.0
    
    # Source
    source: str = "manual"  # manual, vpa, metrics
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TunerConfig(OperatorConfig):
    """Configuration for resource tuner."""
    
    # Limits
    max_cpu_increase_percent: float = Field(100.0, description="Max CPU increase %")
    max_memory_increase_percent: float = Field(100.0, description="Max memory increase %")
    
    # Safety
    min_cpu_request: str = Field("10m", description="Minimum CPU request")
    min_memory_request: str = Field("32Mi", description="Minimum memory request")
    
    # Restart behavior
    restart_on_resource_change: bool = Field(True, description="Restart pods after change")
    rolling_restart: bool = Field(True, description="Use rolling restart")
    
    # VPA integration
    use_vpa_recommendations: bool = Field(False, description="Use VPA recommendations")
    vpa_namespace: str = Field("kube-system", description="VPA namespace")


class TuningResult(OperatorResult):
    """Result of a resource tuning operation."""
    
    # Container affected
    container_name: str = ""
    
    # Resource changes
    original_resources: ResourceSpec | None = None
    new_resources: ResourceSpec | None = None
    
    # Applied recommendation
    recommendation: ResourceRecommendation | None = None
    
    # Restart info
    pods_restarted: int = 0
    restart_duration_seconds: float | None = None


class ResourceTuner(BaseOperator[TuningResult]):
    """
    Intelligent resource tuning operator.
    
    Features:
    - CPU/memory adjustment
    - VPA integration
    - Resource recommendations
    - Safe limit changes
    
    Example:
        tuner = ResourceTuner(k8s_client)
        
        # Adjust resources
        result = await tuner.set_resources(
            "production", "api",
            container_name="api",
            cpu_request="200m",
            memory_limit="512Mi",
        )
        
        # Get recommendations
        recs = await tuner.get_recommendations("production", "api")
        
        # Apply recommendation
        result = await tuner.apply_recommendation(recs[0])
    """
    
    def __init__(
        self,
        k8s_client: Any,
        config: TunerConfig | None = None,
    ):
        super().__init__(k8s_client, config or TunerConfig())
    
    @property
    def name(self) -> str:
        return "ResourceTuner"
    
    @property
    def tuner_config(self) -> TunerConfig:
        return self._config  # type: ignore
    
    async def health_check(self) -> bool:
        """Verify operator can tune resources."""
        try:
            await self._k8s.list_deployments("default", limit=1)
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    async def set_resources(
        self,
        namespace: str,
        deployment_name: str,
        container_name: str | None = None,
        cpu_request: str | None = None,
        cpu_limit: str | None = None,
        memory_request: str | None = None,
        memory_limit: str | None = None,
        restart_pods: bool | None = None,
        dry_run: bool = False,
    ) -> TuningResult:
        """
        Set container resources in a deployment.
        
        Args:
            namespace: Kubernetes namespace
            deployment_name: Deployment name
            container_name: Container name (first if not specified)
            cpu_request: New CPU request
            cpu_limit: New CPU limit
            memory_request: New memory request
            memory_limit: New memory limit
            restart_pods: Restart pods after change
            dry_run: Dry run mode
            
        Returns:
            Tuning result
        """
        dry_run = dry_run or self._config.dry_run
        restart_pods = restart_pods if restart_pods is not None else self.tuner_config.restart_on_resource_change
        
        result = TuningResult(
            operation="set_resources",
            resource_type="deployment",
            resource_name=deployment_name,
            namespace=namespace,
        )
        
        try:
            # Get deployment
            deployment = await self._k8s._request(
                "GET",
                f"/apis/apps/v1/namespaces/{namespace}/deployments/{deployment_name}",
            )
            
            containers = deployment.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
            
            if not containers:
                result.fail("No containers found in deployment")
                return result
            
            # Find target container
            target_container = None
            target_index = 0
            
            if container_name:
                for i, c in enumerate(containers):
                    if c.get("name") == container_name:
                        target_container = c
                        target_index = i
                        break
                
                if not target_container:
                    result.fail(f"Container '{container_name}' not found")
                    return result
            else:
                target_container = containers[0]
                container_name = target_container.get("name")
            
            result.container_name = container_name
            
            # Get current resources
            current_resources = target_container.get("resources", {})
            result.original_resources = ResourceSpec.from_k8s_resources(current_resources)
            
            # Build new resources
            new_spec = ResourceSpec(
                cpu_request=cpu_request or result.original_resources.cpu_request,
                cpu_limit=cpu_limit or result.original_resources.cpu_limit,
                memory_request=memory_request or result.original_resources.memory_request,
                memory_limit=memory_limit or result.original_resources.memory_limit,
            )
            result.new_resources = new_spec
            
            # Validate changes
            validation_error = self._validate_resource_change(
                result.original_resources, new_spec
            )
            if validation_error:
                result.fail(validation_error, "ValidationError")
                return result
            
            logger.info(
                f"Updating resources for {namespace}/{deployment_name}/{container_name}"
            )
            
            if dry_run:
                result.complete(
                    success=True,
                    message=f"Dry run - would update resources for container {container_name}",
                    result_data={
                        "original": result.original_resources.model_dump(),
                        "new": new_spec.model_dump(),
                    },
                )
                return result
            
            # Build patch
            patch = {
                "spec": {
                    "template": {
                        "spec": {
                            "containers": [
                                {
                                    "name": container_name,
                                    "resources": new_spec.to_k8s_resources(),
                                }
                            ]
                        }
                    }
                }
            }
            
            # Apply patch
            result.status = OperatorStatus.EXECUTING
            
            await self._k8s._request(
                "PATCH",
                f"/apis/apps/v1/namespaces/{namespace}/deployments/{deployment_name}",
                json=patch,
                headers={"Content-Type": "application/strategic-merge-patch+json"},
            )
            
            result.add_change(
                "container_resources",
                result.original_resources.model_dump(),
                new_spec.model_dump(),
                f"Updated resources for {container_name}",
            )
            
            # Restart pods if configured
            if restart_pods:
                restart_count = await self._restart_deployment_pods(
                    namespace, deployment_name
                )
                result.pods_restarted = restart_count
            
            result.complete(
                success=True,
                message=f"Updated resources for container {container_name}",
            )
            
        except Exception as e:
            result.fail(str(e), type(e).__name__)
            logger.error(f"Resource tuning failed: {e}", exc_info=True)
        
        self._record_operation(result)
        return result
    
    async def get_recommendations(
        self,
        namespace: str,
        deployment_name: str,
        use_vpa: bool | None = None,
    ) -> list[ResourceRecommendation]:
        """
        Get resource recommendations for a deployment.
        
        Args:
            namespace: Kubernetes namespace
            deployment_name: Deployment name
            use_vpa: Use VPA recommendations if available
            
        Returns:
            List of recommendations per container
        """
        use_vpa = use_vpa if use_vpa is not None else self.tuner_config.use_vpa_recommendations
        recommendations = []
        
        try:
            # Get deployment
            deployment = await self._k8s._request(
                "GET",
                f"/apis/apps/v1/namespaces/{namespace}/deployments/{deployment_name}",
            )
            
            containers = deployment.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
            
            # Try to get VPA recommendations
            vpa_recs = {}
            if use_vpa:
                vpa_recs = await self._get_vpa_recommendations(namespace, deployment_name)
            
            for container in containers:
                container_name = container.get("name")
                current_resources = container.get("resources", {})
                current_spec = ResourceSpec.from_k8s_resources(current_resources)
                
                # Check VPA recommendation
                if container_name in vpa_recs:
                    vpa_rec = vpa_recs[container_name]
                    recommendations.append(ResourceRecommendation(
                        container_name=container_name,
                        current=current_spec,
                        recommended=vpa_rec,
                        reason="Based on VPA recommendation",
                        confidence=0.8,
                        source="vpa",
                    ))
                else:
                    # Generate basic recommendation
                    rec = await self._generate_recommendation(
                        namespace, deployment_name, container_name, current_spec
                    )
                    if rec:
                        recommendations.append(rec)
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Failed to get recommendations: {e}", exc_info=True)
            return []
    
    async def apply_recommendation(
        self,
        recommendation: ResourceRecommendation,
        namespace: str,
        deployment_name: str,
        dry_run: bool = False,
    ) -> TuningResult:
        """
        Apply a resource recommendation.
        
        Args:
            recommendation: Recommendation to apply
            namespace: Kubernetes namespace
            deployment_name: Deployment name
            dry_run: Dry run mode
            
        Returns:
            Tuning result
        """
        result = await self.set_resources(
            namespace=namespace,
            deployment_name=deployment_name,
            container_name=recommendation.container_name,
            cpu_request=recommendation.recommended.cpu_request,
            cpu_limit=recommendation.recommended.cpu_limit,
            memory_request=recommendation.recommended.memory_request,
            memory_limit=recommendation.recommended.memory_limit,
            dry_run=dry_run,
        )
        
        result.recommendation = recommendation
        return result
    
    async def scale_resources(
        self,
        namespace: str,
        deployment_name: str,
        container_name: str | None = None,
        cpu_multiplier: float = 1.0,
        memory_multiplier: float = 1.0,
        dry_run: bool = False,
    ) -> TuningResult:
        """
        Scale resources by a multiplier.
        
        Args:
            namespace: Kubernetes namespace
            deployment_name: Deployment name
            container_name: Container name
            cpu_multiplier: CPU multiplier (1.5 = 50% increase)
            memory_multiplier: Memory multiplier
            dry_run: Dry run mode
            
        Returns:
            Tuning result
        """
        result = TuningResult(
            operation="scale_resources",
            resource_type="deployment",
            resource_name=deployment_name,
            namespace=namespace,
        )
        
        try:
            # Get deployment
            deployment = await self._k8s._request(
                "GET",
                f"/apis/apps/v1/namespaces/{namespace}/deployments/{deployment_name}",
            )
            
            containers = deployment.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
            
            # Find target container
            target = None
            for c in containers:
                if container_name is None or c.get("name") == container_name:
                    target = c
                    break
            
            if not target:
                result.fail(f"Container not found")
                return result
            
            container_name = target.get("name")
            result.container_name = container_name
            
            current_resources = target.get("resources", {})
            current_spec = ResourceSpec.from_k8s_resources(current_resources)
            result.original_resources = current_spec
            
            # Calculate new values
            new_spec = self._scale_spec(current_spec, cpu_multiplier, memory_multiplier)
            
            # Apply change
            return await self.set_resources(
                namespace=namespace,
                deployment_name=deployment_name,
                container_name=container_name,
                cpu_request=new_spec.cpu_request,
                cpu_limit=new_spec.cpu_limit,
                memory_request=new_spec.memory_request,
                memory_limit=new_spec.memory_limit,
                dry_run=dry_run,
            )
            
        except Exception as e:
            result.fail(str(e), type(e).__name__)
            logger.error(f"Resource scaling failed: {e}", exc_info=True)
        
        self._record_operation(result)
        return result
    
    def _validate_resource_change(
        self,
        current: ResourceSpec,
        new: ResourceSpec,
    ) -> str | None:
        """Validate resource change. Returns error or None."""
        config = self.tuner_config
        
        # Check CPU increase limit
        if current.cpu_request and new.cpu_request:
            current_cpu = current.parse_cpu_millicores(current.cpu_request)
            new_cpu = current.parse_cpu_millicores(new.cpu_request)
            
            if current_cpu and new_cpu:
                increase_pct = ((new_cpu - current_cpu) / current_cpu) * 100
                if increase_pct > config.max_cpu_increase_percent:
                    return f"CPU increase ({increase_pct:.0f}%) exceeds limit ({config.max_cpu_increase_percent}%)"
        
        # Check memory increase limit
        if current.memory_request and new.memory_request:
            current_mem = current.parse_memory_bytes(current.memory_request)
            new_mem = current.parse_memory_bytes(new.memory_request)
            
            if current_mem and new_mem:
                increase_pct = ((new_mem - current_mem) / current_mem) * 100
                if increase_pct > config.max_memory_increase_percent:
                    return f"Memory increase ({increase_pct:.0f}%) exceeds limit ({config.max_memory_increase_percent}%)"
        
        return None
    
    def _scale_spec(
        self,
        spec: ResourceSpec,
        cpu_mult: float,
        mem_mult: float,
    ) -> ResourceSpec:
        """Scale a resource spec by multipliers."""
        def scale_cpu(value: str | None, mult: float) -> str | None:
            if not value:
                return None
            
            millicores = spec.parse_cpu_millicores(value)
            if millicores:
                new_val = int(millicores * mult)
                return f"{new_val}m"
            return value
        
        def scale_memory(value: str | None, mult: float) -> str | None:
            if not value:
                return None
            
            bytes_val = spec.parse_memory_bytes(value)
            if bytes_val:
                new_val = int(bytes_val * mult)
                # Convert back to Mi
                mi_val = new_val / (1024 ** 2)
                return f"{int(mi_val)}Mi"
            return value
        
        return ResourceSpec(
            cpu_request=scale_cpu(spec.cpu_request, cpu_mult),
            cpu_limit=scale_cpu(spec.cpu_limit, cpu_mult),
            memory_request=scale_memory(spec.memory_request, mem_mult),
            memory_limit=scale_memory(spec.memory_limit, mem_mult),
        )
    
    async def _get_vpa_recommendations(
        self,
        namespace: str,
        deployment_name: str,
    ) -> dict[str, ResourceSpec]:
        """Get VPA recommendations for containers."""
        try:
            # List VPAs in namespace
            vpas = await self._k8s._request(
                "GET",
                f"/apis/autoscaling.k8s.io/v1/namespaces/{namespace}/verticalpodautoscalers",
            )
            
            for vpa in vpas.get("items", []):
                # Check if VPA targets this deployment
                ref = vpa.get("spec", {}).get("targetRef", {})
                if (
                    ref.get("kind") == "Deployment"
                    and ref.get("name") == deployment_name
                ):
                    recommendations = {}
                    
                    for container_rec in vpa.get("status", {}).get("recommendation", {}).get("containerRecommendations", []):
                        container_name = container_rec.get("containerName")
                        target = container_rec.get("target", {})
                        
                        recommendations[container_name] = ResourceSpec(
                            cpu_request=target.get("cpu"),
                            memory_request=target.get("memory"),
                        )
                    
                    return recommendations
            
            return {}
            
        except Exception as e:
            logger.debug(f"VPA not available: {e}")
            return {}
    
    async def _generate_recommendation(
        self,
        namespace: str,
        deployment_name: str,
        container_name: str,
        current: ResourceSpec,
    ) -> ResourceRecommendation | None:
        """Generate a basic recommendation based on current settings."""
        # This would ideally query Prometheus for actual usage
        # For now, we return a placeholder recommendation
        
        # Simple heuristic: if no limits, suggest some
        if not current.cpu_limit or not current.memory_limit:
            recommended = ResourceSpec(
                cpu_request=current.cpu_request or "100m",
                cpu_limit=current.cpu_limit or "500m",
                memory_request=current.memory_request or "128Mi",
                memory_limit=current.memory_limit or "512Mi",
            )
            
            return ResourceRecommendation(
                container_name=container_name,
                current=current,
                recommended=recommended,
                reason="Adding missing resource limits",
                confidence=0.5,
                source="heuristic",
            )
        
        return None
    
    async def _restart_deployment_pods(
        self,
        namespace: str,
        deployment_name: str,
    ) -> int:
        """Restart deployment pods after resource change."""
        try:
            if self.tuner_config.rolling_restart:
                # Trigger rolling restart
                await self._k8s.restart_deployment(namespace, deployment_name)
            
            # Get pod count
            deployment = await self._k8s.get_deployment(namespace, deployment_name)
            return deployment.replicas
            
        except Exception as e:
            logger.warning(f"Failed to restart pods: {e}")
            return 0
