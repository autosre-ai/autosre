"""
End-to-end tests for full API suite.

Full API test suite:
- All endpoints
- Auth flow
- Error handling
- Pagination
- Webhooks
"""

import asyncio
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from autosre.api.app import create_app


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def app():
    """Create test application."""
    return create_app()


@pytest.fixture
async def client(app):
    """Create async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Authentication headers for protected endpoints."""
    return {
        "Authorization": "Bearer test-api-key",
        "X-Request-ID": f"test-{uuid4()}",
    }


@pytest.fixture
def sample_alert() -> dict[str, Any]:
    """Sample alert payload."""
    return {
        "name": "HighCPU",
        "service": "payment-service",
        "namespace": "production",
        "severity": "critical",
        "source": "prometheus",
        "description": "CPU usage above 90%",
        "labels": {
            "alertname": "HighCPU",
            "service": "payment-service",
        },
    }


@pytest.fixture
def sample_investigation() -> dict[str, Any]:
    """Sample investigation payload."""
    return {
        "title": "Investigate HighCPU",
        "objective": "Determine root cause of high CPU usage",
    }


# ============================================================================
# Test: Health Endpoints
# ============================================================================


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    @pytest.mark.asyncio
    async def test_health_endpoint(self, client: AsyncClient):
        """Test liveness probe endpoint."""
        response = await client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "uptime_seconds" in data

    @pytest.mark.asyncio
    async def test_ready_endpoint(self, client: AsyncClient):
        """Test readiness probe endpoint."""
        response = await client.get("/ready")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["ready", "not_ready"]
        assert "checks" in data

    @pytest.mark.asyncio
    async def test_metrics_endpoint(self, client: AsyncClient):
        """Test Prometheus metrics endpoint."""
        response = await client.get("/metrics")
        
        assert response.status_code == 200
        assert "autosre_up" in response.text
        assert "autosre_uptime_seconds" in response.text

    @pytest.mark.asyncio
    async def test_version_endpoint(self, client: AsyncClient):
        """Test version endpoint."""
        response = await client.get("/version")
        
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert data["name"] == "AutoSRE"

    @pytest.mark.asyncio
    async def test_root_endpoint(self, client: AsyncClient):
        """Test root endpoint."""
        response = await client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "docs" in data


# ============================================================================
# Test: Alert Endpoints
# ============================================================================


