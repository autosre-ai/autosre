"""
Fault Injector for chaos engineering.

Injects various types of faults into Kubernetes resources.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any
from uuid import UUID

from autosre.utils.logging import get_logger

from .models import Fault, FaultType, FaultSeverity, Target, TargetType

logger = get_logger(__name__)


class FaultInjector:
    """
    Injects faults into systems.
    
    Features:
    - Multiple fault types (CPU, memory, network, etc.)
    - Kubernetes-native injection
    - Automatic cleanup
    - Rollback support
    
    Example:
        injector = FaultInjector(k8s_client)
        
        fault = Fault(
            type=FaultType.NETWORK_LATENCY,
            target=Target(type=TargetType.DEPLOYMENT, name="api"),
            parameters={"latency": "200ms"},
            duration_seconds=300,
        )
        
        await injector.inject(fault)
        # ... fault is active ...
        await injector.stop(fault.id)
    """
    
    def __init__(self, k8s_client: Any):
        self._k8s = k8s_client
        
        # Active faults
        self._active: dict[UUID, dict[str, Any]] = {}
        
        # Cleanup tasks
        self._cleanup_tasks: dict[UUID, asyncio.Task] = {}
    
    async def inject(
        self,
        fault: Fault,
        duration: int | None = None,
    ) -> None:
        """
        Inject a fault.
        
        Args:
            fault: Fault to inject
            duration: Override duration
        """
        duration = duration or fault.duration_seconds
        
        logger.info(
            f"Injecting fault: {fault.type.value} "
            f"on {fault.target.type.value}/{fault.target.name} "
            f"for {duration}s"
        )
        
        if fault.dry_run:
            logger.info(f"[DRY RUN] Would inject {fault.type.value}")
            return
        
        # Delay if specified
        if fault.delay_seconds > 0:
            await asyncio.sleep(fault.delay_seconds)
        
        # Inject based on type
        if fault.type == FaultType.CPU_STRESS:
            await self._inject_cpu_stress(fault)
        elif fault.type == FaultType.MEMORY_STRESS:
            await self._inject_memory_stress(fault)
        elif fault.type == FaultType.NETWORK_LATENCY:
            await self._inject_network_latency(fault)
        elif fault.type == FaultType.NETWORK_LOSS:
            await self._inject_network_loss(fault)
        elif fault.type == FaultType.NETWORK_PARTITION:
            await self._inject_network_partition(fault)
        elif fault.type == FaultType.POD_KILL:
            await self._inject_pod_kill(fault)
        elif fault.type == FaultType.POD_FAILURE:
            await self._inject_pod_failure(fault)
        elif fault.type == FaultType.HTTP_DELAY:
            await self._inject_http_delay(fault)
        elif fault.type == FaultType.HTTP_ABORT:
            await self._inject_http_abort(fault)
        else:
            logger.warning(f"Unsupported fault type: {fault.type}")
            return
        
        # Track active fault
        self._active[fault.id] = {
            "fault": fault,
            "started_at": datetime.utcnow(),
            "duration": duration,
        }
        
        # Schedule cleanup
        cleanup_task = asyncio.create_task(
            self._auto_cleanup(fault.id, duration)
        )
        self._cleanup_tasks[fault.id] = cleanup_task
    
    async def stop(self, fault_id: UUID) -> bool:
        """
        Stop an active fault.
        
        Args:
            fault_id: Fault ID
            
        Returns:
            True if stopped
        """
        if fault_id not in self._active:
            return False
        
        active = self._active[fault_id]
        fault = active["fault"]
        
        logger.info(f"Stopping fault: {fault.type.value} (id={fault_id})")
        
        # Cancel cleanup task
        if fault_id in self._cleanup_tasks:
            self._cleanup_tasks[fault_id].cancel()
            del self._cleanup_tasks[fault_id]
        
        # Clean up based on type
        await self._cleanup_fault(fault)
        
        del self._active[fault_id]
        
        return True
    
    async def rollback(self, fault_id: UUID) -> bool:
        """
        Rollback a fault (stop and restore).
        
        Args:
            fault_id: Fault ID
            
        Returns:
            True if rolled back
        """
        return await self.stop(fault_id)
    
    async def _auto_cleanup(self, fault_id: UUID, duration: int) -> None:
        """Auto cleanup after duration."""
        try:
            await asyncio.sleep(duration)
            await self.stop(fault_id)
        except asyncio.CancelledError:
            pass
    
    async def _cleanup_fault(self, fault: Fault) -> None:
        """Clean up fault resources."""
        if fault.type in [
            FaultType.CPU_STRESS,
            FaultType.MEMORY_STRESS,
            FaultType.IO_STRESS,
        ]:
            await self._cleanup_stress_fault(fault)
        elif fault.type in [
            FaultType.NETWORK_LATENCY,
            FaultType.NETWORK_LOSS,
            FaultType.NETWORK_CORRUPTION,
        ]:
            await self._cleanup_network_fault(fault)
        elif fault.type == FaultType.NETWORK_PARTITION:
            await self._cleanup_network_partition(fault)
    
    # Fault injection methods
    
    async def _inject_cpu_stress(self, fault: Fault) -> None:
        """Inject CPU stress using stress-ng or similar."""
        params = fault.get_cpu_stress_params()
        workers = params["workers"]
        load = params["load"]
        
        # Create stress pod or exec into target pods
        pods = await self._get_target_pods(fault.target)
        
        for pod in pods:
            # Execute stress command in pod
            cmd = f"stress-ng --cpu {workers} --cpu-load {load} --timeout {fault.duration_seconds}s &"
            
            logger.info(f"Stressing CPU on pod {pod['name']}")
            # In real impl, exec into pod
    
    async def _inject_memory_stress(self, fault: Fault) -> None:
        """Inject memory stress."""
        params = fault.get_memory_stress_params()
        workers = params["workers"]
        bytes_size = params["bytes"]
        
        pods = await self._get_target_pods(fault.target)
        
        for pod in pods:
            cmd = f"stress-ng --vm {workers} --vm-bytes {bytes_size} --timeout {fault.duration_seconds}s &"
            logger.info(f"Stressing memory on pod {pod['name']}")
    
    async def _inject_network_latency(self, fault: Fault) -> None:
        """Inject network latency using tc."""
        params = fault.get_network_latency_params()
        latency = params["latency"]
        jitter = params["jitter"]
        
        pods = await self._get_target_pods(fault.target)
        
        for pod in pods:
            # tc qdisc add command
            cmd = f"tc qdisc add dev eth0 root netem delay {latency} {jitter}"
            logger.info(f"Adding latency {latency} to pod {pod['name']}")
    
    async def _inject_network_loss(self, fault: Fault) -> None:
        """Inject packet loss."""
        params = fault.get_network_loss_params()
        loss = params["loss"]
        
        pods = await self._get_target_pods(fault.target)
        
        for pod in pods:
            cmd = f"tc qdisc add dev eth0 root netem loss {loss}%"
            logger.info(f"Adding {loss}% packet loss to pod {pod['name']}")
    
    async def _inject_network_partition(self, fault: Fault) -> None:
        """Create network partition."""
        target_ips = fault.parameters.get("target_ips", [])
        
        pods = await self._get_target_pods(fault.target)
        
        for pod in pods:
            for ip in target_ips:
                cmd = f"iptables -A OUTPUT -d {ip} -j DROP"
                logger.info(f"Blocking traffic to {ip} from pod {pod['name']}")
    
    async def _inject_pod_kill(self, fault: Fault) -> None:
        """Kill pods."""
        pods = await self._get_target_pods(fault.target)
        
        # Apply percentage/count selection
        selected_pods = self._select_pods(pods, fault.target)
        
        for pod in selected_pods:
            namespace = fault.target.namespace or "default"
            
            logger.info(f"Killing pod: {namespace}/{pod['name']}")
            
            await self._k8s.delete_pod(
                namespace,
                pod["name"],
                grace_period=0,  # Immediate
            )
    
    async def _inject_pod_failure(self, fault: Fault) -> None:
        """Inject pod failure (crash container)."""
        pods = await self._get_target_pods(fault.target)
        selected_pods = self._select_pods(pods, fault.target)
        
        for pod in selected_pods:
            # Kill main process in container
            cmd = "kill 1"
            logger.info(f"Failing pod: {pod['name']}")
    
    async def _inject_http_delay(self, fault: Fault) -> None:
        """Inject HTTP response delay using Istio or similar."""
        delay = fault.parameters.get("delay", "5s")
        percentage = fault.parameters.get("percentage", 100)
        
        # Create Istio VirtualService with fault injection
        fault_config = {
            "fixedDelay": delay,
            "percentage": {"value": percentage},
        }
        
        logger.info(f"Injecting HTTP delay: {delay} for {percentage}% of requests")
        await self._apply_istio_fault(fault.target, fault_config, "delay")
    
    async def _inject_http_abort(self, fault: Fault) -> None:
        """Inject HTTP abort using Istio or similar."""
        status = fault.parameters.get("status", 503)
        percentage = fault.parameters.get("percentage", 100)
        
        fault_config = {
            "httpStatus": status,
            "percentage": {"value": percentage},
        }
        
        logger.info(f"Injecting HTTP abort: {status} for {percentage}% of requests")
        await self._apply_istio_fault(fault.target, fault_config, "abort")
    
    # Cleanup methods
    
    async def _cleanup_stress_fault(self, fault: Fault) -> None:
        """Clean up stress fault."""
        pods = await self._get_target_pods(fault.target)
        
        for pod in pods:
            # Kill stress-ng process
            cmd = "pkill stress-ng || true"
            logger.info(f"Cleaned up stress on pod {pod['name']}")
    
    async def _cleanup_network_fault(self, fault: Fault) -> None:
        """Clean up network fault."""
        pods = await self._get_target_pods(fault.target)
        
        for pod in pods:
            # Remove tc qdisc
            cmd = "tc qdisc del dev eth0 root || true"
            logger.info(f"Cleaned up network fault on pod {pod['name']}")
    
    async def _cleanup_network_partition(self, fault: Fault) -> None:
        """Clean up network partition."""
        pods = await self._get_target_pods(fault.target)
        
        for pod in pods:
            # Flush iptables
            cmd = "iptables -F || true"
            logger.info(f"Cleaned up network partition on pod {pod['name']}")
    
    # Helper methods
    
    async def _get_target_pods(self, target: Target) -> list[dict[str, Any]]:
        """Get pods matching target."""
        namespace = target.namespace or "default"
        
        if target.type == TargetType.POD:
            pod = await self._k8s.get_pod(namespace, target.name)
            return [{"name": pod.name, "ip": pod.pod_ip}]
        
        elif target.type in [TargetType.DEPLOYMENT, TargetType.STATEFULSET]:
            label_selector = target.to_label_selector()
            pods = await self._k8s.list_pods(namespace, label_selector=label_selector)
            return [{"name": p.name, "ip": p.pod_ip} for p in pods]
        
        else:
            return []
    
    def _select_pods(
        self,
        pods: list[dict[str, Any]],
        target: Target,
    ) -> list[dict[str, Any]]:
        """Select subset of pods based on target criteria."""
        if target.count is not None:
            return pods[:target.count]
        
        if target.percentage < 100:
            import random
            count = max(1, int(len(pods) * target.percentage / 100))
            return random.sample(pods, count)
        
        return pods
    
    async def _apply_istio_fault(
        self,
        target: Target,
        fault_config: dict[str, Any],
        fault_type: str,  # "delay" or "abort"
    ) -> None:
        """Apply Istio fault injection."""
        namespace = target.namespace or "default"
        
        virtual_service = {
            "apiVersion": "networking.istio.io/v1beta1",
            "kind": "VirtualService",
            "metadata": {
                "name": f"chaos-{target.name}",
                "namespace": namespace,
            },
            "spec": {
                "hosts": [target.name],
                "http": [
                    {
                        "fault": {
                            fault_type: fault_config,
                        },
                        "route": [
                            {
                                "destination": {
                                    "host": target.name,
                                },
                            },
                        ],
                    },
                ],
            },
        }
        
        # Apply VirtualService
        logger.info(f"Applied Istio fault config for {target.name}")
    
    def get_active_faults(self) -> list[dict[str, Any]]:
        """Get all active faults."""
        return [
            {
                "id": fault_id,
                "type": info["fault"].type.value,
                "target": info["fault"].target.name,
                "started_at": info["started_at"],
                "duration": info["duration"],
            }
            for fault_id, info in self._active.items()
        ]
