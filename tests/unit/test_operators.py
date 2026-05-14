"""
Unit tests for Kubernetes operators.

Tests for:
- PodRestarter
- ScaleManager
- ResourceTuner
- DrainManager
- DeploymentRollback
"""

from __future__ import annotations

import asyncio
import pytest
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from autosre.operators import (
    BaseOperator,
    OperatorResult,
    OperatorStatus,
    OperatorConfig,
    PodRestarter,
    RestartStrategy,
    RestartResult,
    ScaleManager,
    ScaleMode,
    ScaleResult,
    HPAOverride,
    ResourceTuner,
    ResourceSpec,
    TuningResult,
    ResourceRecommendation,
    DrainManager,
    DrainConfig,
    DrainResult,
    DrainStatus,
    DeploymentRollback,
    RollbackConfig,
    RollbackResult as DeploymentRollbackResult,
    RevisionInfo,
)
from autosre.operators.pod_restarter import RestartConfig
from autosre.operators.scale_manager import ScaleConfig


# ============================================================================
# Mock Kubernetes Client
# ============================================================================

class MockPod:
    """Mock Kubernetes pod."""
    
    def __init__(
        self,
        name: str = "test-pod",
        namespace: str = "default",
        phase: str = "Running",
        ready: bool = True,
    ):
        self.name = name
        self.namespace = namespace
        self.phase = MagicMock(value=phase)
        self.pod_ip = "10.0.0.1"
        self.node_name = "worker-1"
        self.total_restarts = 0
        self.is_ready = ready
        self.labels = {"app": "test", "version": "v1"}
        self.owner_references = [{"kind": "ReplicaSet", "name": "test-rs"}]


class MockDeployment:
    """Mock Kubernetes deployment."""
    
    def __init__(
        self,
        name: str = "test-deployment",
        namespace: str = "default",
        replicas: int = 3,
    ):
        self.name = name
        self.namespace = namespace
        self.replicas = replicas
        self.ready_replicas = replicas
        self.available_replicas = replicas
        self.updated_replicas = replicas
        self.selector = {"app": "test"}
        self.labels = {"app": "test"}
        self.revision = 1


class MockNode:
    """Mock Kubernetes node."""
    
    def __init__(
        self,
        name: str = "worker-1",
        ready: bool = True,
        schedulable: bool = True,
    ):
        self.name = name
        self.is_ready = ready
        self.is_schedulable = schedulable
        self.labels = {"node-role.kubernetes.io/worker": ""}
        self.conditions = []
        self.capacity = {"cpu": "4", "memory": "16Gi", "pods": "110"}
        self.allocatable = {"cpu": "3.5", "memory": "14Gi", "pods": "100"}


