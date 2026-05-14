"""
Drain Manager Operator.

Provides safe node draining capabilities:
- Pre-drain validation
- Graceful pod eviction
- PDB respect
- Cordon/uncordon management
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


class DrainStatus(str, Enum):
    """Status of a drain operation."""
    
    PENDING = "pending"
    CORDONED = "cordoned"
    DRAINING = "draining"
    WAITING_PODS = "waiting_pods"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EvictionResult(BaseModel):
    """Result of a pod eviction."""
    
    pod_name: str
    namespace: str
    success: bool
    message: str = ""
    evicted_at: datetime | None = None
    
    # PDB info
    blocked_by_pdb: bool = False
    pdb_name: str | None = None


class DrainConfig(OperatorConfig):
    """Configuration for drain manager."""
    
    # Eviction settings
    eviction_timeout_seconds: int = Field(300, description="Timeout per pod eviction")
    grace_period_seconds: int = Field(30, description="Pod termination grace period")
    
    # Safety
    ignore_daemonsets: bool = Field(True, description="Ignore DaemonSet pods")
    delete_emptydir_data: bool = Field(False, description="Delete pods with emptyDir")
    force: bool = Field(False, description="Force eviction (ignore PDBs)")
    
    # Parallelism
    max_concurrent_evictions: int = Field(10, description="Max parallel evictions")
    eviction_poll_interval_seconds: float = Field(2.0)
    
    # Pre-checks
    check_pdb_budget: bool = Field(True, description="Check PDB budget before drain")
    min_pdb_available: int = Field(1, description="Minimum pods after drain")


class DrainResult(OperatorResult):
    """Result of a drain operation."""
    
    # Drain status
    drain_status: DrainStatus = DrainStatus.PENDING
    
    # Pods affected
    total_pods: int = 0
    evicted_pods: int = 0
    failed_evictions: int = 0
    skipped_pods: int = 0
    
    # Eviction details
    evictions: list[EvictionResult] = Field(default_factory=list)
    
    # PDB info
    pdbs_checked: int = 0
    pdbs_blocking: list[str] = Field(default_factory=list)
    
    # Node state
    was_cordoned: bool = False
    is_uncordoned: bool = False
    
    # Timing
    drain_started_at: datetime | None = None
    drain_completed_at: datetime | None = None
    
    @property
    def drain_duration_seconds(self) -> float | None:
        if self.drain_started_at and self.drain_completed_at:
            return (self.drain_completed_at - self.drain_started_at).total_seconds()
        return None


class DrainManager(BaseOperator[DrainResult]):
    """
    Safe node draining operator.
    
    Features:
    - Pre-drain validation
    - PDB-aware eviction
    - Graceful pod termination
    - Cordon/uncordon management
    
    Example:
        drain_manager = DrainManager(k8s_client)
        
        # Drain a node
        result = await drain_manager.drain_node("worker-1")
        
        # Cordon without draining
        await drain_manager.cordon_node("worker-1")
        
        # Uncordon after maintenance
        await drain_manager.uncordon_node("worker-1")
    """
    
    def __init__(
        self,
        k8s_client: Any,
        config: DrainConfig | None = None,
    ):
        super().__init__(k8s_client, config or DrainConfig())
        self._active_drains: dict[str, DrainResult] = {}
    
    @property
    def name(self) -> str:
        return "DrainManager"
    
    @property
    def drain_config(self) -> DrainConfig:
        return self._config  # type: ignore
    
    async def health_check(self) -> bool:
        """Verify operator can drain nodes."""
        try:
            await self._k8s.list_nodes(limit=1)
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    async def drain_node(
        self,
        node_name: str,
        ignore_daemonsets: bool | None = None,
        delete_emptydir_data: bool | None = None,
        force: bool | None = None,
        grace_period: int | None = None,
        dry_run: bool = False,
    ) -> DrainResult:
        """
        Drain a node safely.
        
        Args:
            node_name: Node name
            ignore_daemonsets: Ignore DaemonSet pods
            delete_emptydir_data: Delete pods with emptyDir
            force: Force eviction (ignore PDBs)
            grace_period: Pod termination grace period
            dry_run: Dry run mode
            
        Returns:
            Drain result
        """
        dry_run = dry_run or self._config.dry_run
        ignore_daemonsets = ignore_daemonsets if ignore_daemonsets is not None else self.drain_config.ignore_daemonsets
        delete_emptydir_data = delete_emptydir_data if delete_emptydir_data is not None else self.drain_config.delete_emptydir_data
        force = force if force is not None else self.drain_config.force
        grace_period = grace_period or self.drain_config.grace_period_seconds
        
        result = DrainResult(
            operation="drain_node",
            resource_type="node",
            resource_name=node_name,
            namespace=None,
        )
        
        # Track active drain
        self._active_drains[node_name] = result
        
        try:
            logger.info(f"Starting drain of node {node_name}")
            
            # Get node info
            nodes = await self._k8s.list_nodes()
            node = next((n for n in nodes if n.name == node_name), None)
            
            if not node:
                result.fail(f"Node '{node_name}' not found", "NotFound")
                return result
            
            # Get pods on node
            all_pods = []
            namespaces = await self._k8s._request("GET", "/api/v1/namespaces")
            
            for ns in namespaces.get("items", []):
                ns_name = ns.get("metadata", {}).get("name")
                pods = await self._k8s.list_pods(
                    ns_name,
                    field_selector=f"spec.nodeName={node_name}",
                )
                all_pods.extend(pods)
            
            result.total_pods = len(all_pods)
            
            # Filter pods to evict
            pods_to_evict = []
            
            for pod in all_pods:
                should_evict, skip_reason = self._should_evict_pod(
                    pod, ignore_daemonsets, delete_emptydir_data
                )
                
                if should_evict:
                    pods_to_evict.append(pod)
                else:
                    result.skipped_pods += 1
                    logger.debug(f"Skipping pod {pod.namespace}/{pod.name}: {skip_reason}")
            
            logger.info(
                f"Node {node_name}: {len(pods_to_evict)} pods to evict, "
                f"{result.skipped_pods} skipped"
            )
            
            # Check PDBs
            if self.drain_config.check_pdb_budget and not force:
                pdb_issues = await self._check_pdbs(pods_to_evict)
                result.pdbs_checked = len(pdb_issues)
                
                blocking_pdbs = [p for p, ok, _ in pdb_issues if not ok]
                if blocking_pdbs:
                    result.pdbs_blocking = [p[0] for p in blocking_pdbs]
                    
                    if not force:
                        result.fail(
                            f"PDBs would block eviction: {result.pdbs_blocking}",
                            "PDBViolation",
                        )
                        result.drain_status = DrainStatus.FAILED
                        return result
            
            if dry_run:
                result.complete(
                    success=True,
                    message=f"Dry run - would drain {len(pods_to_evict)} pods from {node_name}",
                    result_data={
                        "pods_to_evict": [f"{p.namespace}/{p.name}" for p in pods_to_evict],
                        "skipped": result.skipped_pods,
                    },
                )
                return result
            
            # Cordon node
            result.status = OperatorStatus.EXECUTING
            result.drain_started_at = datetime.utcnow()
            
            cordoned = await self.cordon_node(node_name)
            result.was_cordoned = cordoned
            result.drain_status = DrainStatus.CORDONED
            
            result.add_change("node_unschedulable", False, True, "Node cordoned")
            
            # Evict pods
            result.drain_status = DrainStatus.DRAINING
            
            eviction_results = await self._evict_pods(
                pods_to_evict, grace_period, force
            )
            
            result.evictions = eviction_results
            result.evicted_pods = sum(1 for e in eviction_results if e.success)
            result.failed_evictions = sum(1 for e in eviction_results if not e.success)
            
            result.drain_completed_at = datetime.utcnow()
            
            if result.failed_evictions > 0:
                result.drain_status = DrainStatus.FAILED
                result.fail(
                    f"Failed to evict {result.failed_evictions} pods",
                    "EvictionFailed",
                )
            else:
                result.drain_status = DrainStatus.COMPLETED
                result.complete(
                    success=True,
                    message=f"Successfully drained {result.evicted_pods} pods from {node_name}",
                )
            
        except Exception as e:
            result.fail(str(e), type(e).__name__)
            result.drain_status = DrainStatus.FAILED
            logger.error(f"Drain failed: {e}", exc_info=True)
        
        finally:
            # Remove from active drains
            self._active_drains.pop(node_name, None)
        
        self._record_operation(result)
        return result
    
    async def cordon_node(
        self,
        node_name: str,
        dry_run: bool = False,
    ) -> bool:
        """
        Cordon a node (mark as unschedulable).
        
        Args:
            node_name: Node name
            dry_run: Dry run mode
            
        Returns:
            True if cordoned
        """
        try:
            logger.info(f"Cordoning node {node_name}")
            
            if dry_run:
                return True
            
            patch = {"spec": {"unschedulable": True}}
            
            await self._k8s._request(
                "PATCH",
                f"/api/v1/nodes/{node_name}",
                json=patch,
                headers={"Content-Type": "application/strategic-merge-patch+json"},
            )
            
            logger.info(f"Node {node_name} cordoned")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cordon node: {e}")
            return False
    
    async def uncordon_node(
        self,
        node_name: str,
        dry_run: bool = False,
    ) -> bool:
        """
        Uncordon a node (mark as schedulable).
        
        Args:
            node_name: Node name
            dry_run: Dry run mode
            
        Returns:
            True if uncordoned
        """
        try:
            logger.info(f"Uncordoning node {node_name}")
            
            if dry_run:
                return True
            
            patch = {"spec": {"unschedulable": False}}
            
            await self._k8s._request(
                "PATCH",
                f"/api/v1/nodes/{node_name}",
                json=patch,
                headers={"Content-Type": "application/strategic-merge-patch+json"},
            )
            
            logger.info(f"Node {node_name} uncordoned")
            return True
            
        except Exception as e:
            logger.error(f"Failed to uncordon node: {e}")
            return False
    
    async def cancel_drain(self, node_name: str) -> bool:
        """
        Cancel an active drain operation.
        
        Args:
            node_name: Node name
            
        Returns:
            True if cancelled
        """
        if node_name in self._active_drains:
            result = self._active_drains[node_name]
            result.drain_status = DrainStatus.CANCELLED
            result.status = OperatorStatus.CANCELLED
            
            # Uncordon node
            await self.uncordon_node(node_name)
            result.is_uncordoned = True
            
            logger.info(f"Cancelled drain of node {node_name}")
            return True
        
        return False
    
    def _should_evict_pod(
        self,
        pod: Any,
        ignore_daemonsets: bool,
        delete_emptydir_data: bool,
    ) -> tuple[bool, str]:
        """Determine if pod should be evicted."""
        # Check owner references
        for ref in pod.owner_references:
            if ref.get("kind") == "DaemonSet":
                if ignore_daemonsets:
                    return False, "DaemonSet pod"
        
        # Check for emptyDir volumes
        if not delete_emptydir_data:
            # Would need to check pod spec for emptyDir volumes
            pass
        
        # Mirror pods (managed by kubelet)
        if pod.annotations.get("kubernetes.io/config.mirror"):
            return False, "Mirror pod"
        
        return True, ""
    
    async def _check_pdbs(
        self,
        pods: list[Any],
    ) -> list[tuple[str, bool, str]]:
        """
        Check PDBs for pods to be evicted.
        
        Returns:
            List of (pdb_name, can_evict, reason)
        """
        results = []
        
        # Get unique namespaces
        namespaces = set(pod.namespace for pod in pods)
        
        for ns in namespaces:
            try:
                pdbs = await self._k8s._request(
                    "GET",
                    f"/apis/policy/v1/namespaces/{ns}/poddisruptionbudgets",
                )
                
                for pdb in pdbs.get("items", []):
                    pdb_name = pdb.get("metadata", {}).get("name")
                    status = pdb.get("status", {})
                    
                    disruptions_allowed = status.get("disruptionsAllowed", 0)
                    current_healthy = status.get("currentHealthy", 0)
                    desired_healthy = status.get("desiredHealthy", 0)
                    
                    if disruptions_allowed == 0:
                        results.append((
                            f"{ns}/{pdb_name}",
                            False,
                            f"No disruptions allowed ({current_healthy}/{desired_healthy} healthy)",
                        ))
                    else:
                        results.append((
                            f"{ns}/{pdb_name}",
                            True,
                            f"{disruptions_allowed} disruptions allowed",
                        ))
                        
            except Exception as e:
                logger.warning(f"Failed to check PDBs in {ns}: {e}")
        
        return results
    
    async def _evict_pods(
        self,
        pods: list[Any],
        grace_period: int,
        force: bool,
    ) -> list[EvictionResult]:
        """Evict a list of pods."""
        semaphore = asyncio.Semaphore(self.drain_config.max_concurrent_evictions)
        
        async def evict_with_limit(pod) -> EvictionResult:
            async with semaphore:
                return await self._evict_pod(pod, grace_period, force)
        
        results = await asyncio.gather(
            *[evict_with_limit(pod) for pod in pods],
            return_exceptions=True,
        )
        
        # Convert exceptions
        final_results = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                final_results.append(EvictionResult(
                    pod_name=pods[i].name,
                    namespace=pods[i].namespace,
                    success=False,
                    message=str(r),
                ))
            else:
                final_results.append(r)
        
        return final_results
    
    async def _evict_pod(
        self,
        pod: Any,
        grace_period: int,
        force: bool,
    ) -> EvictionResult:
        """Evict a single pod."""
        result = EvictionResult(
            pod_name=pod.name,
            namespace=pod.namespace,
            success=False,
        )
        
        try:
            # Create eviction
            eviction = {
                "apiVersion": "policy/v1",
                "kind": "Eviction",
                "metadata": {
                    "name": pod.name,
                    "namespace": pod.namespace,
                },
                "deleteOptions": {
                    "gracePeriodSeconds": grace_period,
                },
            }
            
            await self._k8s._request(
                "POST",
                f"/api/v1/namespaces/{pod.namespace}/pods/{pod.name}/eviction",
                json=eviction,
            )
            
            # Wait for pod to terminate
            await self._wait_for_pod_termination(pod.namespace, pod.name)
            
            result.success = True
            result.message = "Pod evicted"
            result.evicted_at = datetime.utcnow()
            
            logger.debug(f"Evicted pod {pod.namespace}/{pod.name}")
            
        except Exception as e:
            error_msg = str(e)
            
            # Check if blocked by PDB
            if "cannot evict" in error_msg.lower() or "pdb" in error_msg.lower():
                result.blocked_by_pdb = True
                result.message = f"Blocked by PDB: {error_msg}"
            else:
                result.message = error_msg
            
            logger.warning(f"Failed to evict {pod.namespace}/{pod.name}: {error_msg}")
        
        return result
    
    async def _wait_for_pod_termination(
        self,
        namespace: str,
        pod_name: str,
    ) -> bool:
        """Wait for pod to terminate."""
        timeout = self.drain_config.eviction_timeout_seconds
        interval = self.drain_config.eviction_poll_interval_seconds
        
        start_time = datetime.utcnow()
        
        while (datetime.utcnow() - start_time).total_seconds() < timeout:
            try:
                await self._k8s.get_pod(namespace, pod_name)
                # Pod still exists
                await asyncio.sleep(interval)
            except Exception:
                # Pod not found - terminated
                return True
        
        logger.warning(f"Timeout waiting for pod {namespace}/{pod_name} to terminate")
        return False
    
    def get_active_drains(self) -> dict[str, DrainResult]:
        """Get active drain operations."""
        return dict(self._active_drains)
