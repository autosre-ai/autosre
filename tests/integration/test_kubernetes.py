"""Integration tests for Kubernetes client."""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from autosre.integrations.kubernetes import (
    ContainerState,
    ContainerStatus,
    Deployment,
    Event,
    EventType,
    KubernetesClient,
    Node,
    Pod,
    PodPhase,
)
from autosre.integrations.base import (
    HealthCheckResult,
    HealthStatus,
    IntegrationError,
)


@pytest.fixture
def k8s_resources():
    """Load K8s mock resources."""
    fixtures_path = Path(__file__).parent.parent / "fixtures" / "k8s_resources.json"
    with open(fixtures_path) as f:
        return json.load(f)


@pytest.fixture
def mock_client():
    """Create a mock Kubernetes client."""
    return KubernetesClient(server="https://kubernetes.test", token="test-token")


# ============================================================================
# Client Configuration Tests
# ============================================================================


class TestKubernetesClientConfig:
    """Tests for Kubernetes client configuration."""

    def test_in_cluster_raises_when_not_in_cluster(self):
        """Test in_cluster raises when not running in cluster."""
        with pytest.raises(IntegrationError, match="Not running"):
            KubernetesClient.in_cluster()

    def test_from_kubeconfig_raises_when_not_found(self, tmp_path):
        """Test from_kubeconfig raises when file not found."""
        with pytest.raises(FileNotFoundError):
            KubernetesClient.from_kubeconfig(str(tmp_path / "nonexistent"))

    def test_client_with_token(self):
        """Test client configuration with token."""
        client = KubernetesClient(
            server="https://k8s.test:6443",
            token="my-token",
        )
        
        assert client._token == "my-token"

    def test_client_with_cert(self):
        """Test client configuration with certificate."""
        client = KubernetesClient(
            server="https://k8s.test:6443",
            client_certificate="/path/to/cert",
            client_key="/path/to/key",
        )
        
        assert client._cert_path == "/path/to/cert"
        assert client._key_path == "/path/to/key"


# ============================================================================
# Pod Operations Tests
# ============================================================================


@pytest.mark.asyncio
class TestPodOperations:
    """Tests for Pod operations."""

    async def test_list_pods(self, mock_client, k8s_resources):
        """Test listing pods."""
        mock_response = {
            "items": [
                {
                    "metadata": {
                        "name": pod["name"],
                        "namespace": pod["namespace"],
                        "labels": pod["labels"],
                        "annotations": {},
                    },
                    "spec": {
                        "nodeName": pod["node"],
                    },
                    "status": {
                        "phase": pod["phase"],
                        "conditions": [],
                        "containerStatuses": [],
                    },
                }
                for pod in k8s_resources["pods"]
            ],
        }
        
        with patch.object(mock_client, "_request") as mock_request:
            mock_request.return_value = mock_response
            
            pods = await mock_client.list_pods("production")
            
            assert len(pods) == 3
            assert all(isinstance(p, Pod) for p in pods)
            assert pods[0].name == "payment-service-abc123"

    async def test_list_pods_with_label_selector(self, mock_client):
        """Test listing pods with label selector."""
        with patch.object(mock_client, "_request") as mock_request:
            mock_request.return_value = {"items": []}
            
            await mock_client.list_pods(
                "production",
                label_selector="app=payment-service",
            )
            
            call_args = mock_request.call_args
            assert call_args[1]["params"]["labelSelector"] == "app=payment-service"

    async def test_get_pod(self, mock_client, k8s_resources):
        """Test getting a specific pod."""
        pod_data = k8s_resources["pods"][0]
        mock_response = {
            "metadata": {
                "name": pod_data["name"],
                "namespace": pod_data["namespace"],
                "labels": pod_data["labels"],
                "annotations": {},
            },
            "spec": {"nodeName": pod_data["node"]},
            "status": {
                "phase": pod_data["phase"],
                "conditions": [{"type": "Ready", "status": "True"}],
                "containerStatuses": [],
            },
        }
        
        with patch.object(mock_client, "_request") as mock_request:
            mock_request.return_value = mock_response
            
            pod = await mock_client.get_pod("production", "payment-service-abc123")
            
            assert isinstance(pod, Pod)
            assert pod.name == "payment-service-abc123"
            assert pod.is_ready is True

    async def test_get_pod_logs(self, mock_client):
        """Test getting pod logs."""
        with patch.object(mock_client, "_request") as mock_request:
            mock_request.return_value = {"text": "Log line 1\nLog line 2\nLog line 3"}
            
            logs = await mock_client.get_pod_logs("production", "my-pod")
            
            assert "Log line 1" in logs
            assert "Log line 2" in logs

    async def test_get_pod_logs_with_container(self, mock_client):
        """Test getting logs for specific container."""
        with patch.object(mock_client, "_request") as mock_request:
            mock_request.return_value = {"text": "Container logs"}
            
            await mock_client.get_pod_logs(
                "production",
                "my-pod",
                container="sidecar",
            )
            
            call_args = mock_request.call_args
            assert call_args[1]["params"]["container"] == "sidecar"

    async def test_get_pod_logs_with_tail(self, mock_client):
        """Test getting pod logs with tail lines."""
        with patch.object(mock_client, "_request") as mock_request:
            mock_request.return_value = {"text": "Last 100 lines"}
            
            await mock_client.get_pod_logs(
                "production",
                "my-pod",
                tail_lines=100,
            )
            
            call_args = mock_request.call_args
            assert call_args[1]["params"]["tailLines"] == 100

    async def test_delete_pod(self, mock_client):
        """Test deleting a pod."""
        with patch.object(mock_client, "_request") as mock_request:
            mock_request.return_value = {}
            
            await mock_client.delete_pod("production", "my-pod")
            
            mock_request.assert_called_once()
            call_args = mock_request.call_args
            assert call_args[0][0] == "DELETE"


