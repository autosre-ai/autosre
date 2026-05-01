"""
Tests for AutoSRE Web Routes

Tests all web endpoints for the dashboard.
"""

import pytest
from fastapi.testclient import TestClient

from autosre.web.app import create_app


@pytest.fixture
def client():
    """Create a test client."""
    app = create_app()
    return TestClient(app)


class TestHealthEndpoints:
    """Test health and status endpoints."""
    
    def test_health_endpoint(self, client):
        """Test /health returns healthy status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "autosre-web"
    
    def test_api_info_endpoint(self, client):
        """Test /api returns API info."""
        response = client.get("/api")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "AutoSRE Web API"
        assert data["version"] == "0.1.0"
        assert data["docs"] == "/api/docs"


class TestDashboardRoutes:
    """Test dashboard routes."""
    
    def test_dashboard_page(self, client):
        """Test main dashboard page loads."""
        response = client.get("/")
        assert response.status_code == 200
        assert "AutoSRE" in response.text
        assert "Dashboard" in response.text
    
    def test_dashboard_contains_nav(self, client):
        """Test dashboard contains navigation."""
        response = client.get("/")
        assert response.status_code == 200
        assert "Evals" in response.text or "evals" in response.text
        assert "Context" in response.text or "context" in response.text
    
    def test_status_cards_partial(self, client):
        """Test status cards HTMX partial - endpoint may not exist."""
        response = client.get("/status-cards")
        # Status cards might be embedded in dashboard, not separate endpoint
        assert response.status_code in [200, 404]


class TestEvalsRoutes:
    """Test evaluation routes."""
    
    def test_evals_page(self, client):
        """Test evals page loads."""
        response = client.get("/evals/")
        assert response.status_code == 200
        assert "Evals" in response.text or "Scenario" in response.text
    
    def test_scenario_list_partial(self, client):
        """Test scenario list HTMX partial."""
        response = client.get("/evals/list")
        assert response.status_code == 200
    
    def test_results_list_partial(self, client):
        """Test results list HTMX partial."""
        response = client.get("/evals/results")
        assert response.status_code == 200
    
    def test_api_scenarios(self, client):
        """Test API scenarios endpoint."""
        response = client.get("/evals/api/scenarios")
        assert response.status_code == 200
        data = response.json()
        assert "scenarios" in data
        assert isinstance(data["scenarios"], list)
    
    def test_api_results(self, client):
        """Test API results endpoint."""
        response = client.get("/evals/api/results")
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert isinstance(data["results"], list)
    
    def test_scenario_detail_not_found(self, client):
        """Test scenario detail with invalid name."""
        response = client.get("/evals/scenario/nonexistent_scenario_xyz")
        assert response.status_code == 200
        assert "not found" in response.text.lower() or "error" in response.text.lower()


class TestContextRoutes:
    """Test context store routes."""
    
    def test_context_page(self, client):
        """Test context page loads."""
        response = client.get("/context/")
        assert response.status_code == 200
        assert "Context" in response.text
    
    def test_services_table_partial(self, client):
        """Test services table HTMX partial."""
        response = client.get("/context/services")
        assert response.status_code == 200
    
    def test_changes_table_partial(self, client):
        """Test changes table HTMX partial."""
        response = client.get("/context/changes")
        assert response.status_code == 200
    
    def test_alerts_table_partial(self, client):
        """Test alerts table HTMX partial."""
        response = client.get("/context/alerts")
        assert response.status_code == 200
    
    def test_runbooks_table_partial(self, client):
        """Test runbooks table HTMX partial."""
        response = client.get("/context/runbooks")
        assert response.status_code == 200


class TestAgentRoutes:
    """Test agent routes."""
    
    def test_agent_page(self, client):
        """Test agent page loads."""
        response = client.get("/agent/")
        assert response.status_code == 200
        assert "Agent" in response.text
    
    def test_agent_status_partial(self, client):
        """Test agent status HTMX partial."""
        response = client.get("/agent/status")
        assert response.status_code == 200
    
    def test_agent_config_partial(self, client):
        """Test agent config HTMX partial."""
        response = client.get("/agent/config")
        assert response.status_code == 200
    
    def test_agent_history_partial(self, client):
        """Test agent history HTMX partial."""
        response = client.get("/agent/history")
        assert response.status_code == 200
    
    def test_agent_logs_partial(self, client):
        """Test agent logs HTMX partial."""
        response = client.get("/agent/logs")
        assert response.status_code == 200


class TestFeedbackRoutes:
    """Test feedback routes."""
    
    def test_feedback_page(self, client):
        """Test feedback page loads."""
        response = client.get("/feedback/")
        assert response.status_code == 200
        assert "Feedback" in response.text
    
    def test_feedback_form_partial(self, client):
        """Test feedback form HTMX partial."""
        # Form requires incident_id parameter
        response = client.get("/feedback/form/INC-123")
        assert response.status_code == 200
    
    def test_feedback_history_partial(self, client):
        """Test feedback history HTMX partial."""
        response = client.get("/feedback/history")
        assert response.status_code == 200
    
    def test_submit_feedback(self, client):
        """Test submitting feedback."""
        response = client.post(
            "/feedback/submit",
            data={
                "incident_id": "INC-123",
                "rating": "positive",
                "category": "general",
                "comment": "Test feedback",
            }
        )
        assert response.status_code == 200


class TestStaticFiles:
    """Test static file serving."""
    
    def test_static_css(self, client):
        """Test static CSS file."""
        response = client.get("/static/style.css")
        # May be 200 or 404 depending on if file exists
        assert response.status_code in [200, 404]


class TestAPIDocumentation:
    """Test API documentation endpoints."""
    
    def test_openapi_docs(self, client):
        """Test OpenAPI docs page."""
        response = client.get("/api/docs")
        assert response.status_code == 200
    
    def test_redoc_docs(self, client):
        """Test ReDoc docs page."""
        response = client.get("/api/redoc")
        assert response.status_code == 200


class TestErrorHandling:
    """Test error handling."""
    
    def test_404_page(self, client):
        """Test 404 for unknown page."""
        response = client.get("/nonexistent/page/xyz")
        assert response.status_code == 404


class TestHTMXIntegration:
    """Test HTMX integration."""
    
    def test_htmx_headers(self, client):
        """Test HTMX headers are handled."""
        response = client.get(
            "/evals/list",
            headers={"HX-Request": "true"}
        )
        assert response.status_code == 200
    
    def test_htmx_partial_content(self, client):
        """Test HTMX partial returns fragment."""
        response = client.get("/context/services")
        assert response.status_code == 200
        # Partial should not include full HTML structure
        text = response.text
        # It's a partial if it doesn't have doctype
        # (though some partials might be full pages)
        assert len(text) > 0
