"""
Fault Injection Module

Provides fault types and injection mechanisms compatible with
Chaos Mesh and LitmusChaos patterns.
"""

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class FaultType(str, Enum):
    """Types of faults that can be injected."""
    
    # Pod/Container faults
    POD_KILL = "pod_kill"
    POD_FAILURE = "pod_failure"
    CONTAINER_KILL = "container_kill"
    
    # Network faults
    NETWORK_DELAY = "network_delay"
    NETWORK_PARTITION = "network_partition"
    NETWORK_LOSS = "network_loss"
    NETWORK_DUPLICATE = "network_duplicate"
    NETWORK_CORRUPT = "network_corrupt"
    NETWORK_BANDWIDTH = "network_bandwidth"
    
    # Stress faults
    CPU_STRESS = "cpu_stress"
    MEMORY_STRESS = "memory_stress"
    IO_STRESS = "io_stress"
    
    # DNS faults
    DNS_ERROR = "dns_error"
    DNS_RANDOM = "dns_random"
    
    # HTTP faults
    HTTP_ABORT = "http_abort"
    HTTP_DELAY = "http_delay"
    HTTP_REPLACE = "http_replace"
    HTTP_PATCH = "http_patch"
    
    # Time faults
    TIME_OFFSET = "time_offset"
    
    # JVM faults
    JVM_EXCEPTION = "jvm_exception"
    JVM_GC = "jvm_gc"
    JVM_STRESS = "jvm_stress"
    
    # Cloud faults
    AWS_EC2_STOP = "aws_ec2_stop"
    AWS_EC2_RESTART = "aws_ec2_restart"
    AWS_DETACH_VOLUME = "aws_detach_volume"
    GCP_VM_STOP = "gcp_vm_stop"
    AZURE_VM_STOP = "azure_vm_stop"


