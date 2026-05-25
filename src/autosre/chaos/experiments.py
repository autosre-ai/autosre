"""
Chaos Experiment Definitions

Provides models and orchestration for chaos experiments compatible
with Chaos Mesh and LitmusChaos patterns.
"""

import uuid
import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field


class ExperimentType(str, Enum):
    """Types of chaos experiments."""
    
    POD_CHAOS = "pod_chaos"
    NETWORK_CHAOS = "network_chaos"
    IO_CHAOS = "io_chaos"
    STRESS_CHAOS = "stress_chaos"
    DNS_CHAOS = "dns_chaos"
    HTTP_CHAOS = "http_chaos"
    TIME_CHAOS = "time_chaos"
    JVM_CHAOS = "jvm_chaos"
    KERNEL_CHAOS = "kernel_chaos"
    AWS_CHAOS = "aws_chaos"
    GCP_CHAOS = "gcp_chaos"
    AZURE_CHAOS = "azure_chaos"
    CUSTOM = "custom"


class ExperimentState(str, Enum):
    """States of a chaos experiment."""
    
    PENDING = "pending"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"
    ROLLED_BACK = "rolled_back"


class TargetSelector(BaseModel):
    """Selector for chaos experiment targets.
    
    Compatible with Chaos Mesh selectors and Kubernetes label selectors.
    """
    
    namespaces: list[str] = Field(default_factory=list, description="Target namespaces")
    label_selectors: dict[str, str] = Field(
        default_factory=dict, description="Kubernetes label selectors"
    )
    annotation_selectors: dict[str, str] = Field(
        default_factory=dict, description="Kubernetes annotation selectors"
    )
    field_selectors: dict[str, str] = Field(
        default_factory=dict, description="Kubernetes field selectors"
    )
    pods: list[str] = Field(default_factory=list, description="Specific pod names")
    nodes: list[str] = Field(default_factory=list, description="Specific node names")
    node_selectors: dict[str, str] = Field(
        default_factory=dict, description="Node label selectors"
    )
    pod_phase_selectors: list[str] = Field(
        default_factory=list, description="Pod phases to target (Running, Pending, etc.)"
    )
    mode: str = Field(
        default="one", description="Selection mode: one, all, fixed, fixed-percent, random-max-percent"
    )
    value: str = Field(default="", description="Value for mode (e.g., percentage)")
    
    def to_chaos_mesh_spec(self) -> dict[str, Any]:
        """Convert to Chaos Mesh selector spec."""
        spec: dict[str, Any] = {"mode": self.mode}
        
        if self.value:
            spec["value"] = self.value
        if self.namespaces:
            spec["namespaces"] = self.namespaces
        if self.label_selectors:
            spec["labelSelectors"] = self.label_selectors
        if self.annotation_selectors:
            spec["annotationSelectors"] = self.annotation_selectors
        if self.field_selectors:
            spec["fieldSelectors"] = self.field_selectors
        if self.pods:
            spec["pods"] = {ns: self.pods for ns in (self.namespaces or ["default"])}
        if self.nodes:
            spec["nodes"] = self.nodes
        if self.node_selectors:
            spec["nodeSelectors"] = self.node_selectors
        if self.pod_phase_selectors:
            spec["podPhaseSelectors"] = self.pod_phase_selectors
            
        return spec
    
    def to_litmus_spec(self) -> dict[str, Any]:
        """Convert to LitmusChaos selector spec."""
        spec: dict[str, Any] = {}
        
        if self.namespaces:
            spec["appns"] = ",".join(self.namespaces)
        if self.label_selectors:
            labels = [f"{k}={v}" for k, v in self.label_selectors.items()]
            spec["applabel"] = ",".join(labels)
        if self.pods:
            spec["targetPods"] = ",".join(self.pods)
        if self.nodes:
            spec["targetNodes"] = ",".join(self.nodes)
            
        return spec


class ExperimentSchedule(BaseModel):
    """Schedule configuration for chaos experiments."""
    
    cron: Optional[str] = Field(None, description="Cron expression for recurring experiments")
    start_time: Optional[datetime] = Field(None, description="One-time start time")
    end_time: Optional[datetime] = Field(None, description="Experiment end time")
    duration: str = Field(default="30s", description="Duration of the experiment (e.g., 30s, 5m, 1h)")
    concurrency_policy: str = Field(
        default="Forbid", description="Concurrency policy: Allow, Forbid, Replace"
    )
    history_limit: int = Field(default=5, description="Number of completed experiments to retain")
    
    def get_duration_seconds(self) -> int:
        """Convert duration string to seconds."""
        duration = self.duration.lower()
        if duration.endswith("s"):
            return int(duration[:-1])
        elif duration.endswith("m"):
            return int(duration[:-1]) * 60
        elif duration.endswith("h"):
            return int(duration[:-1]) * 3600
        elif duration.endswith("d"):
            return int(duration[:-1]) * 86400
        return int(duration)


