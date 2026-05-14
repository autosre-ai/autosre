"""
Pod Restarter Operator.

Provides intelligent pod restart capabilities with:
- Multiple restart strategies
- Health verification
- Graceful shutdown
- Rollout tracking
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


class RestartStrategy(str, Enum):
    """Strategy for restarting pods."""
    
    DELETE = "delete"              # Delete pod (k8s recreates it)
    ROLLING = "rolling"            # Rolling restart via deployment
    FORCE = "force"                # Force delete (immediate)
    GRACEFUL = "graceful"          # Wait for connections to drain


class RestartConfig(OperatorConfig):
    """Configuration for pod restarter."""
    
    # Restart behavior
    default_strategy: RestartStrategy = RestartStrategy.DELETE
    grace_period_seconds: int = Field(30, description="Grace period for shutdown")
    force_grace_period_seconds: int = Field(0, description="Grace period for force delete")
    
    # Health verification
    verify_health_after_restart: bool = Field(True, description="Verify pod health")
    health_check_interval_seconds: float = Field(2.0)
    health_check_max_wait_seconds: int = Field(120)
    
    # Safety
    max_concurrent_restarts: int = Field(5, description="Max pods to restart at once")
    min_ready_percentage: float = Field(0.5, description="Min ready % before proceeding")


class RestartResult(OperatorResult):
    """Result of a pod restart operation."""
    
    # Strategy used
    strategy: RestartStrategy = RestartStrategy.DELETE
    
    # Timing
    pod_deleted_at: datetime | None = None
    new_pod_ready_at: datetime | None = None
    
    # New pod info
    new_pod_name: str | None = None
    new_pod_ip: str | None = None
    
    # Health
    health_verified: bool = False
    health_check_attempts: int = 0
    
    @property
    def restart_duration_seconds(self) -> float | None:
        if self.pod_deleted_at and self.new_pod_ready_at:
            return (self.new_pod_ready_at - self.pod_deleted_at).total_seconds()
        return None


class PodRestarter(BaseOperator[RestartResult]):
    """
    Intelligent pod restart operator.
    
    Features:
    - Multiple restart strategies
    - Health verification after restart
    - Graceful shutdown support
    - Concurrent restart limiting
    
    Example:
        restarter = PodRestarter(k8s_client)
        
        # Simple restart
        result = await restarter.restart_pod("default", "api-server-xyz")
        
        # Rolling restart of deployment
        results = await restarter.restart_deployment("default", "api-server")
        
        # Force restart
        result = await restarter.restart_pod(
            "default", "stuck-pod",
            strategy=RestartStrategy.FORCE
        )
    """
    
    def __init__(
        self,
        k8s_client: Any,
        config: RestartConfig | None = None,
    ):
        super().__init__(k8s_client, config or RestartConfig())
    
    @property
    def name(self) -> str:
        return "PodRestarter"
    
    @property
    def restart_config(self) -> RestartConfig:
        return self._config  # type: ignore
    
    async def health_check(self) -> bool:
        """Verify operator can perform restarts."""
        try:
            # Test API connectivity by listing pods in kube-system
            await self._k8s.list_pods("kube-system", limit=1)
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    async def restart_pod(
        self,
        namespace: str,
        pod_name: str,
        strategy: RestartStrategy | None = None,
        grace_period: int | None = None,
        wait_for_ready: bool = True,
        dry_run: bool = False,
    ) -> RestartResult:
        """
        Restart a single pod.
        
        Args:
            namespace: Kubernetes namespace
            pod_name: Pod name
            strategy: Restart strategy (default from config)
            grace_period: Override grace period
            wait_for_ready: Wait for new pod to be ready
            dry_run: Dry run mode
            
        Returns:
            Restart result
        """
        strategy = strategy or self.restart_config.default_strategy
        dry_run = dry_run or self._config.dry_run
        
        result = RestartResult(
            operation="restart_pod",
            resource_type="pod",
            resource_name=pod_name,
            namespace=namespace,
            strategy=strategy,
        )
        
        try:
            logger.info(
                f"Restarting pod {namespace}/{pod_name} "
                f"(strategy={strategy.value}, dry_run={dry_run})"
            )
            
            # Get current pod info
            current_pod = await self._k8s.get_pod(namespace, pod_name)
            result.result_data["original_pod"] = {
                "name": current_pod.name,
                "phase": current_pod.phase.value,
                "pod_ip": current_pod.pod_ip,
                "node_name": current_pod.node_name,
                "restarts": current_pod.total_restarts,
            }
            
            if dry_run:
                result.complete(
                    success=True,
                    message="Dry run - would restart pod",
                    result_data={"dry_run": True},
                )
                return result
            
            # Delete the pod
            result.status = OperatorStatus.EXECUTING
            effective_grace_period = grace_period or (
                self.restart_config.force_grace_period_seconds
                if strategy == RestartStrategy.FORCE
                else self.restart_config.grace_period_seconds
            )
            
            await self._k8s.delete_pod(
                namespace,
                pod_name,
                grace_period=effective_grace_period,
            )
            
            result.pod_deleted_at = datetime.utcnow()
            result.add_change("pod_status", "Running", "Terminating", "Pod deleted")
            
            logger.info(f"Deleted pod {namespace}/{pod_name}")
            
            # Wait for new pod if requested
            if wait_for_ready:
                result.status = OperatorStatus.WAITING
                new_pod = await self._wait_for_replacement_pod(
                    namespace,
                    current_pod,
                    result,
                )
                
                if new_pod:
                    result.new_pod_name = new_pod.name
                    result.new_pod_ip = new_pod.pod_ip
                    result.new_pod_ready_at = datetime.utcnow()
                    
                    result.add_change(
                        "pod_name",
                        pod_name,
                        new_pod.name,
                        "New pod created",
                    )
                    
                    # Verify health
                    if self.restart_config.verify_health_after_restart:
                        healthy = await self._verify_pod_health(
                            namespace,
                            new_pod.name,
                            result,
                        )
                        result.health_verified = healthy
            
            result.complete(
                success=True,
                message=f"Pod restarted successfully"
                + (f" (new pod: {result.new_pod_name})" if result.new_pod_name else ""),
            )
            
        except Exception as e:
            result.fail(str(e), type(e).__name__)
            logger.error(f"Failed to restart pod: {e}", exc_info=True)
        
        self._record_operation(result)
        return result
    
    async def restart_deployment(
        self,
        namespace: str,
        deployment_name: str,
        max_concurrent: int | None = None,
        strategy: RestartStrategy = RestartStrategy.ROLLING,
        dry_run: bool = False,
    ) -> list[RestartResult]:
        """
        Restart all pods in a deployment.
        
        Args:
            namespace: Kubernetes namespace
            deployment_name: Deployment name
            max_concurrent: Max concurrent restarts
            strategy: Restart strategy
            dry_run: Dry run mode
            
        Returns:
            List of restart results for each pod
        """
        max_concurrent = max_concurrent or self.restart_config.max_concurrent_restarts
        dry_run = dry_run or self._config.dry_run
        
        results = []
        
        try:
            if strategy == RestartStrategy.ROLLING:
                # Use deployment rollout restart
                return await self._rolling_restart_deployment(
                    namespace, deployment_name, dry_run
                )
            
            # Get deployment
            deployment = await self._k8s.get_deployment(namespace, deployment_name)
            
            # Get pods for deployment
            label_selector = ",".join(
                f"{k}={v}" for k, v in deployment.selector.items()
            )
            pods = await self._k8s.list_pods(namespace, label_selector=label_selector)
            
            logger.info(
                f"Restarting {len(pods)} pods in deployment {deployment_name}"
            )
            
            # Restart pods with concurrency limit
            semaphore = asyncio.Semaphore(max_concurrent)
            
            async def restart_with_limit(pod):
                async with semaphore:
                    return await self.restart_pod(
                        namespace,
                        pod.name,
                        strategy=strategy,
                        dry_run=dry_run,
                    )
            
            tasks = [restart_with_limit(pod) for pod in pods]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Convert exceptions to failed results
            final_results = []
            for i, r in enumerate(results):
                if isinstance(r, Exception):
                    result = RestartResult(
                        operation="restart_pod",
                        resource_type="pod",
                        resource_name=pods[i].name,
                        namespace=namespace,
                        strategy=strategy,
                    )
                    result.fail(str(r))
                    final_results.append(result)
                else:
                    final_results.append(r)
            
            return final_results
            
        except Exception as e:
            logger.error(f"Failed to restart deployment: {e}", exc_info=True)
            result = RestartResult(
                operation="restart_deployment",
                resource_type="deployment",
                resource_name=deployment_name,
                namespace=namespace,
                strategy=strategy,
            )
            result.fail(str(e))
            return [result]
    
    async def _rolling_restart_deployment(
        self,
        namespace: str,
        deployment_name: str,
        dry_run: bool = False,
    ) -> list[RestartResult]:
        """Trigger rolling restart via deployment annotation."""
        result = RestartResult(
            operation="rolling_restart",
            resource_type="deployment",
            resource_name=deployment_name,
            namespace=namespace,
            strategy=RestartStrategy.ROLLING,
        )
        
        try:
            if dry_run:
                result.complete(
                    success=True,
                    message="Dry run - would trigger rolling restart",
                )
                return [result]
            
            # Trigger restart via annotation
            deployment = await self._k8s.restart_deployment(namespace, deployment_name)
            
            result.add_change(
                "restart_annotation",
                None,
                datetime.utcnow().isoformat(),
                "Triggered rolling restart",
            )
            
            # Wait for rollout to complete
            await self._wait_for_rollout(namespace, deployment_name, result)
            
            result.complete(
                success=True,
                message=f"Rolling restart completed for {deployment_name}",
            )
            
        except Exception as e:
            result.fail(str(e))
            logger.error(f"Rolling restart failed: {e}", exc_info=True)
        
        self._record_operation(result)
        return [result]
    
    async def _wait_for_replacement_pod(
        self,
        namespace: str,
        original_pod: Any,
        result: RestartResult,
    ) -> Any | None:
        """Wait for a replacement pod to be ready."""
        timeout = self.restart_config.health_check_max_wait_seconds
        interval = self.restart_config.health_check_interval_seconds
        
        # Find owner reference to identify replacement
        owner_refs = original_pod.owner_references
        if not owner_refs:
            logger.warning("Pod has no owner reference, cannot track replacement")
            return None
        
        owner_kind = owner_refs[0].get("kind", "")
        owner_name = owner_refs[0].get("name", "")
        
        start_time = datetime.utcnow()
        attempts = 0
        
        while (datetime.utcnow() - start_time).total_seconds() < timeout:
            attempts += 1
            
            try:
                # List pods with same labels
                pods = await self._k8s.list_pods(
                    namespace,
                    label_selector=",".join(
                        f"{k}={v}" for k, v in original_pod.labels.items()
                        if k not in ["pod-template-hash"]  # Exclude hash labels
                    )
                )
                
                # Find new ready pod
                for pod in pods:
                    if pod.name != original_pod.name and pod.is_ready:
                        # Verify it's owned by same controller
                        for ref in pod.owner_references:
                            if (
                                ref.get("kind") == owner_kind
                                and ref.get("name") == owner_name
                            ):
                                logger.info(f"Found replacement pod: {pod.name}")
                                return pod
                
            except Exception as e:
                logger.warning(f"Error checking for replacement pod: {e}")
            
            await asyncio.sleep(interval)
        
        logger.warning(
            f"Timeout waiting for replacement pod after {attempts} attempts"
        )
        return None
    
    async def _verify_pod_health(
        self,
        namespace: str,
        pod_name: str,
        result: RestartResult,
    ) -> bool:
        """Verify pod is healthy after restart."""
        timeout = self.restart_config.health_check_max_wait_seconds
        interval = self.restart_config.health_check_interval_seconds
        
        start_time = datetime.utcnow()
        
        while (datetime.utcnow() - start_time).total_seconds() < timeout:
            result.health_check_attempts += 1
            
            try:
                pod = await self._k8s.get_pod(namespace, pod_name)
                
                if pod.is_ready:
                    logger.info(f"Pod {pod_name} is healthy")
                    return True
                
            except Exception as e:
                logger.warning(f"Health check error: {e}")
            
            await asyncio.sleep(interval)
        
        logger.warning(f"Pod {pod_name} did not become healthy in time")
        return False
    
    async def _wait_for_rollout(
        self,
        namespace: str,
        deployment_name: str,
        result: RestartResult,
    ) -> bool:
        """Wait for deployment rollout to complete."""
        timeout = self.restart_config.operation_timeout_seconds
        interval = 5.0
        
        start_time = datetime.utcnow()
        
        while (datetime.utcnow() - start_time).total_seconds() < timeout:
            try:
                deployment = await self._k8s.get_deployment(namespace, deployment_name)
                
                # Check if rollout is complete
                if (
                    deployment.ready_replicas == deployment.replicas
                    and deployment.updated_replicas == deployment.replicas
                    and deployment.available_replicas == deployment.replicas
                ):
                    logger.info(f"Deployment {deployment_name} rollout complete")
                    return True
                
                logger.debug(
                    f"Rollout progress: {deployment.ready_replicas}/{deployment.replicas} ready"
                )
                
            except Exception as e:
                logger.warning(f"Error checking rollout: {e}")
            
            await asyncio.sleep(interval)
        
        logger.warning(f"Rollout did not complete in time")
        return False
    
    async def restart_pods_by_label(
        self,
        namespace: str,
        label_selector: str,
        strategy: RestartStrategy | None = None,
        max_concurrent: int | None = None,
        dry_run: bool = False,
    ) -> list[RestartResult]:
        """
        Restart all pods matching a label selector.
        
        Args:
            namespace: Kubernetes namespace
            label_selector: Label selector (e.g., "app=api,tier=backend")
            strategy: Restart strategy
            max_concurrent: Max concurrent restarts
            dry_run: Dry run mode
            
        Returns:
            List of restart results
        """
        strategy = strategy or self.restart_config.default_strategy
        max_concurrent = max_concurrent or self.restart_config.max_concurrent_restarts
        dry_run = dry_run or self._config.dry_run
        
        try:
            pods = await self._k8s.list_pods(namespace, label_selector=label_selector)
            
            logger.info(
                f"Found {len(pods)} pods matching '{label_selector}' in {namespace}"
            )
            
            if not pods:
                return []
            
            # Restart with concurrency limit
            semaphore = asyncio.Semaphore(max_concurrent)
            
            async def restart_with_limit(pod):
                async with semaphore:
                    return await self.restart_pod(
                        namespace,
                        pod.name,
                        strategy=strategy,
                        dry_run=dry_run,
                    )
            
            results = await asyncio.gather(
                *[restart_with_limit(pod) for pod in pods],
                return_exceptions=True,
            )
            
            # Convert exceptions
            return [
                r if isinstance(r, RestartResult)
                else self._exception_to_result(pods[i].name, namespace, strategy, r)
                for i, r in enumerate(results)
            ]
            
        except Exception as e:
            logger.error(f"Failed to restart pods by label: {e}", exc_info=True)
            result = RestartResult(
                operation="restart_pods_by_label",
                resource_type="pods",
                resource_name=label_selector,
                namespace=namespace,
                strategy=strategy,
            )
            result.fail(str(e))
            return [result]
    
    def _exception_to_result(
        self,
        pod_name: str,
        namespace: str,
        strategy: RestartStrategy,
        exception: Exception,
    ) -> RestartResult:
        """Convert exception to failed result."""
        result = RestartResult(
            operation="restart_pod",
            resource_type="pod",
            resource_name=pod_name,
            namespace=namespace,
            strategy=strategy,
        )
        result.fail(str(exception), type(exception).__name__)
        return result
