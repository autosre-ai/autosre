"""Integration tests for webhook handlers.

Tests webhook endpoints for receiving alerts from various sources:
- AlertManager (Prometheus)
- PagerDuty
- Generic/Custom alerts
- Batch processing
"""

import hashlib
import hmac
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from autosre.api.app import create_app

# Webhook endpoints are mounted at /webhooks, not /webhooks
WEBHOOK_BASE = "/webhooks"


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
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        yield client


@pytest.fixture
def alertmanager_payload_factory():
    """Factory for creating AlertManager payloads."""
    
    def _create(
        status: str = "firing",
        alert_count: int = 1,
        alert_name: str = "HighErrorRate",
        severity: str = "critical",
        service: str = "payment-service",
        namespace: str = "production",
    ) -> dict:
        alerts = []
        for i in range(alert_count):
            alert_data = {
                "status": status,
                "labels": {
                    "alertname": f"{alert_name}_{i}" if alert_count > 1 else alert_name,
                    "service": service,
                    "severity": severity,
                    "namespace": namespace,
                    "pod": f"{service}-abc{i}",
                },
                "annotations": {
                    "summary": f"Alert {i}: {alert_name}",
                    "description": f"Test alert {i} description",
                    "runbook_url": f"https://runbooks.example.com/{alert_name.lower()}",
                },
                "startsAt": "2024-01-15T10:00:00Z",
                "generatorURL": "http://prometheus:9090/graph",
                "fingerprint": f"fp-{alert_name.lower()}-{i}",
            }
            # Only add endsAt if resolved (AlertManager uses null or missing for firing)
            if status == "resolved":
                alert_data["endsAt"] = "2024-01-15T10:30:00Z"
            alerts.append(alert_data)
        
        return {
            "version": "4",
            "groupKey": f"{{alertname=\"{alert_name}\"}}",
            "truncatedAlerts": 0,
            "status": status,
            "receiver": "autosre-webhook",
            "groupLabels": {"alertname": alert_name},
            "commonLabels": {
                "alertname": alert_name,
                "service": service,
                "severity": severity,
            },
            "commonAnnotations": {
                "summary": f"Alerts for {service}",
            },
            "externalURL": "http://alertmanager:9093",
            "alerts": alerts,
        }
    
    return _create


@pytest.fixture
def pagerduty_payload_factory():
    """Factory for creating PagerDuty payloads."""
    
    def _create(
        event: str = "incident.triggered",
        incident_id: str = "P12345",
        title: str = "High Latency Alert",
        urgency: str = "high",
        service_name: str = "checkout-service",
        description: str = "P99 latency above 1 second",
    ) -> dict:
        return {
            "messages": [
                {
                    "event": event,
                    "incident": {
                        "id": incident_id,
                        "incident_number": 12345,
                        "title": title,
                        "status": "triggered",
                        "urgency": urgency,
                        "created_at": "2024-01-15T10:00:00Z",
                        "service": {
                            "id": "PSERVICE1",
                            "name": service_name,
                            "summary": f"{service_name} service",
                        },
                        "description": description,
                        "html_url": f"https://pagerduty.com/incidents/{incident_id}",
                        "assignees": [
                            {"summary": "oncall@example.com"}
                        ],
                    },
                    "log_entries": [
                        {
                            "type": "trigger",
                            "created_at": "2024-01-15T10:00:00Z",
                        }
                    ],
                }
            ],
        }
    
    return _create


@pytest.fixture
def generic_alert_payload_factory():
    """Factory for creating generic alert payloads."""
    
    def _create(
        name: str = "TestAlert",
        severity: str = "high",
        status: str = "firing",
        description: str = "Test alert description",
        service: str = "test-service",
        namespace: str = "production",
        labels: dict = None,
        annotations: dict = None,
    ) -> dict:
        return {
            "name": name,
            "severity": severity,
            "status": status,
            "description": description,
            "service": service,
            "namespace": namespace,
            "cluster": "prod-cluster",
            "instance": "test-instance-1",
            "labels": labels or {"team": "platform", "tier": "1"},
            "annotations": annotations or {"runbook": "https://runbooks.example.com"},
            "source": "custom",
            "raw_data": {"custom_field": "custom_value"},
        }
    
    return _create


