"""
Test resource utilization context in observations.
"""


import pytest

from opensre_core.adapters.kubernetes import PodInfo
from opensre_core.agents.observe import ObserverAgent


class TestResourceUtilization:
    """Test resource utilization observation features."""

    def setup_method(self):
        """Setup test fixtures."""
        self.agent = ObserverAgent()

    def test_format_bytes(self):
        """Test byte formatting."""
        # Test various byte sizes
        assert self.agent._format_bytes(500) == "500B"
        assert self.agent._format_bytes(1024) == "1KB"
        assert self.agent._format_bytes(1024 * 1024) == "1MB"
        assert self.agent._format_bytes(260 * 1024 * 1024) == "260MB"
        assert self.agent._format_bytes(512 * 1024 * 1024) == "512MB"
        assert self.agent._format_bytes(1024 ** 3) == "1.00GB"
        assert self.agent._format_bytes(4.5 * 1024 ** 3) == "4.50GB"

    def test_utilization_severity(self):
        """Test severity thresholds for utilization."""
        # < 50% = info
        assert self.agent._utilization_severity(0.10) == "info"
        assert self.agent._utilization_severity(0.49) == "info"

        # 50-80% = info (but monitored)
        assert self.agent._utilization_severity(0.50) == "info"
        assert self.agent._utilization_severity(0.79) == "info"

        # 80-95% = warning
        assert self.agent._utilization_severity(0.81) == "warning"
        assert self.agent._utilization_severity(0.90) == "warning"
        assert self.agent._utilization_severity(0.95) == "warning"

        # > 95% = critical
        assert self.agent._utilization_severity(0.96) == "critical"
        assert self.agent._utilization_severity(0.99) == "critical"
        assert self.agent._utilization_severity(1.0) == "critical"

    def test_create_memory_utilization_observation_with_limit(self):
        """Test creating memory observation with limit context."""
        usage = 260 * 1024 * 1024  # 260MB
        limit = 512 * 1024 * 1024  # 512MB

        obs = self.agent._create_utilization_observation(
            pod_name="payment-service-abc123",
            resource_type="memory",
            usage=usage,
            limit=limit,
        )

        assert obs.source == "prometheus"
        assert obs.type == "resource_utilization"
        # Key format: "260MB / 512MB (51%)"
        assert "260MB" in obs.summary
        assert "512MB" in obs.summary
        assert "51%" in obs.summary
        assert "payment-service-abc123" in obs.summary

        # Check details
        assert obs.details["usage_bytes"] == usage
        assert obs.details["limit_bytes"] == limit
        assert abs(obs.details["utilization"] - 0.5078) < 0.01  # ~50.7%

        # Severity should be info at 51%
        assert obs.severity == "info"

    def test_create_memory_utilization_observation_no_limit(self):
        """Test creating memory observation without limit."""
        usage = 260 * 1024 * 1024  # 260MB

        obs = self.agent._create_utilization_observation(
            pod_name="payment-service-abc123",
            resource_type="memory",
            usage=usage,
            limit=None,
        )

        assert "260MB" in obs.summary
        assert "no limit set" in obs.summary
        assert obs.details["utilization"] is None
        assert obs.severity == "info"

    def test_create_memory_utilization_high_warning(self):
        """Test warning severity at 85% utilization."""
        usage = 435 * 1024 * 1024  # 435MB
        limit = 512 * 1024 * 1024  # 512MB (85% utilization)

        obs = self.agent._create_utilization_observation(
            pod_name="api-gateway-xyz",
            resource_type="memory",
            usage=usage,
            limit=limit,
        )

        assert obs.severity == "warning"
        assert "85%" in obs.summary

    def test_create_memory_utilization_critical(self):
        """Test critical severity at 98% utilization."""
        usage = 502 * 1024 * 1024  # 502MB
        limit = 512 * 1024 * 1024  # 512MB (98% utilization)

        obs = self.agent._create_utilization_observation(
            pod_name="api-gateway-xyz",
            resource_type="memory",
            usage=usage,
            limit=limit,
        )

        assert obs.severity == "critical"
        assert "98%" in obs.summary

    def test_create_cpu_utilization_observation(self):
        """Test CPU utilization observation."""
        usage = 0.450  # 450m cores
        limit = 1.0    # 1 core

        obs = self.agent._create_utilization_observation(
            pod_name="worker-pod",
            resource_type="cpu",
            usage=usage,
            limit=limit,
        )

        assert "CPU" in obs.summary
        assert "0.450 cores" in obs.summary
        assert "1.000 cores" in obs.summary
        assert "45%" in obs.summary
        assert obs.severity == "info"

    def test_create_cpu_utilization_high(self):
        """Test high CPU utilization observation."""
        usage = 0.9   # 900m cores
        limit = 1.0   # 1 core (90% utilization)

        obs = self.agent._create_utilization_observation(
            pod_name="worker-pod",
            resource_type="cpu",
            usage=usage,
            limit=limit,
        )

        assert obs.severity == "warning"
        assert "90%" in obs.summary


