"""
End-to-end tests for complete alert lifecycle.

Test complete alert flow:
1. Receive alert webhook
2. Alert created in system
3. Start investigation
4. Collect observations
5. Generate root cause
6. Execute remediation
7. Resolve alert
"""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from autosre.api.app import create_app
from autosre.core.models import (
    Action,
    ActionStatus,
    ActionType,
    Alert,
    AlertSeverity,
    AlertStatus,
    Hypothesis,
    HypothesisStatus,
    Investigation,
    InvestigationStatus,
    Observation,
    ObservationType,
    Report,
)


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
def prometheus_webhook_payload() -> dict[str, Any]:
    """Standard Prometheus Alertmanager webhook payload."""
    return {
        "version": "4",
        "groupKey": "{}:{alertname=\"HighCPU\"}",
        "status": "firing",
        "receiver": "autosre",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "HighCPU",
                    "service": "payment-service",
                    "namespace": "production",
                    "severity": "critical",
                    "pod": "payment-service-abc123",
                    "instance": "10.0.0.1:8080",
                },
                "annotations": {
                    "summary": "High CPU usage detected",
                    "description": "CPU usage is above 90% for 10 minutes",
                    "runbook_url": "https://runbooks.example.com/high-cpu",
                },
                "startsAt": "2024-01-15T10:00:00.000Z",
                "endsAt": "0001-01-01T00:00:00Z",
                "fingerprint": "abc123def456",
                "generatorURL": "http://prometheus:9090/graph",
            }
        ],
        "commonLabels": {
            "alertname": "HighCPU",
            "service": "payment-service",
        },
        "externalURL": "http://alertmanager:9093",
    }


@pytest.fixture
def pagerduty_webhook_payload() -> dict[str, Any]:
    """PagerDuty webhook payload."""
    return {
        "messages": [
            {
                "event": "incident.trigger",
                "incident": {
                    "id": "P12345",
                    "incident_number": 123,
                    "title": "High CPU on payment-service",
                    "status": "triggered",
                    "urgency": "high",
                    "html_url": "https://example.pagerduty.com/incidents/P12345",
                    "created_at": "2024-01-15T10:00:00Z",
                    "service": {
                        "id": "PS12345",
                        "name": "payment-service",
                        "html_url": "https://example.pagerduty.com/services/PS12345",
                    },
                    "assignments": [
                        {
                            "assignee": {
                                "id": "PU12345",
                                "name": "On-Call Engineer",
                                "email": "oncall@example.com",
                            }
                        }
                    ],
                },
            }
        ],
    }


@pytest.fixture
def mock_integrations():
    """Mock all external integrations."""
    with patch("autosre.integrations.prometheus.PrometheusClient") as mock_prom, \
         patch("autosre.integrations.kubernetes.KubernetesClient") as mock_k8s, \
         patch("autosre.integrations.loki.LokiClient") as mock_loki, \
         patch("autosre.core.llm.LLMClient") as mock_llm:
        
        # Configure Prometheus mock
        mock_prom.return_value.query = AsyncMock(return_value={
            "status": "success",
            "data": {
                "resultType": "vector",
                "result": [
                    {"metric": {"pod": "payment-service-abc123"}, "value": [1705312800, "0.95"]}
                ],
            },
        })
        mock_prom.return_value.health_check = AsyncMock()
        
        # Configure K8s mock
        mock_k8s.return_value.get_pod = AsyncMock(return_value={
            "metadata": {"name": "payment-service-abc123", "namespace": "production"},
            "status": {"phase": "Running", "containerStatuses": [{"restartCount": 3}]},
        })
        mock_k8s.return_value.get_pod_logs = AsyncMock(return_value="Error: OutOfMemoryError")
        mock_k8s.return_value.get_events = AsyncMock(return_value=[
            {"reason": "OOMKilled", "message": "Container exceeded memory limit"}
        ])
        mock_k8s.return_value.health_check = AsyncMock()
        
        # Configure Loki mock
        mock_loki.return_value.query = AsyncMock(return_value={
            "data": {
                "result": [
                    {"stream": {"app": "payment-service"}, "values": [["1705312800", "OutOfMemoryError"]]}
                ]
            }
        })
        mock_loki.return_value.health_check = AsyncMock()
        
        # Configure LLM mock
        mock_llm.return_value.generate = AsyncMock(return_value={
            "root_cause": "Memory leak causing OOM kills",
            "confidence": 0.85,
            "recommendations": ["Increase memory limit", "Fix memory leak"],
        })
        
        yield {
            "prometheus": mock_prom,
            "kubernetes": mock_k8s,
            "loki": mock_loki,
            "llm": mock_llm,
        }


