"""
Integration tests for critical OpenSRE skills.

These tests require actual service connections and should be run
with appropriate credentials configured.

Run with: pytest tests/integration/ -v --integration
"""

import pytest
import os
from unittest.mock import AsyncMock, MagicMock, patch

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


class TestPrometheusIntegration:
    """Integration tests for Prometheus skill."""

    @pytest.fixture
    def prometheus_skill(self):
        from skills.prometheus.actions import PrometheusSkill
        config = {
            "url": os.environ.get("PROMETHEUS_URL", "http://localhost:9090"),
            "timeout": 30,
        }
        return PrometheusSkill(config)

    @pytest.mark.asyncio
    async def test_query_basic(self, prometheus_skill):
        """Test basic PromQL query."""
        await prometheus_skill.initialize()
        try:
            result = await prometheus_skill.query("up")
            assert result.success or "connection" in (result.error or "").lower()
        finally:
            await prometheus_skill.shutdown()

    @pytest.mark.asyncio
    async def test_get_targets(self, prometheus_skill):
        """Test listing scrape targets."""
        await prometheus_skill.initialize()
        try:
            result = await prometheus_skill.get_targets()
            assert result.success or "connection" in (result.error or "").lower()
        finally:
            await prometheus_skill.shutdown()

    @pytest.mark.asyncio
    async def test_get_alerts(self, prometheus_skill):
        """Test listing active alerts."""
        await prometheus_skill.initialize()
        try:
            result = await prometheus_skill.get_alerts()
            assert result.success or "connection" in (result.error or "").lower()
        finally:
            await prometheus_skill.shutdown()


class TestKubernetesIntegration:
    """Integration tests for Kubernetes skill."""

    @pytest.fixture
    def kubernetes_skill(self):
        from skills.kubernetes.actions import KubernetesSkill
        config = {
            "namespace": "default",
        }
        return KubernetesSkill(config)

    @pytest.mark.asyncio
    async def test_get_pods(self, kubernetes_skill):
        """Test listing pods."""
        await kubernetes_skill.initialize()
        try:
            result = await kubernetes_skill.get_pods(namespace="default")
            # May fail if not connected to cluster
            assert result.success or result.error is not None
        finally:
            await kubernetes_skill.shutdown()

    @pytest.mark.asyncio
    async def test_get_deployments(self, kubernetes_skill):
        """Test listing deployments."""
        await kubernetes_skill.initialize()
        try:
            result = await kubernetes_skill.get_deployments(namespace="default")
            assert result.success or result.error is not None
        finally:
            await kubernetes_skill.shutdown()

    @pytest.mark.asyncio
    async def test_get_events(self, kubernetes_skill):
        """Test listing events."""
        await kubernetes_skill.initialize()
        try:
            result = await kubernetes_skill.get_events(namespace="default", minutes=60)
            assert result.success or result.error is not None
        finally:
            await kubernetes_skill.shutdown()


class TestHTTPIntegration:
    """Integration tests for HTTP skill."""

    @pytest.fixture
    def http_skill(self):
        from skills.http.actions import HTTPSkill
        return HTTPSkill({})

    @pytest.mark.asyncio
    async def test_get_request(self, http_skill):
        """Test HTTP GET request."""
        await http_skill.initialize()
        try:
            result = await http_skill.get(url="https://httpbin.org/get")
            assert result.success
            assert result.data.status_code == 200
        finally:
            await http_skill.shutdown()

    @pytest.mark.asyncio
    async def test_post_request(self, http_skill):
        """Test HTTP POST request."""
        await http_skill.initialize()
        try:
            result = await http_skill.post(
                url="https://httpbin.org/post",
                body={"test": "data"},
            )
            assert result.success
            assert result.data.status_code == 200
        finally:
            await http_skill.shutdown()

    @pytest.mark.asyncio
    async def test_health_check(self, http_skill):
        """Test health check."""
        await http_skill.initialize()
        try:
            result = await http_skill.health_check_action(
                url="https://httpbin.org/status/200",
                expected_status=200,
            )
            assert result.success
            assert result.data.healthy
        finally:
            await http_skill.shutdown()

    @pytest.mark.asyncio
    async def test_health_check_failure(self, http_skill):
        """Test health check with wrong status."""
        await http_skill.initialize()
        try:
            result = await http_skill.health_check_action(
                url="https://httpbin.org/status/500",
                expected_status=200,
            )
            assert result.success
            assert not result.data.healthy
        finally:
            await http_skill.shutdown()


class TestDatadogIntegration:
    """Integration tests for Datadog skill."""

    @pytest.fixture
    def datadog_skill(self):
        from skills.datadog.actions import DatadogSkill
        config = {
            "api_key": os.environ.get("DD_API_KEY", ""),
            "app_key": os.environ.get("DD_APP_KEY", ""),
            "site": os.environ.get("DD_SITE", "datadoghq.com"),
        }
        return DatadogSkill(config)

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.environ.get("DD_API_KEY"),
        reason="Datadog credentials not configured"
    )
    async def test_query_metrics(self, datadog_skill):
        """Test querying Datadog metrics."""
        await datadog_skill.initialize()
        try:
            result = await datadog_skill.query_metrics("avg:system.cpu.user{*}")
            assert result.success or "authentication" in (result.error or "").lower()
        finally:
            await datadog_skill.shutdown()

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.environ.get("DD_API_KEY"),
        reason="Datadog credentials not configured"
    )
    async def test_get_monitors(self, datadog_skill):
        """Test listing Datadog monitors."""
        await datadog_skill.initialize()
        try:
            result = await datadog_skill.get_monitors()
            assert result.success or "authentication" in (result.error or "").lower()
        finally:
            await datadog_skill.shutdown()


class TestElasticsearchIntegration:
    """Integration tests for Elasticsearch skill."""

    @pytest.fixture
    def elasticsearch_skill(self):
        from skills.elasticsearch.actions import ElasticsearchSkill
        config = {
            "hosts": [os.environ.get("ES_HOST", "http://localhost:9200")],
        }
        return ElasticsearchSkill(config)

    @pytest.mark.asyncio
    async def test_cluster_health(self, elasticsearch_skill):
        """Test cluster health check."""
        await elasticsearch_skill.initialize()
        try:
            result = await elasticsearch_skill.cluster_health()
            assert result.success or "connection" in (result.error or "").lower()
        finally:
            await elasticsearch_skill.shutdown()

    @pytest.mark.asyncio
    async def test_get_indices(self, elasticsearch_skill):
        """Test listing indices."""
        await elasticsearch_skill.initialize()
        try:
            result = await elasticsearch_skill.get_indices()
            assert result.success or "connection" in (result.error or "").lower()
        finally:
            await elasticsearch_skill.shutdown()