class MockK8sClient:
    """Mock Kubernetes client for testing."""
    
    def __init__(self):
        self.pods = {}
        self.deployments = {}
        self.nodes = {}
        self.hpas = {}
        self.call_log = []
    
    async def get_pod(self, namespace: str, name: str) -> MockPod:
        self.call_log.append(("get_pod", namespace, name))
        key = f"{namespace}/{name}"
        if key in self.pods:
            return self.pods[key]
        return MockPod(name=name, namespace=namespace)
    
    async def list_pods(
        self,
        namespace: str,
        label_selector: str | None = None,
        limit: int | None = None,
    ) -> list[MockPod]:
        self.call_log.append(("list_pods", namespace, label_selector))
        return [
            pod for key, pod in self.pods.items()
            if pod.namespace == namespace
        ] or [MockPod(namespace=namespace)]
    
    async def delete_pod(
        self,
        namespace: str,
        name: str,
        grace_period: int = 30,
    ) -> bool:
        self.call_log.append(("delete_pod", namespace, name, grace_period))
        key = f"{namespace}/{name}"
        self.pods.pop(key, None)
        return True
    
    async def get_deployment(self, namespace: str, name: str) -> MockDeployment:
        self.call_log.append(("get_deployment", namespace, name))
        key = f"{namespace}/{name}"
        if key in self.deployments:
            return self.deployments[key]
        return MockDeployment(name=name, namespace=namespace)
    
    async def restart_deployment(self, namespace: str, name: str) -> MockDeployment:
        self.call_log.append(("restart_deployment", namespace, name))
        return MockDeployment(name=name, namespace=namespace)
    
    async def scale_deployment(
        self,
        namespace: str,
        name: str,
        replicas: int,
    ) -> MockDeployment:
        self.call_log.append(("scale_deployment", namespace, name, replicas))
        deployment = MockDeployment(name=name, namespace=namespace, replicas=replicas)
        key = f"{namespace}/{name}"
        self.deployments[key] = deployment
        return deployment
    
    async def get_node(self, name: str) -> MockNode:
        self.call_log.append(("get_node", name))
        if name in self.nodes:
            return self.nodes[name]
        return MockNode(name=name)
    
    async def list_nodes(self, label_selector: str | None = None) -> list[MockNode]:
        self.call_log.append(("list_nodes", label_selector))
        return list(self.nodes.values()) or [MockNode()]
    
    async def cordon_node(self, name: str) -> bool:
        self.call_log.append(("cordon_node", name))
        return True
    
    async def uncordon_node(self, name: str) -> bool:
        self.call_log.append(("uncordon_node", name))
        return True
    
    async def drain_node(
        self,
        name: str,
        force: bool = False,
        grace_period: int = 30,
    ) -> bool:
        self.call_log.append(("drain_node", name, force, grace_period))
        return True
    
    async def evict_pod(self, namespace: str, name: str) -> bool:
        self.call_log.append(("evict_pod", namespace, name))
        return True
    
    async def get_hpa(self, namespace: str, name: str) -> dict:
        self.call_log.append(("get_hpa", namespace, name))
        key = f"{namespace}/{name}"
        return self.hpas.get(key, {
            "name": name,
            "min_replicas": 2,
            "max_replicas": 10,
            "current_replicas": 3,
            "metrics": [],
        })
    
    async def update_hpa(
        self,
        namespace: str,
        name: str,
        min_replicas: int | None = None,
        max_replicas: int | None = None,
    ) -> dict:
        self.call_log.append(("update_hpa", namespace, name, min_replicas, max_replicas))
        return {
            "name": name,
            "min_replicas": min_replicas or 2,
            "max_replicas": max_replicas or 10,
        }
    
    async def delete_hpa(self, namespace: str, name: str) -> bool:
        self.call_log.append(("delete_hpa", namespace, name))
        return True
    
    async def get_deployment_revisions(
        self,
        namespace: str,
        name: str,
    ) -> list[dict]:
        self.call_log.append(("get_deployment_revisions", namespace, name))
        return [
            {"revision": 1, "image": "app:v1.0", "created_at": datetime.utcnow()},
            {"revision": 2, "image": "app:v1.1", "created_at": datetime.utcnow()},
            {"revision": 3, "image": "app:v1.2", "created_at": datetime.utcnow()},
        ]
    
    async def rollback_deployment(
        self,
        namespace: str,
        name: str,
        revision: int,
    ) -> MockDeployment:
        self.call_log.append(("rollback_deployment", namespace, name, revision))
        return MockDeployment(name=name, namespace=namespace)
    
    async def patch_pod(
        self,
        namespace: str,
        name: str,
        patch: dict,
    ) -> MockPod:
        self.call_log.append(("patch_pod", namespace, name, patch))
        return MockPod(name=name, namespace=namespace)
    
    async def patch_deployment(
        self,
        namespace: str,
        name: str,
        patch: dict,
    ) -> MockDeployment:
        self.call_log.append(("patch_deployment", namespace, name, patch))
        return MockDeployment(name=name, namespace=namespace)
    
    async def get_pod_metrics(
        self,
        namespace: str,
        name: str,
    ) -> dict:
        self.call_log.append(("get_pod_metrics", namespace, name))
        return {
            "cpu_usage": "100m",
            "memory_usage": "256Mi",
        }


@pytest.fixture
def k8s_client() -> MockK8sClient:
    """Create a mock K8s client."""
    return MockK8sClient()


# ============================================================================
# PodRestarter Tests
# ============================================================================