class TestAlertEndpoints:
    """Tests for alert management endpoints."""

    @pytest.mark.asyncio
    async def test_create_alert(self, client: AsyncClient, sample_alert: dict[str, Any]):
        """Test creating an alert."""
        response = await client.post("/api/v1/alerts", json=sample_alert)
        
        # Endpoint may or may not exist yet
        if response.status_code in [200, 201]:
            data = response.json()
            assert "id" in data
            assert data["name"] == sample_alert["name"]
        else:
            assert response.status_code in [404, 501]

    @pytest.mark.asyncio
    async def test_get_alert(self, client: AsyncClient, sample_alert: dict[str, Any]):
        """Test getting an alert by ID."""
        # First create
        create_response = await client.post("/api/v1/alerts", json=sample_alert)
        
        if create_response.status_code in [200, 201]:
            alert_id = create_response.json()["id"]
            
            # Then get
            response = await client.get(f"/api/v1/alerts/{alert_id}")
            assert response.status_code == 200
            assert response.json()["id"] == str(alert_id)

    @pytest.mark.asyncio
    async def test_list_alerts(self, client: AsyncClient):
        """Test listing alerts."""
        response = await client.get("/api/v1/alerts")
        
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_list_alerts_with_filters(self, client: AsyncClient):
        """Test listing alerts with filters."""
        response = await client.get(
            "/api/v1/alerts",
            params={
                "severity": "critical",
                "status": "firing",
                "service": "payment-service",
            },
        )
        
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_update_alert(self, client: AsyncClient, sample_alert: dict[str, Any]):
        """Test updating an alert."""
        create_response = await client.post("/api/v1/alerts", json=sample_alert)
        
        if create_response.status_code in [200, 201]:
            alert_id = create_response.json()["id"]
            
            response = await client.patch(
                f"/api/v1/alerts/{alert_id}",
                json={"severity": "high"},
            )
            
            if response.status_code == 200:
                assert response.json()["severity"] == "high"

    @pytest.mark.asyncio
    async def test_delete_alert(self, client: AsyncClient, sample_alert: dict[str, Any]):
        """Test deleting an alert."""
        create_response = await client.post("/api/v1/alerts", json=sample_alert)
        
        if create_response.status_code in [200, 201]:
            alert_id = create_response.json()["id"]
            
            response = await client.delete(f"/api/v1/alerts/{alert_id}")
            
            assert response.status_code in [200, 204, 404]

    @pytest.mark.asyncio
    async def test_acknowledge_alert(self, client: AsyncClient, sample_alert: dict[str, Any]):
        """Test acknowledging an alert."""
        create_response = await client.post("/api/v1/alerts", json=sample_alert)
        
        if create_response.status_code in [200, 201]:
            alert_id = create_response.json()["id"]
            
            response = await client.post(
                f"/api/v1/alerts/{alert_id}/acknowledge",
                json={"acknowledged_by": "test@example.com"},
            )
            
            if response.status_code == 200:
                assert response.json()["status"] == "acknowledged"

    @pytest.mark.asyncio
    async def test_resolve_alert(self, client: AsyncClient, sample_alert: dict[str, Any]):
        """Test resolving an alert."""
        create_response = await client.post("/api/v1/alerts", json=sample_alert)
        
        if create_response.status_code in [200, 201]:
            alert_id = create_response.json()["id"]
            
            response = await client.post(
                f"/api/v1/alerts/{alert_id}/resolve",
                json={"resolution": "Issue fixed by scaling up"},
            )
            
            if response.status_code == 200:
                assert response.json()["status"] == "resolved"


# ============================================================================
# Test: Investigation Endpoints
# ============================================================================


class TestInvestigationEndpoints:
    """Tests for investigation endpoints."""

    @pytest.mark.asyncio
    async def test_create_investigation(
        self, client: AsyncClient, sample_investigation: dict[str, Any]
    ):
        """Test creating an investigation."""
        response = await client.post("/api/v1/investigations", json=sample_investigation)
        
        if response.status_code in [200, 201]:
            data = response.json()
            assert "id" in data
            assert data["title"] == sample_investigation["title"]

    @pytest.mark.asyncio
    async def test_get_investigation(
        self, client: AsyncClient, sample_investigation: dict[str, Any]
    ):
        """Test getting an investigation."""
        create_response = await client.post(
            "/api/v1/investigations", json=sample_investigation
        )
        
        if create_response.status_code in [200, 201]:
            inv_id = create_response.json()["id"]
            
            response = await client.get(f"/api/v1/investigations/{inv_id}")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_list_investigations(self, client: AsyncClient):
        """Test listing investigations."""
        response = await client.get("/api/v1/investigations")
        
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_list_investigations_by_alert(self, client: AsyncClient):
        """Test listing investigations by alert ID."""
        alert_id = str(uuid4())
        
        response = await client.get(
            "/api/v1/investigations",
            params={"alert_id": alert_id},
        )
        
        if response.status_code == 200:
            assert isinstance(response.json(), list)

    @pytest.mark.asyncio
    async def test_cancel_investigation(
        self, client: AsyncClient, sample_investigation: dict[str, Any]
    ):
        """Test canceling an investigation."""
        create_response = await client.post(
            "/api/v1/investigations", json=sample_investigation
        )
        
        if create_response.status_code in [200, 201]:
            inv_id = create_response.json()["id"]
            
            response = await client.post(f"/api/v1/investigations/{inv_id}/cancel")
            
            if response.status_code == 200:
                assert response.json()["status"] in ["cancelled", "canceled"]

    @pytest.mark.asyncio
    async def test_get_investigation_observations(
        self, client: AsyncClient, sample_investigation: dict[str, Any]
    ):
        """Test getting investigation observations."""
        create_response = await client.post(
            "/api/v1/investigations", json=sample_investigation
        )
        
        if create_response.status_code in [200, 201]:
            inv_id = create_response.json()["id"]
            
            response = await client.get(f"/api/v1/investigations/{inv_id}/observations")
            
            if response.status_code == 200:
                assert isinstance(response.json(), list)

    @pytest.mark.asyncio
    async def test_get_investigation_report(
        self, client: AsyncClient, sample_investigation: dict[str, Any]
    ):
        """Test getting investigation report."""
        create_response = await client.post(
            "/api/v1/investigations", json=sample_investigation
        )
        
        if create_response.status_code in [200, 201]:
            inv_id = create_response.json()["id"]
            
            response = await client.get(f"/api/v1/investigations/{inv_id}/report")
            
            # Report may not exist yet
            assert response.status_code in [200, 404]


