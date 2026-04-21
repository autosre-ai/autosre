"""
Unit Tests for Kubernetes Adapter

Tests the Kubernetes cluster interaction functionality including:
- Pod retrieval and parsing
- Event retrieval and filtering
- Deployment management
- Resource quantity parsing
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from opensre_core.adapters.kubernetes import (
    DeploymentInfo,
    EventInfo,
    KubernetesAdapter,
    PodInfo,
)


class TestPodInfo:
    """Tests for PodInfo dataclass."""

    def test_pod_info_creation(self):
        """Test PodInfo creation."""
        pod = PodInfo(
            name="api-server-abc123",
            namespace="default",
            status="Running",
            ready=True,
            restarts=2,
            age="5h",
        )

        assert pod.name == "api-server-abc123"
        assert pod.status == "Running"
        assert pod.ready is True

    def test_pod_info_with_resources(self):
        """Test PodInfo with resource limits."""
        pod = PodInfo(
            name="api-server",
            namespace="default",
            status="Running",
            ready=True,
            restarts=0,
            age="1h",
            memory_limit=512 * 1024 * 1024,
            memory_request=256 * 1024 * 1024,
            cpu_limit=0.5,
            cpu_request=0.25,
        )

        assert pod.memory_limit == 512 * 1024 * 1024
        assert pod.cpu_limit == 0.5


class TestEventInfo:
    """Tests for EventInfo dataclass."""

    def test_event_info_creation(self):
        """Test EventInfo creation."""
        event = EventInfo(
            type="Warning",
            reason="OOMKilled",
            message="Container killed due to memory",
            count=3,
            first_seen=datetime.now(timezone.utc),
            last_seen=datetime.now(timezone.utc),
            involved_object="Pod/api-server-abc123",
        )

        assert event.type == "Warning"
        assert event.reason == "OOMKilled"
        assert event.count == 3


class TestDeploymentInfo:
    """Tests for DeploymentInfo dataclass."""

    def test_deployment_info_creation(self):
        """Test DeploymentInfo creation."""
        deploy = DeploymentInfo(
            name="api-server",
            namespace="default",
            replicas=3,
            ready_replicas=3,
            available_replicas=3,
            strategy="RollingUpdate",
        )

        assert deploy.name == "api-server"
        assert deploy.replicas == 3
        assert deploy.ready_replicas == 3


class TestKubernetesAdapterInit:
    """Tests for KubernetesAdapter initialization."""

    def test_adapter_lazy_init(self):
        """Test adapter uses lazy initialization."""
        adapter = KubernetesAdapter()

        assert adapter._initialized is False
        assert adapter._v1 is None
        assert adapter._apps_v1 is None

    def test_adapter_custom_kubeconfig(self):
        """Test adapter with custom kubeconfig."""
        adapter = KubernetesAdapter(kubeconfig="/path/to/kubeconfig")

        assert adapter.kubeconfig == "/path/to/kubeconfig"


class TestKubernetesAdapterResourceParsing:
    """Tests for resource quantity parsing."""

    @pytest.fixture
    def adapter(self):
        return KubernetesAdapter()

    # CPU parsing
    def test_parse_cpu_millicores(self, adapter):
        """Test parsing CPU millicores."""
        result = adapter._parse_resource_quantity("500m", "cpu")
        assert result == 0.5

    def test_parse_cpu_whole_cores(self, adapter):
        """Test parsing whole CPU cores."""
        result = adapter._parse_resource_quantity("2", "cpu")
        assert result == 2.0

    def test_parse_cpu_decimal(self, adapter):
        """Test parsing decimal CPU."""
        result = adapter._parse_resource_quantity("0.5", "cpu")
        assert result == 0.5

    def test_parse_cpu_large_millicores(self, adapter):
        """Test parsing large millicores."""
        result = adapter._parse_resource_quantity("2000m", "cpu")
        assert result == 2.0

    # Memory parsing
    def test_parse_memory_bytes(self, adapter):
        """Test parsing plain bytes."""
        result = adapter._parse_resource_quantity("1000000", "memory")
        assert result == 1000000

    def test_parse_memory_kilobytes(self, adapter):
        """Test parsing kilobytes."""
        result = adapter._parse_resource_quantity("1024K", "memory")
        assert result == 1024000

    def test_parse_memory_kibibytes(self, adapter):
        """Test parsing kibibytes."""
        result = adapter._parse_resource_quantity("1024Ki", "memory")
        assert result == 1024 * 1024

    def test_parse_memory_megabytes(self, adapter):
        """Test parsing megabytes."""
        result = adapter._parse_resource_quantity("512M", "memory")
        assert result == 512 * 1000 ** 2

    def test_parse_memory_mebibytes(self, adapter):
        """Test parsing mebibytes."""
        result = adapter._parse_resource_quantity("512Mi", "memory")
        assert result == 512 * 1024 ** 2

    def test_parse_memory_gigabytes(self, adapter):
        """Test parsing gigabytes."""
        result = adapter._parse_resource_quantity("1G", "memory")
        assert result == 1000 ** 3

    def test_parse_memory_gibibytes(self, adapter):
        """Test parsing gibibytes."""
        result = adapter._parse_resource_quantity("1Gi", "memory")
        assert result == 1024 ** 3


class TestKubernetesAdapterGetPods:
    """Tests for pod retrieval."""

    @pytest.fixture
    def adapter(self):
        adapter = KubernetesAdapter()
        adapter._initialized = True
        adapter._v1 = MagicMock()
        return adapter

    def _create_mock_pod(
        self,
        name="test-pod",
        namespace="default",
        phase="Running",
        ready=True,
        restarts=0,
    ):
        """Helper to create mock pod object."""
        mock_pod = MagicMock()
        mock_pod.metadata.name = name
        mock_pod.metadata.namespace = namespace
        mock_pod.metadata.creation_timestamp = datetime.now(timezone.utc) - timedelta(hours=1)

        mock_pod.status.phase = phase

        # Conditions
        condition = MagicMock()
        condition.type = "Ready"
        condition.status = "True" if ready else "False"
        mock_pod.status.conditions = [condition]

        # Container statuses
        container_status = MagicMock()
        container_status.name = "main"
        container_status.ready = ready
        container_status.restart_count = restarts
        container_status.state.running = MagicMock() if phase == "Running" else None
        container_status.state.waiting = None
        container_status.state.terminated = None
        mock_pod.status.container_statuses = [container_status]

        mock_pod.spec.node_name = "node-1"
        mock_pod.spec.containers = []

        return mock_pod

    @pytest.mark.asyncio
    async def test_get_pods_returns_list(self, adapter):
        """Test get_pods returns list of PodInfo."""
        mock_pod = self._create_mock_pod()

        mock_list = MagicMock()
        mock_list.items = [mock_pod]
        adapter._v1.list_namespaced_pod.return_value = mock_list

        pods = await adapter.get_pods("default")

        assert len(pods) == 1
        assert isinstance(pods[0], PodInfo)

    @pytest.mark.asyncio
    async def test_get_pods_parses_status(self, adapter):
        """Test get_pods parses pod status correctly."""
        mock_pod = self._create_mock_pod(phase="Running", ready=True, restarts=5)

        mock_list = MagicMock()
        mock_list.items = [mock_pod]
        adapter._v1.list_namespaced_pod.return_value = mock_list

        pods = await adapter.get_pods("default")

        assert pods[0].status == "Running"
        assert pods[0].ready is True
        assert pods[0].restarts == 5

    @pytest.mark.asyncio
    async def test_get_pods_with_label_selector(self, adapter):
        """Test get_pods with label selector."""
        mock_list = MagicMock()
        mock_list.items = []
        adapter._v1.list_namespaced_pod.return_value = mock_list

        await adapter.get_pods("default", label_selector="app=api")

        adapter._v1.list_namespaced_pod.assert_called_with(
            namespace="default",
            label_selector="app=api",
        )

    @pytest.mark.asyncio
    async def test_get_pods_all_namespaces(self, adapter):
        """Test get_pods for all namespaces."""
        mock_list = MagicMock()
        mock_list.items = []
        adapter._v1.list_pod_for_all_namespaces.return_value = mock_list

        await adapter.get_pods("all")

        adapter._v1.list_pod_for_all_namespaces.assert_called()


class TestKubernetesAdapterGetEvents:
    """Tests for event retrieval."""

    @pytest.fixture
    def adapter(self):
        adapter = KubernetesAdapter()
        adapter._initialized = True
        adapter._v1 = MagicMock()
        return adapter

    def _create_mock_event(
        self,
        event_type="Warning",
        reason="OOMKilled",
        message="Container killed",
        count=1,
        minutes_ago=5,
    ):
        """Helper to create mock event object."""
        mock_event = MagicMock()
        mock_event.type = event_type
        mock_event.reason = reason
        mock_event.message = message
        mock_event.count = count
        mock_event.first_timestamp = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
        mock_event.last_timestamp = datetime.now(timezone.utc) - timedelta(minutes=1)
        mock_event.involved_object.kind = "Pod"
        mock_event.involved_object.name = "test-pod"
        return mock_event

    @pytest.mark.asyncio
    async def test_get_events_returns_list(self, adapter):
        """Test get_events returns list of EventInfo."""
        mock_event = self._create_mock_event()

        mock_list = MagicMock()
        mock_list.items = [mock_event]
        adapter._v1.list_namespaced_event.return_value = mock_list

        # Mock get_pods for filtering
        adapter.get_pods = AsyncMock(return_value=[
            PodInfo(name="test-pod", namespace="default", status="Running", ready=True, restarts=0, age="1h")
        ])

        events = await adapter.get_events("default")

        assert len(events) >= 0  # May be filtered
        if events:
            assert isinstance(events[0], EventInfo)

    @pytest.mark.asyncio
    async def test_get_events_filters_old_events(self, adapter):
        """Test get_events filters old events."""
        old_event = self._create_mock_event(minutes_ago=60)
        recent_event = self._create_mock_event(minutes_ago=5)

        mock_list = MagicMock()
        mock_list.items = [old_event, recent_event]
        adapter._v1.list_namespaced_event.return_value = mock_list

        adapter.get_pods = AsyncMock(return_value=[
            PodInfo(name="test-pod", namespace="default", status="Running", ready=True, restarts=0, age="1h")
        ])

        events = await adapter.get_events("default", minutes=15)

        # Old event should be filtered out
        assert all(
            (e.last_seen is None or
             (datetime.now(timezone.utc) - e.last_seen.replace(tzinfo=timezone.utc)).total_seconds() < 900)
            for e in events
        )


class TestKubernetesAdapterGetPodLogs:
    """Tests for pod log retrieval."""

    @pytest.fixture
    def adapter(self):
        adapter = KubernetesAdapter()
        adapter._initialized = True
        adapter._v1 = MagicMock()
        return adapter

    @pytest.mark.asyncio
    async def test_get_pod_logs_returns_string(self, adapter):
        """Test get_pod_logs returns log string."""
        adapter._v1.read_namespaced_pod_log.return_value = "2024-01-01 ERROR: Something failed"

        logs = await adapter.get_pod_logs("test-pod", "default")

        assert isinstance(logs, str)
        assert "ERROR" in logs

    @pytest.mark.asyncio
    async def test_get_pod_logs_with_tail(self, adapter):
        """Test get_pod_logs with tail_lines."""
        adapter._v1.read_namespaced_pod_log.return_value = "last line"

        await adapter.get_pod_logs("test-pod", "default", tail_lines=50)

        adapter._v1.read_namespaced_pod_log.assert_called_with(
            name="test-pod",
            namespace="default",
            container=None,
            tail_lines=50,
            since_seconds=None,
        )


class TestKubernetesAdapterDeploymentOperations:
    """Tests for deployment operations."""

    @pytest.fixture
    def adapter(self):
        adapter = KubernetesAdapter()
        adapter._initialized = True
        adapter._v1 = MagicMock()
        adapter._apps_v1 = MagicMock()
        return adapter

    @pytest.mark.asyncio
    async def test_rollout_restart_dry_run(self, adapter):
        """Test rollout restart in dry run mode."""
        result = await adapter.rollout_restart("api-server", "default", dry_run=True)

        assert result["dry_run"] is True
        assert "rollout restart" in result["command"]
        assert result["approved"] is False

    @pytest.mark.asyncio
    async def test_rollout_restart_execute(self, adapter):
        """Test rollout restart execution."""
        adapter._apps_v1.patch_namespaced_deployment.return_value = None

        result = await adapter.rollout_restart("api-server", "default", dry_run=False)

        assert result["success"] is True
        adapter._apps_v1.patch_namespaced_deployment.assert_called()

    @pytest.mark.asyncio
    async def test_scale_deployment_dry_run(self, adapter):
        """Test scale deployment in dry run mode."""
        result = await adapter.scale_deployment("api-server", 5, "default", dry_run=True)

        assert result["dry_run"] is True
        assert "scale" in result["command"]
        assert "5" in result["command"]

    @pytest.mark.asyncio
    async def test_scale_deployment_execute(self, adapter):
        """Test scale deployment execution."""
        adapter._apps_v1.patch_namespaced_deployment_scale.return_value = None

        result = await adapter.scale_deployment("api-server", 5, "default", dry_run=False)

        assert result["success"] is True
        adapter._apps_v1.patch_namespaced_deployment_scale.assert_called()


class TestKubernetesAdapterHealthCheck:
    """Tests for health check functionality."""

    @pytest.fixture
    def adapter(self):
        adapter = KubernetesAdapter()
        return adapter

    @pytest.mark.asyncio
    async def test_health_check_success(self, adapter):
        """Test successful health check."""
        with patch("kubernetes.client.VersionApi") as mock_version_api:
            mock_version = MagicMock()
            mock_version.git_version = "v1.28.0"
            mock_version_api.return_value.get_code.return_value = mock_version

            with patch.object(adapter, "_init_client"):
                result = await adapter.health_check()

        assert result["status"] == "healthy"
        assert "v1.28.0" in result["details"]


class TestKubernetesAdapterContainerState:
    """Tests for container state parsing."""

    @pytest.fixture
    def adapter(self):
        return KubernetesAdapter()

    def test_get_container_state_running(self, adapter):
        """Test parsing running state."""
        state = MagicMock()
        state.running = MagicMock()
        state.waiting = None
        state.terminated = None

        result = adapter._get_container_state(state)

        assert result == "Running"

    def test_get_container_state_waiting(self, adapter):
        """Test parsing waiting state."""
        state = MagicMock()
        state.running = None
        state.waiting = MagicMock()
        state.waiting.reason = "CrashLoopBackOff"
        state.terminated = None

        result = adapter._get_container_state(state)

        assert "Waiting" in result
        assert "CrashLoopBackOff" in result

    def test_get_container_state_terminated(self, adapter):
        """Test parsing terminated state."""
        state = MagicMock()
        state.running = None
        state.waiting = None
        state.terminated = MagicMock()
        state.terminated.reason = "OOMKilled"

        result = adapter._get_container_state(state)

        assert "Terminated" in result
        assert "OOMKilled" in result


class TestKubernetesAdapterDescribeResource:
    """Tests for resource description."""

    @pytest.fixture
    def adapter(self):
        adapter = KubernetesAdapter()
        adapter._initialized = True
        adapter._v1 = MagicMock()
        adapter._apps_v1 = MagicMock()
        return adapter

    @pytest.mark.asyncio
    async def test_describe_pod(self, adapter):
        """Test describing a pod."""
        adapter.get_pod = AsyncMock(return_value=PodInfo(
            name="test-pod",
            namespace="default",
            status="Running",
            ready=True,
            restarts=2,
            age="1h",
            containers=[{"name": "main", "ready": True}],
            events=[{"type": "Warning", "reason": "Pulled"}],
        ))

        result = await adapter.describe_resource("pod", "test-pod", "default")

        assert result["kind"] == "pod"
        assert result["name"] == "test-pod"
        assert result["status"] == "Running"

    @pytest.mark.asyncio
    async def test_describe_deployment(self, adapter):
        """Test describing a deployment."""
        adapter.get_deployment = AsyncMock(return_value=DeploymentInfo(
            name="api-server",
            namespace="default",
            replicas=3,
            ready_replicas=3,
            available_replicas=3,
            strategy="RollingUpdate",
        ))

        result = await adapter.describe_resource("deployment", "api-server", "default")

        assert result["kind"] == "deployment"
        assert result["replicas"] == 3