# ============================================================================
# Deployment Operations Tests
# ============================================================================


@pytest.mark.asyncio
class TestDeploymentOperations:
    """Tests for Deployment operations."""

    async def test_list_deployments(self, mock_client, k8s_resources):
        """Test listing deployments."""
        mock_response = {
            "items": [
                {
                    "metadata": {
                        "name": dep["name"],
                        "namespace": dep["namespace"],
                        "labels": dep["labels"],
                    },
                    "spec": {
                        "replicas": dep["replicas"],
                        "selector": {"matchLabels": dep["labels"]},
                        "strategy": {"type": "RollingUpdate"},
                    },
                    "status": {
                        "replicas": dep["replicas"],
                        "readyReplicas": dep["ready_replicas"],
                        "availableReplicas": dep["available_replicas"],
                        "updatedReplicas": dep["replicas"],
                        "conditions": [],
                    },
                }
                for dep in k8s_resources["deployments"]
            ],
        }
        
        with patch.object(mock_client, "_request") as mock_request:
            mock_request.return_value = mock_response
            
            deployments = await mock_client.list_deployments("production")
            
            assert len(deployments) == 2
            assert all(isinstance(d, Deployment) for d in deployments)

    async def test_get_deployment(self, mock_client, k8s_resources):
        """Test getting a specific deployment."""
        dep = k8s_resources["deployments"][0]
        mock_response = {
            "metadata": {
                "name": dep["name"],
                "namespace": dep["namespace"],
                "labels": dep["labels"],
            },
            "spec": {
                "replicas": dep["replicas"],
                "selector": {"matchLabels": dep["labels"]},
                "strategy": {"type": "RollingUpdate"},
            },
            "status": {
                "replicas": dep["replicas"],
                "readyReplicas": dep["ready_replicas"],
                "availableReplicas": dep["available_replicas"],
                "updatedReplicas": dep["replicas"],
                "conditions": [],
            },
        }
        
        with patch.object(mock_client, "_request") as mock_request:
            mock_request.return_value = mock_response
            
            deployment = await mock_client.get_deployment("production", "payment-service")
            
            assert deployment.name == "payment-service"
            assert deployment.replicas == 3
            assert deployment.ready_replicas == 2

    async def test_scale_deployment(self, mock_client):
        """Test scaling a deployment."""
        get_response = {
            "metadata": {"name": "test", "namespace": "default"},
            "spec": {"replicas": 2},
            "status": {
                "replicas": 2,
                "readyReplicas": 2,
                "availableReplicas": 2,
                "updatedReplicas": 2,
            },
        }
        put_response = {
            "metadata": {"name": "test", "namespace": "default"},
            "spec": {"replicas": 5},
            "status": {
                "replicas": 5,
                "readyReplicas": 2,
                "availableReplicas": 2,
                "updatedReplicas": 5,
            },
        }
        
        with patch.object(mock_client, "_request") as mock_request:
            mock_request.side_effect = [get_response, put_response]
            
            deployment = await mock_client.scale_deployment("default", "test", 5)
            
            assert deployment.replicas == 5

    async def test_restart_deployment(self, mock_client):
        """Test restarting a deployment."""
        response = {
            "metadata": {"name": "test", "namespace": "default"},
            "spec": {
                "replicas": 2,
                "template": {"metadata": {"annotations": {}}},
            },
            "status": {
                "replicas": 2,
                "readyReplicas": 2,
                "availableReplicas": 2,
                "updatedReplicas": 2,
            },
        }
        
        with patch.object(mock_client, "_request") as mock_request:
            mock_request.return_value = response
            
            deployment = await mock_client.restart_deployment("default", "test")
            
            # Verify PATCH was called
            call_args = mock_request.call_args
            assert call_args[0][0] == "PATCH"


