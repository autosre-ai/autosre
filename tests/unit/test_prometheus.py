"""
Unit Tests for Prometheus Adapter

Tests the Prometheus metric and alert query functionality including:
- Connection health checks
- Instant and range queries
- Alert retrieval
- Service metrics
- Anomaly detection
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from opensre_core.adapters.prometheus import (
    AlertResult,
    MetricResult,
    PrometheusAdapter,
)


class TestMetricResult:
    """Tests for MetricResult dataclass."""

    def test_metric_result_creation(self):
        """Test MetricResult creation."""
        result = MetricResult(
            metric_name="container_memory_usage_bytes",
            labels={"pod": "my-pod", "namespace": "default"},
            values=[],
            current_value=256 * 1024 * 1024,
        )

        assert result.metric_name == "container_memory_usage_bytes"
        assert result.labels["pod"] == "my-pod"
        assert result.current_value == 256 * 1024 * 1024

    def test_metric_result_with_values(self):
        """Test MetricResult with time series values."""
        now = datetime.now()
        result = MetricResult(
            metric_name="test_metric",
            labels={},
            values=[(now, 100.0), (now, 200.0)],
            current_value=200.0,
        )

        assert len(result.values) == 2
        assert result.values[1][1] == 200.0


class TestAlertResult:
    """Tests for AlertResult dataclass."""

    def test_alert_result_creation(self):
        """Test AlertResult creation."""
        result = AlertResult(
            alert_name="HighMemoryUsage",
            state="firing",
            labels={"severity": "critical"},
            annotations={"summary": "Memory is high"},
        )

        assert result.alert_name == "HighMemoryUsage"
        assert result.state == "firing"

    def test_alert_result_with_timestamp(self):
        """Test AlertResult with started_at timestamp."""
        now = datetime.now(timezone.utc)
        result = AlertResult(
            alert_name="TestAlert",
            state="pending",
            labels={},
            annotations={},
            started_at=now,
        )

        assert result.started_at == now


class TestPrometheusAdapterInit:
    """Tests for PrometheusAdapter initialization."""

    def test_adapter_default_url(self):
        """Test adapter uses default URL from settings."""
        with patch("opensre_core.adapters.prometheus.settings") as mock_settings:
            mock_settings.prometheus_url = "http://prometheus:9090"

            adapter = PrometheusAdapter()

            assert adapter.url == "http://prometheus:9090"

    def test_adapter_custom_url(self):
        """Test adapter with custom URL."""
        adapter = PrometheusAdapter(url="http://custom:9090")

        assert adapter.url == "http://custom:9090"

    def test_adapter_lazy_client(self):
        """Test client is lazily initialized."""
        adapter = PrometheusAdapter()

        # Client should not be created yet
        assert adapter._client is None


class TestPrometheusAdapterHealthCheck:
    """Tests for health check functionality."""

    @pytest.fixture
    def adapter(self):
        return PrometheusAdapter(url="http://localhost:9090")

    @pytest.mark.asyncio
    async def test_health_check_success(self, adapter):
        """Test successful health check."""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value.__aenter__.return_value.get.return_value = mock_response

            # Create a proper async context manager mock
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await adapter.health_check()

            assert result["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_health_check_failure(self, adapter):
        """Test health check failure."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value.get.side_effect = Exception("Connection refused")
            mock_client_class.return_value = mock_client

            with pytest.raises(Exception, match="Connection refused"):
                await adapter.health_check()


