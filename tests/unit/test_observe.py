"""
Unit Tests for ObserverAgent

Tests the observation collection functionality including:
- Metric keyword extraction
- Service name extraction
- Prometheus metric observation
- Kubernetes observation
- Resource utilization observation
"""


import pytest

from opensre_core.agents.observe import ObservationResult, ObserverAgent


class TestObserverAgentKeywordExtraction:
    """Tests for keyword extraction from issue descriptions."""

    @pytest.fixture
    def agent(self):
        return ObserverAgent()

    def test_extract_metric_keywords_memory(self, agent):
        """Test memory keyword extraction."""
        keywords = agent._extract_metric_keywords("high memory usage")
        assert "memory" in keywords

    def test_extract_metric_keywords_memory_aliases(self, agent):
        """Test memory keyword aliases (mem, oom, ram)."""
        assert "memory" in agent._extract_metric_keywords("high mem consumption")
        assert "memory" in agent._extract_metric_keywords("OOMKilled in production")
        assert "memory" in agent._extract_metric_keywords("out of memory error")
        assert "memory" in agent._extract_metric_keywords("RAM usage too high")

    def test_extract_metric_keywords_cpu(self, agent):
        """Test CPU keyword extraction."""
        keywords = agent._extract_metric_keywords("CPU spike on api-server")
        assert "cpu" in keywords

    def test_extract_metric_keywords_cpu_aliases(self, agent):
        """Test CPU keyword aliases."""
        assert "cpu" in agent._extract_metric_keywords("processor utilization")
        assert "cpu" in agent._extract_metric_keywords("high compute load")
        assert "cpu" in agent._extract_metric_keywords("high load on server")

    def test_extract_metric_keywords_latency(self, agent):
        """Test latency keyword extraction."""
        keywords = agent._extract_metric_keywords("slow response times")
        assert "latency" in keywords

    def test_extract_metric_keywords_latency_aliases(self, agent):
        """Test latency keyword aliases."""
        assert "latency" in agent._extract_metric_keywords("high latency")
        assert "latency" in agent._extract_metric_keywords("request delay")
        assert "latency" in agent._extract_metric_keywords("timeout errors")

    def test_extract_metric_keywords_error(self, agent):
        """Test error keyword extraction."""
        keywords = agent._extract_metric_keywords("high error rate")
        assert "error" in keywords

    def test_extract_metric_keywords_error_aliases(self, agent):
        """Test error keyword aliases."""
        assert "error" in agent._extract_metric_keywords("5xx errors increasing")
        assert "error" in agent._extract_metric_keywords("500 internal server error")
        assert "error" in agent._extract_metric_keywords("failed requests")

    def test_extract_metric_keywords_disk(self, agent):
        """Test disk keyword extraction."""
        keywords = agent._extract_metric_keywords("disk space low")
        assert "disk" in keywords

    def test_extract_metric_keywords_disk_aliases(self, agent):
        """Test disk keyword aliases."""
        assert "disk" in agent._extract_metric_keywords("storage full")
        assert "disk" in agent._extract_metric_keywords("filesystem 95%")
        assert "disk" in agent._extract_metric_keywords("PVC almost full")

    def test_extract_metric_keywords_network(self, agent):
        """Test network keyword extraction."""
        keywords = agent._extract_metric_keywords("network issues")
        assert "network" in keywords

    def test_extract_metric_keywords_network_aliases(self, agent):
        """Test network keyword aliases."""
        assert "network" in agent._extract_metric_keywords("bandwidth exhausted")
        assert "network" in agent._extract_metric_keywords("throughput degraded")
        assert "network" in agent._extract_metric_keywords("packet loss")
        assert "network" in agent._extract_metric_keywords("connection refused")

    def test_extract_metric_keywords_multiple(self, agent):
        """Test extracting multiple keywords."""
        keywords = agent._extract_metric_keywords("high memory and CPU usage causing latency")
        assert "memory" in keywords
        assert "cpu" in keywords
        assert "latency" in keywords

    def test_extract_metric_keywords_empty(self, agent):
        """Test no keywords for unrelated issue."""
        # Note: "failed" matches "error" keyword alias, so use truly unrelated text
        keywords = agent._extract_metric_keywords("pod not starting")
        assert len(keywords) == 0

    def test_extract_metric_keywords_case_insensitive(self, agent):
        """Test case insensitivity."""
        keywords = agent._extract_metric_keywords("HIGH MEMORY USAGE")
        assert "memory" in keywords