# ============================================================================
# Events Operations Tests
# ============================================================================


@pytest.mark.asyncio
class TestEventOperations:
    """Tests for Event operations."""

    async def test_list_events(self, mock_client, k8s_resources):
        """Test listing events."""
        mock_response = {
            "items": [
                {
                    "metadata": {
                        "name": evt["name"],
                        "namespace": evt["namespace"],
                    },
                    "type": evt["type"],
                    "reason": evt["reason"],
                    "message": evt["message"],
                    "count": evt["count"],
                    "firstTimestamp": evt["first_timestamp"],
                    "lastTimestamp": evt["last_timestamp"],
                    "involvedObject": {
                        "kind": evt["involved_object_kind"],
                        "name": evt["involved_object_name"],
                        "namespace": evt["namespace"],
                    },
                    "source": {},
                }
                for evt in k8s_resources["events"]
            ],
        }
        
        with patch.object(mock_client, "_request") as mock_request:
            mock_request.return_value = mock_response
            
            events = await mock_client.list_events("production")
            
            assert len(events) == 3
            assert all(isinstance(e, Event) for e in events)
            # Should be sorted by last_timestamp
            assert events[0].reason in ["OOMKilled", "BackOff", "ScalingReplicaSet"]

    async def test_list_events_for_object(self, mock_client):
        """Test listing events for specific object."""
        with patch.object(mock_client, "_request") as mock_request:
            mock_request.return_value = {"items": []}
            
            await mock_client.list_events(
                "production",
                involved_object_name="my-pod",
                involved_object_kind="Pod",
            )
            
            call_args = mock_request.call_args
            field_selector = call_args[1]["params"]["fieldSelector"]
            assert "involvedObject.name=my-pod" in field_selector


# ============================================================================
# Node Operations Tests
# ============================================================================


@pytest.mark.asyncio
class TestNodeOperations:
    """Tests for Node operations."""

    async def test_list_nodes(self, mock_client, k8s_resources):
        """Test listing nodes."""
        mock_response = {
            "items": [
                {
                    "metadata": {
                        "name": node["name"],
                        "labels": node["labels"],
                        "annotations": {},
                    },
                    "spec": {"unschedulable": False},
                    "status": {
                        "conditions": [
                            {"type": "Ready", "status": "True" if node["ready"] else "False"}
                        ],
                        "allocatable": {
                            "cpu": node["cpu_capacity"],
                            "memory": node["memory_capacity"],
                        },
                        "capacity": {
                            "cpu": node["cpu_capacity"],
                            "memory": node["memory_capacity"],
                        },
                        "nodeInfo": {"kubeletVersion": "v1.28.0"},
                    },
                }
                for node in k8s_resources["nodes"]
            ],
        }
        
        with patch.object(mock_client, "_request") as mock_request:
            mock_request.return_value = mock_response
            
            nodes = await mock_client.list_nodes()
            
            assert len(nodes) == 2
            assert all(isinstance(n, Node) for n in nodes)
            assert all(n.is_ready for n in nodes)