class ExperimentConfig(BaseModel):
    """Configuration for a chaos experiment."""
    
    experiment_type: ExperimentType
    target: TargetSelector
    schedule: Optional[ExperimentSchedule] = None
    fault_config: dict[str, Any] = Field(default_factory=dict)
    safety_config: dict[str, Any] = Field(
        default_factory=dict, description="Safety and blast radius config"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )
    dry_run: bool = Field(default=False, description="Run in dry-run mode")
    
    # Hooks
    pre_hooks: list[str] = Field(
        default_factory=list, description="Commands to run before experiment"
    )
    post_hooks: list[str] = Field(
        default_factory=list, description="Commands to run after experiment"
    )


@dataclass
class ExperimentResult:
    """Result of a chaos experiment."""
    
    experiment_id: str
    state: ExperimentState
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0
    
    # Impact metrics
    affected_pods: list[str] = field(default_factory=list)
    affected_nodes: list[str] = field(default_factory=list)
    affected_services: list[str] = field(default_factory=list)
    
    # Observations
    steady_state_before: dict[str, Any] = field(default_factory=dict)
    steady_state_after: dict[str, Any] = field(default_factory=dict)
    steady_state_maintained: bool = True
    
    # Errors and findings
    errors: list[str] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    
    # Safety
    safety_violations: list[str] = field(default_factory=list)
    was_rolled_back: bool = False
    rollback_reason: Optional[str] = None
    
    # Raw data
    events: list[dict[str, Any]] = field(default_factory=list)
    metrics_data: dict[str, Any] = field(default_factory=dict)
    
    def is_successful(self) -> bool:
        """Check if experiment completed successfully."""
        return self.state == ExperimentState.COMPLETED and not self.errors
    
    def add_event(self, event_type: str, message: str, data: Optional[dict] = None) -> None:
        """Add an event to the experiment log."""
        self.events.append({
            "timestamp": datetime.utcnow().isoformat(),
            "type": event_type,
            "message": message,
            "data": data or {},
        })


class ChaosExperiment(BaseModel):
    """A chaos experiment definition.
    
    Compatible with both Chaos Mesh and LitmusChaos patterns.
    """
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., description="Human-readable experiment name")
    description: str = Field(default="", description="Experiment description")
    hypothesis: str = Field(
        default="", description="What behavior is being tested"
    )
    
    config: ExperimentConfig
    
    # State
    state: ExperimentState = ExperimentState.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Ownership
    created_by: str = Field(default="system")
    team: Optional[str] = None
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)
    
    # Results
    result: Optional[dict[str, Any]] = None
    
    class Config:
        use_enum_values = True
    
    def to_chaos_mesh_manifest(self) -> dict[str, Any]:
        """Convert to Chaos Mesh CRD manifest."""
        manifest: dict[str, Any] = {
            "apiVersion": "chaos-mesh.org/v1alpha1",
            "kind": self._get_chaos_mesh_kind(),
            "metadata": {
                "name": self.name.lower().replace(" ", "-"),
                "namespace": "chaos-testing",
                "labels": self.labels,
                "annotations": self.annotations,
            },
            "spec": {
                "selector": self.config.target.to_chaos_mesh_spec(),
                **self.config.fault_config,
            },
        }
        
        if self.config.schedule:
            manifest["spec"]["duration"] = self.config.schedule.duration
            if self.config.schedule.cron:
                # Wrap in Schedule CRD
                return {
                    "apiVersion": "chaos-mesh.org/v1alpha1",
                    "kind": "Schedule",
                    "metadata": manifest["metadata"],
                    "spec": {
                        "schedule": self.config.schedule.cron,
                        "concurrencyPolicy": self.config.schedule.concurrency_policy,
                        "historyLimit": self.config.schedule.history_limit,
                        "type": self._get_chaos_mesh_kind(),
                        self._get_chaos_mesh_kind().lower(): manifest["spec"],
                    },
                }
        
        return manifest
    
    def to_litmus_manifest(self) -> dict[str, Any]:
        """Convert to LitmusChaos ChaosEngine manifest."""
        return {
            "apiVersion": "litmuschaos.io/v1alpha1",
            "kind": "ChaosEngine",
            "metadata": {
                "name": self.name.lower().replace(" ", "-"),
                "namespace": self.config.target.namespaces[0] if self.config.target.namespaces else "default",
                "labels": self.labels,
                "annotations": self.annotations,
            },
            "spec": {
                "engineState": "active",
                "appinfo": self.config.target.to_litmus_spec(),
                "chaosServiceAccount": "litmus-admin",
                "experiments": [
                    {
                        "name": self._get_litmus_experiment_name(),
                        "spec": {
                            "components": {
                                "env": self._get_litmus_env_vars(),
                            },
                        },
                    },
                ],
            },
        }
    
    def _get_chaos_mesh_kind(self) -> str:
        """Get Chaos Mesh CRD kind for experiment type."""
        mapping = {
            ExperimentType.POD_CHAOS: "PodChaos",
            ExperimentType.NETWORK_CHAOS: "NetworkChaos",
            ExperimentType.IO_CHAOS: "IOChaos",
            ExperimentType.STRESS_CHAOS: "StressChaos",
            ExperimentType.DNS_CHAOS: "DNSChaos",
            ExperimentType.HTTP_CHAOS: "HTTPChaos",
            ExperimentType.TIME_CHAOS: "TimeChaos",
            ExperimentType.JVM_CHAOS: "JVMChaos",
            ExperimentType.KERNEL_CHAOS: "KernelChaos",
            ExperimentType.AWS_CHAOS: "AWSChaos",
            ExperimentType.GCP_CHAOS: "GCPChaos",
            ExperimentType.AZURE_CHAOS: "AzureChaos",
        }
        return mapping.get(self.config.experiment_type, "PodChaos")
    
    def _get_litmus_experiment_name(self) -> str:
        """Get LitmusChaos experiment name for experiment type."""
        mapping = {
            ExperimentType.POD_CHAOS: "pod-delete",
            ExperimentType.NETWORK_CHAOS: "pod-network-latency",
            ExperimentType.IO_CHAOS: "disk-fill",
            ExperimentType.STRESS_CHAOS: "pod-cpu-hog",
            ExperimentType.DNS_CHAOS: "pod-dns-error",
        }
        return mapping.get(self.config.experiment_type, "generic-chaos")
    
    def _get_litmus_env_vars(self) -> list[dict[str, str]]:
        """Convert fault config to LitmusChaos env vars."""
        env_vars = []
        for key, value in self.config.fault_config.items():
            env_vars.append({
                "name": key.upper(),
                "value": str(value),
            })
        
        # Add duration
        if self.config.schedule:
            env_vars.append({
                "name": "TOTAL_CHAOS_DURATION",
                "value": str(self.config.schedule.get_duration_seconds()),
            })
        
        return env_vars