class TestPrometheusAdapterQuery:
    """Tests for query functionality."""

    @pytest.fixture
    def adapter(self):
        adapter = PrometheusAdapter(url="http://localhost:9090")
        adapter._client = MagicMock()
        return adapter

    @pytest.mark.asyncio
    async def test_query_returns_metrics(self, adapter):
        """Test query returns list of MetricResult."""
        adapter._client.custom_query.return_value = [
            {
                "metric": {"__name__": "test_metric", "pod": "my-pod"},
                "value": [1704067200, "100.5"],
            }
        ]

        results = await adapter.query("test_metric{pod='my-pod'}")

        assert len(results) == 1
        assert isinstance(results[0], MetricResult)
        assert results[0].metric_name == "test_metric"
        assert results[0].current_value == 100.5

    @pytest.mark.asyncio
    async def test_query_parses_labels(self, adapter):
        """Test query parses labels correctly."""
        adapter._client.custom_query.return_value = [
            {
                "metric": {
                    "__name__": "container_memory_usage_bytes",
                    "pod": "api-server-abc",
                    "namespace": "production",
                    "container": "api",
                },
                "value": [1704067200, "268435456"],
            }
        ]

        results = await adapter.query("container_memory_usage_bytes")

        assert results[0].labels["pod"] == "api-server-abc"
        assert results[0].labels["namespace"] == "production"
        assert results[0].labels["container"] == "api"
        assert "__name__" not in results[0].labels

    @pytest.mark.asyncio
    async def test_query_handles_empty_result(self, adapter):
        """Test query handles empty results."""
        adapter._client.custom_query.return_value = []

        results = await adapter.query("nonexistent_metric")

        assert results == []

    @pytest.mark.asyncio
    async def test_query_handles_null_value(self, adapter):
        """Test query handles null current value."""
        adapter._client.custom_query.return_value = [
            {
                "metric": {"__name__": "test"},
                "value": [1704067200],  # Missing value
            }
        ]

        results = await adapter.query("test")

        assert results[0].current_value is None


class TestPrometheusAdapterQueryRange:
    """Tests for range query functionality."""

    @pytest.fixture
    def adapter(self):
        adapter = PrometheusAdapter(url="http://localhost:9090")
        adapter._client = MagicMock()
        return adapter

    @pytest.mark.asyncio
    async def test_query_range_returns_time_series(self, adapter):
        """Test query_range returns time series data."""
        adapter._client.custom_query_range.return_value = [
            {
                "metric": {"__name__": "cpu_usage"},
                "values": [
                    [1704067200, "0.5"],
                    [1704067215, "0.6"],
                    [1704067230, "0.7"],
                ],
            }
        ]

        results = await adapter.query_range("cpu_usage")

        assert len(results) == 1
        assert len(results[0].values) == 3
        assert results[0].values[0][1] == 0.5
        assert results[0].current_value == 0.7


class TestPrometheusAdapterGetAlerts:
    """Tests for alert retrieval functionality."""

    @pytest.fixture
    def adapter(self):
        return PrometheusAdapter(url="http://localhost:9090")

    @pytest.mark.asyncio
    async def test_get_alerts_returns_alerts(self, adapter):
        """Test get_alerts returns list of AlertResult."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": {
                "alerts": [
                    {
                        "labels": {"alertname": "HighCPU", "severity": "warning"},
                        "annotations": {"summary": "CPU is high"},
                        "state": "firing",
                        "activeAt": "2024-01-01T00:00:00Z",
                    }
                ]
            }
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            alerts = await adapter.get_alerts()

        assert len(alerts) == 1
        assert isinstance(alerts[0], AlertResult)
        assert alerts[0].alert_name == "HighCPU"
        assert alerts[0].state == "firing"

    @pytest.mark.asyncio
    async def test_get_alerts_filters_by_state(self, adapter):
        """Test get_alerts filters by state."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": {
                "alerts": [
                    {"labels": {"alertname": "Firing1"}, "annotations": {}, "state": "firing"},
                    {"labels": {"alertname": "Pending1"}, "annotations": {}, "state": "pending"},
                ]
            }
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            alerts = await adapter.get_alerts(state="firing")

        assert len(alerts) == 1
        assert alerts[0].alert_name == "Firing1"


