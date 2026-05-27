"""Tests for the AutoSRE webhook server."""

import pytest
from datetime import datetime, UTC
from unittest.mock import patch, AsyncMock

from autosre.cli.commands.serve import (
    AlertmanagerAlert,
    AlertmanagerWebhook,
    InvestigationResult,
    InvestigationStore,
    WebhookResponse,
    create_fastapi_app,
)


class TestAlertmanagerModels:
    """Tests for Alertmanager webhook payload models."""
    
    def test_alertmanager_alert_parsing(self):
        """Test parsing a single alert from Alertmanager."""
        alert_data = {
            "status": "firing",
            "labels": {
                "alertname": "HighErrorRate",
                "service": "api-gateway",
                "severity": "critical",
            },
            "annotations": {
                "summary": "High error rate detected",
                "description": "Error rate is above 5%",
            },
            "startsAt": "2024-01-15T10:00:00Z",
            "fingerprint": "abc123",
        }
        
        alert = AlertmanagerAlert(**alert_data)
        
        assert alert.alertname == "HighErrorRate"
        assert alert.service == "api-gateway"
        assert alert.severity == "critical"
        assert alert.description == "Error rate is above 5%"
    
    def test_alertmanager_alert_service_extraction(self):
        """Test service extraction from various label names."""
        # service label
        alert1 = AlertmanagerAlert(
            status="firing",
            labels={"alertname": "Test", "service": "my-service"},
            startsAt="2024-01-15T10:00:00Z",
        )
        assert alert1.service == "my-service"
        
        # job label fallback
        alert2 = AlertmanagerAlert(
            status="firing",
            labels={"alertname": "Test", "job": "my-job"},
            startsAt="2024-01-15T10:00:00Z",
        )
        assert alert2.service == "my-job"
        
        # app label fallback
        alert3 = AlertmanagerAlert(
            status="firing",
            labels={"alertname": "Test", "app": "my-app"},
            startsAt="2024-01-15T10:00:00Z",
        )
        assert alert3.service == "my-app"
    
    def test_alertmanager_webhook_parsing(self):
        """Test parsing full webhook payload."""
        webhook_data = {
            "version": "4",
            "status": "firing",
            "receiver": "autosre",
            "groupLabels": {"alertname": "HighErrorRate"},
            "alerts": [
                {
                    "status": "firing",
                    "labels": {"alertname": "HighErrorRate", "severity": "critical"},
                    "annotations": {"summary": "Test alert"},
                    "startsAt": "2024-01-15T10:00:00Z",
                }
            ],
        }
        
        webhook = AlertmanagerWebhook(**webhook_data)
        
        assert webhook.status == "firing"
        assert len(webhook.alerts) == 1
        assert webhook.alerts[0].alertname == "HighErrorRate"


class TestInvestigationStore:
    """Tests for the investigation store."""
    
    def test_store_add_and_get(self):
        """Test adding and retrieving investigations."""
        store = InvestigationStore()
        
        result = InvestigationResult(
            investigation_id="inv-001",
            alert_fingerprint="fp-001",
            alertname="TestAlert",
            service="test-service",
            severity="high",
            status="pending",
            started_at=datetime.now(UTC),
        )
        
        store.add(result)
        
        retrieved = store.get("inv-001")
        assert retrieved is not None
        assert retrieved.alertname == "TestAlert"
    
    def test_store_deduplication(self):
        """Test alert deduplication logic."""
        store = InvestigationStore()
        
        # First alert should be investigated
        assert store.should_investigate("fp-001") is True
        
        # Same fingerprint within window should be skipped
        assert store.should_investigate("fp-001") is False
        
        # Different fingerprint should be investigated
        assert store.should_investigate("fp-002") is True
    
    def test_store_update(self):
        """Test updating investigation status."""
        store = InvestigationStore()
        
        result = InvestigationResult(
            investigation_id="inv-001",
            alert_fingerprint="fp-001",
            alertname="TestAlert",
            service="test-service",
            severity="high",
            status="pending",
            started_at=datetime.now(UTC),
        )
        store.add(result)
        
        store.update("inv-001", status="completed", root_cause="Config issue")
        
        updated = store.get("inv-001")
        assert updated.status == "completed"
        assert updated.root_cause == "Config issue"
    
    def test_store_list_recent(self):
        """Test listing recent investigations."""
        store = InvestigationStore()
        
        for i in range(5):
            result = InvestigationResult(
                investigation_id=f"inv-{i:03d}",
                alert_fingerprint=f"fp-{i:03d}",
                alertname=f"TestAlert{i}",
                service="test-service",
                severity="high",
                status="pending",
                started_at=datetime.now(UTC),
            )
            store.add(result)
        
        recent = store.list_recent(limit=3)
        assert len(recent) == 3
    
    def test_store_stats(self):
        """Test getting investigation stats."""
        store = InvestigationStore()
        
        # Add investigations with different statuses
        statuses = ["pending", "running", "completed", "completed", "failed"]
        for i, status in enumerate(statuses):
            result = InvestigationResult(
                investigation_id=f"inv-{i}",
                alert_fingerprint=f"fp-{i}",
                alertname="TestAlert",
                service="test-service",
                severity="high",
                status=status,
                started_at=datetime.now(UTC),
            )
            store.add(result)
        
        stats = store.get_stats()
        
        assert stats["total"] == 5
        assert stats["pending"] == 1
        assert stats["running"] == 1
        assert stats["completed"] == 2
        assert stats["failed"] == 1