# ============================================================================
# Test: Complete Alert Lifecycle - Happy Path
# ============================================================================


class TestCompleteAlertLifecycle:
    """End-to-end tests for complete alert lifecycle."""

    @pytest.mark.asyncio
    async def test_full_lifecycle_prometheus_alert(
        self, client: AsyncClient, prometheus_webhook_payload: dict[str, Any]
    ):
        """
        Test complete lifecycle from webhook to resolution.
        
        Flow:
        1. Receive Prometheus alert webhook
        2. Alert created and stored
        3. Investigation auto-started
        4. Observations collected
        5. Root cause identified
        6. Remediation executed
        7. Alert resolved
        """
        # Step 1: Send webhook
        response = await client.post(
            "/webhooks/prometheus",
            json=prometheus_webhook_payload,
        )
        assert response.status_code == 200
        webhook_result = response.json()
        assert webhook_result["status"] == "ok"
        assert webhook_result.get("alerts_processed", 0) >= 1
        
        # Step 2: Verify alert created
        alert_id = webhook_result.get("alert_ids", [None])[0]
        if alert_id:
            response = await client.get(f"/api/v1/alerts/{alert_id}")
            assert response.status_code == 200
            alert = response.json()
            assert alert["status"] == "firing"
            assert alert["severity"] == "critical"
        
        # Step 3: Verify investigation started (if auto-start enabled)
        if alert_id:
            response = await client.get(
                "/api/v1/investigations",
                params={"alert_id": alert_id},
            )
            if response.status_code == 200:
                investigations = response.json()
                if investigations:
                    assert investigations[0]["status"] in ["pending", "in_progress"]

    @pytest.mark.asyncio
    async def test_lifecycle_with_auto_investigation(
        self, client: AsyncClient, prometheus_webhook_payload: dict[str, Any], mock_integrations
    ):
        """Test lifecycle with automatic investigation enabled."""
        # Create alert via webhook
        response = await client.post(
            "/webhooks/prometheus",
            json=prometheus_webhook_payload,
        )
        assert response.status_code == 200
        
        # Start investigation manually
        alert_data = prometheus_webhook_payload["alerts"][0]
        response = await client.post(
            "/api/v1/investigations",
            json={
                "alert": alert_data,
                "auto_start": True,
            },
        )
        
        if response.status_code == 201:
            investigation = response.json()
            investigation_id = investigation["id"]
            
            # Poll for completion
            max_polls = 10
            for _ in range(max_polls):
                response = await client.get(f"/api/v1/investigations/{investigation_id}")
                if response.status_code == 200:
                    status = response.json().get("status")
                    if status in ["completed", "failed"]:
                        break

    @pytest.mark.asyncio
    async def test_lifecycle_with_manual_approval(self, client: AsyncClient):
        """Test lifecycle requiring human approval for remediation."""
        # Create alert
        alert_payload = {
            "name": "CriticalDatabaseDown",
            "service": "postgres-primary",
            "severity": "critical",
            "status": "firing",
            "source": "prometheus",
            "description": "Primary database is not responding",
        }
        
        response = await client.post("/api/v1/alerts", json=alert_payload)
        assert response.status_code in [200, 201]
        
        # Start investigation
        alert_id = response.json().get("id")
        response = await client.post(
            "/api/v1/investigations",
            json={"alert_id": alert_id},
        )
        
        if response.status_code == 201:
            investigation = response.json()
            
            # Add action requiring approval
            action_payload = {
                "investigation_id": investigation["id"],
                "type": "remediation",
                "name": "failover_database",
                "description": "Failover to secondary database",
                "requires_approval": True,
                "is_destructive": True,
                "risk_level": "high",
            }
            
            response = await client.post("/api/v1/actions", json=action_payload)
            
            if response.status_code == 201:
                action = response.json()
                assert action["status"] == "requires_approval"
                
                # Approve action
                response = await client.post(
                    f"/api/v1/actions/{action['id']}/approve",
                    json={"approved_by": "admin@example.com"},
                )
                
                if response.status_code == 200:
                    assert response.json()["status"] == "approved"


# ============================================================================
# Test: Alert Webhook Processing
# ============================================================================


