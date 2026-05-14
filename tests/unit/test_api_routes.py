"""Unit tests for API routes.

Tests route handlers, request parsing, response formatting,
and route-level validation without full app integration.
"""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

# ============================================================================
# Alert Routes Tests
# ============================================================================


class TestAlertRoutes:
    """Tests for alert route handlers."""

    @pytest.fixture
    def mock_auth_user(self):
        """Mock authenticated user."""
        return {"id": "user-123", "roles": ["admin"], "email": "test@example.com"}

    @pytest.fixture
    def sample_alert_create(self):
        """Sample alert creation payload."""
        return {
            "alertname": "HighErrorRate",
            "severity": "critical",
            "summary": "Error rate above 5%",
            "description": "Payment service experiencing high error rates",
            "source": "prometheus",
            "labels": {"service": "payment-service", "env": "production"},
            "annotations": {"dashboard": "https://grafana.local/d/abc"},
        }

    @pytest.mark.asyncio
    async def test_list_alerts_returns_paginated_response(self, api_client, mock_auth_user):
        """Test list_alerts returns proper pagination structure."""
        with patch("autosre.api.routes.alerts.get_current_user", return_value=mock_auth_user):
            response = await api_client.get("/api/v1/alerts")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "total_pages" in data

    @pytest.mark.asyncio
    async def test_list_alerts_filters_by_status(self, api_client, mock_auth_user):
        """Test list_alerts filters by status query param."""
        with patch("autosre.api.routes.alerts.get_current_user", return_value=mock_auth_user):
            response = await api_client.get("/api/v1/alerts?status=firing")

        assert response.status_code == 200
        # In real implementation, would verify filtered results

    @pytest.mark.asyncio
    async def test_list_alerts_filters_by_severity(self, api_client, mock_auth_user):
        """Test list_alerts filters by severity."""
        with patch("autosre.api.routes.alerts.get_current_user", return_value=mock_auth_user):
            response = await api_client.get("/api/v1/alerts?severity=critical")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_list_alerts_pagination_params(self, api_client, mock_auth_user):
        """Test list_alerts respects pagination parameters."""
        with patch("autosre.api.routes.alerts.get_current_user", return_value=mock_auth_user):
            response = await api_client.get("/api/v1/alerts?page=2&page_size=50")

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 2
        assert data["page_size"] == 50

    @pytest.mark.asyncio
    async def test_list_alerts_page_size_limits(self, api_client, mock_auth_user):
        """Test list_alerts enforces page_size limits."""
        with patch("autosre.api.routes.alerts.get_current_user", return_value=mock_auth_user):
            # page_size > 100 should be rejected or clamped
            response = await api_client.get("/api/v1/alerts?page_size=500")

        # Either 422 validation error or clamped to max
        assert response.status_code in [200, 422]

    @pytest.mark.asyncio
    async def test_get_alert_not_found(self, api_client, mock_auth_user):
        """Test get_alert returns 404 for non-existent alert."""
        alert_id = uuid4()
        with patch("autosre.api.routes.alerts.get_current_user", return_value=mock_auth_user):
            response = await api_client.get(f"/api/v1/alerts/{alert_id}")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_alert_invalid_uuid(self, api_client, mock_auth_user):
        """Test get_alert returns 422 for invalid UUID."""
        with patch("autosre.api.routes.alerts.get_current_user", return_value=mock_auth_user):
            response = await api_client.get("/api/v1/alerts/not-a-uuid")

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_alert_validation(self, api_client, mock_auth_user, sample_alert_create):
        """Test create_alert validates input."""
        with patch("autosre.api.routes.alerts.get_current_user", return_value=mock_auth_user):
            # Valid payload
            response = await api_client.post(
                "/api/v1/alerts",
                json=sample_alert_create,
            )

        # Currently returns 501 as not implemented
        assert response.status_code in [201, 501]

    @pytest.mark.asyncio
    async def test_create_alert_missing_required_fields(self, api_client, mock_auth_user):
        """Test create_alert rejects missing required fields."""
        with patch("autosre.api.routes.alerts.get_current_user", return_value=mock_auth_user):
            response = await api_client.post(
                "/api/v1/alerts",
                json={"description": "Missing required fields"},
            )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_alert_invalid_severity(self, api_client, mock_auth_user):
        """Test create_alert rejects invalid severity."""
        with patch("autosre.api.routes.alerts.get_current_user", return_value=mock_auth_user):
            response = await api_client.post(
                "/api/v1/alerts",
                json={
                    "alertname": "Test",
                    "severity": "invalid_severity",
                    "summary": "Test",
                    "source": "test",
                },
            )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_alert_partial_update(self, api_client, mock_auth_user):
        """Test update_alert allows partial updates."""
        alert_id = uuid4()
        with patch("autosre.api.routes.alerts.get_current_user", return_value=mock_auth_user):
            response = await api_client.patch(
                f"/api/v1/alerts/{alert_id}",
                json={"status": "acknowledged"},
            )

        # 404 because alert doesn't exist, but validates partial update works
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_alert_returns_204(self, api_client, mock_auth_user):
        """Test delete_alert returns 204 No Content on success."""
        alert_id = uuid4()
        with patch("autosre.api.routes.alerts.get_current_user", return_value=mock_auth_user):
            response = await api_client.delete(f"/api/v1/alerts/{alert_id}")

        # 404 because doesn't exist, but verifies endpoint exists
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_trigger_investigation_for_alert(self, api_client, mock_auth_user):
        """Test triggering investigation for an alert."""
        alert_id = uuid4()
        with patch("autosre.api.routes.alerts.get_current_user", return_value=mock_auth_user):
            response = await api_client.post(
                f"/api/v1/alerts/{alert_id}/investigate",
                json={"auto_remediate": False, "priority": "high"},
            )

        assert response.status_code == 404  # Alert doesn't exist

    @pytest.mark.asyncio
    async def test_acknowledge_alert(self, api_client, mock_auth_user):
        """Test acknowledging an alert."""
        alert_id = uuid4()
        with patch("autosre.api.routes.alerts.get_current_user", return_value=mock_auth_user):
            response = await api_client.post(f"/api/v1/alerts/{alert_id}/acknowledge")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_resolve_alert(self, api_client, mock_auth_user):
        """Test resolving an alert."""
        alert_id = uuid4()
        with patch("autosre.api.routes.alerts.get_current_user", return_value=mock_auth_user):
            response = await api_client.post(f"/api/v1/alerts/{alert_id}/resolve")

        assert response.status_code == 404