class ExperimentRunner(ABC):
    """Abstract base class for experiment runners."""
    
    @abstractmethod
    async def run(self, experiment: ChaosExperiment) -> ExperimentResult:
        """Run a chaos experiment."""
        pass
    
    @abstractmethod
    async def pause(self, experiment_id: str) -> bool:
        """Pause a running experiment."""
        pass
    
    @abstractmethod
    async def resume(self, experiment_id: str) -> bool:
        """Resume a paused experiment."""
        pass
    
    @abstractmethod
    async def abort(self, experiment_id: str, rollback: bool = True) -> bool:
        """Abort an experiment."""
        pass
    
    @abstractmethod
    async def get_status(self, experiment_id: str) -> ExperimentState:
        """Get current experiment status."""
        pass


class LocalExperimentRunner(ExperimentRunner):
    """Local experiment runner for testing and development."""
    
    def __init__(self):
        self._experiments: dict[str, ChaosExperiment] = {}
        self._results: dict[str, ExperimentResult] = {}
        self._tasks: dict[str, asyncio.Task] = {}
    
    async def run(self, experiment: ChaosExperiment) -> ExperimentResult:
        """Run a chaos experiment locally (simulated)."""
        experiment.state = ExperimentState.RUNNING
        self._experiments[experiment.id] = experiment
        
        result = ExperimentResult(
            experiment_id=experiment.id,
            state=ExperimentState.RUNNING,
            start_time=datetime.utcnow(),
        )
        self._results[experiment.id] = result
        
        result.add_event("started", f"Experiment '{experiment.name}' started")
        
        # Simulate experiment execution
        duration = 5  # Default 5 seconds for local testing
        if experiment.config.schedule:
            duration = min(experiment.config.schedule.get_duration_seconds(), 60)
        
        try:
            await asyncio.sleep(duration)
            
            # Simulate completion
            result.state = ExperimentState.COMPLETED
            result.end_time = datetime.utcnow()
            result.duration_seconds = (result.end_time - result.start_time).total_seconds()
            result.steady_state_maintained = True
            result.affected_pods = ["simulated-pod-1", "simulated-pod-2"]
            result.findings.append("Experiment completed successfully in simulation mode")
            result.add_event("completed", "Experiment completed successfully")
            
            experiment.state = ExperimentState.COMPLETED
            experiment.result = {
                "success": True,
                "duration": result.duration_seconds,
            }
            
        except asyncio.CancelledError:
            result.state = ExperimentState.ABORTED
            result.end_time = datetime.utcnow()
            result.add_event("aborted", "Experiment was aborted")
            experiment.state = ExperimentState.ABORTED
            
        return result
    
    async def pause(self, experiment_id: str) -> bool:
        """Pause a running experiment."""
        if experiment_id in self._experiments:
            self._experiments[experiment_id].state = ExperimentState.PAUSED
            return True
        return False
    
    async def resume(self, experiment_id: str) -> bool:
        """Resume a paused experiment."""
        if experiment_id in self._experiments:
            exp = self._experiments[experiment_id]
            if exp.state == ExperimentState.PAUSED:
                exp.state = ExperimentState.RUNNING
                return True
        return False
    
    async def abort(self, experiment_id: str, rollback: bool = True) -> bool:
        """Abort an experiment."""
        if experiment_id in self._tasks:
            self._tasks[experiment_id].cancel()
            
        if experiment_id in self._experiments:
            self._experiments[experiment_id].state = ExperimentState.ABORTED
            if experiment_id in self._results:
                self._results[experiment_id].was_rolled_back = rollback
                self._results[experiment_id].rollback_reason = "Manual abort"
            return True
        return False
    
    async def get_status(self, experiment_id: str) -> ExperimentState:
        """Get current experiment status."""
        if experiment_id in self._experiments:
            return ExperimentState(self._experiments[experiment_id].state)
        return ExperimentState.PENDING