# ============================================================================
# Resource Describe Tests
# ============================================================================


@pytest.mark.asyncio
class TestDescribeResource:
    """Tests for describe_resource."""

    async def test_describe_pod(self, mock_client):
        """Test describing a pod."""
        with patch.object(mock_client, "_request") as mock_request:
            mock_request.return_value = {
                "apiVersion": "v1",
                "kind": "Pod",
                "metadata": {"name": "test-pod"},
            }
            
            result = await mock_client.describe_resource("Pod", "default", "test-pod")
            
            assert result["kind"] == "Pod"

    async def test_describe_deployment(self, mock_client):
        """Test describing a deployment."""
        with patch.object(mock_client, "_request") as mock_request:
            mock_request.return_value = {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
            }
            
            result = await mock_client.describe_resource("Deployment", "default", "test")
            
            assert result["kind"] == "Deployment"

    async def test_describe_unknown_kind(self, mock_client):
        """Test describing unknown resource kind."""
        with pytest.raises(IntegrationError, match="Unknown resource kind"):
            await mock_client.describe_resource("UnknownKind", "default", "test")


# ============================================================================
# Health Check Tests
# ============================================================================


@pytest.mark.asyncio
class TestHealthCheck:
    """Tests for health check."""

    async def test_health_check_success(self, mock_client):
        """Test successful health check."""
        with patch.object(mock_client, "_request") as mock_request:
            mock_request.return_value = {}
            
            result = await mock_client.health_check()
            
            assert result.status == HealthStatus.HEALTHY

    async def test_health_check_failure(self, mock_client):
        """Test failed health check."""
        with patch.object(mock_client, "_request") as mock_request:
            mock_request.side_effect = Exception("Connection refused")
            
            result = await mock_client.health_check()
            
            assert result.status == HealthStatus.UNHEALTHY
            assert "Connection refused" in result.message


# ============================================================================
# Parser Tests
# ============================================================================


class TestParsers:
    """Tests for response parsers."""

    def test_parse_datetime(self, mock_client):
        """Test datetime parsing."""
        dt = mock_client._parse_datetime("2024-01-15T10:00:00Z")
        
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 15

    def test_parse_datetime_none(self, mock_client):
        """Test datetime parsing with None."""
        dt = mock_client._parse_datetime(None)
        
        assert dt is None

    def test_parse_container_status_running(self, mock_client):
        """Test parsing running container status."""
        data = {
            "name": "main",
            "state": {"running": {"startedAt": "2024-01-15T10:00:00Z"}},
            "ready": True,
            "restartCount": 0,
            "image": "nginx:latest",
            "started": True,
        }
        
        status = mock_client._parse_container_status(data)
        
        assert status.state == ContainerState.RUNNING
        assert status.ready is True

    def test_parse_container_status_waiting(self, mock_client):
        """Test parsing waiting container status."""
        data = {
            "name": "init",
            "state": {
                "waiting": {
                    "reason": "CrashLoopBackOff",
                    "message": "Back-off restarting",
                }
            },
            "ready": False,
            "restartCount": 5,
            "image": "init:latest",
        }
        
        status = mock_client._parse_container_status(data)
        
        assert status.state == ContainerState.WAITING
        assert status.state_reason == "CrashLoopBackOff"

    def test_parse_container_status_terminated(self, mock_client):
        """Test parsing terminated container status."""
        data = {
            "name": "job",
            "state": {
                "terminated": {
                    "reason": "Completed",
                    "exitCode": 0,
                }
            },
            "ready": False,
            "restartCount": 0,
            "image": "job:latest",
        }
        
        status = mock_client._parse_container_status(data)
        
        assert status.state == ContainerState.TERMINATED
        assert status.state_reason == "Completed"