class TestPodRestarter:
    """Tests for PodRestarter operator."""
    
    @pytest.fixture
    def restarter(self, k8s_client: MockK8sClient) -> PodRestarter:
        """Create a PodRestarter instance."""
        config = RestartConfig(
            dry_run=False,
            grace_period_seconds=10,
            verify_health_after_restart=False,  # Disable for faster tests
            health_check_max_wait_seconds=5,
        )
        return PodRestarter(k8s_client, config)
    
    def test_restarter_name(self, restarter: PodRestarter):
        """Test operator name."""
        assert restarter.name == "PodRestarter"
    
    @pytest.mark.asyncio
    async def test_health_check(self, restarter: PodRestarter):
        """Test health check."""
        healthy = await restarter.health_check()
        assert healthy
    
    @pytest.mark.asyncio
    async def test_restart_pod_delete_strategy(
        self,
        restarter: PodRestarter,
        k8s_client: MockK8sClient,
    ):
        """Test restarting pod with delete strategy."""
        result = await restarter.restart_pod(
            namespace="default",
            pod_name="api-server-xyz",
            strategy=RestartStrategy.DELETE,
            wait_for_ready=False,  # Don't wait in test
        )
        
        assert result.success
        assert result.status == OperatorStatus.COMPLETED
        assert result.strategy == RestartStrategy.DELETE
        assert ("delete_pod", "default", "api-server-xyz", 10) in k8s_client.call_log
    
    @pytest.mark.asyncio
    async def test_restart_pod_force_strategy(
        self,
        restarter: PodRestarter,
        k8s_client: MockK8sClient,
    ):
        """Test force restart."""
        result = await restarter.restart_pod(
            namespace="default",
            pod_name="stuck-pod",
            strategy=RestartStrategy.FORCE,
            wait_for_ready=False,
        )
        
        assert result.success
        # Force strategy uses grace_period=0
        assert ("delete_pod", "default", "stuck-pod", 0) in k8s_client.call_log
    
    @pytest.mark.asyncio
    async def test_restart_pod_dry_run(
        self,
        restarter: PodRestarter,
        k8s_client: MockK8sClient,
    ):
        """Test dry-run restart."""
        result = await restarter.restart_pod(
            namespace="default",
            pod_name="api-server-xyz",
            dry_run=True,
        )
        
        assert result.success
        assert result.result_data.get("dry_run") is True
        # Should not have called delete_pod
        assert not any(call[0] == "delete_pod" for call in k8s_client.call_log)
    
    @pytest.mark.asyncio
    async def test_restart_deployment_rolling(
        self,
        restarter: PodRestarter,
        k8s_client: MockK8sClient,
    ):
        """Test rolling restart of deployment."""
        results = await restarter.restart_deployment(
            namespace="default",
            deployment_name="api-server",
            strategy=RestartStrategy.ROLLING,
        )
        
        assert len(results) == 1
        assert results[0].success
        assert ("restart_deployment", "default", "api-server") in k8s_client.call_log
    
    @pytest.mark.asyncio
    async def test_restart_pods_by_label(
        self,
        restarter: PodRestarter,
        k8s_client: MockK8sClient,
    ):
        """Test restarting pods by label selector."""
        # Add some pods
        k8s_client.pods["default/pod-1"] = MockPod(name="pod-1", namespace="default")
        k8s_client.pods["default/pod-2"] = MockPod(name="pod-2", namespace="default")
        
        results = await restarter.restart_pods_by_label(
            namespace="default",
            label_selector="app=test",
            wait_for_ready=False,
        )
        
        assert len(results) == 2
        assert all(r.success for r in results)
    
    def test_get_metrics(self, restarter: PodRestarter):
        """Test getting operator metrics."""
        metrics = restarter.get_metrics()
        
        assert "operator" in metrics
        assert metrics["operator"] == "PodRestarter"
        assert "operations_total" in metrics
        assert "success_rate" in metrics
    
    def test_get_history(self, restarter: PodRestarter):
        """Test getting operation history."""
        history = restarter.get_history()
        
        # Initially empty
        assert len(history) == 0


# ============================================================================
# ScaleManager Tests
# ============================================================================