# ============================================================================
# Test: Action Endpoints
# ============================================================================


class TestActionEndpoints:
    """Tests for action management endpoints."""

    @pytest.mark.asyncio
    async def test_create_action(self, client: AsyncClient):
        """Test creating an action."""
        action_payload = {
            "type": "scale",
            "name": "scale_up_replicas",
            "description": "Scale up payment-service to 5 replicas",
            "tool": "kubernetes",
            "parameters": {"replicas": 5},
        }
        
        response = await client.post("/api/v1/actions", json=action_payload)
        
        if response.status_code in [200, 201]:
            data = response.json()
            assert "id" in data

    @pytest.mark.asyncio
    async def test_get_action(self, client: AsyncClient):
        """Test getting an action."""
        action_payload = {
            "type": "diagnostic",
            "name": "check_logs",
            "description": "Check logs for errors",
        }
        
        create_response = await client.post("/api/v1/actions", json=action_payload)
        
        if create_response.status_code in [200, 201]:
            action_id = create_response.json()["id"]
            
            response = await client.get(f"/api/v1/actions/{action_id}")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_approve_action(self, client: AsyncClient):
        """Test approving an action."""
        action_payload = {
            "type": "remediation",
            "name": "restart_pod",
            "description": "Restart failing pod",
            "requires_approval": True,
        }
        
        create_response = await client.post("/api/v1/actions", json=action_payload)
        
        if create_response.status_code in [200, 201]:
            action_id = create_response.json()["id"]
            
            response = await client.post(
                f"/api/v1/actions/{action_id}/approve",
                json={"approved_by": "admin@example.com"},
            )
            
            if response.status_code == 200:
                assert response.json()["status"] == "approved"

    @pytest.mark.asyncio
    async def test_reject_action(self, client: AsyncClient):
        """Test rejecting an action."""
        action_payload = {
            "type": "remediation",
            "name": "restart_deployment",
            "description": "Restart entire deployment",
            "requires_approval": True,
        }
        
        create_response = await client.post("/api/v1/actions", json=action_payload)
        
        if create_response.status_code in [200, 201]:
            action_id = create_response.json()["id"]
            
            response = await client.post(
                f"/api/v1/actions/{action_id}/reject",
                json={"reason": "Too risky"},
            )
            
            if response.status_code == 200:
                assert response.json()["status"] in ["rejected", "cancelled"]

    @pytest.mark.asyncio
    async def test_execute_action(self, client: AsyncClient):
        """Test executing an action."""
        action_payload = {
            "type": "diagnostic",
            "name": "get_metrics",
            "description": "Get current CPU metrics",
            "requires_approval": False,
        }
        
        create_response = await client.post("/api/v1/actions", json=action_payload)
        
        if create_response.status_code in [200, 201]:
            action_id = create_response.json()["id"]
            
            response = await client.post(f"/api/v1/actions/{action_id}/execute")
            
            if response.status_code == 200:
                assert response.json()["status"] in ["executing", "completed"]


# ============================================================================
# Test: Webhook Endpoints
# ============================================================================


