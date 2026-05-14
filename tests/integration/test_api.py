"""Integration tests for API endpoints."""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from autosre.api.app import create_app


@pytest.fixture
def app():
    """Create test application."""
    return create_app()


@pytest.fixture
async def client(app):
    """Create async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        yield client


@pytest.fixture
def auth_headers():
    """Return auth headers for authenticated requests."""
    # Mock auth - in real tests, generate proper JWT
    return {"Authorization": "Bearer test-token"}


# ============================================================================
# Health Endpoints
# ============================================================================


@pytest.mark.asyncio
class TestHealthEndpoints:
    """Tests for health check endpoints."""

    async def test_root_endpoint(self, client):
        """Test root endpoint returns API info."""
        response = await client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "health" in data

    async def test_health_endpoint(self, client):
        """Test /health endpoint."""
        response = await client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    async def test_ready_endpoint(self, client):
        """Test /ready endpoint."""
        response = await client.get("/ready")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"


# ============================================================================
# Alert Endpoints
# ============================================================================


@pytest.mark.asyncio
class TestAlertEndpoints:
    """Tests for alert management endpoints."""

    async def test_list_alerts_empty(self, client, auth_headers):
        """Test listing alerts when empty."""
        with patch("autosre.api.routes.alerts._alerts", {}):
            response = await client.get("/api/v1/alerts", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []

    async def test_create_alert(self, client, auth_headers):
        """Test creating an alert."""
        alert_data = {
            "name": "HighErrorRate",
            "description": "Error rate above 5%",
            "severity": "critical",
            "source": "prometheus",
            "labels": {"service": "payment-service"},
        }
        
        response = await client.post(
            "/api/v1/alerts",
            json=alert_data,
            headers=auth_headers,
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["alert"]["name"] == "HighErrorRate"
        assert data["alert"]["severity"] == "critical"

    async def test_get_alert(self, client, auth_headers):
        """Test getting a specific alert."""
        # Create an alert first
        alert_data = {
            "name": "TestAlert",
            "severity": "warning",
        }
        create_response = await client.post(
            "/api/v1/alerts",
            json=alert_data,
            headers=auth_headers,
        )
        alert_id = create_response.json()["alert"]["id"]
        
        # Get the alert
        response = await client.get(
            f"/api/v1/alerts/{alert_id}",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == alert_id
        assert data["name"] == "TestAlert"

    async def test_get_alert_not_found(self, client, auth_headers):
        """Test getting non-existent alert."""
        response = await client.get(
            "/api/v1/alerts/nonexistent",
            headers=auth_headers,
        )
        
        assert response.status_code == 404

    async def test_acknowledge_alert(self, client, auth_headers):
        """Test acknowledging an alert."""
        # Create alert
        create_response = await client.post(
            "/api/v1/alerts",
            json={"name": "AckTest", "severity": "high"},
            headers=auth_headers,
        )
        alert_id = create_response.json()["alert"]["id"]
        
        # Acknowledge it
        response = await client.post(
            f"/api/v1/alerts/{alert_id}/acknowledge",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "acknowledged"
        assert data["acknowledged_at"] is not None

    async def test_resolve_alert(self, client, auth_headers):
        """Test resolving an alert."""
        # Create alert
        create_response = await client.post(
            "/api/v1/alerts",
            json={"name": "ResolveTest", "severity": "medium"},
            headers=auth_headers,
        )
        alert_id = create_response.json()["alert"]["id"]
        
        # Resolve it
        response = await client.post(
            f"/api/v1/alerts/{alert_id}/resolve",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "resolved"

    async def test_start_investigation_for_alert(self, client, auth_headers):
        """Test starting investigation for alert."""
        # Create alert
        create_response = await client.post(
            "/api/v1/alerts",
            json={"name": "InvestigateTest", "severity": "critical"},
            headers=auth_headers,
        )
        alert_id = create_response.json()["alert"]["id"]
        
        # Start investigation
        response = await client.post(
            f"/api/v1/alerts/{alert_id}/investigate",
            json={"priority": 1, "auto_remediate": False},
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["investigation"]["alert_id"] == alert_id

    async def test_filter_alerts_by_severity(self, client, auth_headers):
        """Test filtering alerts by severity."""
        # Create alerts with different severities
        await client.post(
            "/api/v1/alerts",
            json={"name": "Critical1", "severity": "critical"},
            headers=auth_headers,
        )
        await client.post(
            "/api/v1/alerts",
            json={"name": "Warning1", "severity": "warning"},
            headers=auth_headers,
        )
        
        # Filter by critical
        response = await client.get(
            "/api/v1/alerts?severity=critical",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            assert item["severity"] == "critical"

    async def test_duplicate_fingerprint_updates_existing(self, client, auth_headers):
        """Test that duplicate fingerprint updates existing alert."""
        # Create first alert
        response1 = await client.post(
            "/api/v1/alerts",
            json={
                "name": "DupeTest",
                "severity": "warning",
                "fingerprint": "unique-fp-123",
            },
            headers=auth_headers,
        )
        assert response1.status_code == 201
        
        # Create second with same fingerprint
        response2 = await client.post(
            "/api/v1/alerts",
            json={
                "name": "DupeTest",
                "severity": "warning",
                "fingerprint": "unique-fp-123",
            },
            headers=auth_headers,
        )
        
        assert response2.status_code == 201
        # Should update existing, not create new
        assert "updated" in response2.json()["message"].lower()


# ============================================================================
# Investigation Endpoints
# ============================================================================


@pytest.mark.asyncio
class TestInvestigationEndpoints:
    """Tests for investigation management endpoints."""

    async def test_list_investigations_empty(self, client, auth_headers):
        """Test listing investigations when empty."""
        with patch("autosre.api.routes.alerts._investigations", {}):
            response = await client.get(
                "/api/v1/investigations",
                headers=auth_headers,
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0

    async def test_get_investigation(self, client, auth_headers):
        """Test getting a specific investigation."""
        # Create alert and investigation
        alert_resp = await client.post(
            "/api/v1/alerts",
            json={"name": "GetInvTest", "severity": "high"},
            headers=auth_headers,
        )
        alert_id = alert_resp.json()["alert"]["id"]
        
        inv_resp = await client.post(
            f"/api/v1/alerts/{alert_id}/investigate",
            json={"priority": 2},
            headers=auth_headers,
        )
        inv_id = inv_resp.json()["investigation"]["id"]
        
        # Get investigation
        response = await client.get(
            f"/api/v1/investigations/{inv_id}",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == inv_id
        assert data["alert_id"] == alert_id

    async def test_get_investigation_timeline(self, client, auth_headers):
        """Test getting investigation timeline."""
        # Create alert and investigation
        alert_resp = await client.post(
            "/api/v1/alerts",
            json={"name": "TimelineTest", "severity": "high"},
            headers=auth_headers,
        )
        alert_id = alert_resp.json()["alert"]["id"]
        
        inv_resp = await client.post(
            f"/api/v1/alerts/{alert_id}/investigate",
            json={"priority": 2},
            headers=auth_headers,
        )
        inv_id = inv_resp.json()["investigation"]["id"]
        
        # Get timeline
        response = await client.get(
            f"/api/v1/investigations/{inv_id}/timeline",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["investigation_id"] == inv_id
        assert "events" in data

    async def test_add_timeline_event(self, client, auth_headers):
        """Test adding timeline event."""
        # Create alert and investigation
        alert_resp = await client.post(
            "/api/v1/alerts",
            json={"name": "AddEventTest", "severity": "high"},
            headers=auth_headers,
        )
        alert_id = alert_resp.json()["alert"]["id"]
        
        inv_resp = await client.post(
            f"/api/v1/alerts/{alert_id}/investigate",
            json={"priority": 2},
            headers=auth_headers,
        )
        inv_id = inv_resp.json()["investigation"]["id"]
        
        # Add event
        response = await client.post(
            f"/api/v1/investigations/{inv_id}/timeline",
            json={
                "event_type": "note",
                "message": "Test note",
            },
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Test note"

    async def test_execute_action(self, client, auth_headers):
        """Test executing action in investigation."""
        # Create alert and investigation
        alert_resp = await client.post(
            "/api/v1/alerts",
            json={"name": "ActionTest", "severity": "high"},
            headers=auth_headers,
        )
        alert_id = alert_resp.json()["alert"]["id"]
        
        inv_resp = await client.post(
            f"/api/v1/alerts/{alert_id}/investigate",
            json={"priority": 2},
            headers=auth_headers,
        )
        inv_id = inv_resp.json()["investigation"]["id"]
        
        # Execute action (dry run)
        response = await client.post(
            f"/api/v1/investigations/{inv_id}/action",
            json={
                "action_type": "command",
                "name": "check_pods",
                "command": "kubectl get pods",
                "dry_run": True,
            },
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["action"]["status"] in ("completed", "dry_run")

    async def test_complete_investigation(self, client, auth_headers):
        """Test completing an investigation."""
        # Create alert and investigation
        alert_resp = await client.post(
            "/api/v1/alerts",
            json={"name": "CompleteTest", "severity": "high"},
            headers=auth_headers,
        )
        alert_id = alert_resp.json()["alert"]["id"]
        
        inv_resp = await client.post(
            f"/api/v1/alerts/{alert_id}/investigate",
            json={"priority": 2},
            headers=auth_headers,
        )
        inv_id = inv_resp.json()["investigation"]["id"]
        
        # Complete investigation
        response = await client.post(
            f"/api/v1/investigations/{inv_id}/complete",
            params={
                "summary": "Resolved issue",
                "root_cause": "Memory leak",
                "resolution": "Increased memory limit",
            },
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["root_cause"] == "Memory leak"

    async def test_cancel_investigation(self, client, auth_headers):
        """Test cancelling an investigation."""
        # Create alert and investigation
        alert_resp = await client.post(
            "/api/v1/alerts",
            json={"name": "CancelTest", "severity": "high"},
            headers=auth_headers,
        )
        alert_id = alert_resp.json()["alert"]["id"]
        
        inv_resp = await client.post(
            f"/api/v1/alerts/{alert_id}/investigate",
            json={"priority": 2},
            headers=auth_headers,
        )
        inv_id = inv_resp.json()["investigation"]["id"]
        
        # Cancel investigation
        response = await client.post(
            f"/api/v1/investigations/{inv_id}/cancel",
            params={"reason": "False alarm"},
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"


# ============================================================================
# Chat Endpoints
# ============================================================================


@pytest.mark.asyncio
class TestChatEndpoints:
    """Tests for chat endpoints."""

    async def test_send_message(self, client, auth_headers):
        """Test sending a chat message."""
        response = await client.post(
            "/api/v1/chat/message",
            json={"message": "What's the status?"},
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert data["message"]["role"] == "assistant"
        assert len(data["message"]["content"]) > 0

    async def test_send_message_with_investigation_context(self, client, auth_headers):
        """Test sending message with investigation context."""
        # Create alert and investigation
        alert_resp = await client.post(
            "/api/v1/alerts",
            json={"name": "ChatContextTest", "severity": "high"},
            headers=auth_headers,
        )
        alert_id = alert_resp.json()["alert"]["id"]
        
        inv_resp = await client.post(
            f"/api/v1/alerts/{alert_id}/investigate",
            json={"priority": 2},
            headers=auth_headers,
        )
        inv_id = inv_resp.json()["investigation"]["id"]
        
        # Send message with context
        response = await client.post(
            "/api/v1/chat/message",
            json={
                "message": "What do you see?",
                "investigation_id": inv_id,
            },
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        # Should have context used
        assert data.get("context_used") is not None or data["message"]["investigation_id"] == inv_id

    async def test_get_chat_history(self, client, auth_headers):
        """Test getting chat history."""
        # Send a message first
        await client.post(
            "/api/v1/chat/message",
            json={"message": "Test message"},
            headers=auth_headers,
        )
        
        response = await client.get(
            "/api/v1/chat/history",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "messages" in data
        assert "total" in data


# ============================================================================
# Webhook Endpoints
# ============================================================================


@pytest.mark.asyncio
class TestWebhookEndpoints:
    """Tests for webhook receiver endpoints."""

    async def test_alertmanager_webhook(self, client):
        """Test AlertManager webhook."""
        payload = {
            "status": "firing",
            "alerts": [
                {
                    "status": "firing",
                    "labels": {
                        "alertname": "HighErrorRate",
                        "service": "payment-service",
                        "severity": "critical",
                    },
                    "annotations": {
                        "summary": "High error rate detected",
                    },
                    "startsAt": "2024-01-15T10:00:00Z",
                    "fingerprint": "webhook-test-fp",
                },
            ],
            "commonLabels": {"alertname": "HighErrorRate"},
        }
        
        response = await client.post(
            "/api/v1/webhooks/alertmanager",
            json=payload,
        )
        
        assert response.status_code == 200


# ============================================================================
# Error Handling
# ============================================================================


@pytest.mark.asyncio
class TestErrorHandling:
    """Tests for API error handling."""

    async def test_validation_error(self, client, auth_headers):
        """Test validation error response."""
        response = await client.post(
            "/api/v1/alerts",
            json={},  # Missing required 'name' field
            headers=auth_headers,
        )
        
        assert response.status_code == 422
        data = response.json()
        assert data["success"] is False
        assert "error" in data

    async def test_not_found_error(self, client, auth_headers):
        """Test 404 error response."""
        response = await client.get(
            "/api/v1/nonexistent",
            headers=auth_headers,
        )
        
        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "not_found"

    async def test_request_id_in_response(self, client, auth_headers):
        """Test request ID is included in response."""
        response = await client.get(
            "/api/v1/alerts",
            headers=auth_headers,
        )
        
        assert "X-Request-ID" in response.headers
        assert "X-Response-Time" in response.headers

    async def test_custom_request_id_honored(self, client, auth_headers):
        """Test custom request ID is honored."""
        custom_id = "my-custom-request-id"
        headers = {**auth_headers, "X-Request-ID": custom_id}
        
        response = await client.get(
            "/api/v1/alerts",
            headers=headers,
        )
        
        assert response.headers.get("X-Request-ID") == custom_id