def compute_hmac_signature(payload: bytes, secret: str) -> str:
    """Compute HMAC-SHA256 signature for payload verification."""
    return hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()


# ============================================================================
# AlertManager Webhook Tests
# ============================================================================


@pytest.mark.asyncio
class TestAlertmanagerWebhook:
    """Tests for AlertManager webhook endpoint."""

    async def test_receive_firing_alert(self, client, alertmanager_payload_factory):
        """Test receiving a firing alert from AlertManager."""
        payload = alertmanager_payload_factory(status="firing")
        
        response = await client.post(
            "/webhooks/alertmanager",
            json=payload,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "received"
        assert data["alert_count"] == 1
        assert "AlertManager" in data["message"]

    async def test_receive_resolved_alert(self, client, alertmanager_payload_factory):
        """Test receiving a resolved alert from AlertManager."""
        payload = alertmanager_payload_factory(status="resolved")
        
        response = await client.post(
            "/webhooks/alertmanager",
            json=payload,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "received"
        # Resolved alerts shouldn't create investigations
        assert len(data["investigation_ids"]) == 0

    async def test_receive_multiple_alerts(self, client, alertmanager_payload_factory):
        """Test receiving multiple alerts in a single webhook."""
        payload = alertmanager_payload_factory(
            status="firing",
            alert_count=3,
            alert_name="MultipleAlerts",
        )
        
        response = await client.post(
            "/webhooks/alertmanager",
            json=payload,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["alert_count"] == 3
        assert len(data["investigation_ids"]) == 3

    async def test_receive_alert_with_all_severities(self, client, alertmanager_payload_factory):
        """Test receiving alerts with various severity levels."""
        severities = ["critical", "high", "warning", "info"]
        
        for severity in severities:
            payload = alertmanager_payload_factory(severity=severity)
            
            response = await client.post(
                "/webhooks/alertmanager",
                json=payload,
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "received"

    async def test_receive_alert_with_signature_header(self, client, alertmanager_payload_factory):
        """Test receiving alert with X-Alertmanager-Signature header."""
        payload = alertmanager_payload_factory()
        payload_bytes = json.dumps(payload).encode("utf-8")
        signature = compute_hmac_signature(payload_bytes, "test-secret")
        
        response = await client.post(
            "/webhooks/alertmanager",
            json=payload,
            headers={"X-Alertmanager-Signature": signature},
        )
        
        assert response.status_code == 200

    async def test_alertmanager_minimal_payload(self, client):
        """Test with minimal AlertManager payload."""
        payload = {
            "status": "firing",
            "alerts": [
                {
                    "status": "firing",
                    "labels": {"alertname": "MinimalAlert"},
                }
            ],
        }
        
        response = await client.post(
            "/webhooks/alertmanager",
            json=payload,
        )
        
        assert response.status_code == 200

    async def test_alertmanager_empty_alerts_array(self, client):
        """Test AlertManager payload with empty alerts array."""
        payload = {
            "status": "firing",
            "alerts": [],
        }
        
        response = await client.post(
            "/webhooks/alertmanager",
            json=payload,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["alert_count"] == 0

    async def test_alertmanager_with_all_fields(self, client):
        """Test AlertManager payload with all optional fields populated."""
        payload = {
            "version": "4",
            "groupKey": "{alertname=\"FullTest\"}",
            "truncatedAlerts": 0,
            "status": "firing",
            "receiver": "autosre",
            "groupLabels": {"alertname": "FullTest", "cluster": "prod"},
            "commonLabels": {
                "alertname": "FullTest",
                "severity": "critical",
                "cluster": "prod",
                "env": "production",
            },
            "commonAnnotations": {
                "summary": "Full test alert",
                "description": "Comprehensive test",
            },
            "externalURL": "http://alertmanager:9093",
            "alerts": [
                {
                    "status": "firing",
                    "labels": {
                        "alertname": "FullTest",
                        "severity": "critical",
                        "service": "test-service",
                        "pod": "test-pod-abc123",
                        "container": "main",
                        "namespace": "production",
                    },
                    "annotations": {
                        "summary": "Test summary",
                        "description": "Test description",
                        "runbook_url": "https://runbooks.example.com/test",
                        "dashboard_url": "https://grafana.example.com/test",
                    },
                    "startsAt": "2024-01-15T10:00:00Z",
                    "generatorURL": "http://prometheus:9090/graph?q=test",
                    "fingerprint": "abc123def456",
                },
            ],
        }
        
        response = await client.post(
            "/webhooks/alertmanager",
            json=payload,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "received"
        assert data["alert_count"] == 1


# ============================================================================
# PagerDuty Webhook Tests
# ============================================================================


@pytest.mark.asyncio
class TestPagerDutyWebhook:
    """Tests for PagerDuty webhook endpoint."""

    async def test_receive_triggered_incident(self, client, pagerduty_payload_factory):
        """Test receiving a triggered incident from PagerDuty."""
        payload = pagerduty_payload_factory(event="incident.triggered")
        
        response = await client.post(
            "/webhooks/pagerduty",
            json=payload,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "received"
        assert data["alert_count"] == 1
        assert "PagerDuty" in data["message"]

    async def test_receive_acknowledged_incident(self, client, pagerduty_payload_factory):
        """Test receiving an acknowledged incident (should not create investigation)."""
        payload = pagerduty_payload_factory(event="incident.acknowledged")
        
        response = await client.post(
            "/webhooks/pagerduty",
            json=payload,
        )
        
        assert response.status_code == 200
        data = response.json()
        # Acknowledged events shouldn't create new investigations
        assert data["alert_count"] == 0

    async def test_receive_resolved_incident(self, client, pagerduty_payload_factory):
        """Test receiving a resolved incident from PagerDuty."""
        payload = pagerduty_payload_factory(event="incident.resolved")
        
        response = await client.post(
            "/webhooks/pagerduty",
            json=payload,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["alert_count"] == 0

    async def test_receive_high_urgency_incident(self, client, pagerduty_payload_factory):
        """Test receiving a high urgency incident."""
        payload = pagerduty_payload_factory(urgency="high")
        
        response = await client.post(
            "/webhooks/pagerduty",
            json=payload,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "received"

    async def test_receive_low_urgency_incident(self, client, pagerduty_payload_factory):
        """Test receiving a low urgency incident."""
        payload = pagerduty_payload_factory(urgency="low")
        
        response = await client.post(
            "/webhooks/pagerduty",
            json=payload,
        )
        
        assert response.status_code == 200

    async def test_receive_multiple_incidents(self, client, pagerduty_payload_factory):
        """Test receiving multiple incidents in a single payload."""
        # Create a payload with multiple messages
        payload = {"messages": []}
        for i in range(3):
            base = pagerduty_payload_factory(
                incident_id=f"P{12345 + i}",
                title=f"Incident {i}",
            )
            payload["messages"].extend(base["messages"])
        
        response = await client.post(
            "/webhooks/pagerduty",
            json=payload,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["alert_count"] == 3

    async def test_pagerduty_empty_messages(self, client):
        """Test PagerDuty payload with empty messages array."""
        payload = {"messages": []}
        
        response = await client.post(
            "/webhooks/pagerduty",
            json=payload,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["alert_count"] == 0

    async def test_pagerduty_with_minimal_incident(self, client):
        """Test PagerDuty with minimal incident data."""
        payload = {
            "messages": [
                {
                    "event": "incident.triggered",
                    "incident": {
                        "id": "P99999",
                        "title": "Minimal Incident",
                    },
                }
            ],
        }
        
        response = await client.post(
            "/webhooks/pagerduty",
            json=payload,
        )
        
        assert response.status_code == 200


# ============================================================================
# Generic Webhook Tests
# ============================================================================


@pytest.mark.asyncio
class TestGenericWebhook:
    """Tests for generic/custom webhook endpoint."""

    async def test_receive_generic_alert(self, client, generic_alert_payload_factory):
        """Test receiving a generic alert."""
        payload = generic_alert_payload_factory()
        
        response = await client.post(
            "/webhooks/generic",
            json=payload,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "received"
        assert data["alert_count"] == 1

    async def test_generic_alert_with_api_key(self, client, generic_alert_payload_factory):
        """Test receiving alert with X-API-Key header."""
        payload = generic_alert_payload_factory()
        
        response = await client.post(
            "/webhooks/generic",
            json=payload,
            headers={"X-API-Key": "test-api-key"},
        )
        
        assert response.status_code == 200

    async def test_generic_alert_all_severities(self, client, generic_alert_payload_factory):
        """Test generic alerts with all severity levels."""
        severities = ["critical", "high", "medium", "low", "info"]
        
        for severity in severities:
            payload = generic_alert_payload_factory(severity=severity)
            
            response = await client.post(
                "/webhooks/generic",
                json=payload,
            )
            
            assert response.status_code == 200

    async def test_generic_alert_resolved_status(self, client, generic_alert_payload_factory):
        """Test generic alert with resolved status."""
        payload = generic_alert_payload_factory(status="resolved")
        
        response = await client.post(
            "/webhooks/generic",
            json=payload,
        )
        
        assert response.status_code == 200
        data = response.json()
        # Resolved alerts shouldn't create investigations
        assert len(data["investigation_ids"]) == 0

    async def test_generic_alert_minimal_payload(self, client):
        """Test generic alert with minimal required fields."""
        payload = {"name": "MinimalAlert"}
        
        response = await client.post(
            "/webhooks/generic",
            json=payload,
        )
        
        assert response.status_code == 200

    async def test_generic_alert_custom_labels(self, client, generic_alert_payload_factory):
        """Test generic alert with custom labels."""
        payload = generic_alert_payload_factory(
            labels={
                "team": "sre",
                "environment": "production",
                "region": "us-east-1",
                "priority": "P1",
                "custom_tag": "test",
            },
        )
        
        response = await client.post(
            "/webhooks/generic",
            json=payload,
        )
        
        assert response.status_code == 200

    async def test_generic_alert_with_raw_data(self, client, generic_alert_payload_factory):
        """Test generic alert with raw_data field."""
        payload = generic_alert_payload_factory()
        payload["raw_data"] = {
            "trace_id": "abc123",
            "span_id": "def456",
            "custom_metrics": {"value": 100, "threshold": 80},
        }
        
        response = await client.post(
            "/webhooks/generic",
            json=payload,
        )
        
        assert response.status_code == 200

    async def test_generic_alert_missing_name(self, client):
        """Test generic alert without required name field."""
        payload = {
            "severity": "high",
            "description": "Missing name",
        }
        
        response = await client.post(
            "/webhooks/generic",
            json=payload,
        )
        
        # Should fail validation
        assert response.status_code == 422


# ============================================================================
# Batch Webhook Tests
# ============================================================================


@pytest.mark.asyncio
class TestBatchWebhook:
    """Tests for batch webhook endpoint."""

    async def test_batch_single_alert(self, client, generic_alert_payload_factory):
        """Test batch webhook with single alert."""
        alerts = [generic_alert_payload_factory()]
        
        response = await client.post(
            "/webhooks/batch",
            json=alerts,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["alert_count"] == 1

    async def test_batch_multiple_alerts(self, client, generic_alert_payload_factory):
        """Test batch webhook with multiple alerts."""
        alerts = [
            generic_alert_payload_factory(name=f"BatchAlert{i}", service=f"service-{i}")
            for i in range(5)
        ]
        
        response = await client.post(
            "/webhooks/batch",
            json=alerts,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["alert_count"] == 5
        assert len(data["investigation_ids"]) == 5

    async def test_batch_mixed_severities(self, client, generic_alert_payload_factory):
        """Test batch webhook with mixed severity alerts."""
        severities = ["critical", "high", "medium", "low", "info"]
        alerts = [
            generic_alert_payload_factory(name=f"Alert{i}", severity=sev)
            for i, sev in enumerate(severities)
        ]
        
        response = await client.post(
            "/webhooks/batch",
            json=alerts,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["alert_count"] == 5

    async def test_batch_mixed_status(self, client, generic_alert_payload_factory):
        """Test batch webhook with mixed status alerts."""
        alerts = [
            generic_alert_payload_factory(name="FiringAlert", status="firing"),
            generic_alert_payload_factory(name="ResolvedAlert", status="resolved"),
            generic_alert_payload_factory(name="AnotherFiring", status="firing"),
        ]
        
        response = await client.post(
            "/webhooks/batch",
            json=alerts,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["alert_count"] == 3
        # Only firing alerts should create investigations
        assert len(data["investigation_ids"]) == 2

    async def test_batch_empty_array(self, client):
        """Test batch webhook with empty array."""
        response = await client.post(
            "/webhooks/batch",
            json=[],
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["alert_count"] == 0

    async def test_batch_large_payload(self, client, generic_alert_payload_factory):
        """Test batch webhook with large number of alerts."""
        alerts = [
            generic_alert_payload_factory(name=f"Alert{i}")
            for i in range(50)
        ]
        
        response = await client.post(
            "/webhooks/batch",
            json=alerts,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["alert_count"] == 50

    async def test_batch_with_api_key(self, client, generic_alert_payload_factory):
        """Test batch webhook with X-API-Key header."""
        alerts = [generic_alert_payload_factory()]
        
        response = await client.post(
            "/webhooks/batch",
            json=alerts,
            headers={"X-API-Key": "test-api-key"},
        )
        
        assert response.status_code == 200


# ============================================================================
# Test Webhook Endpoint Tests
# ============================================================================


@pytest.mark.asyncio
class TestTestWebhook:
    """Tests for test webhook endpoint."""

    async def test_test_webhook_json(self, client):
        """Test the test webhook with JSON payload."""
        payload = {"test": "data", "key": "value"}
        
        response = await client.post(
            "/webhooks/test",
            json=payload,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "received"
        assert "successfully" in data["message"].lower()

    async def test_test_webhook_plain_text(self, client):
        """Test the test webhook with plain text payload."""
        response = await client.post(
            "/webhooks/test",
            content=b"plain text payload",
            headers={"Content-Type": "text/plain"},
        )
        
        assert response.status_code == 200

    async def test_test_webhook_empty(self, client):
        """Test the test webhook with empty payload."""
        response = await client.post(
            "/webhooks/test",
            content=b"",
        )
        
        assert response.status_code == 200

    async def test_test_webhook_returns_zero_alerts(self, client):
        """Test that test webhook doesn't process alerts."""
        response = await client.post(
            "/webhooks/test",
            json={"alerts": [{"name": "Test"}]},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["alert_count"] == 0


# ============================================================================
# Error Handling Tests
# ============================================================================


@pytest.mark.asyncio
class TestWebhookErrorHandling:
    """Tests for webhook error handling."""

    async def test_invalid_json_payload(self, client):
        """Test handling of invalid JSON."""
        response = await client.post(
            "/webhooks/alertmanager",
            content=b"not valid json",
            headers={"Content-Type": "application/json"},
        )
        
        assert response.status_code == 422

    async def test_missing_required_field(self, client):
        """Test handling of missing required fields."""
        # AlertManager requires 'alerts' field
        payload = {"status": "firing"}
        
        response = await client.post(
            "/webhooks/alertmanager",
            json=payload,
        )
        
        assert response.status_code == 422

    async def test_invalid_field_type(self, client):
        """Test handling of invalid field types."""
        payload = {
            "status": "firing",
            "alerts": "not an array",  # Should be an array
        }
        
        response = await client.post(
            "/webhooks/alertmanager",
            json=payload,
        )
        
        assert response.status_code == 422

    async def test_malformed_alert_in_batch(self, client, generic_alert_payload_factory):
        """Test batch with one malformed alert."""
        alerts = [
            generic_alert_payload_factory(name="ValidAlert"),
            {"invalid": "no name field"},  # Missing required 'name'
            generic_alert_payload_factory(name="AnotherValid"),
        ]
        
        response = await client.post(
            "/webhooks/batch",
            json=alerts,
        )
        
        # Should fail validation for the malformed alert
        assert response.status_code == 422


# ============================================================================
# Response Format Tests
# ============================================================================


@pytest.mark.asyncio
class TestWebhookResponseFormat:
    """Tests for webhook response format consistency."""

    async def test_response_has_status(self, client, alertmanager_payload_factory):
        """Test response includes status field."""
        payload = alertmanager_payload_factory()
        
        response = await client.post(
            "/webhooks/alertmanager",
            json=payload,
        )
        
        data = response.json()
        assert "status" in data
        assert data["status"] in ["received", "error"]

    async def test_response_has_message(self, client, alertmanager_payload_factory):
        """Test response includes message field."""
        payload = alertmanager_payload_factory()
        
        response = await client.post(
            "/webhooks/alertmanager",
            json=payload,
        )
        
        data = response.json()
        assert "message" in data
        assert len(data["message"]) > 0

    async def test_response_has_alert_count(self, client, alertmanager_payload_factory):
        """Test response includes alert_count field."""
        payload = alertmanager_payload_factory()
        
        response = await client.post(
            "/webhooks/alertmanager",
            json=payload,
        )
        
        data = response.json()
        assert "alert_count" in data
        assert isinstance(data["alert_count"], int)

    async def test_response_has_investigation_ids(self, client, alertmanager_payload_factory):
        """Test response includes investigation_ids field."""
        payload = alertmanager_payload_factory()
        
        response = await client.post(
            "/webhooks/alertmanager",
            json=payload,
        )
        
        data = response.json()
        assert "investigation_ids" in data
        assert isinstance(data["investigation_ids"], list)

    async def test_response_has_timestamp(self, client, alertmanager_payload_factory):
        """Test response includes timestamp field."""
        payload = alertmanager_payload_factory()
        
        response = await client.post(
            "/webhooks/alertmanager",
            json=payload,
        )
        
        data = response.json()
        assert "timestamp" in data
        # Should be a valid ISO timestamp
        datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))


# ============================================================================
# Signature Validation Tests
# ============================================================================


@pytest.mark.asyncio
class TestSignatureValidation:
    """Tests for webhook signature validation (when implemented)."""

    async def test_valid_hmac_signature_accepted(self, client, alertmanager_payload_factory):
        """Test that valid HMAC signature is accepted."""
        payload = alertmanager_payload_factory()
        payload_bytes = json.dumps(payload).encode("utf-8")
        
        # Create valid signature (implementation may vary)
        secret = "webhook-secret"
        signature = f"sha256={compute_hmac_signature(payload_bytes, secret)}"
        
        response = await client.post(
            "/webhooks/alertmanager",
            json=payload,
            headers={"X-Alertmanager-Signature": signature},
        )
        
        # Should succeed (signature validation may be optional)
        assert response.status_code == 200

    async def test_missing_signature_allowed_when_optional(self, client, alertmanager_payload_factory):
        """Test that missing signature is allowed when validation is optional."""
        payload = alertmanager_payload_factory()
        
        response = await client.post(
            "/webhooks/alertmanager",
            json=payload,
            # No signature header
        )
        
        assert response.status_code == 200


# ============================================================================
# Concurrent Request Tests
# ============================================================================


@pytest.mark.asyncio
class TestConcurrentWebhookRequests:
    """Tests for handling concurrent webhook requests."""

    async def test_concurrent_alertmanager_webhooks(self, client, alertmanager_payload_factory):
        """Test handling concurrent AlertManager webhooks."""
        import asyncio
        
        payloads = [
            alertmanager_payload_factory(alert_name=f"ConcurrentAlert{i}")
            for i in range(10)
        ]
        
        async def send_webhook(payload):
            return await client.post(
                "/webhooks/alertmanager",
                json=payload,
            )
        
        responses = await asyncio.gather(*[
            send_webhook(p) for p in payloads
        ])
        
        # All should succeed
        assert all(r.status_code == 200 for r in responses)
        
        # Total alerts processed should be 10
        total_alerts = sum(r.json()["alert_count"] for r in responses)
        assert total_alerts == 10

    async def test_concurrent_mixed_webhooks(self, client, alertmanager_payload_factory, pagerduty_payload_factory, generic_alert_payload_factory):
        """Test handling concurrent webhooks from different sources."""
        import asyncio
        
        requests = [
            ("alertmanager", alertmanager_payload_factory()),
            ("pagerduty", pagerduty_payload_factory()),
            ("generic", generic_alert_payload_factory()),
            ("alertmanager", alertmanager_payload_factory(alert_name="Second")),
            ("generic", generic_alert_payload_factory(name="SecondGeneric")),
        ]
        
        async def send_webhook(endpoint, payload):
            return await client.post(
                f"/webhooks/{endpoint}",
                json=payload,
            )
        
        responses = await asyncio.gather(*[
            send_webhook(ep, p) for ep, p in requests
        ])
        
        assert all(r.status_code == 200 for r in responses)