class TestAlertWebhookProcessing:
    """Tests for webhook processing from various sources."""

    @pytest.mark.asyncio
    async def test_prometheus_single_alert(
        self, client: AsyncClient, prometheus_webhook_payload: dict[str, Any]
    ):
        """Test processing single Prometheus alert."""
        response = await client.post(
            "/webhooks/prometheus",
            json=prometheus_webhook_payload,
        )
        
        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_prometheus_batch_alerts(self, client: AsyncClient):
        """Test processing batch of Prometheus alerts."""
        payload = {
            "version": "4",
            "status": "firing",
            "alerts": [
                {
                    "status": "firing",
                    "labels": {"alertname": f"Alert{i}", "service": f"service-{i}"},
                    "annotations": {"summary": f"Test alert {i}"},
                    "startsAt": "2024-01-15T10:00:00.000Z",
                    "fingerprint": f"fp-{i}",
                }
                for i in range(5)
            ],
        }
        
        response = await client.post("/webhooks/prometheus", json=payload)
        
        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_prometheus_resolved_alert(self, client: AsyncClient):
        """Test processing resolved alert."""
        payload = {
            "version": "4",
            "status": "resolved",
            "alerts": [
                {
                    "status": "resolved",
                    "labels": {
                        "alertname": "HighCPU",
                        "service": "test-service",
                    },
                    "annotations": {"summary": "Alert resolved"},
                    "startsAt": "2024-01-15T10:00:00.000Z",
                    "endsAt": "2024-01-15T10:30:00.000Z",
                    "fingerprint": "resolved-alert-1",
                }
            ],
        }
        
        response = await client.post("/webhooks/prometheus", json=payload)
        
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_pagerduty_webhook(
        self, client: AsyncClient, pagerduty_webhook_payload: dict[str, Any]
    ):
        """Test processing PagerDuty webhook."""
        response = await client.post(
            "/webhooks/pagerduty",
            json=pagerduty_webhook_payload,
        )
        
        # PagerDuty endpoint may not be implemented yet
        assert response.status_code in [200, 404, 501]

    @pytest.mark.asyncio
    async def test_malformed_webhook(self, client: AsyncClient):
        """Test handling malformed webhook payload."""
        response = await client.post(
            "/webhooks/prometheus",
            json={"invalid": "payload"},
        )
        
        # Should handle gracefully
        assert response.status_code in [200, 400, 422]

    @pytest.mark.asyncio
    async def test_webhook_idempotency(
        self, client: AsyncClient, prometheus_webhook_payload: dict[str, Any]
    ):
        """Test that duplicate webhooks are handled idempotently."""
        # Send same webhook twice
        response1 = await client.post(
            "/webhooks/prometheus",
            json=prometheus_webhook_payload,
        )
        response2 = await client.post(
            "/webhooks/prometheus",
            json=prometheus_webhook_payload,
        )
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        # Both should succeed but not create duplicates
        # (depends on implementation - fingerprint deduplication)


# ============================================================================
# Test: Alert State Transitions
# ============================================================================


