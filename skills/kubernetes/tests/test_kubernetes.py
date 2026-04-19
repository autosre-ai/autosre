"""
Tests for Kubernetes Skill
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from skills.kubernetes import KubernetesSkill


@pytest.fixture
def skill():
    """Create Kubernetes skill instance."""
    with patch('opensre.skills.kubernetes.actions.K8S_AVAILABLE', True):
        return KubernetesSkill({
            "namespace": "default",
        })


@pytest.fixture
def mock_pod():
    """Create mock pod object."""
    pod = MagicMock()
    pod.metadata.name = "test-pod"
    pod.metadata.namespace = "default"
    pod.metadata.creation_timestamp = datetime.now(timezone.utc) - timedelta(hours=1)
    pod.metadata.labels = {"app": "test"}

    pod.status.phase = "Running"
    pod.status.conditions = [MagicMock(type="Ready", status="True")]

    container_status = MagicMock()
    container_status.name = "main"
    container_status.ready = True
    container_status.restart_count = 0
    container_status.state.running = True
    container_status.state.waiting = None
    container_status.state.terminated = None
    pod.status.container_statuses = [container_status]

    pod.spec.node_name = "node-1"
    pod.spec.containers = []
    pod.spec.volumes = []

    return pod


@pytest.fixture
def mock_deployment():
    """Create mock deployment object."""
    deploy = MagicMock()
    deploy.metadata.name = "test-deploy"
    deploy.metadata.namespace = "default"
    deploy.metadata.creation_timestamp = datetime.now(timezone.utc) - timedelta(days=7)

    deploy.spec.replicas = 3
    deploy.spec.strategy.type = "RollingUpdate"

    deploy.status.replicas = 3
    deploy.status.ready_replicas = 3
    deploy.status.available_replicas = 3
    deploy.status.conditions = []

    return deploy


class TestKubernetesSkillInit:
    """Test skill initialization."""

    def test_default_config(self):
        """Test skill with default config."""
        with patch('opensre.skills.kubernetes.actions.K8S_AVAILABLE', True):
            skill = KubernetesSkill()
            assert skill.default_namespace == "default"
            assert skill.kubeconfig is None

    def test_custom_config(self):
        """Test skill with custom config."""
        with patch('opensre.skills.kubernetes.actions.K8S_AVAILABLE', True):
            skill = KubernetesSkill({
                "kubeconfig": "/path/to/config",
                "context": "prod",
                "namespace": "production",
            })
            assert skill.kubeconfig == "/path/to/config"
            assert skill.context == "prod"
            assert skill.default_namespace == "production"


class TestHealthCheck:
    """Test health check action."""

    @pytest.mark.asyncio
    async def test_health_check_success(self, skill):
        """Test successful health check."""
        with patch.object(skill, '_init_client'):
            with patch('kubernetes.client.VersionApi') as mock_version:
                mock_version.return_value.get_code.return_value = MagicMock(
                    git_version="v1.28.0"
                )

                result = await skill.health_check()

                assert result.success
                assert result.data["status"] == "healthy"
                assert "v1.28.0" in result.data["version"]

    @pytest.mark.asyncio
    async def test_health_check_not_available(self):
        """Test health check when k8s not installed."""
        with patch('opensre.skills.kubernetes.actions.K8S_AVAILABLE', False):
            skill = KubernetesSkill()
            result = await skill.health_check()

            assert not result.success
            assert "not installed" in result.error


class TestGetPods:
    """Test get_pods action."""

    @pytest.mark.asyncio
    async def test_get_pods_success(self, skill, mock_pod):
        """Test getting pods."""
        mock_list = MagicMock()
        mock_list.items = [mock_pod]

        with patch.object(skill, 'v1', new_callable=PropertyMock) as mock_v1:
            mock_v1.return_value.list_namespaced_pod.return_value = mock_list

            result = await skill.get_pods(namespace="default")

            assert result.success
            assert len(result.data) == 1
            assert result.data[0].name == "test-pod"
            assert result.data[0].status == "Running"

    @pytest.mark.asyncio
    async def test_get_pods_all_namespaces(self, skill, mock_pod):
        """Test getting pods from all namespaces."""
        mock_list = MagicMock()
        mock_list.items = [mock_pod]

        with patch.object(skill, 'v1', new_callable=PropertyMock) as mock_v1:
            mock_v1.return_value.list_pod_for_all_namespaces.return_value = mock_list

            result = await skill.get_pods(namespace="all")

            assert result.success
            mock_v1.return_value.list_pod_for_all_namespaces.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_pods_with_labels(self, skill, mock_pod):
        """Test getting pods with label selector."""
        mock_list = MagicMock()
        mock_list.items = [mock_pod]

        with patch.object(skill, 'v1', new_callable=PropertyMock) as mock_v1:
            mock_v1.return_value.list_namespaced_pod.return_value = mock_list

            result = await skill.get_pods(labels="app=test")

            assert result.success
            mock_v1.return_value.list_namespaced_pod.assert_called_with(
                namespace="default",
                label_selector="app=test",
            )


class TestGetPodLogs:
    """Test get_pod_logs action."""

    @pytest.mark.asyncio
    async def test_get_logs_success(self, skill):
        """Test getting pod logs."""
        with patch.object(skill, 'v1', new_callable=PropertyMock) as mock_v1:
            mock_v1.return_value.read_namespaced_pod_log.return_value = "log line 1\nlog line 2"

            result = await skill.get_pod_logs(pod="test-pod", lines=50)

            assert result.success
            assert "log line 1" in result.data
            mock_v1.return_value.read_namespaced_pod_log.assert_called_with(
                name="test-pod",
                namespace="default",
                container=None,
                tail_lines=50,
                since_seconds=None,
            )

    @pytest.mark.asyncio
    async def test_get_logs_not_found(self, skill):
        """Test getting logs for non-existent pod."""
        from kubernetes.client.exceptions import ApiException

        with patch.object(skill, 'v1', new_callable=PropertyMock) as mock_v1:
            mock_v1.return_value.read_namespaced_pod_log.side_effect = ApiException(
                status=404, reason="Not Found"
            )

            result = await skill.get_pod_logs(pod="nonexistent")

            assert not result.success
            assert "not found" in result.error.lower()


class TestGetDeployments:
    """Test get_deployments action."""

    @pytest.mark.asyncio
    async def test_get_deployments_success(self, skill, mock_deployment):
        """Test getting deployments."""
        mock_list = MagicMock()
        mock_list.items = [mock_deployment]

        with patch.object(skill, 'apps_v1', new_callable=PropertyMock) as mock_apps:
            mock_apps.return_value.list_namespaced_deployment.return_value = mock_list

            result = await skill.get_deployments()

            assert result.success
            assert len(result.data) == 1
            assert result.data[0].name == "test-deploy"
            assert result.data[0].replicas == 3


class TestScaleDeployment:
    """Test scale_deployment action."""

    @pytest.mark.asyncio
    async def test_scale_success(self, skill, mock_deployment):
        """Test scaling deployment."""
        with patch.object(skill, 'apps_v1', new_callable=PropertyMock) as mock_apps:
            mock_apps.return_value.read_namespaced_deployment.return_value = mock_deployment

            result = await skill.scale_deployment(name="test-deploy", replicas=5)

            assert result.success
            assert result.data.previous_replicas == 3
            assert result.data.new_replicas == 5
            mock_apps.return_value.patch_namespaced_deployment_scale.assert_called_once()

    @pytest.mark.asyncio
    async def test_scale_not_found(self, skill):
        """Test scaling non-existent deployment."""
        from kubernetes.client.exceptions import ApiException

        with patch.object(skill, 'apps_v1', new_callable=PropertyMock) as mock_apps:
            mock_apps.return_value.read_namespaced_deployment.side_effect = ApiException(
                status=404, reason="Not Found"
            )

            result = await skill.scale_deployment(name="nonexistent", replicas=5)

            assert not result.success
            assert "not found" in result.error.lower()


class TestGetEvents:
    """Test get_events action."""

    @pytest.mark.asyncio
    async def test_get_events_success(self, skill):
        """Test getting events."""
        mock_event = MagicMock()
        mock_event.type = "Warning"
        mock_event.reason = "FailedScheduling"
        mock_event.message = "No nodes available"
        mock_event.count = 3
        mock_event.first_timestamp = datetime.now(timezone.utc) - timedelta(minutes=5)
        mock_event.last_timestamp = datetime.now(timezone.utc)
        mock_event.involved_object.kind = "Pod"
        mock_event.involved_object.name = "test-pod"

        mock_list = MagicMock()
        mock_list.items = [mock_event]

        with patch.object(skill, 'v1', new_callable=PropertyMock) as mock_v1:
            mock_v1.return_value.list_namespaced_event.return_value = mock_list

            result = await skill.get_events(minutes=10)

            assert result.success
            assert len(result.data) == 1
            assert result.data[0].type == "Warning"
            assert result.data[0].reason == "FailedScheduling"


class TestDescribePod:
    """Test describe_pod action."""

    @pytest.mark.asyncio
    async def test_describe_pod_success(self, skill, mock_pod):
        """Test describing pod."""
        mock_pod.status.conditions = [
            MagicMock(type="Ready", status="True", reason=None, message=None)
        ]

        with patch.object(skill, 'v1', new_callable=PropertyMock) as mock_v1:
            mock_v1.return_value.read_namespaced_pod.return_value = mock_pod

            # Mock get_events
            with patch.object(skill, 'get_events') as mock_events:
                from opensre.core.skills import ActionResult
                mock_events.return_value = ActionResult.ok([])

                result = await skill.describe_pod(pod="test-pod")

                assert result.success
                assert result.data.pod.name == "test-pod"
                assert isinstance(result.data.conditions, list)


class TestActionRegistration:
    """Test action registration."""

    def test_actions_registered(self, skill):
        """Test that all actions are registered."""
        actions = skill.get_actions()
        action_names = [a.name for a in actions]

        assert "get_pods" in action_names
        assert "get_pod_logs" in action_names
        assert "describe_pod" in action_names
        assert "get_deployments" in action_names
        assert "scale_deployment" in action_names
        assert "rollback_deployment" in action_names
        assert "get_events" in action_names
        assert "exec_command" in action_names

    def test_approval_required(self, skill):
        """Test that write actions require approval."""
        scale_action = skill.get_action("scale_deployment")
        rollback_action = skill.get_action("rollback_deployment")
        exec_action = skill.get_action("exec_command")

        assert scale_action.requires_approval
        assert rollback_action.requires_approval
        assert exec_action.requires_approval

        # Read actions should not require approval
        get_pods_action = skill.get_action("get_pods")
        assert not get_pods_action.requires_approval


class TestResourceParsing:
    """Test resource quantity parsing."""

    def test_parse_memory_mi(self, skill):
        """Test parsing memory in Mi."""
        assert skill._parse_memory("256Mi") == 256 * 1024 * 1024

    def test_parse_memory_gi(self, skill):
        """Test parsing memory in Gi."""
        assert skill._parse_memory("1Gi") == 1024 * 1024 * 1024

    def test_parse_cpu_millis(self, skill):
        """Test parsing CPU in millicores."""
        assert skill._parse_cpu("500m") == 0.5

    def test_parse_cpu_cores(self, skill):
        """Test parsing CPU in cores."""
        assert skill._parse_cpu("2") == 2.0