class KubernetesExperimentRunner(ExperimentRunner):
    """Kubernetes-based experiment runner using Chaos Mesh or LitmusChaos."""
    
    def __init__(
        self,
        backend: str = "chaos-mesh",  # or "litmus"
        namespace: str = "chaos-testing",
        kubeconfig: Optional[str] = None,
    ):
        self.backend = backend
        self.namespace = namespace
        self.kubeconfig = kubeconfig
        self._experiments: dict[str, ChaosExperiment] = {}
    
    async def run(self, experiment: ChaosExperiment) -> ExperimentResult:
        """Run a chaos experiment on Kubernetes."""
        result = ExperimentResult(
            experiment_id=experiment.id,
            state=ExperimentState.RUNNING,
            start_time=datetime.utcnow(),
        )
        
        try:
            # Generate manifest
            if self.backend == "chaos-mesh":
                manifest = experiment.to_chaos_mesh_manifest()
            else:
                manifest = experiment.to_litmus_manifest()
            
            result.add_event("manifest_generated", "Generated chaos manifest", {"manifest": manifest})
            
            # In a real implementation, we would:
            # 1. Apply the manifest using kubernetes client
            # 2. Watch for experiment completion
            # 3. Collect metrics and events
            
            # For now, simulate the execution
            experiment.state = ExperimentState.RUNNING
            self._experiments[experiment.id] = experiment
            
            # Simulate waiting for completion
            duration = 30
            if experiment.config.schedule:
                duration = experiment.config.schedule.get_duration_seconds()
            
            await asyncio.sleep(min(duration, 5))  # Cap at 5s for demo
            
            result.state = ExperimentState.COMPLETED
            result.end_time = datetime.utcnow()
            result.duration_seconds = (result.end_time - result.start_time).total_seconds()
            result.add_event("completed", "Experiment completed")
            
            experiment.state = ExperimentState.COMPLETED
            
        except Exception as e:
            result.state = ExperimentState.FAILED
            result.errors.append(str(e))
            result.add_event("error", f"Experiment failed: {e}")
            experiment.state = ExperimentState.FAILED
        
        return result
    
    async def pause(self, experiment_id: str) -> bool:
        """Pause a running experiment by patching the CRD."""
        # In real implementation: kubectl patch to pause
        if experiment_id in self._experiments:
            self._experiments[experiment_id].state = ExperimentState.PAUSED
            return True
        return False
    
    async def resume(self, experiment_id: str) -> bool:
        """Resume a paused experiment."""
        if experiment_id in self._experiments:
            self._experiments[experiment_id].state = ExperimentState.RUNNING
            return True
        return False
    
    async def abort(self, experiment_id: str, rollback: bool = True) -> bool:
        """Abort an experiment by deleting the CRD."""
        # In real implementation: kubectl delete
        if experiment_id in self._experiments:
            self._experiments[experiment_id].state = ExperimentState.ABORTED
            return True
        return False
    
    async def get_status(self, experiment_id: str) -> ExperimentState:
        """Get experiment status from Kubernetes."""
        if experiment_id in self._experiments:
            return ExperimentState(self._experiments[experiment_id].state)
        return ExperimentState.PENDING