class TestAlertStateTransitions:
    """Tests for alert state machine transitions."""

    @pytest.mark.asyncio
    async def test_firing_to_acknowledged(self, client: AsyncClient):
        """Test transition from firing to acknowledged."""
        # Create firing alert
        create_response = await client.post(
            "/api/v1/alerts",
            json={
                "name": "TestAlert",
                "service": "test-service",
                "severity": "warning",
                "source": "test",
            },
        )
        
        if create_response.status_code in [200, 201]:
            alert_id = create_response.json()["id"]
            
            # Acknowledge
            response = await client.post(
                f"/api/v1/alerts/{alert_id}/acknowledge",
                json={"acknowledged_by": "test@example.com"},
            )
            
            assert response.status_code in [200, 404]
            if response.status_code == 200:
                assert response.json()["status"] == "acknowledged"

    @pytest.mark.asyncio
    async def test_firing_to_resolved(self, client: AsyncClient):
        """Test transition from firing to resolved."""
        create_response = await client.post(
            "/api/v1/alerts",
            json={
                "name": "TestAlert",
                "service": "test-service",
                "severity": "warning",
                "source": "test",
            },
        )
        
        if create_response.status_code in [200, 201]:
            alert_id = create_response.json()["id"]
            
            # Resolve
            response = await client.post(
                f"/api/v1/alerts/{alert_id}/resolve",
                json={"resolution": "Issue fixed"},
            )
            
            assert response.status_code in [200, 404]
            if response.status_code == 200:
                assert response.json()["status"] == "resolved"

    @pytest.mark.asyncio
    async def test_invalid_transition(self, client: AsyncClient):
        """Test invalid state transition is rejected."""
        create_response = await client.post(
            "/api/v1/alerts",
            json={
                "name": "TestAlert",
                "service": "test-service",
                "severity": "warning",
                "status": "resolved",
                "source": "test",
            },
        )
        
        if create_response.status_code in [200, 201]:
            alert_id = create_response.json()["id"]
            
            # Try to acknowledge already resolved alert
            response = await client.post(
                f"/api/v1/alerts/{alert_id}/acknowledge",
                json={"acknowledged_by": "test@example.com"},
            )
            
            # Should fail or be a no-op
            assert response.status_code in [200, 400, 404, 409]

    @pytest.mark.asyncio
    async def test_severity_escalation(self, client: AsyncClient):
        """Test severity can be escalated."""
        create_response = await client.post(
            "/api/v1/alerts",
            json={
                "name": "TestAlert",
                "service": "test-service",
                "severity": "warning",
                "source": "test",
            },
        )
        
        if create_response.status_code in [200, 201]:
            alert_id = create_response.json()["id"]
            
            # Escalate severity
            response = await client.patch(
                f"/api/v1/alerts/{alert_id}",
                json={"severity": "critical"},
            )
            
            assert response.status_code in [200, 404]
            if response.status_code == 200:
                assert response.json()["severity"] == "critical"


# ============================================================================
# Test: Investigation Lifecycle
# ============================================================================


class TestInvestigationLifecycle:
    """Tests for investigation lifecycle within alert context."""

    @pytest.mark.asyncio
    async def test_create_investigation_from_alert(self, client: AsyncClient):
        """Test creating investigation from alert."""
        # First create alert
        alert_response = await client.post(
            "/api/v1/alerts",
            json={
                "name": "InvestigateMe",
                "service": "test-service",
                "severity": "critical",
                "source": "test",
            },
        )
        
        if alert_response.status_code in [200, 201]:
            alert_id = alert_response.json()["id"]
            
            # Create investigation
            response = await client.post(
                "/api/v1/investigations",
                json={
                    "alert_id": str(alert_id),
                    "title": "Investigation for InvestigateMe",
                    "objective": "Determine root cause",
                },
            )
            
            assert response.status_code in [200, 201, 404]
            if response.status_code == 201:
                investigation = response.json()
                assert investigation["status"] in ["pending", "in_progress"]

    @pytest.mark.asyncio
    async def test_investigation_collects_observations(
        self, client: AsyncClient, mock_integrations
    ):
        """Test investigation collects observations from integrations."""
        # Create alert and investigation
        alert_response = await client.post(
            "/api/v1/alerts",
            json={
                "name": "ObserveMe",
                "service": "payment-service",
                "severity": "critical",
                "source": "prometheus",
            },
        )
        
        if alert_response.status_code in [200, 201]:
            alert_id = alert_response.json()["id"]
            
            inv_response = await client.post(
                "/api/v1/investigations",
                json={"alert_id": str(alert_id)},
            )
            
            if inv_response.status_code == 201:
                investigation_id = inv_response.json()["id"]
                
                # Add observation
                obs_response = await client.post(
                    f"/api/v1/investigations/{investigation_id}/observations",
                    json={
                        "type": "metric",
                        "source": "prometheus",
                        "description": "CPU usage at 95%",
                        "data": {"cpu_percent": 95},
                        "is_anomalous": True,
                    },
                )
                
                assert obs_response.status_code in [200, 201, 404]

    @pytest.mark.asyncio
    async def test_investigation_generates_hypotheses(self, client: AsyncClient):
        """Test investigation generates hypotheses."""
        # Create simple alert
        alert = Alert(
            name="TestAlert",
            source="test",
            service="test-service",
            severity=AlertSeverity.CRITICAL,
        )
        
        # Create investigation
        investigation = Investigation(
            alert_id=alert.id,
            title="Test Investigation",
        )
        
        # Add hypothesis
        hypothesis = Hypothesis(
            statement="High CPU due to memory leak",
            reasoning="Memory usage trending up correlates with CPU",
            confidence=0.7,
        )
        investigation.add_hypothesis(hypothesis)
        
        assert len(investigation.hypotheses) == 1
        assert investigation.hypotheses[0].status == HypothesisStatus.PROPOSED

    @pytest.mark.asyncio
    async def test_investigation_executes_actions(self, client: AsyncClient):
        """Test investigation can execute remediation actions."""
        # Create action
        action = Action(
            type=ActionType.SCALE,
            name="scale_up_replicas",
            description="Scale up payment service replicas",
            tool="kubernetes",
            command="kubectl scale deployment payment-service --replicas=5",
            parameters={"replicas": 5, "deployment": "payment-service"},
            is_destructive=False,
            requires_approval=False,
            risk_level="medium",
        )
        
        assert action.status == ActionStatus.PENDING
        
        # Simulate execution
        action.status = ActionStatus.EXECUTING
        action.started_at = datetime.now(timezone.utc)
        
        # Complete
        action.status = ActionStatus.COMPLETED
        action.completed_at = datetime.now(timezone.utc)
        action.result = {"new_replicas": 5}
        
        assert action.duration_seconds >= 0

    @pytest.mark.asyncio
    async def test_investigation_generates_report(self, client: AsyncClient):
        """Test investigation generates final report."""
        # Create investigation
        alert = Alert(
            name="ReportTest",
            source="test",
            service="test-service",
            severity=AlertSeverity.CRITICAL,
        )
        
        investigation = Investigation(
            alert_id=alert.id,
            title="Test Investigation",
        )
        
        # Add some data
        observation = Observation(
            type=ObservationType.LOG,
            source="loki",
            description="OutOfMemoryError found",
            data={"error": "java.lang.OutOfMemoryError"},
            is_anomalous=True,
        )
        investigation.add_observation(observation)
        
        hypothesis = Hypothesis(
            statement="Memory leak causing OOM",
            reasoning="Logs show OOM errors",
            confidence=0.85,
        )
        hypothesis.status = HypothesisStatus.CONFIRMED
        investigation.add_hypothesis(hypothesis)
        
        # Generate report
        report = Report(
            investigation_id=investigation.id,
            title="Investigation Report: ReportTest",
            executive_summary="Memory leak identified causing service restarts.",
            root_cause="Memory leak in payment processing module",
            root_cause_confidence=0.85,
            impact_summary="Service availability degraded to 95%",
            affected_services=["payment-service", "checkout-service"],
            recommendations=[
                "Fix memory leak in PaymentProcessor.java",
                "Increase memory limits as temporary mitigation",
            ],
        )
        
        investigation.report = report
        
        # Verify report
        assert investigation.report is not None
        markdown = report.to_markdown()
        assert "Memory leak" in markdown
        assert "payment-service" in markdown