class TestKubernetesResourceParsing:
    """Test Kubernetes resource limit parsing."""

    def test_parse_resource_quantity_cpu(self):
        """Test CPU quantity parsing."""
        from opensre_core.adapters.kubernetes import KubernetesAdapter
        adapter = KubernetesAdapter()

        # Millicores
        assert adapter._parse_resource_quantity("500m", "cpu") == 0.5
        assert adapter._parse_resource_quantity("1000m", "cpu") == 1.0
        assert adapter._parse_resource_quantity("250m", "cpu") == 0.25

        # Whole cores
        assert adapter._parse_resource_quantity("1", "cpu") == 1.0
        assert adapter._parse_resource_quantity("2", "cpu") == 2.0

    def test_parse_resource_quantity_memory(self):
        """Test memory quantity parsing."""
        from opensre_core.adapters.kubernetes import KubernetesAdapter
        adapter = KubernetesAdapter()

        # Binary units (Ki, Mi, Gi)
        assert adapter._parse_resource_quantity("128Mi", "memory") == 128 * 1024 ** 2
        assert adapter._parse_resource_quantity("512Mi", "memory") == 512 * 1024 ** 2
        assert adapter._parse_resource_quantity("1Gi", "memory") == 1024 ** 3
        assert adapter._parse_resource_quantity("2Gi", "memory") == 2 * 1024 ** 3

        # Decimal units (M, G)
        assert adapter._parse_resource_quantity("128M", "memory") == 128 * 1000 ** 2
        assert adapter._parse_resource_quantity("1G", "memory") == 1000 ** 3

        # Plain bytes
        assert adapter._parse_resource_quantity("1000000", "memory") == 1000000


class TestPodInfoResources:
    """Test PodInfo dataclass with resources."""

    def test_pod_info_with_resources(self):
        """Test PodInfo includes resource fields."""
        pod = PodInfo(
            name="test-pod",
            namespace="default",
            status="Running",
            ready=True,
            restarts=0,
            age="1h",
            memory_limit=512 * 1024 ** 2,  # 512Mi
            memory_request=256 * 1024 ** 2,  # 256Mi
            cpu_limit=1.0,  # 1 core
            cpu_request=0.5,  # 500m
        )

        assert pod.memory_limit == 512 * 1024 ** 2
        assert pod.memory_request == 256 * 1024 ** 2
        assert pod.cpu_limit == 1.0
        assert pod.cpu_request == 0.5

    def test_pod_info_without_resources(self):
        """Test PodInfo defaults for resources."""
        pod = PodInfo(
            name="test-pod",
            namespace="default",
            status="Running",
            ready=True,
            restarts=0,
            age="1h",
        )

        assert pod.memory_limit is None
        assert pod.memory_request is None
        assert pod.cpu_limit is None
        assert pod.cpu_request is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
