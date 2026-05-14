"""Integration tests for Prometheus client."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from autosre.integrations.prometheus import (
    MetricResult,
    MetricSample,
    PrometheusClient,
    QueryResponse,
    RangeVector,
)


@pytest.fixture
def prometheus_responses():
    """Load Prometheus mock responses."""
    fixtures_path = Path(__file__).parent.parent / "fixtures" / "prometheus_responses.json"
    with open(fixtures_path) as f:
        return json.load(f)


@pytest.fixture
def mock_client():
    """Create a mock Prometheus client."""
    client = PrometheusClient()
    return client


# ============================================================================
# Connection Tests
# ============================================================================


@pytest.mark.asyncio
class TestPrometheusConnection:
    """Tests for Prometheus connection handling."""

    async def test_check_connection_success(self, mock_client):
        """Test successful connection check."""
        with patch.object(mock_client, "_query_api") as mock_api:
            mock_api.return_value = QueryResponse(status="success")
            
            result = await mock_client.check_connection()
            
            assert result is True

    async def test_check_connection_failure(self, mock_client):
        """Test connection check failure."""
        with patch.object(mock_client, "_query_api") as mock_api:
            mock_api.side_effect = httpx.ConnectError("Connection refused")
            
            result = await mock_client.check_connection()
            
            assert result is False

    async def test_client_close(self, mock_client):
        """Test client close."""
        mock_client._client = AsyncMock()
        mock_client._client.is_closed = False
        
        await mock_client.close()
        
        mock_client._client.aclose.assert_called_once()


# ============================================================================
# Instant Query Tests
# ============================================================================


@pytest.mark.asyncio
class TestInstantQuery:
    """Tests for instant queries."""

    async def test_query_returns_vector_results(self, mock_client, prometheus_responses):
        """Test instant query returns vector results."""
        with patch.object(mock_client, "_query_api") as mock_api:
            mock_api.return_value = QueryResponse(
                status="success",
                data=prometheus_responses["instant_query_success"]["data"],
            )
            
            results = await mock_client.query("up")
            
            assert len(results) == 1
            assert isinstance(results[0], MetricResult)
            assert results[0].value == 1.0

    async def test_query_with_time_parameter(self, mock_client, prometheus_responses):
        """Test instant query with specific time."""
        with patch.object(mock_client, "_query_api") as mock_api:
            mock_api.return_value = QueryResponse(
                status="success",
                data=prometheus_responses["instant_query_success"]["data"],
            )
            
            query_time = datetime.now(timezone.utc) - timedelta(hours=1)
            results = await mock_client.query("up", time=query_time)
            
            # Should pass time to API
            call_args = mock_api.call_args
            assert call_args is not None

    async def test_query_returns_empty_on_no_results(self, mock_client, prometheus_responses):
        """Test query returns empty list when no results."""
        with patch.object(mock_client, "_query_api") as mock_api:
            mock_api.return_value = QueryResponse(
                status="success",
                data=prometheus_responses["empty_result"]["data"],
            )
            
            results = await mock_client.query("nonexistent_metric")
            
            assert results == []

    async def test_query_handles_error_response(self, mock_client, prometheus_responses):
        """Test query handles error response."""
        with patch.object(mock_client, "_query_api") as mock_api:
            mock_api.return_value = QueryResponse(
                status="error",
                error=prometheus_responses["error_response"]["error"],
                error_type=prometheus_responses["error_response"]["errorType"],
            )
            
            results = await mock_client.query("invalid{")
            
            assert results == []


# ============================================================================
# Range Query Tests
# ============================================================================


@pytest.mark.asyncio
class TestRangeQuery:
    """Tests for range queries."""

    async def test_range_query_returns_matrix(self, mock_client, prometheus_responses):
        """Test range query returns matrix results."""
        with patch.object(mock_client, "_query_api") as mock_api:
            mock_api.return_value = QueryResponse(
                status="success",
                data=prometheus_responses["range_query_success"]["data"],
            )
            
            result = await mock_client.query_range(
                "container_cpu_usage_seconds_total",
                duration=timedelta(hours=1),
            )
            
            assert isinstance(result, RangeVector)
            assert len(result.results) == 1
            assert len(result.results[0].values) == 5

    async def test_range_query_with_explicit_times(self, mock_client, prometheus_responses):
        """Test range query with explicit start/end times."""
        with patch.object(mock_client, "_query_api") as mock_api:
            mock_api.return_value = QueryResponse(
                status="success",
                data=prometheus_responses["range_query_success"]["data"],
            )
            
            end = datetime.now(timezone.utc)
            start = end - timedelta(hours=2)
            
            result = await mock_client.query_range(
                "cpu",
                start=start,
                end=end,
                step="30s",
            )
            
            assert result.start == start
            assert result.end == end
            assert result.step == "30s"

    async def test_range_query_filter_by_label(self, mock_client, prometheus_responses):
        """Test range query result filtering."""
        with patch.object(mock_client, "_query_api") as mock_api:
            mock_api.return_value = QueryResponse(
                status="success",
                data={
                    "resultType": "matrix",
                    "result": [
                        {"metric": {"pod": "pod-1"}, "values": [[1, "0.5"]]},
                        {"metric": {"pod": "pod-2"}, "values": [[1, "0.6"]]},
                    ],
                },
            )
            
            result = await mock_client.query_range("cpu", duration=timedelta(hours=1))
            filtered = result.filter_by_label("pod", "pod-1")
            
            assert len(filtered) == 1
            assert filtered[0].label("pod") == "pod-1"


# ============================================================================
# Helper Method Tests
# ============================================================================


@pytest.mark.asyncio
class TestPrometheusHelpers:
    """Tests for Prometheus helper methods."""

    async def test_get_error_rate(self, mock_client, prometheus_responses):
        """Test error rate helper."""
        with patch.object(mock_client, "query") as mock_query:
            mock_query.return_value = [
                MetricResult.from_instant(
                    prometheus_responses["error_rate_query"]["data"]["result"][0]
                )
            ]
            
            rate = await mock_client.get_error_rate("payment-service")
            
            assert rate == 0.05

    async def test_get_error_rate_with_namespace(self, mock_client, prometheus_responses):
        """Test error rate with namespace filter."""
        with patch.object(mock_client, "query") as mock_query:
            mock_query.return_value = [
                MetricResult(metric={}, value=0.03)
            ]
            
            rate = await mock_client.get_error_rate(
                "payment-service",
                namespace="production",
            )
            
            assert rate == 0.03
            # Verify namespace was included in query
            call_args = mock_query.call_args
            assert 'namespace="production"' in call_args[0][0]

    async def test_get_error_rate_returns_none_when_no_data(self, mock_client):
        """Test error rate returns None when no data."""
        with patch.object(mock_client, "query") as mock_query:
            mock_query.return_value = []
            
            rate = await mock_client.get_error_rate("nonexistent")
            
            assert rate is None

    async def test_get_latency_percentile(self, mock_client, prometheus_responses):
        """Test latency percentile helper."""
        with patch.object(mock_client, "query") as mock_query:
            mock_query.return_value = [
                MetricResult.from_instant(
                    prometheus_responses["latency_percentile_query"]["data"]["result"][0]
                )
            ]
            
            latency = await mock_client.get_latency_percentile("payment-service")
            
            assert latency == 0.250

    async def test_get_latency_percentile_custom(self, mock_client):
        """Test latency with custom percentile."""
        with patch.object(mock_client, "query") as mock_query:
            mock_query.return_value = [MetricResult(metric={}, value=0.5)]
            
            latency = await mock_client.get_latency_percentile(
                "service",
                percentile=0.95,
            )
            
            # Verify percentile was used
            call_args = mock_query.call_args
            assert "0.95" in call_args[0][0]

    async def test_get_request_rate(self, mock_client, prometheus_responses):
        """Test request rate helper."""
        with patch.object(mock_client, "query") as mock_query:
            mock_query.return_value = [
                MetricResult.from_instant(
                    prometheus_responses["request_rate"]["data"]["result"][0]
                )
            ]
            
            rate = await mock_client.get_request_rate("payment-service")
            
            assert rate == 150.5

    async def test_get_resource_usage(self, mock_client):
        """Test resource usage helper."""
        with patch.object(mock_client, "query") as mock_query:
            # Return different results for CPU and memory queries
            mock_query.side_effect = [
                [MetricResult(metric={"pod": "test-pod"}, value=0.5)],  # CPU
                [MetricResult(metric={"pod": "test-pod"}, value=1073741824)],  # Memory
            ]
            
            usage = await mock_client.get_resource_usage(
                "test-.*",
                "production",
            )
            
            assert "cpu" in usage
            assert "memory" in usage
            assert usage["cpu"]["test-pod"] == 0.5


# ============================================================================
# Metadata Tests
# ============================================================================


@pytest.mark.asyncio
class TestPrometheusMetadata:
    """Tests for Prometheus metadata operations."""

    async def test_get_labels(self, mock_client, prometheus_responses):
        """Test getting label values."""
        with patch.object(mock_client, "_query_api") as mock_api:
            mock_api.return_value = QueryResponse(
                status="success",
                data={"data": prometheus_responses["labels_response"]["data"]},
            )
            
            labels = await mock_client.get_labels("__name__")
            
            assert "up" in labels
            assert "http_requests_total" in labels

    async def test_get_series(self, mock_client, prometheus_responses):
        """Test getting series."""
        with patch.object(mock_client, "_query_api") as mock_api:
            mock_api.return_value = QueryResponse(
                status="success",
                data={"data": prometheus_responses["series_response"]["data"]},
            )
            
            series = await mock_client.get_series(["up"])
            
            assert len(series) == 2
            assert series[0]["__name__"] == "up"

    async def test_get_metric_metadata(self, mock_client, prometheus_responses):
        """Test getting metric metadata."""
        with patch.object(mock_client, "_query_api") as mock_api:
            mock_api.return_value = QueryResponse(
                status="success",
                data=prometheus_responses["metadata_response"]["data"],
            )
            
            metadata = await mock_client.get_metric_metadata("http_requests_total")
            
            assert metadata["type"] == "counter"
            assert "Total HTTP" in metadata["help"]


# ============================================================================
# Module Functions Tests
# ============================================================================


@pytest.mark.asyncio
class TestModuleFunctions:
    """Tests for module-level convenience functions."""

    async def test_get_client_singleton(self):
        """Test get_client returns singleton."""
        from autosre.integrations.prometheus import get_client
        
        client1 = get_client()
        client2 = get_client()
        
        assert client1 is client2

    async def test_module_query_function(self):
        """Test module-level query function."""
        from autosre.integrations import prometheus
        
        with patch.object(PrometheusClient, "query") as mock_query:
            mock_query.return_value = []
            
            # This creates/uses the default client
            # The test verifies the function exists and is callable
            assert callable(prometheus.query)

    async def test_module_query_range_function(self):
        """Test module-level query_range function."""
        from autosre.integrations import prometheus
        
        assert callable(prometheus.query_range)