class TestScaleManager:
    """Tests for ScaleManager operator."""
    
    @pytest.fixture
    def scaler(self, k8s_client: MockK8sClient) -> ScaleManager:
        """Create a ScaleManager instance."""
        return ScaleManager(k8s_client)
    
    def test_scaler_name(self, scaler: ScaleManager):
        """Test operator name."""
        assert scaler.name == "ScaleManager"
    
    @pytest.mark.asyncio
    async def test_scale_deployment(
        self,
        scaler: ScaleManager,
        k8s_client: MockK8sClient,
    ):
        """Test scaling a deployment."""
        result = await scaler.scale_deployment(
            namespace="default",
            deployment_name="api-server",
            replicas=5,
        )
        
        assert result.success
        assert result.target_replicas == 5
        assert ("scale_deployment", "default", "api-server", 5) in k8s_client.call_log
    
    @pytest.mark.asyncio
    async def test_scale_deployment_dry_run(
        self,
        scaler: ScaleManager,
        k8s_client: MockK8sClient,
    ):
        """Test dry-run scaling."""
        result = await scaler.scale_deployment(
            namespace="default",
            deployment_name="api-server",
            replicas=10,
            dry_run=True,
        )
        
        assert result.success
        # Should not have called scale_deployment
        assert not any(
            call[0] == "scale_deployment"
            for call in k8s_client.call_log
        )
    
    @pytest.mark.asyncio
    async def test_scale_to_zero_blocked(
        self,
        scaler: ScaleManager,
        k8s_client: MockK8sClient,
    ):
        """Test that scaling to zero is blocked by default."""
        result = await scaler.scale_deployment(
            namespace="default",
            deployment_name="api-server",
            replicas=0,
        )
        
        # Should fail due to safety check
        assert not result.success or scaler._config.allow_scale_to_zero
    
    @pytest.mark.asyncio
    async def test_hpa_override(
        self,
        scaler: ScaleManager,
        k8s_client: MockK8sClient,
    ):
        """Test HPA override."""
        result = await scaler.override_hpa(
            namespace="default",
            hpa_name="api-hpa",
            min_replicas=5,
            max_replicas=10,
            duration_minutes=30,
        )
        
        assert result.success
        assert ("update_hpa", "default", "api-hpa", 5, 10) in k8s_client.call_log
    
    @pytest.mark.asyncio
    async def test_disable_hpa(
        self,
        scaler: ScaleManager,
        k8s_client: MockK8sClient,
    ):
        """Test disabling HPA."""
        result = await scaler.disable_hpa(
            namespace="default",
            hpa_name="api-hpa",
        )
        
        assert result.success
    
    @pytest.mark.asyncio
    async def test_get_current_scale(
        self,
        scaler: ScaleManager,
        k8s_client: MockK8sClient,
    ):
        """Test getting current scale."""
        k8s_client.deployments["default/api-server"] = MockDeployment(
            name="api-server",
            namespace="default",
            replicas=3,
        )
        
        scale_info = await scaler.get_current_scale(
            namespace="default",
            deployment_name="api-server",
        )
        
        assert scale_info["replicas"] == 3


# ============================================================================
# ResourceTuner Tests
# ============================================================================