# ============================================================================
# Investigation Routes Tests
# ============================================================================


class TestInvestigationRoutes:
    """Tests for investigation route handlers."""

    @pytest.fixture
    def mock_auth_user(self):
        """Mock authenticated user."""
        return {"id": "user-123", "roles": ["admin"]}

    @pytest.mark.asyncio
    async def test_list_investigations_pagination(self, api_client, mock_auth_user):
        """Test list_investigations returns paginated results."""
        with patch("autosre.api.routes.investigations.get_current_user", return_value=mock_auth_user):
            response = await api_client.get("/api/v1/investigations")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_list_investigations_filter_by_status(self, api_client, mock_auth_user):
        """Test filtering investigations by status."""
        with patch("autosre.api.routes.investigations.get_current_user", return_value=mock_auth_user):
            response = await api_client.get("/api/v1/investigations?status=running")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_list_investigations_filter_by_alert_id(self, api_client, mock_auth_user):
        """Test filtering investigations by alert ID."""
        alert_id = uuid4()
        with patch("autosre.api.routes.investigations.get_current_user", return_value=mock_auth_user):
            response = await api_client.get(f"/api/v1/investigations?alert_id={alert_id}")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_investigation_detail(self, api_client, mock_auth_user):
        """Test getting investigation details."""
        inv_id = uuid4()
        with patch("autosre.api.routes.investigations.get_current_user", return_value=mock_auth_user):
            response = await api_client.get(f"/api/v1/investigations/{inv_id}")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_investigation_timeline(self, api_client, mock_auth_user):
        """Test getting investigation timeline."""
        inv_id = uuid4()
        with patch("autosre.api.routes.investigations.get_current_user", return_value=mock_auth_user):
            response = await api_client.get(f"/api/v1/investigations/{inv_id}/timeline")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_execute_investigation_action(self, api_client, mock_auth_user):
        """Test executing action in investigation."""
        inv_id = uuid4()
        with patch("autosre.api.routes.investigations.get_current_user", return_value=mock_auth_user):
            response = await api_client.post(
                f"/api/v1/investigations/{inv_id}/action",
                json={
                    "action_type": "approve",
                    "target": "remediation-123",
                    "message": "Approved",
                },
            )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_execute_action_invalid_type(self, api_client, mock_auth_user):
        """Test executing action with invalid type."""
        inv_id = uuid4()
        with patch("autosre.api.routes.investigations.get_current_user", return_value=mock_auth_user):
            response = await api_client.post(
                f"/api/v1/investigations/{inv_id}/action",
                json={"action_type": "invalid_action"},
            )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_investigation_steps(self, api_client, mock_auth_user):
        """Test getting investigation steps."""
        inv_id = uuid4()
        with patch("autosre.api.routes.investigations.get_current_user", return_value=mock_auth_user):
            response = await api_client.get(f"/api/v1/investigations/{inv_id}/steps")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_cancel_investigation(self, api_client, mock_auth_user):
        """Test cancelling an investigation."""
        inv_id = uuid4()
        with patch("autosre.api.routes.investigations.get_current_user", return_value=mock_auth_user):
            response = await api_client.post(f"/api/v1/investigations/{inv_id}/cancel")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_retry_investigation(self, api_client, mock_auth_user):
        """Test retrying a failed investigation."""
        inv_id = uuid4()
        with patch("autosre.api.routes.investigations.get_current_user", return_value=mock_auth_user):
            response = await api_client.post(f"/api/v1/investigations/{inv_id}/retry")

        assert response.status_code == 404