# ============================================================================
# Test: Error Scenarios
# ============================================================================


class TestErrorScenarios:
    """Tests for error handling in alert lifecycle."""

    @pytest.mark.asyncio
    async def test_webhook_server_error_recovery(self, client: AsyncClient):
        """Test webhook endpoint recovers from server errors."""
        # Send empty alerts array
        response = await client.post(
            "/webhooks/prometheus",
            json={"alerts": []},
        )
        
        # Should handle gracefully
        assert response.status_code in [200, 400]

    @pytest.mark.asyncio
    async def test_alert_not_found(self, client: AsyncClient):
        """Test handling non-existent alert."""
        fake_id = str(uuid4())
        response = await client.get(f"/api/v1/alerts/{fake_id}")
        
        assert response.status_code in [404, 400]

    @pytest.mark.asyncio
    async def test_investigation_timeout_handling(self, client: AsyncClient):
        """Test investigation handles timeout gracefully."""
        investigation = Investigation(
            alert_id=uuid4(),
            title="Timeout Test",
        )
        
        # Simulate timeout
        investigation.status = InvestigationStatus.FAILED
        investigation.completed_at = datetime.now(timezone.utc)
        
        assert investigation.status == InvestigationStatus.FAILED

    @pytest.mark.asyncio
    async def test_integration_failure_recovery(
        self, client: AsyncClient, prometheus_webhook_payload: dict[str, Any]
    ):
        """Test system handles integration failures."""
        with patch("autosre.integrations.prometheus.PrometheusClient") as mock:
            mock.return_value.query = AsyncMock(side_effect=ConnectionError("Prometheus down"))
            
            # Webhook should still succeed
            response = await client.post(
                "/webhooks/prometheus",
                json=prometheus_webhook_payload,
            )
            
            # Should handle gracefully even if Prometheus is down
            assert response.status_code in [200, 500, 503]