class TestResourceTuner:
    """Tests for ResourceTuner operator."""
    
    @pytest.fixture
    def tuner(self, k8s_client: MockK8sClient) -> ResourceTuner:
        """Create a ResourceTuner instance."""
        return ResourceTuner(k8s_client)
    
    def test_tuner_name(self, tuner: ResourceTuner):
        """Test operator name."""
        assert tuner.name == "ResourceTuner"
    
    @pytest.mark.asyncio
    async def test_update_resources(
        self,
        tuner: ResourceTuner,
        k8s_client: MockK8sClient,
    ):
        """Test updating container resources."""
        result = await tuner.update_resources(
            namespace="default",
            deployment_name="api-server",
            container_name="api",
            cpu_request="200m",
            cpu_limit="500m",
            memory_request="256Mi",
            memory_limit="512Mi",
        )
        
        assert result.success
        assert result.changes  # Should have changes recorded
    
    @pytest.mark.asyncio
    async def test_update_resources_dry_run(
        self,
        tuner: ResourceTuner,
        k8s_client: MockK8sClient,
    ):
        """Test dry-run resource update."""
        result = await tuner.update_resources(
            namespace="default",
            deployment_name="api-server",
            container_name="api",
            cpu_request="200m",
            dry_run=True,
        )
        
        assert result.success
    
    @pytest.mark.asyncio
    async def test_get_resource_recommendations(
        self,
        tuner: ResourceTuner,
        k8s_client: MockK8sClient,
    ):
        """Test getting resource recommendations."""
        recommendations = await tuner.get_recommendations(
            namespace="default",
            deployment_name="api-server",
        )
        
        assert isinstance(recommendations, list)
    
    @pytest.mark.asyncio
    async def test_apply_recommendation(
        self,
        tuner: ResourceTuner,
        k8s_client: MockK8sClient,
    ):
        """Test applying a recommendation."""
        recommendation = ResourceRecommendation(
            container_name="api",
            current_cpu_request="100m",
            current_cpu_limit="200m",
            current_memory_request="128Mi",
            current_memory_limit="256Mi",
            recommended_cpu_request="150m",
            recommended_cpu_limit="300m",
            recommended_memory_request="192Mi",
            recommended_memory_limit="384Mi",
            reason="Based on usage patterns",
            confidence=0.85,
        )
        
        result = await tuner.apply_recommendation(
            namespace="default",
            deployment_name="api-server",
            recommendation=recommendation,
        )
        
        assert result.success


# ============================================================================
# DrainManager Tests
# ============================================================================

class TestDrainManager:
    """Tests for DrainManager operator."""
    
    @pytest.fixture
    def drain_manager(self, k8s_client: MockK8sClient) -> DrainManager:
        """Create a DrainManager instance."""
        config = DrainConfig(
            grace_period_seconds=10,
            timeout_seconds=60,
            force=False,
            delete_emptydir_data=False,
            ignore_daemonsets=True,
        )
        return DrainManager(k8s_client, config)
    
    def test_manager_name(self, drain_manager: DrainManager):
        """Test operator name."""
        assert drain_manager.name == "DrainManager"
    
    @pytest.mark.asyncio
    async def test_drain_node(
        self,
        drain_manager: DrainManager,
        k8s_client: MockK8sClient,
    ):
        """Test draining a node."""
        result = await drain_manager.drain_node(
            node_name="worker-1",
        )
        
        assert result.success
        assert result.drain_status == DrainStatus.COMPLETED
        assert ("cordon_node", "worker-1") in k8s_client.call_log
    
    @pytest.mark.asyncio
    async def test_drain_node_dry_run(
        self,
        drain_manager: DrainManager,
        k8s_client: MockK8sClient,
    ):
        """Test dry-run drain."""
        result = await drain_manager.drain_node(
            node_name="worker-1",
            dry_run=True,
        )
        
        assert result.success
        # Should not have called cordon_node
        assert not any(
            call[0] == "cordon_node"
            for call in k8s_client.call_log
        )
    
    @pytest.mark.asyncio
    async def test_uncordon_node(
        self,
        drain_manager: DrainManager,
        k8s_client: MockK8sClient,
    ):
        """Test uncordoning a node."""
        result = await drain_manager.uncordon_node(
            node_name="worker-1",
        )
        
        assert result.success
        assert ("uncordon_node", "worker-1") in k8s_client.call_log
    
    @pytest.mark.asyncio
    async def test_cordon_node(
        self,
        drain_manager: DrainManager,
        k8s_client: MockK8sClient,
    ):
        """Test cordoning a node without draining."""
        result = await drain_manager.cordon_node(
            node_name="worker-1",
        )
        
        assert result.success
    
    @pytest.mark.asyncio
    async def test_get_node_status(
        self,
        drain_manager: DrainManager,
        k8s_client: MockK8sClient,
    ):
        """Test getting node drain status."""
        status = await drain_manager.get_node_status(
            node_name="worker-1",
        )
        
        assert "node_name" in status
        assert "is_schedulable" in status


# ============================================================================
# DeploymentRollback Tests
# ============================================================================