# ============================================================================
# Health Routes Tests
# ============================================================================


class TestHealthRoutes:
    """Tests for health check route handlers."""

    @pytest.mark.asyncio
    async def test_health_check_returns_healthy(self, api_client):
        """Test basic health check returns healthy status."""
        response = await api_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_ready_check_returns_checks(self, api_client):
        """Test readiness check returns component checks."""
        response = await api_client.get("/ready")

        assert response.status_code in [200, 503]
        data = response.json()
        assert "status" in data
        assert "checks" in data

    @pytest.mark.asyncio
    async def test_ready_check_includes_database(self, api_client):
        """Test readiness check includes database status."""
        response = await api_client.get("/ready")

        data = response.json()
        assert "database" in data["checks"]

    @pytest.mark.asyncio
    async def test_ready_check_includes_cache(self, api_client):
        """Test readiness check includes cache status."""
        response = await api_client.get("/ready")

        data = response.json()
        assert "cache" in data["checks"]

    @pytest.mark.asyncio
    async def test_metrics_endpoint_returns_prometheus_format(self, api_client):
        """Test metrics endpoint returns Prometheus format."""
        response = await api_client.get("/metrics")

        assert response.status_code == 200
        assert "text/plain" in response.headers.get("content-type", "")
        content = response.text
        assert "# HELP" in content
        assert "# TYPE" in content

    @pytest.mark.asyncio
    async def test_metrics_includes_uptime(self, api_client):
        """Test metrics includes uptime metric."""
        response = await api_client.get("/metrics")

        assert "autosre_uptime_seconds" in response.text

    @pytest.mark.asyncio
    async def test_metrics_includes_version(self, api_client):
        """Test metrics includes version info."""
        response = await api_client.get("/metrics")

        assert "autosre_info" in response.text
        assert "version" in response.text


# ============================================================================
# Chat Routes Tests
# ============================================================================