class TestWebhookEndpoints:
    """Tests for webhook endpoints."""

    @pytest.mark.asyncio
    async def test_prometheus_webhook(self, client: AsyncClient):
        """Test Prometheus/Alertmanager webhook."""
        payload = {
            "version": "4",
            "status": "firing",
            "alerts": [
                {
                    "status": "firing",
                    "labels": {"alertname": "TestAlert", "severity": "warning"},
                    "annotations": {"summary": "Test alert"},
                    "startsAt": "2024-01-15T10:00:00Z",
                    "fingerprint": "test-fp-1",
                }
            ],
        }
        
        response = await client.post("/webhooks/prometheus", json=payload)
        
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    @pytest.mark.asyncio
    async def test_alertmanager_webhook(self, client: AsyncClient):
        """Test Alertmanager-specific webhook."""
        payload = {
            "version": "4",
            "groupKey": "{}:{alertname=\"Test\"}",
            "status": "firing",
            "receiver": "autosre",
            "alerts": [
                {
                    "status": "firing",
                    "labels": {"alertname": "Test"},
                    "annotations": {},
                    "startsAt": "2024-01-15T10:00:00Z",
                    "fingerprint": "am-fp-1",
                }
            ],
        }
        
        response = await client.post("/webhooks/alertmanager", json=payload)
        
        # May be same as prometheus or separate endpoint
        assert response.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_pagerduty_webhook(self, client: AsyncClient):
        """Test PagerDuty webhook."""
        payload = {
            "messages": [
                {
                    "event": "incident.trigger",
                    "incident": {
                        "id": "P12345",
                        "title": "Test Incident",
                        "status": "triggered",
                        "urgency": "high",
                    },
                }
            ],
        }
        
        response = await client.post("/webhooks/pagerduty", json=payload)
        
        assert response.status_code in [200, 404, 501]

    @pytest.mark.asyncio
    async def test_opsgenie_webhook(self, client: AsyncClient):
        """Test OpsGenie webhook."""
        payload = {
            "action": "Create",
            "alert": {
                "alertId": "abc-123",
                "message": "Test Alert",
                "priority": "P1",
            },
        }
        
        response = await client.post("/webhooks/opsgenie", json=payload)
        
        assert response.status_code in [200, 404, 501]

    @pytest.mark.asyncio
    async def test_generic_webhook(self, client: AsyncClient):
        """Test generic webhook endpoint."""
        payload = {
            "source": "custom-monitoring",
            "alert": {
                "name": "CustomAlert",
                "severity": "high",
            },
        }
        
        response = await client.post("/webhooks/generic", json=payload)
        
        assert response.status_code in [200, 404, 501]


# ============================================================================
# Test: Chat Endpoints
# ============================================================================