class TestObserverAgentServiceExtraction:
    """Tests for service name extraction."""

    @pytest.fixture
    def agent(self):
        return ObserverAgent()

    def test_extract_service_from_issue_basic(self, agent):
        """Test basic service name extraction."""
        service = agent._extract_service_from_issue("high CPU on payment-service")
        assert service == "payment-service"

    def test_extract_service_with_underscore(self, agent):
        """Test service with underscore (converts to hyphen)."""
        service = agent._extract_service_from_issue("issues with payment_service")
        assert service == "payment-service"

    def test_extract_service_api_suffix(self, agent):
        """Test service with api suffix."""
        service = agent._extract_service_from_issue("slow userapi responses")
        assert service == "userapi"

    def test_extract_service_on_pattern(self, agent):
        """Test 'on <service>' pattern."""
        service = agent._extract_service_from_issue("alerts on my-service detected")
        assert service == "my-service"

    def test_extract_service_none(self, agent):
        """Test when no service can be extracted."""
        service = agent._extract_service_from_issue("general system slowdown")
        assert service is None


class TestObserverAgentUtilizationFormatting:
    """Tests for resource utilization formatting."""

    @pytest.fixture
    def agent(self):
        return ObserverAgent()

    def test_format_bytes_gigabytes(self, agent):
        """Test formatting bytes to GB."""
        formatted = agent._format_bytes(5 * 1024**3)
        assert "5.00GB" in formatted

    def test_format_bytes_megabytes(self, agent):
        """Test formatting bytes to MB."""
        formatted = agent._format_bytes(256 * 1024**2)
        assert "256MB" in formatted

    def test_format_bytes_kilobytes(self, agent):
        """Test formatting bytes to KB."""
        formatted = agent._format_bytes(512 * 1024)
        assert "512KB" in formatted

    def test_format_bytes_bytes(self, agent):
        """Test formatting small byte values."""
        formatted = agent._format_bytes(500)
        assert "500B" in formatted

    def test_utilization_severity_critical(self, agent):
        """Test critical severity for >95% utilization."""
        severity = agent._utilization_severity(0.98)
        assert severity == "critical"

    def test_utilization_severity_warning(self, agent):
        """Test warning severity for 80-95% utilization."""
        severity = agent._utilization_severity(0.85)
        assert severity == "warning"

    def test_utilization_severity_info(self, agent):
        """Test info severity for <80% utilization."""
        severity = agent._utilization_severity(0.50)
        assert severity == "info"

    def test_utilization_severity_boundary_80(self, agent):
        """Test boundary at 80%."""
        assert agent._utilization_severity(0.80) == "info"
        assert agent._utilization_severity(0.81) == "warning"

    def test_utilization_severity_boundary_95(self, agent):
        """Test boundary at 95%."""
        assert agent._utilization_severity(0.95) == "warning"
        assert agent._utilization_severity(0.96) == "critical"