class Fault(BaseModel, ABC):
    """Base class for all fault types."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    fault_type: FaultType
    name: str = Field(default="")
    description: str = Field(default="")
    duration: str = Field(default="30s", description="Duration of the fault")
    
    # Targeting
    target_namespace: str = Field(default="default")
    target_labels: dict[str, str] = Field(default_factory=dict)
    target_pods: list[str] = Field(default_factory=list)
    target_percentage: Optional[int] = Field(None, ge=0, le=100)
    
    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)
    
    @abstractmethod
    def to_chaos_mesh_spec(self) -> dict[str, Any]:
        """Convert to Chaos Mesh spec."""
        pass
    
    @abstractmethod
    def to_litmus_spec(self) -> dict[str, Any]:
        """Convert to LitmusChaos spec."""
        pass
    
    def get_duration_seconds(self) -> int:
        """Convert duration string to seconds."""
        duration = self.duration.lower()
        if duration.endswith("s"):
            return int(duration[:-1])
        elif duration.endswith("m"):
            return int(duration[:-1]) * 60
        elif duration.endswith("h"):
            return int(duration[:-1]) * 3600
        return int(duration)


# =============================================================================
# Pod/Container Faults
# =============================================================================

class PodKillFault(Fault):
    """Kill pods to test recovery and resilience."""
    
    fault_type: FaultType = FaultType.POD_KILL
    grace_period: int = Field(default=0, description="Grace period in seconds")
    
    def to_chaos_mesh_spec(self) -> dict[str, Any]:
        return {
            "action": "pod-kill",
            "gracePeriod": self.grace_period,
            "duration": self.duration,
        }
    
    def to_litmus_spec(self) -> dict[str, Any]:
        return {
            "name": "pod-delete",
            "TOTAL_CHAOS_DURATION": str(self.get_duration_seconds()),
            "FORCE": "true" if self.grace_period == 0 else "false",
            "CHAOS_INTERVAL": "10",
        }


class PodFailureFault(Fault):
    """Inject pod failure without killing (container stays but fails)."""
    
    fault_type: FaultType = FaultType.POD_FAILURE
    
    def to_chaos_mesh_spec(self) -> dict[str, Any]:
        return {
            "action": "pod-failure",
            "duration": self.duration,
        }
    
    def to_litmus_spec(self) -> dict[str, Any]:
        return {
            "name": "pod-delete",  # LitmusChaos doesn't have direct pod-failure
            "TOTAL_CHAOS_DURATION": str(self.get_duration_seconds()),
        }


# =============================================================================
# Network Faults
# =============================================================================

class NetworkDelayFault(Fault):
    """Inject network latency."""
    
    fault_type: FaultType = FaultType.NETWORK_DELAY
    latency: str = Field(default="100ms", description="Latency to inject")
    jitter: str = Field(default="0ms", description="Jitter variance")
    correlation: str = Field(default="0", description="Correlation percentage")
    
    # Direction and targeting
    direction: str = Field(default="to", description="Direction: to, from, both")
    external_targets: list[str] = Field(
        default_factory=list, description="External IPs/CIDRs to target"
    )
    target_service: Optional[str] = Field(None, description="Target Kubernetes service")
    target_port: Optional[int] = Field(None, description="Target port")
    
    def to_chaos_mesh_spec(self) -> dict[str, Any]:
        spec: dict[str, Any] = {
            "action": "delay",
            "delay": {
                "latency": self.latency,
                "jitter": self.jitter,
                "correlation": self.correlation,
            },
            "direction": self.direction,
            "duration": self.duration,
        }
        
        if self.external_targets:
            spec["externalTargets"] = self.external_targets
        if self.target_port:
            spec["target"] = {"selector": {"ports": [self.target_port]}}
            
        return spec
    
    def to_litmus_spec(self) -> dict[str, Any]:
        return {
            "name": "pod-network-latency",
            "TOTAL_CHAOS_DURATION": str(self.get_duration_seconds()),
            "NETWORK_LATENCY": self.latency.replace("ms", ""),
            "JITTER": self.jitter.replace("ms", ""),
            "DESTINATION_IPS": ",".join(self.external_targets) if self.external_targets else "",
        }


class NetworkPartitionFault(Fault):
    """Create network partition between services."""
    
    fault_type: FaultType = FaultType.NETWORK_PARTITION
    direction: str = Field(default="both")
    external_targets: list[str] = Field(default_factory=list)
    
    def to_chaos_mesh_spec(self) -> dict[str, Any]:
        return {
            "action": "partition",
            "direction": self.direction,
            "duration": self.duration,
            "externalTargets": self.external_targets,
        }
    
    def to_litmus_spec(self) -> dict[str, Any]:
        return {
            "name": "pod-network-partition",
            "TOTAL_CHAOS_DURATION": str(self.get_duration_seconds()),
            "DESTINATION_IPS": ",".join(self.external_targets),
        }


class NetworkLossFault(Fault):
    """Inject packet loss."""
    
    fault_type: FaultType = FaultType.NETWORK_LOSS
    loss: str = Field(default="25", description="Percentage of packets to drop")
    correlation: str = Field(default="0")
    direction: str = Field(default="to")
    
    def to_chaos_mesh_spec(self) -> dict[str, Any]:
        return {
            "action": "loss",
            "loss": {
                "loss": self.loss,
                "correlation": self.correlation,
            },
            "direction": self.direction,
            "duration": self.duration,
        }
    
    def to_litmus_spec(self) -> dict[str, Any]:
        return {
            "name": "pod-network-loss",
            "TOTAL_CHAOS_DURATION": str(self.get_duration_seconds()),
            "NETWORK_PACKET_LOSS_PERCENTAGE": self.loss,
        }


# =============================================================================
# Stress Faults
# =============================================================================

class CPUStressFault(Fault):
    """Inject CPU stress."""
    
    fault_type: FaultType = FaultType.CPU_STRESS
    workers: int = Field(default=1, description="Number of CPU workers")
    load: int = Field(default=50, ge=0, le=100, description="CPU load percentage per worker")
    
    def to_chaos_mesh_spec(self) -> dict[str, Any]:
        return {
            "stressors": {
                "cpu": {
                    "workers": self.workers,
                    "load": self.load,
                },
            },
            "duration": self.duration,
        }
    
    def to_litmus_spec(self) -> dict[str, Any]:
        return {
            "name": "pod-cpu-hog",
            "TOTAL_CHAOS_DURATION": str(self.get_duration_seconds()),
            "CPU_CORES": str(self.workers),
            "CPU_LOAD": str(self.load),
        }


class MemoryStressFault(Fault):
    """Inject memory stress."""
    
    fault_type: FaultType = FaultType.MEMORY_STRESS
    workers: int = Field(default=1, description="Number of memory workers")
    size: str = Field(default="256Mi", description="Memory size to consume per worker")
    
    def to_chaos_mesh_spec(self) -> dict[str, Any]:
        return {
            "stressors": {
                "memory": {
                    "workers": self.workers,
                    "size": self.size,
                },
            },
            "duration": self.duration,
        }
    
    def to_litmus_spec(self) -> dict[str, Any]:
        # Convert size to MB
        size_mb = self.size
        if size_mb.endswith("Mi"):
            size_mb = size_mb[:-2]
        elif size_mb.endswith("Gi"):
            size_mb = str(int(size_mb[:-2]) * 1024)
            
        return {
            "name": "pod-memory-hog",
            "TOTAL_CHAOS_DURATION": str(self.get_duration_seconds()),
            "MEMORY_CONSUMPTION": size_mb,
        }


class IOStressFault(Fault):
    """Inject I/O stress."""
    
    fault_type: FaultType = FaultType.IO_STRESS
    workers: int = Field(default=1)
    size: str = Field(default="1Gi", description="Total data size for I/O operations")
    path: str = Field(default="/tmp", description="Path for I/O operations")
    
    def to_chaos_mesh_spec(self) -> dict[str, Any]:
        return {
            "stressors": {
                "io": {
                    "workers": self.workers,
                },
            },
            "duration": self.duration,
        }
    
    def to_litmus_spec(self) -> dict[str, Any]:
        return {
            "name": "disk-fill",
            "TOTAL_CHAOS_DURATION": str(self.get_duration_seconds()),
            "FILL_PERCENTAGE": "80",
            "CONTAINER_PATH": self.path,
        }


# =============================================================================
# DNS Faults
# =============================================================================

class DNSFault(Fault):
    """Inject DNS failures."""
    
    fault_type: FaultType = FaultType.DNS_ERROR
    action: str = Field(default="error", description="error or random")
    domain_patterns: list[str] = Field(
        default_factory=list, description="Domain patterns to target"
    )
    
    def to_chaos_mesh_spec(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "patterns": self.domain_patterns or ["*"],
            "duration": self.duration,
        }
    
    def to_litmus_spec(self) -> dict[str, Any]:
        return {
            "name": "pod-dns-error",
            "TOTAL_CHAOS_DURATION": str(self.get_duration_seconds()),
            "TARGET_HOSTNAMES": ",".join(self.domain_patterns) if self.domain_patterns else "",
        }


# =============================================================================
# HTTP Faults
# =============================================================================

class HTTPFault(Fault):
    """Inject HTTP-level faults."""
    
    fault_type: FaultType = FaultType.HTTP_DELAY
    action: str = Field(default="delay", description="delay, abort, replace, patch")
    
    # Delay config
    delay: str = Field(default="100ms")
    
    # Abort config
    abort_code: int = Field(default=500)
    
    # Replace/patch config
    body: Optional[str] = None
    headers: dict[str, str] = Field(default_factory=dict)
    
    # Matching rules
    port: int = Field(default=80)
    path: str = Field(default="*")
    method: str = Field(default="*")
    
    def to_chaos_mesh_spec(self) -> dict[str, Any]:
        spec: dict[str, Any] = {
            "port": self.port,
            "duration": self.duration,
            "target": "Request",
        }
        
        if self.path != "*":
            spec["path"] = self.path
        if self.method != "*":
            spec["method"] = self.method
            
        if self.action == "delay":
            spec["delay"] = self.delay
        elif self.action == "abort":
            spec["abort"] = True
            spec["code"] = self.abort_code
        elif self.action in ("replace", "patch"):
            spec["action"] = self.action
            if self.body:
                spec["body"] = self.body
            if self.headers:
                spec["headers"] = self.headers
                
        return spec
    
    def to_litmus_spec(self) -> dict[str, Any]:
        return {
            "name": "pod-http-latency",
            "TOTAL_CHAOS_DURATION": str(self.get_duration_seconds()),
            "LATENCY": self.delay.replace("ms", "") if self.action == "delay" else "0",
            "TARGET_SERVICE_PORT": str(self.port),
        }


# =============================================================================
# Fault Injector
# =============================================================================

@dataclass
class InjectionResult:
    """Result of fault injection."""
    
    fault_id: str
    success: bool
    message: str
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None
    affected_targets: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    rollback_performed: bool = False


class FaultInjector:
    """Coordinates fault injection across different backends."""
    
    def __init__(
        self,
        backend: str = "local",  # local, chaos-mesh, litmus
        namespace: str = "chaos-testing",
        dry_run: bool = False,
    ):
        self.backend = backend
        self.namespace = namespace
        self.dry_run = dry_run
        self._active_faults: dict[str, Fault] = {}
    
    async def inject(self, fault: Fault) -> InjectionResult:
        """Inject a fault into the target system."""
        result = InjectionResult(
            fault_id=fault.id,
            success=False,
            message="",
        )
        
        if self.dry_run:
            result.success = True
            result.message = f"[DRY RUN] Would inject {fault.fault_type} fault"
            result.affected_targets = ["dry-run-target"]
            return result
        
        try:
            self._active_faults[fault.id] = fault
            
            if self.backend == "local":
                result = await self._inject_local(fault)
            elif self.backend == "chaos-mesh":
                result = await self._inject_chaos_mesh(fault)
            elif self.backend == "litmus":
                result = await self._inject_litmus(fault)
            else:
                result.message = f"Unknown backend: {self.backend}"
                
        except Exception as e:
            result.success = False
            result.errors.append(str(e))
            result.message = f"Injection failed: {e}"
            
        return result
    
    async def rollback(self, fault_id: str) -> bool:
        """Rollback/remove an injected fault."""
        if fault_id not in self._active_faults:
            return False
            
        fault = self._active_faults.pop(fault_id)
        
        if self.backend == "local":
            return True  # Local simulation, nothing to rollback
        elif self.backend == "chaos-mesh":
            # In real implementation: kubectl delete the chaos CRD
            return True
        elif self.backend == "litmus":
            # In real implementation: update ChaosEngine to stop
            return True
            
        return False
    
    async def rollback_all(self) -> int:
        """Rollback all active faults."""
        count = 0
        for fault_id in list(self._active_faults.keys()):
            if await self.rollback(fault_id):
                count += 1
        return count
    
    async def list_active(self) -> list[Fault]:
        """List all currently active faults."""
        return list(self._active_faults.values())
    
    async def _inject_local(self, fault: Fault) -> InjectionResult:
        """Simulate fault injection locally."""
        return InjectionResult(
            fault_id=fault.id,
            success=True,
            message=f"[LOCAL] Simulated {fault.fault_type} injection",
            affected_targets=fault.target_pods or ["simulated-pod"],
        )
    
    async def _inject_chaos_mesh(self, fault: Fault) -> InjectionResult:
        """Inject fault using Chaos Mesh."""
        # Generate the Chaos Mesh spec
        spec = fault.to_chaos_mesh_spec()
        
        # In real implementation:
        # 1. Create the appropriate Chaos Mesh CRD
        # 2. Wait for injection to take effect
        # 3. Monitor the chaos condition
        
        return InjectionResult(
            fault_id=fault.id,
            success=True,
            message=f"Injected {fault.fault_type} via Chaos Mesh",
            affected_targets=fault.target_pods,
        )
    
    async def _inject_litmus(self, fault: Fault) -> InjectionResult:
        """Inject fault using LitmusChaos."""
        # Generate the LitmusChaos spec
        spec = fault.to_litmus_spec()
        
        # In real implementation:
        # 1. Create/update ChaosEngine
        # 2. Wait for experiment runner pod
        # 3. Monitor chaos result
        
        return InjectionResult(
            fault_id=fault.id,
            success=True,
            message=f"Injected {fault.fault_type} via LitmusChaos",
            affected_targets=fault.target_pods,
        )


class FaultRegistry:
    """Registry of available fault types with factory methods."""
    
    _fault_types: dict[FaultType, type] = {
        FaultType.POD_KILL: PodKillFault,
        FaultType.POD_FAILURE: PodFailureFault,
        FaultType.NETWORK_DELAY: NetworkDelayFault,
        FaultType.NETWORK_PARTITION: NetworkPartitionFault,
        FaultType.NETWORK_LOSS: NetworkLossFault,
        FaultType.CPU_STRESS: CPUStressFault,
        FaultType.MEMORY_STRESS: MemoryStressFault,
        FaultType.IO_STRESS: IOStressFault,
        FaultType.DNS_ERROR: DNSFault,
        FaultType.HTTP_DELAY: HTTPFault,
        FaultType.HTTP_ABORT: HTTPFault,
    }
    
    @classmethod
    def create(cls, fault_type: FaultType, **kwargs) -> Fault:
        """Create a fault instance by type."""
        if fault_type not in cls._fault_types:
            raise ValueError(f"Unknown fault type: {fault_type}")
        return cls._fault_types[fault_type](fault_type=fault_type, **kwargs)
    
    @classmethod
    def list_types(cls) -> list[FaultType]:
        """List all registered fault types."""
        return list(cls._fault_types.keys())
    
    @classmethod
    def register(cls, fault_type: FaultType, fault_class: type) -> None:
        """Register a custom fault type."""
        cls._fault_types[fault_type] = fault_class


# Convenience functions for common fault patterns
def pod_kill(
    namespace: str = "default",
    labels: Optional[dict[str, str]] = None,
    pods: Optional[list[str]] = None,
    duration: str = "30s",
    grace_period: int = 0,
) -> PodKillFault:
    """Create a pod kill fault."""
    return PodKillFault(
        name=f"pod-kill-{namespace}",
        target_namespace=namespace,
        target_labels=labels or {},
        target_pods=pods or [],
        duration=duration,
        grace_period=grace_period,
    )


def network_delay(
    namespace: str = "default",
    labels: Optional[dict[str, str]] = None,
    latency: str = "100ms",
    jitter: str = "10ms",
    duration: str = "5m",
    direction: str = "to",
) -> NetworkDelayFault:
    """Create a network delay fault."""
    return NetworkDelayFault(
        name=f"network-delay-{namespace}",
        target_namespace=namespace,
        target_labels=labels or {},
        latency=latency,
        jitter=jitter,
        duration=duration,
        direction=direction,
    )


def cpu_stress(
    namespace: str = "default",
    labels: Optional[dict[str, str]] = None,
    workers: int = 2,
    load: int = 80,
    duration: str = "5m",
) -> CPUStressFault:
    """Create a CPU stress fault."""
    return CPUStressFault(
        name=f"cpu-stress-{namespace}",
        target_namespace=namespace,
        target_labels=labels or {},
        workers=workers,
        load=load,
        duration=duration,
    )


def memory_stress(
    namespace: str = "default",
    labels: Optional[dict[str, str]] = None,
    workers: int = 1,
    size: str = "512Mi",
    duration: str = "5m",
) -> MemoryStressFault:
    """Create a memory stress fault."""
    return MemoryStressFault(
        name=f"memory-stress-{namespace}",
        target_namespace=namespace,
        target_labels=labels or {},
        workers=workers,
        size=size,
        duration=duration,
    )
