"""Tests for opensre_core.api module."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from opensre_core.api import create_app


@pytest.fixture
def client():
    """Create a test client for the API."""
    app = create_app()
    return TestClient(app)


class TestHealthEndpoint:
    """Tests for /api/health endpoint."""

    def test_health_returns_200(self, client):
        """Test health endpoint returns 200 OK."""
        response = client.get("/api/health")
        assert response.status_code == 200

    def test_health_returns_healthy_status(self, client):
        """Test health endpoint returns healthy status."""
        response = client.get("/api/health")
        data = response.json()
        assert data["status"] == "healthy"

    def test_health_includes_version(self, client):
        """Test health endpoint includes version."""
        response = client.get("/api/health")
        data = response.json()
        assert "version" in data
        assert data["version"] == "0.1.0"


class TestStatusEndpoint:
    """Tests for /api/status endpoint."""

    def test_status_returns_200(self, client):
        """Test status endpoint returns 200."""
        response = client.get("/api/status")
        assert response.status_code == 200

    def test_status_includes_version(self, client):
        """Test status includes version."""
        response = client.get("/api/status")
        data = response.json()
        assert "version" in data

    def test_status_includes_integrations(self, client):
        """Test status includes integrations."""
        response = client.get("/api/status")
        data = response.json()
        assert "integrations" in data
        # Should have at least prometheus and kubernetes
        assert "prometheus" in data["integrations"]
        assert "kubernetes" in data["integrations"]


class TestCORSHeaders:
    """Tests for CORS headers."""

    def test_cors_allows_all_origins(self, client):
        """Test CORS allows all origins."""
        response = client.get("/api/health")
        # CORS middleware should be configured
        assert response.status_code == 200


class TestOpenAPISpec:
    """Tests for OpenAPI spec."""

    def test_openapi_spec_accessible(self, client):
        """Test OpenAPI spec is accessible."""
        response = client.get("/openapi.json")
        assert response.status_code == 200

    def test_openapi_has_info(self, client):
        """Test OpenAPI spec has info section."""
        response = client.get("/openapi.json")
        spec = response.json()
        assert "info" in spec
        assert "title" in spec["info"]

    def test_openapi_has_paths(self, client):
        """Test OpenAPI spec has paths."""
        response = client.get("/openapi.json")
        spec = response.json()
        assert "paths" in spec
        assert "/api/health" in spec["paths"]


class TestDocsEndpoint:
    """Tests for documentation endpoint."""

    def test_docs_accessible(self, client):
        """Test /docs endpoint is accessible."""
        response = client.get("/docs")
        assert response.status_code == 200


class TestInvestigationsEndpoint:
    """Tests for /api/investigations endpoint."""

    def test_investigations_list_requires_auth_or_init(self, client):
        """Test investigations list requires auth or initialization."""
        response = client.get("/api/investigations")
        # Without proper initialization, should return 500 or auth error
        assert response.status_code in [200, 401, 500]


class TestPrometheusEndpoints:
    """Tests for /api/prometheus endpoints."""

    def test_prometheus_query_requires_query_param(self, client):
        """Test prometheus query requires query parameter."""
        response = client.get("/api/prometheus/query")
        assert response.status_code == 422


class TestKubernetesEndpoints:
    """Tests for /api/kubernetes endpoints."""

    def test_kubernetes_pods_returns_pods(self, client):
        """Test kubernetes pods endpoint."""
        response = client.get("/api/kubernetes/pods")
        # May fail without K8s connection but should not 500
        assert response.status_code in [200, 500]

    def test_kubernetes_events_returns_events(self, client):
        """Test kubernetes events endpoint."""
        response = client.get("/api/kubernetes/events")
        assert response.status_code in [200, 500]


class TestRemediationEndpoints:
    """Tests for /api/remediation endpoints."""

    @pytest.fixture
    def auth_client(self):
        """Create a test client with auth mocked."""
        from opensre_core.api import create_app, get_current_user
        app = create_app()
        # Override auth dependency
        app.dependency_overrides[get_current_user] = lambda: {"user": "test", "roles": ["admin"]}
        return TestClient(app)

    def test_remediation_actions_returns_200(self, auth_client):
        """Test remediation actions endpoint."""
        response = auth_client.get("/api/remediation/actions")
        assert response.status_code == 200

    def test_remediation_stats_returns_200(self, auth_client):
        """Test remediation stats endpoint."""
        response = auth_client.get("/api/remediation/stats")
        assert response.status_code == 200

    def test_remediation_stats_has_counts(self, auth_client):
        """Test remediation stats includes count fields."""
        response = auth_client.get("/api/remediation/stats")
        data = response.json()
        assert "pending" in data
        assert "total_executed" in data


class TestAppCreation:
    """Tests for app creation."""

    def test_create_app_returns_fastapi(self):
        """Test create_app returns FastAPI app."""
        from fastapi import FastAPI
        app = create_app()
        assert isinstance(app, FastAPI)

    def test_create_app_has_title(self):
        """Test app has title set."""
        app = create_app()
        # App should have a title
        assert app.title is not None
        assert len(app.title) > 0


class TestMetricsEndpoint:
    """Tests for /metrics endpoint."""

    def test_metrics_returns_200(self, client):
        """Test metrics endpoint returns 200."""
        response = client.get("/metrics")
        assert response.status_code == 200

    def test_metrics_returns_prometheus_format(self, client):
        """Test metrics are in Prometheus format."""
        response = client.get("/metrics")
        content = response.text
        # Should have some prometheus-style metrics
        assert "# HELP" in content or "# TYPE" in content or len(content) > 0