class TestObserverAgentMetricFormatting:
    """Tests for metric value formatting."""

    @pytest.fixture
    def agent(self):
        return ObserverAgent()

    def test_format_metric_value_bytes(self, agent):
        """Test formatting bytes metrics."""
        value = agent._format_metric_value("container_memory_usage_bytes", 512 * 1024**2)
        assert "MB" in value

    def test_format_metric_value_cpu(self, agent):
        """Test formatting CPU metrics."""
        # Note: The current implementation formats CPU "rate" metrics as rates (without cores unit)
        # Only pure "cpu" metrics without "rate" would get "cores" unit
        value = agent._format_metric_value("container_cpu_usage", 0.5)
        assert "cores" in value

    def test_format_metric_value_duration(self, agent):
        """Test formatting duration/latency metrics."""
        # Seconds (>= 1)
        value = agent._format_metric_value("http_request_duration_p99", 2.5)
        assert "s" in value

        # Milliseconds (< 1)
        value = agent._format_metric_value("latency_avg", 0.150)
        assert "ms" in value

    def test_format_metric_value_rate(self, agent):
        """Test formatting rate metrics."""
        value = agent._format_metric_value("error_rate", 0.0123)
        assert "0.0123" in value

    def test_format_metric_value_none(self, agent):
        """Test formatting None value."""
        value = agent._format_metric_value("any_metric", None)
        assert value == "N/A"


class TestObserverAgentMetricSeverity:
    """Tests for metric severity assessment."""

    @pytest.fixture
    def agent(self):
        return ObserverAgent()

    def test_assess_memory_severity_critical(self, agent):
        """Test critical memory usage."""
        severity = agent._assess_metric_severity("memory_usage_bytes", 5 * 1024**3)
        assert severity == "critical"

    def test_assess_memory_severity_warning(self, agent):
        """Test warning memory usage."""
        severity = agent._assess_metric_severity("memory_usage_bytes", 2 * 1024**3)
        assert severity == "warning"

    def test_assess_memory_severity_info(self, agent):
        """Test normal memory usage."""
        severity = agent._assess_metric_severity("memory_usage_bytes", 500 * 1024**2)
        assert severity == "info"

    def test_assess_cpu_severity_critical(self, agent):
        """Test critical CPU usage."""
        severity = agent._assess_metric_severity("cpu_usage", 3.0)
        assert severity == "critical"

    def test_assess_cpu_severity_warning(self, agent):
        """Test warning CPU usage."""
        severity = agent._assess_metric_severity("cpu_usage", 1.0)
        assert severity == "warning"

    def test_assess_cpu_severity_info(self, agent):
        """Test normal CPU usage."""
        severity = agent._assess_metric_severity("cpu_usage", 0.5)
        assert severity == "info"

    def test_assess_error_severity(self, agent):
        """Test error metric severity."""
        # Many errors
        severity = agent._assess_metric_severity("http_5xx_rate", 15)
        assert severity == "critical"

        # Some errors
        severity = agent._assess_metric_severity("error_count", 5)
        assert severity == "warning"

        # No errors
        severity = agent._assess_metric_severity("error_count", 0)
        assert severity == "info"

    def test_assess_latency_severity(self, agent):
        """Test latency severity."""
        # Very high
        severity = agent._assess_metric_severity("request_duration", 10.0)
        assert severity == "critical"

        # High
        severity = agent._assess_metric_severity("request_duration", 2.0)
        assert severity == "warning"

        # Normal
        severity = agent._assess_metric_severity("request_duration", 0.5)
        assert severity == "info"


class TestObserverAgentResourceUtilization:
    """Tests for resource utilization observation creation."""

    @pytest.fixture
    def agent(self):
        return ObserverAgent()

    def test_create_utilization_observation_memory_with_limit(self, agent):
        """Test memory utilization with limit."""
        obs = agent._create_utilization_observation(
            pod_name="test-pod",
            resource_type="memory",
            usage=256 * 1024**2,  # 256MB
            limit=512 * 1024**2,  # 512MB
        )

        assert "test-pod" in obs.summary
        assert "memory" in obs.summary.lower()
        assert "256MB" in obs.summary
        assert "512MB" in obs.summary
        assert "50%" in obs.summary
        assert obs.details["utilization"] == 0.5

    def test_create_utilization_observation_memory_no_limit(self, agent):
        """Test memory utilization without limit."""
        obs = agent._create_utilization_observation(
            pod_name="test-pod",
            resource_type="memory",
            usage=256 * 1024**2,
            limit=None,
        )

        assert "no limit" in obs.summary.lower()
        assert obs.details["utilization"] is None

    def test_create_utilization_observation_cpu_with_limit(self, agent):
        """Test CPU utilization with limit."""
        obs = agent._create_utilization_observation(
            pod_name="test-pod",
            resource_type="cpu",
            usage=0.25,  # 250m
            limit=0.5,   # 500m
        )

        assert "test-pod" in obs.summary
        assert "CPU" in obs.summary
        assert "50%" in obs.summary
        assert obs.details["utilization"] == 0.5

    def test_create_utilization_observation_high_severity(self, agent):
        """Test high utilization triggers correct severity."""
        obs = agent._create_utilization_observation(
            pod_name="test-pod",
            resource_type="memory",
            usage=490 * 1024**2,  # 490MB
            limit=500 * 1024**2,  # 500MB (98% utilization)
        )

        assert obs.severity == "critical"