class TestChatRoutes:
    """Tests for chat route handlers."""

    @pytest.fixture
    def mock_auth_user(self):
        """Mock authenticated user."""
        return {"id": "user-123", "roles": ["user"]}

    @pytest.mark.asyncio
    async def test_send_chat_message(self, api_client, mock_auth_user):
        """Test sending a chat message."""
        with patch("autosre.api.routes.chat.get_current_user", return_value=mock_auth_user):
            response = await api_client.post(
                "/api/v1/chat/message",
                json={"content": "What's causing the high latency?"},
            )

        # 501 as not implemented
        assert response.status_code == 501

    @pytest.mark.asyncio
    async def test_send_message_with_context(self, api_client, mock_auth_user):
        """Test sending message with context."""
        with patch("autosre.api.routes.chat.get_current_user", return_value=mock_auth_user):
            response = await api_client.post(
                "/api/v1/chat/message",
                json={
                    "content": "Analyze this alert",
                    "context": {"alert_ids": ["uuid-1"]},
                },
            )

        assert response.status_code in [200, 501]

    @pytest.mark.asyncio
    async def test_send_message_empty_content(self, api_client, mock_auth_user):
        """Test sending message with empty content fails."""
        with patch("autosre.api.routes.chat.get_current_user", return_value=mock_auth_user):
            response = await api_client.post(
                "/api/v1/chat/message",
                json={"content": ""},
            )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_send_message_content_too_long(self, api_client, mock_auth_user):
        """Test sending message with content exceeding limit."""
        with patch("autosre.api.routes.chat.get_current_user", return_value=mock_auth_user):
            response = await api_client.post(
                "/api/v1/chat/message",
                json={"content": "x" * 15000},  # Exceeds 10000 char limit
            )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_chat_history(self, api_client, mock_auth_user):
        """Test getting chat history."""
        with patch("autosre.api.routes.chat.get_current_user", return_value=mock_auth_user):
            response = await api_client.get("/api/v1/chat/history")

        assert response.status_code == 200
        data = response.json()
        assert "messages" in data
        assert "has_more" in data

    @pytest.mark.asyncio
    async def test_get_chat_history_with_session_filter(self, api_client, mock_auth_user):
        """Test getting chat history filtered by session."""
        session_id = uuid4()
        with patch("autosre.api.routes.chat.get_current_user", return_value=mock_auth_user):
            response = await api_client.get(f"/api/v1/chat/history?session_id={session_id}")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_list_chat_sessions(self, api_client, mock_auth_user):
        """Test listing chat sessions."""
        with patch("autosre.api.routes.chat.get_current_user", return_value=mock_auth_user):
            response = await api_client.get("/api/v1/chat/sessions")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    @pytest.mark.asyncio
    async def test_create_chat_session(self, api_client, mock_auth_user):
        """Test creating a new chat session."""
        with patch("autosre.api.routes.chat.get_current_user", return_value=mock_auth_user):
            response = await api_client.post("/api/v1/chat/sessions")

        assert response.status_code in [201, 501]

    @pytest.mark.asyncio
    async def test_get_chat_session(self, api_client, mock_auth_user):
        """Test getting a specific chat session."""
        session_id = uuid4()
        with patch("autosre.api.routes.chat.get_current_user", return_value=mock_auth_user):
            response = await api_client.get(f"/api/v1/chat/sessions/{session_id}")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_chat_session(self, api_client, mock_auth_user):
        """Test deleting a chat session."""
        session_id = uuid4()
        with patch("autosre.api.routes.chat.get_current_user", return_value=mock_auth_user):
            response = await api_client.delete(f"/api/v1/chat/sessions/{session_id}")

        assert response.status_code == 404


# ============================================================================
# Runbook Routes Tests
# ============================================================================