class TestFastAPIEndpoints:
    """Tests for FastAPI webhook endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create test client for FastAPI app."""
        from fastapi.testclient import TestClient
        
        app = create_fastapi_app(auto_investigate=False)
        return TestClient(app)
    
    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "investigations" in data
    
    def test_readiness_endpoint(self, client):
        """Test readiness probe endpoint."""
        response = client.get("/readiness")
        
        assert response.status_code == 200
        assert response.json()["status"] == "ready"
    
    def test_liveness_endpoint(self, client):
        """Test liveness probe endpoint."""
        response = client.get("/liveness")
        
        assert response.status_code == 200
        assert response.json()["status"] == "alive"
    
    def test_alertmanager_webhook_firing(self, client):
        """Test alertmanager webhook with firing alerts."""
        webhook_payload = {
            "version": "4",
            "status": "firing",
            "receiver": "autosre",
            "groupLabels": {"alertname": "HighErrorRate"},
            "commonLabels": {"alertname": "HighErrorRate", "severity": "critical"},
            "alerts": [
                {
                    "status": "firing",
                    "labels": {
                        "alertname": "HighErrorRate",
                        "severity": "critical",
                        "service": "api-gateway",
                    },
                    "annotations": {
                        "summary": "High error rate on api-gateway",
                        "description": "Error rate is above threshold",
                    },
                    "startsAt": "2024-01-15T10:00:00Z",
                    "fingerprint": "test-fingerprint-001",
                }
            ],
        }
        
        response = client.post("/webhook/alertmanager", json=webhook_payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        assert data["investigations_started"] == 1
        assert len(data["investigation_ids"]) == 1
    
    def test_alertmanager_webhook_resolved(self, client):
        """Test that resolved alerts don't start investigations."""
        webhook_payload = {
            "version": "4",
            "status": "resolved",
            "receiver": "autosre",
            "alerts": [
                {
                    "status": "resolved",
                    "labels": {"alertname": "HighErrorRate"},
                    "annotations": {"summary": "Resolved"},
                    "startsAt": "2024-01-15T10:00:00Z",
                    "endsAt": "2024-01-15T10:30:00Z",
                }
            ],
        }
        
        response = client.post("/webhook/alertmanager", json=webhook_payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["investigations_started"] == 0
    
    def test_investigations_list_endpoint(self, client):
        """Test listing investigations endpoint."""
        # First create an investigation via webhook
        webhook_payload = {
            "version": "4",
            "status": "firing",
            "receiver": "autosre",
            "alerts": [
                {
                    "status": "firing",
                    "labels": {"alertname": "TestAlert"},
                    "annotations": {"summary": "Test"},
                    "startsAt": "2024-01-15T10:00:00Z",
                    "fingerprint": "unique-fp-for-list-test",
                }
            ],
        }
        client.post("/webhook/alertmanager", json=webhook_payload)
        
        # Then list investigations
        response = client.get("/investigations")
        
        assert response.status_code == 200
        data = response.json()
        assert "investigations" in data
        assert "stats" in data
    
    def test_get_investigation_not_found(self, client):
        """Test getting non-existent investigation."""
        response = client.get("/investigations/nonexistent-id")
        
        assert response.status_code == 404


class TestWebhookDeduplication:
    """Tests for webhook deduplication behavior."""
    
    @pytest.fixture
    def client(self):
        """Create test client for FastAPI app."""
        from fastapi.testclient import TestClient
        
        app = create_fastapi_app(auto_investigate=False)
        return TestClient(app)
    
    def test_duplicate_alerts_deduplicated(self, client):
        """Test that duplicate alerts within window are deduplicated."""
        webhook_payload = {
            "version": "4",
            "status": "firing",
            "receiver": "autosre",
            "alerts": [
                {
                    "status": "firing",
                    "labels": {"alertname": "DuplicateTest"},
                    "annotations": {"summary": "Test"},
                    "startsAt": "2024-01-15T10:00:00Z",
                    "fingerprint": "same-fingerprint-123",
                }
            ],
        }
        
        # First webhook - should create investigation
        response1 = client.post("/webhook/alertmanager", json=webhook_payload)
        assert response1.json()["investigations_started"] == 1
        
        # Second webhook with same fingerprint - should be deduplicated
        response2 = client.post("/webhook/alertmanager", json=webhook_payload)
        assert response2.json()["investigations_started"] == 0
