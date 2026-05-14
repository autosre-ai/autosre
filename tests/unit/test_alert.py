"""Unit tests for Alert model."""

from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError

from autosre.models.alert import Alert, AlertSeverity, AlertSource, AlertStatus


class TestAlertSeverity:
    """Tests for AlertSeverity enum."""

    def test_severity_values(self):
        """Test severity enum values."""
        assert AlertSeverity.CRITICAL.value == "critical"
        assert AlertSeverity.HIGH.value == "high"
        assert AlertSeverity.WARNING.value == "warning"
        assert AlertSeverity.LOW.value == "low"
        assert AlertSeverity.INFO.value == "info"

    def test_severity_comparison(self):
        """Test severity can be compared."""
        assert AlertSeverity.CRITICAL == AlertSeverity.CRITICAL
        assert AlertSeverity.CRITICAL != AlertSeverity.WARNING


class TestAlertStatus:
    """Tests for AlertStatus enum."""

    def test_status_values(self):
        """Test status enum values."""
        assert AlertStatus.FIRING.value == "firing"
        assert AlertStatus.RESOLVED.value == "resolved"
        assert AlertStatus.ACKNOWLEDGED.value == "acknowledged"
        assert AlertStatus.SILENCED.value == "silenced"
        assert AlertStatus.INVESTIGATING.value == "investigating"


class TestAlertSource:
    """Tests for AlertSource enum."""

    def test_source_values(self):
        """Test source enum values."""
        assert AlertSource.PROMETHEUS.value == "prometheus"
        assert AlertSource.PAGERDUTY.value == "pagerduty"
        assert AlertSource.DATADOG.value == "datadog"
        assert AlertSource.CUSTOM.value == "custom"