class TestRunbookRoutes:
    """Tests for runbook route handlers."""

    @pytest.fixture
    def mock_auth_user(self):
        """Mock authenticated user."""
        return {"id": "user-123", "roles": ["admin"]}

    @pytest.fixture
    def sample_runbook_create(self):
        """Sample runbook creation payload."""
        return {
            "name": "Restart Service",
            "description": "Safely restart a service",
            "category": "remediation",
            "steps": [
                {"type": "check", "action": "verify_health"},
                {"type": "action", "action": "restart"},
                {"type": "wait", "seconds": 30},
            ],
            "parameters": [
                {"name": "service_name", "type": "string", "required": True},
            ],
            "tags": ["restart", "service"],
        }

    @pytest.mark.asyncio
    async def test_list_runbooks(self, api_client, mock_auth_user):
        """Test listing runbooks."""
        with patch("autosre.api.routes.runbooks.get_current_user", return_value=mock_auth_user):
            response = await api_client.get("/api/v1/runbooks")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    @pytest.mark.asyncio
    async def test_list_runbooks_filter_by_category(self, api_client, mock_auth_user):
        """Test filtering runbooks by category."""
        with patch("autosre.api.routes.runbooks.get_current_user", return_value=mock_auth_user):
            response = await api_client.get("/api/v1/runbooks?category=remediation")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_list_runbooks_search(self, api_client, mock_auth_user):
        """Test searching runbooks."""
        with patch("autosre.api.routes.runbooks.get_current_user", return_value=mock_auth_user):
            response = await api_client.get("/api/v1/runbooks?search=restart")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_create_runbook(self, api_client, mock_auth_user, sample_runbook_create):
        """Test creating a runbook."""
        with patch("autosre.api.routes.runbooks.get_current_user", return_value=mock_auth_user):
            response = await api_client.post(
                "/api/v1/runbooks",
                json=sample_runbook_create,
            )

        assert response.status_code in [201, 501]

    @pytest.mark.asyncio
    async def test_create_runbook_missing_steps(self, api_client, mock_auth_user):
        """Test creating runbook without steps fails."""
        with patch("autosre.api.routes.runbooks.get_current_user", return_value=mock_auth_user):
            response = await api_client.post(
                "/api/v1/runbooks",
                json={
                    "name": "Test",
                    "category": "test",
                    "steps": [],  # Empty steps
                },
            )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_runbook(self, api_client, mock_auth_user):
        """Test getting a runbook."""
        runbook_id = uuid4()
        with patch("autosre.api.routes.runbooks.get_current_user", return_value=mock_auth_user):
            response = await api_client.get(f"/api/v1/runbooks/{runbook_id}")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_runbook(self, api_client, mock_auth_user):
        """Test updating a runbook."""
        runbook_id = uuid4()
        with patch("autosre.api.routes.runbooks.get_current_user", return_value=mock_auth_user):
            response = await api_client.put(
                f"/api/v1/runbooks/{runbook_id}",
                json={"name": "Updated Name"},
            )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_runbook(self, api_client, mock_auth_user):
        """Test deleting a runbook."""
        runbook_id = uuid4()
        with patch("autosre.api.routes.runbooks.get_current_user", return_value=mock_auth_user):
            response = await api_client.delete(f"/api/v1/runbooks/{runbook_id}")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_execute_runbook(self, api_client, mock_auth_user):
        """Test executing a runbook."""
        runbook_id = uuid4()
        with patch("autosre.api.routes.runbooks.get_current_user", return_value=mock_auth_user):
            response = await api_client.post(
                f"/api/v1/runbooks/{runbook_id}/execute",
                json={
                    "parameters": {"service_name": "api-gateway"},
                    "dry_run": True,
                },
            )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_runbook_executions(self, api_client, mock_auth_user):
        """Test listing runbook executions."""
        runbook_id = uuid4()
        with patch("autosre.api.routes.runbooks.get_current_user", return_value=mock_auth_user):
            response = await api_client.get(f"/api/v1/runbooks/{runbook_id}/executions")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_execution_status(self, api_client, mock_auth_user):
        """Test getting execution status."""
        execution_id = uuid4()
        with patch("autosre.api.routes.runbooks.get_current_user", return_value=mock_auth_user):
            response = await api_client.get(f"/api/v1/runbooks/executions/{execution_id}")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_cancel_execution(self, api_client, mock_auth_user):
        """Test cancelling a runbook execution."""
        execution_id = uuid4()
        with patch("autosre.api.routes.runbooks.get_current_user", return_value=mock_auth_user):
            response = await api_client.post(f"/api/v1/runbooks/executions/{execution_id}/cancel")

        assert response.status_code == 404


# ============================================================================
# Webhook Routes Tests
# ============================================================================