class TestPrometheusAdapterGetServiceMetrics:
    """Tests for service metrics functionality."""

    @pytest.fixture
    def adapter(self):
        adapter = PrometheusAdapter(url="http://localhost:9090")
        adapter._client = MagicMock()
        return adapter

    @pytest.mark.asyncio
    async def test_get_service_metrics_returns_dict(self, adapter):
        """Test get_service_metrics returns metrics dictionary."""
        adapter._client.custom_query.return_value = [
            {"metric": {}, "value": [1704067200, "0.5"]}
        ]

        metrics = await adapter.get_service_metrics("api-server")

        assert isinstance(metrics, dict)
        # Should have keys for cpu_usage, memory_usage, etc.
        assert "cpu_usage" in metrics or metrics.get("cpu_usage") is not None

    @pytest.mark.asyncio
    async def test_get_service_metrics_handles_missing(self, adapter):
        """Test get_service_metrics handles missing metrics."""
        adapter._client.custom_query.return_value = []

        metrics = await adapter.get_service_metrics("nonexistent")

        # Should have None for missing metrics
        assert isinstance(metrics, dict)


class TestPrometheusAdapterFindAnomalies:
    """Tests for anomaly detection functionality."""

    @pytest.fixture
    def adapter(self):
        adapter = PrometheusAdapter(url="http://localhost:9090")
        adapter._client = MagicMock()
        return adapter

    @pytest.mark.asyncio
    async def test_find_anomalies_high_cpu(self, adapter):
        """Test anomaly detection for high CPU."""
        # Mock high CPU
        def mock_query(query):
            if "cpu" in query.lower():
                return [{"metric": {}, "value": [1704067200, "0.9"]}]
            return []

        adapter._client.custom_query.side_effect = mock_query

        anomalies = await adapter.find_anomalies("api-server")

        assert len(anomalies) >= 1
        assert any(a["type"] == "high_cpu" for a in anomalies)

    @pytest.mark.asyncio
    async def test_find_anomalies_high_error_rate(self, adapter):
        """Test anomaly detection for high error rate."""
        # Mock the get_service_metrics method directly since find_anomalies uses it
        adapter.get_service_metrics = AsyncMock(return_value={
            "cpu_usage": 0.3,
            "memory_usage": 256 * 1024 * 1024,
            "request_rate": 100.0,
            "error_rate": 0.05,  # 5% - above 1% threshold
            "latency_p99": 0.5,
        })

        anomalies = await adapter.find_anomalies("api-server")

        assert any(a["type"] == "high_error_rate" for a in anomalies)

    @pytest.mark.asyncio
    async def test_find_anomalies_high_latency(self, adapter):
        """Test anomaly detection for high latency."""
        def mock_query(query):
            if "latency" in query.lower() or "duration" in query.lower():
                return [{"metric": {}, "value": [1704067200, "2.5"]}]
            return []

        adapter._client.custom_query.side_effect = mock_query

        anomalies = await adapter.find_anomalies("api-server")

        assert any(a["type"] == "high_latency" for a in anomalies)

    @pytest.mark.asyncio
    async def test_find_anomalies_no_anomalies(self, adapter):
        """Test no anomalies for healthy service."""
        # Mock the get_service_metrics method directly with all healthy values
        adapter.get_service_metrics = AsyncMock(return_value={
            "cpu_usage": 0.3,  # Below 0.8 threshold
            "memory_usage": 256 * 1024 * 1024,
            "request_rate": 100.0,
            "error_rate": 0.005,  # Below 1% threshold
            "latency_p99": 0.5,  # Below 1.0s threshold
        })

        anomalies = await adapter.find_anomalies("healthy-service")

        # Should have no critical anomalies
        assert len([a for a in anomalies if a["severity"] == "critical"]) == 0


class TestPrometheusAdapterParseTime:
    """Tests for timestamp parsing."""

    @pytest.fixture
    def adapter(self):
        return PrometheusAdapter()

    def test_parse_time_iso_format(self, adapter):
        """Test parsing ISO format timestamp."""
        result = adapter._parse_time("2024-01-01T12:00:00Z")

        assert result is not None
        assert isinstance(result, datetime)

    def test_parse_time_none(self, adapter):
        """Test parsing None timestamp."""
        result = adapter._parse_time(None)

        assert result is None

    def test_parse_time_invalid(self, adapter):
        """Test parsing invalid timestamp."""
        result = adapter._parse_time("not-a-timestamp")

        assert result is None