class TestObserverAgentObserve:
    """Tests for the main observe method."""

    @pytest.fixture
    def agent(self, mock_prometheus, mock_kubernetes):
        agent = ObserverAgent()
        agent.prometheus = mock_prometheus
        agent.kubernetes = mock_kubernetes
        return agent

    @pytest.mark.asyncio
    async def test_observe_returns_result(self, agent):
        """Test observe returns valid ObservationResult."""
        result = await agent.observe("test issue", namespace="default")

        assert isinstance(result, ObservationResult)
        assert result.issue == "test issue"
        assert result.namespace == "default"

    @pytest.mark.asyncio
    async def test_observe_extracts_service(self, agent):
        """Test observe extracts service name."""
        result = await agent.observe("high CPU on api-service", namespace="default")

        assert "api-service" in result.services_involved

    @pytest.mark.asyncio
    async def test_observe_calls_prometheus(self, agent, mock_prometheus):
        """Test observe queries Prometheus."""
        await agent.observe("high memory usage", namespace="default")

        # Should have queried Prometheus for memory metrics
        mock_prometheus.query.assert_called()

    @pytest.mark.asyncio
    async def test_observe_calls_kubernetes(self, agent, mock_kubernetes):
        """Test observe queries Kubernetes."""
        mock_kubernetes.get_pods.return_value = []
        mock_kubernetes.get_events.return_value = []

        await agent.observe("test issue", namespace="default")

        # get_pods may be called multiple times (once for resource utilization, once for pod status)
        assert mock_kubernetes.get_pods.call_count >= 1
        mock_kubernetes.get_events.assert_called_once()

    @pytest.mark.asyncio
    async def test_observe_handles_prometheus_error(self, agent, mock_prometheus):
        """Test observe handles Prometheus errors gracefully."""
        mock_prometheus.query.side_effect = Exception("Connection refused")
        mock_prometheus.get_alerts.side_effect = Exception("Connection refused")

        result = await agent.observe("memory issue", namespace="default")

        # Should still return result with error observations
        assert result is not None
        error_obs = [o for o in result.observations if o.type == "error"]
        assert len(error_obs) > 0

    @pytest.mark.asyncio
    async def test_observe_handles_kubernetes_error(self, agent, mock_kubernetes):
        """Test observe handles Kubernetes errors gracefully."""
        mock_kubernetes.get_pods.side_effect = Exception("Not authorized")
        mock_kubernetes.get_events.side_effect = Exception("Not authorized")

        result = await agent.observe("test issue", namespace="default")

        # Should still return result
        assert result is not None


class TestObservationResultToContext:
    """Tests for ObservationResult.to_context()."""

    def test_to_context_basic(self, sample_observations):
        """Test basic context generation."""
        context = sample_observations.to_context()

        assert "Issue:" in context
        assert "Namespace:" in context
        assert "Observations:" in context
        assert sample_observations.issue in context

    def test_to_context_includes_observations(self, sample_observations):
        """Test context includes all observations."""
        context = sample_observations.to_context()

        for obs in sample_observations.observations:
            assert obs.summary in context

    def test_to_context_severity_icons(self, sample_observations):
        """Test context uses severity icons."""
        context = sample_observations.to_context()

        # Warning severity should have warning icon
        assert "⚠️" in context