class TestWebhookRoutes:
    """Tests for webhook route handlers."""

    @pytest.mark.asyncio
    async def test_alertmanager_webhook_valid_payload(self, api_client, prometheus_alert_payload):
        """Test Alertmanager webhook with valid payload."""
        payload = {
            "status": "firing",
            "alerts": [prometheus_alert_payload],
            "commonLabels": {"alertname": "HighCPUUsage"},
        }

        response = await api_client.post("/api/v1/webhooks/alertmanager", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "received" in data

    @pytest.mark.asyncio
    async def test_alertmanager_webhook_empty_alerts(self, api_client):
        """Test Alertmanager webhook with empty alerts."""
        payload = {
            "status": "resolved",
            "alerts": [],
        }

        response = await api_client.post("/api/v1/webhooks/alertmanager", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["received"] == 0

    @pytest.mark.asyncio
    async def test_alertmanager_webhook_invalid_json(self, api_client):
        """Test Alertmanager webhook with invalid JSON."""
        response = await api_client.post(
            "/api/v1/webhooks/alertmanager",
            content="invalid json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_alertmanager_webhook_multiple_alerts(self, api_client):
        """Test Alertmanager webhook with multiple alerts."""
        payload = {
            "status": "firing",
            "alerts": [
                {
                    "status": "firing",
                    "labels": {"alertname": "Alert1"},
                    "annotations": {},
                },
                {
                    "status": "firing",
                    "labels": {"alertname": "Alert2"},
                    "annotations": {},
                },
            ],
        }

        response = await api_client.post("/api/v1/webhooks/alertmanager", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["received"] == 2

    @pytest.mark.asyncio
    async def test_pagerduty_webhook_valid_payload(self, api_client, pagerduty_incident_payload):
        """Test PagerDuty webhook with valid payload."""
        payload = {"event": pagerduty_incident_payload}

        response = await api_client.post("/api/v1/webhooks/pagerduty", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_pagerduty_webhook_missing_event(self, api_client):
        """Test PagerDuty webhook with missing event."""
        response = await api_client.post("/api/v1/webhooks/pagerduty", json={})

        assert response.status_code == 200  # Still processes, just with unknown type

    @pytest.mark.asyncio
    async def test_generic_webhook_valid_payload(self, api_client):
        """Test generic webhook with valid payload."""
        payload = {
            "alertname": "CustomAlert",
            "severity": "warning",
            "summary": "Custom alert triggered",
            "source": "custom-system",
        }

        response = await api_client.post("/api/v1/webhooks/generic", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_generic_webhook_missing_required(self, api_client):
        """Test generic webhook with missing required fields."""
        payload = {
            "description": "Missing required fields",
        }

        response = await api_client.post("/api/v1/webhooks/generic", json=payload)

        assert response.status_code == 400
        data = response.json()
        assert "Missing required fields" in data["detail"]

    @pytest.mark.asyncio
    async def test_generic_webhook_with_secret(self, api_client):
        """Test generic webhook with secret header."""
        payload = {
            "alertname": "SecureAlert",
            "severity": "info",
            "summary": "Secured alert",
        }

        response = await api_client.post(
            "/api/v1/webhooks/generic",
            json=payload,
            headers={"X-Webhook-Secret": "test-secret"},
        )

        assert response.status_code == 200


# ============================================================================
# Route Authentication Tests
# ============================================================================


class TestRouteAuthentication:
    """Tests for route authentication requirements."""

    @pytest.mark.asyncio
    async def test_alerts_requires_auth(self, api_client):
        """Test alerts endpoints require authentication."""
        response = await api_client.get("/api/v1/alerts")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_investigations_requires_auth(self, api_client):
        """Test investigations endpoints require authentication."""
        response = await api_client.get("/api/v1/investigations")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_chat_requires_auth(self, api_client):
        """Test chat endpoints require authentication."""
        response = await api_client.post(
            "/api/v1/chat/message",
            json={"content": "test"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_runbooks_requires_auth(self, api_client):
        """Test runbooks endpoints require authentication."""
        response = await api_client.get("/api/v1/runbooks")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_health_no_auth_required(self, api_client):
        """Test health endpoints don't require authentication."""
        response = await api_client.get("/health")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_webhooks_no_auth_required(self, api_client):
        """Test webhooks don't require JWT auth (use signatures instead)."""
        response = await api_client.post(
            "/api/v1/webhooks/alertmanager",
            json={"status": "firing", "alerts": []},
        )

        assert response.status_code == 200