class TestDeploymentRollback:
    """Tests for DeploymentRollback operator."""
    
    @pytest.fixture
    def rollbacker(self, k8s_client: MockK8sClient) -> DeploymentRollback:
        """Create a DeploymentRollback instance."""
        return DeploymentRollback(k8s_client)
    
    def test_rollbacker_name(self, rollbacker: DeploymentRollback):
        """Test operator name."""
        assert rollbacker.name == "DeploymentRollback"
    
    @pytest.mark.asyncio
    async def test_rollback_to_revision(
        self,
        rollbacker: DeploymentRollback,
        k8s_client: MockK8sClient,
    ):
        """Test rollback to specific revision."""
        result = await rollbacker.rollback(
            namespace="default",
            deployment_name="api-server",
            revision=2,
        )
        
        assert result.success
        assert ("rollback_deployment", "default", "api-server", 2) in k8s_client.call_log
    
    @pytest.mark.asyncio
    async def test_rollback_to_previous(
        self,
        rollbacker: DeploymentRollback,
        k8s_client: MockK8sClient,
    ):
        """Test rollback to previous revision."""
        result = await rollbacker.rollback_to_previous(
            namespace="default",
            deployment_name="api-server",
        )
        
        assert result.success
    
    @pytest.mark.asyncio
    async def test_rollback_dry_run(
        self,
        rollbacker: DeploymentRollback,
        k8s_client: MockK8sClient,
    ):
        """Test dry-run rollback."""
        result = await rollbacker.rollback(
            namespace="default",
            deployment_name="api-server",
            revision=1,
            dry_run=True,
        )
        
        assert result.success
        # Should not have called rollback_deployment
        assert not any(
            call[0] == "rollback_deployment"
            for call in k8s_client.call_log
        )
    
    @pytest.mark.asyncio
    async def test_get_revisions(
        self,
        rollbacker: DeploymentRollback,
        k8s_client: MockK8sClient,
    ):
        """Test getting deployment revisions."""
        revisions = await rollbacker.get_revisions(
            namespace="default",
            deployment_name="api-server",
        )
        
        assert len(revisions) > 0
        assert all(isinstance(r, RevisionInfo) for r in revisions)
    
    @pytest.mark.asyncio
    async def test_get_current_revision(
        self,
        rollbacker: DeploymentRollback,
        k8s_client: MockK8sClient,
    ):
        """Test getting current revision."""
        revision = await rollbacker.get_current_revision(
            namespace="default",
            deployment_name="api-server",
        )
        
        assert revision is not None
    
    @pytest.mark.asyncio
    async def test_find_last_good_revision(
        self,
        rollbacker: DeploymentRollback,
        k8s_client: MockK8sClient,
    ):
        """Test finding last known good revision."""
        revision = await rollbacker.find_last_good_revision(
            namespace="default",
            deployment_name="api-server",
        )
        
        # Should find some revision
        assert revision is not None or revision == 0


# ============================================================================
# OperatorResult Tests
# ============================================================================