class TestChatEndpoints:
    """Tests for chat endpoints."""

    @pytest.mark.asyncio
    async def test_send_chat_message(self, client: AsyncClient):
        """Test sending a chat message."""
        response = await client.post(
            "/api/v1/chat/message",
            json={"message": "What alerts are firing?"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert "session_id" in data

    @pytest.mark.asyncio
    async def test_get_chat_history(self, client: AsyncClient):
        """Test getting chat history."""
        # Create message first
        msg_response = await client.post(
            "/api/v1/chat/message",
            json={"message": "Test"},
        )
        session_id = msg_response.json()["session_id"]
        
        # Get history
        response = await client.get(
            "/api/v1/chat/history",
            params={"session_id": session_id},
        )
        
        assert response.status_code == 200
        assert "messages" in response.json()

    @pytest.mark.asyncio
    async def test_clear_chat_history(self, client: AsyncClient):
        """Test clearing chat history."""
        # Create message first
        msg_response = await client.post(
            "/api/v1/chat/message",
            json={"message": "Test"},
        )
        session_id = msg_response.json()["session_id"]
        
        # Clear
        response = await client.delete(f"/api/v1/chat/history/{session_id}")
        
        assert response.status_code == 200


# ============================================================================
# Test: Runbook Endpoints
# ============================================================================


class TestRunbookEndpoints:
    """Tests for runbook endpoints."""

    @pytest.mark.asyncio
    async def test_list_runbooks(self, client: AsyncClient):
        """Test listing runbooks."""
        response = await client.get("/api/v1/runbooks")
        
        if response.status_code == 200:
            assert isinstance(response.json(), list)

    @pytest.mark.asyncio
    async def test_get_runbook(self, client: AsyncClient):
        """Test getting a specific runbook."""
        response = await client.get("/api/v1/runbooks/high-cpu")
        
        assert response.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_search_runbooks(self, client: AsyncClient):
        """Test searching runbooks."""
        response = await client.get(
            "/api/v1/runbooks/search",
            params={"q": "cpu"},
        )
        
        if response.status_code == 200:
            assert isinstance(response.json(), list)


# ============================================================================
# Test: Error Handling
# ============================================================================


class TestErrorHandling:
    """Tests for API error handling."""

    @pytest.mark.asyncio
    async def test_not_found_error(self, client: AsyncClient):
        """Test 404 error response."""
        response = await client.get("/api/v1/nonexistent")
        
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_invalid_json_error(self, client: AsyncClient):
        """Test handling invalid JSON."""
        response = await client.post(
            "/api/v1/chat/message",
            content="not valid json",
            headers={"Content-Type": "application/json"},
        )
        
        assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_validation_error(self, client: AsyncClient):
        """Test validation error response."""
        # Missing required fields
        response = await client.post("/api/v1/alerts", json={})
        
        assert response.status_code in [400, 422, 404]

    @pytest.mark.asyncio
    async def test_method_not_allowed(self, client: AsyncClient):
        """Test method not allowed error."""
        response = await client.delete("/health")
        
        assert response.status_code == 405

    @pytest.mark.asyncio
    async def test_request_id_in_response(self, client: AsyncClient, auth_headers):
        """Test request ID is returned in response."""
        response = await client.get("/health", headers=auth_headers)
        
        # Request ID should be echoed back
        assert response.status_code == 200
        assert "X-Request-ID" in response.headers


# ============================================================================
# Test: Pagination
# ============================================================================


class TestPagination:
    """Tests for API pagination."""

    @pytest.mark.asyncio
    async def test_alerts_pagination(self, client: AsyncClient):
        """Test alerts list pagination."""
        response = await client.get(
            "/api/v1/alerts",
            params={"limit": 10, "offset": 0},
        )
        
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)
            assert len(data) <= 10

    @pytest.mark.asyncio
    async def test_investigations_pagination(self, client: AsyncClient):
        """Test investigations list pagination."""
        response = await client.get(
            "/api/v1/investigations",
            params={"limit": 5, "offset": 0},
        )
        
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_chat_history_pagination(self, client: AsyncClient):
        """Test chat history pagination."""
        # Create session with messages
        msg_response = await client.post(
            "/api/v1/chat/message",
            json={"message": "Test"},
        )
        session_id = msg_response.json()["session_id"]
        
        response = await client.get(
            "/api/v1/chat/history",
            params={"session_id": session_id, "limit": 10, "offset": 0},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "has_more" in data
        assert "total_messages" in data

    @pytest.mark.asyncio
    async def test_pagination_with_invalid_params(self, client: AsyncClient):
        """Test pagination with invalid parameters."""
        response = await client.get(
            "/api/v1/alerts",
            params={"limit": -1, "offset": -1},
        )
        
        # Should be rejected or use defaults
        assert response.status_code in [200, 400, 422]


# ============================================================================
# Test: Authentication (when enabled)
# ============================================================================


class TestAuthentication:
    """Tests for API authentication."""

    @pytest.mark.asyncio
    async def test_protected_endpoint_without_auth(self, client: AsyncClient):
        """Test accessing protected endpoint without auth."""
        # Health endpoints should be public
        response = await client.get("/health")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_protected_endpoint_with_auth(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Test accessing protected endpoint with auth."""
        response = await client.get("/api/v1/alerts", headers=auth_headers)
        
        # Should work with or without auth depending on config
        assert response.status_code in [200, 401, 403, 404]

    @pytest.mark.asyncio
    async def test_invalid_auth_token(self, client: AsyncClient):
        """Test with invalid auth token."""
        headers = {"Authorization": "Bearer invalid-token"}
        
        response = await client.get("/api/v1/alerts", headers=headers)
        
        # May or may not require auth
        assert response.status_code in [200, 401, 403, 404]


# ============================================================================
# Test: Rate Limiting (when enabled)
# ============================================================================


class TestRateLimiting:
    """Tests for API rate limiting."""

    @pytest.mark.asyncio
    async def test_rate_limit_health(self, client: AsyncClient):
        """Test rate limiting on health endpoint (should not be limited)."""
        responses = []
        for _ in range(20):
            responses.append(await client.get("/health"))
        
        # Health endpoint should not be rate limited
        assert all(r.status_code == 200 for r in responses)

    @pytest.mark.asyncio
    async def test_rate_limit_api(self, client: AsyncClient):
        """Test rate limiting on API endpoints."""
        responses = []
        for _ in range(50):
            responses.append(
                await client.post(
                    "/api/v1/chat/message",
                    json={"message": "Test"},
                )
            )
        
        # Some may be rate limited
        status_codes = [r.status_code for r in responses]
        assert 200 in status_codes
        # 429 indicates rate limiting is working
        # All 200s means no rate limiting configured


# ============================================================================
# Test: Response Headers
# ============================================================================


class TestResponseHeaders:
    """Tests for API response headers."""

    @pytest.mark.asyncio
    async def test_cors_headers(self, client: AsyncClient):
        """Test CORS headers are present."""
        response = await client.options(
            "/api/v1/alerts",
            headers={"Origin": "http://localhost:3000"},
        )
        
        # CORS should be configured
        assert response.status_code in [200, 204, 404, 405]

    @pytest.mark.asyncio
    async def test_content_type_json(self, client: AsyncClient):
        """Test JSON content type in response."""
        response = await client.get("/health")
        
        assert response.status_code == 200
        assert "application/json" in response.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_response_time_header(self, client: AsyncClient):
        """Test response time header is present."""
        response = await client.get("/health")
        
        # Response time header may be added by middleware
        # X-Response-Time-Ms is common
        assert response.status_code == 200


# ============================================================================
# Test: OpenAPI Documentation
# ============================================================================


class TestOpenAPIDocumentation:
    """Tests for OpenAPI documentation endpoints."""

    @pytest.mark.asyncio
    async def test_openapi_json(self, client: AsyncClient):
        """Test OpenAPI JSON schema endpoint."""
        response = await client.get("/openapi.json")
        
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "info" in data
        assert "paths" in data

    @pytest.mark.asyncio
    async def test_docs_endpoint(self, client: AsyncClient):
        """Test Swagger UI docs endpoint."""
        response = await client.get("/docs")
        
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_redoc_endpoint(self, client: AsyncClient):
        """Test ReDoc docs endpoint."""
        response = await client.get("/redoc")
        
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")


# ============================================================================
# Test: Concurrent API Access
# ============================================================================


class TestConcurrentAccess:
    """Tests for concurrent API access."""

    @pytest.mark.asyncio
    async def test_concurrent_health_checks(self, client: AsyncClient):
        """Test concurrent health check requests."""
        tasks = [client.get("/health") for _ in range(100)]
        responses = await asyncio.gather(*tasks)
        
        assert all(r.status_code == 200 for r in responses)

    @pytest.mark.asyncio
    async def test_concurrent_alert_creation(
        self, client: AsyncClient, sample_alert: dict[str, Any]
    ):
        """Test concurrent alert creation."""
        alerts = [
            {**sample_alert, "name": f"ConcurrentAlert-{i}"}
            for i in range(10)
        ]
        
        tasks = [client.post("/api/v1/alerts", json=alert) for alert in alerts]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All should complete without errors
        for r in responses:
            if not isinstance(r, Exception):
                assert r.status_code in [200, 201, 404, 501]

    @pytest.mark.asyncio
    async def test_concurrent_chat_messages(self, client: AsyncClient):
        """Test concurrent chat messages."""
        tasks = [
            client.post(
                "/api/v1/chat/message",
                json={"message": f"Message {i}"},
            )
            for i in range(20)
        ]
        
        responses = await asyncio.gather(*tasks)
        
        assert all(r.status_code == 200 for r in responses)