class TestAlert:
    """Tests for Alert model."""

    def test_create_minimal_alert(self):
        """Test creating alert with minimal required fields."""
        alert = Alert(name="TestAlert")
        
        assert alert.name == "TestAlert"
        assert alert.severity == AlertSeverity.WARNING
        assert alert.status == AlertStatus.FIRING
        assert alert.source == AlertSource.PROMETHEUS

    def test_create_full_alert(self):
        """Test creating alert with all fields."""
        now = datetime.utcnow()
        
        alert = Alert(
            name="HighErrorRate",
            alert_id="alert-001",
            fingerprint="fp-001",
            service="payment-service",
            namespace="production",
            cluster="prod-cluster",
            severity=AlertSeverity.CRITICAL,
            status=AlertStatus.FIRING,
            source=AlertSource.PROMETHEUS,
            started_at=now,
            description="Error rate above 5%",
            summary="High error rate",
            runbook_url="https://runbooks.example.com/error-rate",
            labels={"team": "payments"},
            annotations={"description": "Error rate is high"},
        )
        
        assert alert.name == "HighErrorRate"
        assert alert.alert_id == "alert-001"
        assert alert.service == "payment-service"
        assert alert.severity == AlertSeverity.CRITICAL

    def test_name_validation(self):
        """Test name validation."""
        # Empty name should fail
        with pytest.raises(ValidationError):
            Alert(name="")
        
        # Whitespace-only name should fail
        with pytest.raises(ValidationError):
            Alert(name="   ")
        
        # Name gets trimmed
        alert = Alert(name="  Test Alert  ")
        assert alert.name == "Test Alert"

    def test_name_max_length(self):
        """Test name max length validation."""
        # Valid long name
        alert = Alert(name="A" * 256)
        assert len(alert.name) == 256
        
        # Too long name should fail
        with pytest.raises(ValidationError):
            Alert(name="A" * 257)

    def test_ended_at_validation(self):
        """Test ended_at must be after started_at."""
        now = datetime.utcnow()
        
        # Valid: ended_at after started_at
        alert = Alert(
            name="Test",
            started_at=now,
            ended_at=now + timedelta(hours=1),
        )
        assert alert.ended_at > alert.started_at
        
        # Invalid: ended_at before started_at
        with pytest.raises(ValidationError):
            Alert(
                name="Test",
                started_at=now,
                ended_at=now - timedelta(hours=1),
            )

    def test_is_firing_property(self):
        """Test is_firing property."""
        firing_alert = Alert(name="Test", status=AlertStatus.FIRING)
        assert firing_alert.is_firing is True
        
        resolved_alert = Alert(name="Test", status=AlertStatus.RESOLVED)
        assert resolved_alert.is_firing is False

    def test_is_resolved_property(self):
        """Test is_resolved property."""
        resolved_alert = Alert(name="Test", status=AlertStatus.RESOLVED)
        assert resolved_alert.is_resolved is True
        
        firing_alert = Alert(name="Test", status=AlertStatus.FIRING)
        assert firing_alert.is_resolved is False

    def test_is_critical_property(self):
        """Test is_critical property."""
        critical_alert = Alert(name="Test", severity=AlertSeverity.CRITICAL)
        assert critical_alert.is_critical is True
        
        warning_alert = Alert(name="Test", severity=AlertSeverity.WARNING)
        assert warning_alert.is_critical is False

    def test_duration_seconds_firing(self):
        """Test duration_seconds for firing alert."""
        started = datetime.utcnow() - timedelta(minutes=5)
        alert = Alert(name="Test", started_at=started)
        
        # Should be approximately 5 minutes (300 seconds)
        duration = alert.duration_seconds
        assert 295 <= duration <= 310

    def test_duration_seconds_resolved(self):
        """Test duration_seconds for resolved alert."""
        started = datetime.utcnow() - timedelta(hours=1)
        ended = datetime.utcnow()
        
        alert = Alert(
            name="Test",
            started_at=started,
            ended_at=ended,
            status=AlertStatus.RESOLVED,
        )
        
        duration = alert.duration_seconds
        assert 3595 <= duration <= 3605  # ~1 hour

    def test_to_dict(self):
        """Test to_dict serialization."""
        alert = Alert(
            name="Test",
            service="test-service",
            severity=AlertSeverity.HIGH,
        )
        
        data = alert.to_dict()
        
        assert isinstance(data, dict)
        assert data["name"] == "Test"
        assert data["service"] == "test-service"
        assert data["severity"] == "high"

    def test_from_prometheus_basic(self, prometheus_alert_payload):
        """Test from_prometheus factory method."""
        alert = Alert.from_prometheus(prometheus_alert_payload)
        
        assert alert.name == "HighCPUUsage"
        assert alert.service == "api-gateway"
        assert alert.severity == AlertSeverity.WARNING
        assert alert.status == AlertStatus.FIRING
        assert alert.source == AlertSource.PROMETHEUS
        assert alert.namespace == "production"

    def test_from_prometheus_resolved(self):
        """Test from_prometheus with resolved status."""
        payload = {
            "status": "resolved",
            "labels": {
                "alertname": "Test",
                "severity": "critical",
            },
            "startsAt": "2024-01-15T10:00:00Z",
            "endsAt": "2024-01-15T10:30:00Z",
        }
        
        alert = Alert.from_prometheus(payload)
        
        assert alert.status == AlertStatus.RESOLVED
        assert alert.ended_at is not None

    def test_from_prometheus_severity_mapping(self):
        """Test from_prometheus maps severity correctly."""
        severities = [
            ("critical", AlertSeverity.CRITICAL),
            ("high", AlertSeverity.HIGH),
            ("warning", AlertSeverity.WARNING),
            ("low", AlertSeverity.LOW),
            ("info", AlertSeverity.INFO),
            ("unknown", AlertSeverity.WARNING),  # default
        ]
        
        for prom_severity, expected in severities:
            payload = {
                "labels": {
                    "alertname": "Test",
                    "severity": prom_severity,
                },
            }
            alert = Alert.from_prometheus(payload)
            assert alert.severity == expected, f"Failed for {prom_severity}"

    def test_from_prometheus_missing_fields(self):
        """Test from_prometheus handles missing fields."""
        payload = {"labels": {}}
        
        alert = Alert.from_prometheus(payload)
        
        assert alert.name == "UnknownAlert"
        assert alert.severity == AlertSeverity.WARNING
        assert alert.service is None

    def test_from_pagerduty_basic(self, pagerduty_incident_payload):
        """Test from_pagerduty factory method."""
        alert = Alert.from_pagerduty(pagerduty_incident_payload)
        
        assert alert.name == "High Latency Alert"
        assert alert.alert_id == "P12345"
        assert alert.service == "Checkout Service"
        assert alert.severity == AlertSeverity.CRITICAL  # urgency: high
        assert alert.status == AlertStatus.FIRING
        assert alert.source == AlertSource.PAGERDUTY

    def test_from_pagerduty_acknowledged(self):
        """Test from_pagerduty with acknowledged status."""
        payload = {
            "incident": {
                "id": "P12345",
                "title": "Test",
                "status": "acknowledged",
                "urgency": "low",
            },
        }
        
        alert = Alert.from_pagerduty(payload)
        
        assert alert.status == AlertStatus.ACKNOWLEDGED
        assert alert.severity == AlertSeverity.WARNING

    def test_from_pagerduty_resolved(self):
        """Test from_pagerduty with resolved status."""
        payload = {
            "incident": {
                "id": "P12345",
                "title": "Test",
                "status": "resolved",
                "urgency": "high",
                "created_at": "2024-01-15T10:00:00Z",
                "resolved_at": "2024-01-15T10:30:00Z",
            },
        }
        
        alert = Alert.from_pagerduty(payload)
        
        assert alert.status == AlertStatus.RESOLVED
        assert alert.ended_at is not None

    def test_labels_immutability(self):
        """Test that labels dict is properly copied."""
        labels = {"key": "value"}
        alert = Alert(name="Test", labels=labels)
        
        # Modify original dict
        labels["new_key"] = "new_value"
        
        # Alert labels should not be affected
        assert "new_key" not in alert.labels

    def test_description_max_length(self):
        """Test description max length validation."""
        # Valid long description
        alert = Alert(name="Test", description="A" * 4096)
        assert len(alert.description) == 4096
        
        # Too long description should fail
        with pytest.raises(ValidationError):
            Alert(name="Test", description="A" * 4097)


class TestAlertEquality:
    """Tests for Alert equality and hashing."""

    def test_alerts_with_same_data_are_equal(self):
        """Test alerts with same data are equal."""
        now = datetime.utcnow()
        
        alert1 = Alert(
            name="Test",
            alert_id="123",
            started_at=now,
        )
        alert2 = Alert(
            name="Test",
            alert_id="123",
            started_at=now,
        )
        
        assert alert1 == alert2

    def test_alerts_with_different_data_are_not_equal(self):
        """Test alerts with different data are not equal."""
        alert1 = Alert(name="Test1")
        alert2 = Alert(name="Test2")
        
        assert alert1 != alert2