class TestOperatorResult:
    """Tests for OperatorResult model."""
    
    def test_result_creation(self):
        """Test creating an operator result."""
        result = OperatorResult(
            operation="restart_pod",
            resource_type="pod",
            resource_name="api-server-xyz",
            namespace="default",
        )
        
        assert result.operation == "restart_pod"
        assert result.status == OperatorStatus.PENDING
        assert not result.success
    
    def test_result_add_change(self):
        """Test adding a change record."""
        result = OperatorResult(
            operation="scale_deployment",
            resource_type="deployment",
            resource_name="api-server",
            namespace="default",
        )
        
        result.add_change(
            field="replicas",
            old_value=3,
            new_value=5,
            description="Scaled up",
        )
        
        assert len(result.changes) == 1
        assert result.changes[0]["field"] == "replicas"
        assert result.changes[0]["old_value"] == 3
        assert result.changes[0]["new_value"] == 5
    
    def test_result_complete_success(self):
        """Test completing with success."""
        result = OperatorResult(
            operation="restart_pod",
            resource_type="pod",
            resource_name="api-server-xyz",
            namespace="default",
        )
        
        result.complete(
            success=True,
            message="Pod restarted",
            result_data={"new_pod": "api-server-abc"},
        )
        
        assert result.success
        assert result.status == OperatorStatus.COMPLETED
        assert result.message == "Pod restarted"
        assert result.completed_at is not None
    
    def test_result_complete_failure(self):
        """Test completing with failure."""
        result = OperatorResult(
            operation="drain_node",
            resource_type="node",
            resource_name="worker-1",
        )
        
        result.complete(success=False, message="Drain timeout")
        
        assert not result.success
        assert result.status == OperatorStatus.FAILED
    
    def test_result_fail(self):
        """Test marking as failed."""
        result = OperatorResult(
            operation="scale_deployment",
            resource_type="deployment",
            resource_name="api-server",
            namespace="default",
        )
        
        result.fail("Connection refused", "ConnectionError")
        
        assert not result.success
        assert result.status == OperatorStatus.FAILED
        assert result.error == "Connection refused"
        assert result.error_type == "ConnectionError"
    
    def test_result_duration(self):
        """Test duration calculation."""
        result = OperatorResult(
            operation="restart_pod",
            resource_type="pod",
            resource_name="api-server-xyz",
            namespace="default",
        )
        result.started_at = datetime.utcnow() - timedelta(seconds=30)
        result.completed_at = datetime.utcnow()
        
        assert result.duration_seconds is not None
        assert 29 <= result.duration_seconds <= 31
    
    def test_result_to_summary(self):
        """Test summary generation."""
        result = OperatorResult(
            operation="restart_pod",
            resource_type="pod",
            resource_name="api-server-xyz",
            namespace="default",
        )
        result.complete(success=True, message="Done")
        
        summary = result.to_summary()
        
        assert "✅" in summary
        assert "restart_pod" in summary
        assert "pod" in summary


# ============================================================================
# OperatorConfig Tests
# ============================================================================

class TestOperatorConfig:
    """Tests for OperatorConfig model."""
    
    def test_default_config(self):
        """Test default configuration."""
        config = OperatorConfig()
        
        assert config.operation_timeout_seconds == 300
        assert config.max_retries == 3
        assert config.dry_run is False
        assert config.enable_metrics is True
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = OperatorConfig(
            operation_timeout_seconds=600,
            max_retries=5,
            dry_run=True,
            cluster_name="production",
        )
        
        assert config.operation_timeout_seconds == 600
        assert config.max_retries == 5
        assert config.dry_run is True
        assert config.cluster_name == "production"


# ============================================================================
# Integration Tests
# ============================================================================

class TestOperatorIntegration:
    """Integration tests for operators working together."""
    
    @pytest.mark.asyncio
    async def test_restart_and_scale(self, k8s_client: MockK8sClient):
        """Test restart followed by scale operation."""
        restarter = PodRestarter(k8s_client)
        scaler = ScaleManager(k8s_client)
        
        # First restart
        restart_result = await restarter.restart_pod(
            namespace="default",
            pod_name="api-server-xyz",
            wait_for_ready=False,
        )
        
        assert restart_result.success
        
        # Then scale
        scale_result = await scaler.scale_deployment(
            namespace="default",
            deployment_name="api-server",
            replicas=5,
        )
        
        assert scale_result.success
    
    @pytest.mark.asyncio
    async def test_drain_and_rollback(self, k8s_client: MockK8sClient):
        """Test drain followed by rollback operation."""
        drain_config = DrainConfig(grace_period_seconds=5)
        drain_manager = DrainManager(k8s_client, drain_config)
        rollbacker = DeploymentRollback(k8s_client)
        
        # First drain
        drain_result = await drain_manager.drain_node(
            node_name="worker-1",
        )
        
        assert drain_result.success
        
        # Then rollback a deployment
        rollback_result = await rollbacker.rollback(
            namespace="default",
            deployment_name="api-server",
            revision=1,
        )
        
        assert rollback_result.success
    
    @pytest.mark.asyncio
    async def test_all_operators_health_check(self, k8s_client: MockK8sClient):
        """Test health checks for all operators."""
        operators = [
            PodRestarter(k8s_client),
            ScaleManager(k8s_client),
            ResourceTuner(k8s_client),
            DrainManager(k8s_client),
            DeploymentRollback(k8s_client),
        ]
        
        for op in operators:
            healthy = await op.health_check()
            assert healthy, f"{op.name} health check failed"