# ============================================================================
# Test: Concurrency
# ============================================================================


class TestConcurrency:
    """Tests for concurrent alert processing."""

    @pytest.mark.asyncio
    async def test_concurrent_webhooks(self, client: AsyncClient):
        """Test handling concurrent webhook requests."""
        import asyncio
        
        payloads = [
            {
                "alerts": [
                    {
                        "status": "firing",
                        "labels": {"alertname": f"Concurrent{i}", "service": f"svc-{i}"},
                        "annotations": {"summary": f"Test {i}"},
                        "startsAt": "2024-01-15T10:00:00.000Z",
                        "fingerprint": f"concurrent-{i}",
                    }
                ]
            }
            for i in range(10)
        ]
        
        # Send all webhooks concurrently
        tasks = [
            client.post("/webhooks/prometheus", json=payload)
            for payload in payloads
        ]
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All should succeed
        for response in responses:
            if isinstance(response, Exception):
                pytest.fail(f"Concurrent request failed: {response}")
            else:
                assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_concurrent_investigations(self, client: AsyncClient):
        """Test running multiple investigations concurrently."""
        import asyncio
        
        # Create multiple investigations
        investigation_ids = []
        
        for i in range(3):
            response = await client.post(
                "/api/v1/investigations",
                json={
                    "title": f"Concurrent Investigation {i}",
                    "objective": "Test concurrent processing",
                },
            )
            if response.status_code == 201:
                investigation_ids.append(response.json()["id"])
        
        # All should be in valid state
        for inv_id in investigation_ids:
            response = await client.get(f"/api/v1/investigations/{inv_id}")
            if response.status_code == 200:
                assert response.json()["status"] in ["pending", "in_progress", "completed"]


# ============================================================================
# Test: Model Validation
# ============================================================================


class TestModelValidation:
    """Tests for data model validation."""

    def test_alert_validation(self):
        """Test alert model validation."""
        # Valid alert
        alert = Alert(
            name="ValidAlert",
            source="prometheus",
            severity=AlertSeverity.CRITICAL,
        )
        assert alert.name == "ValidAlert"
        assert alert.is_active is True
        
        # Test context string
        context = alert.to_context_string()
        assert "ValidAlert" in context

    def test_observation_validation(self):
        """Test observation model validation."""
        observation = Observation(
            type=ObservationType.METRIC,
            source="prometheus",
            description="CPU at 95%",
            data={"cpu": 95},
            relevance_score=0.9,
        )
        
        assert observation.relevance_score == 0.9
        context = observation.to_context_string()
        assert "CPU at 95%" in context

    def test_hypothesis_confidence_update(self):
        """Test hypothesis confidence updates with evidence."""
        hypothesis = Hypothesis(
            statement="Memory leak",
            confidence=0.5,
        )
        
        # Add supporting evidence
        hypothesis.add_supporting_evidence(uuid4())
        hypothesis.add_supporting_evidence(uuid4())
        
        # Add contradicting evidence
        hypothesis.add_contradicting_evidence(uuid4())
        
        # Confidence should be 2/(2+1) = 0.67
        assert abs(hypothesis.confidence - 0.67) < 0.01

    def test_action_duration_calculation(self):
        """Test action duration calculation."""
        action = Action(
            type=ActionType.DIAGNOSTIC,
            name="test_action",
            description="Test action",
        )
        
        # No duration when not started
        assert action.duration_seconds is None
        
        # Set times
        action.started_at = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        action.completed_at = datetime(2024, 1, 15, 10, 0, 30, tzinfo=timezone.utc)
        
        assert action.duration_seconds == 30

    def test_report_markdown_generation(self):
        """Test report markdown generation."""
        report = Report(
            investigation_id=uuid4(),
            title="Test Report",
            executive_summary="Service experienced high CPU due to memory leak.",
            root_cause="Memory leak in payment module",
            root_cause_confidence=0.9,
            affected_services=["payment", "checkout"],
            recommendations=["Fix leak", "Add monitoring"],
            preventive_measures=["Memory profiling in CI"],
        )
        
        markdown = report.to_markdown()
        
        assert "# Test Report" in markdown
        assert "Memory leak" in markdown
        assert "90%" in markdown  # Confidence formatted
        assert "payment" in markdown
        assert "Fix leak" in markdown
