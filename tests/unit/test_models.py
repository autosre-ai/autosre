"""Unit tests for Pydantic models."""

import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from autosre.models.alert import Alert, AlertSeverity, AlertStatus, AlertSource
from autosre.models.investigation import (
    AgentState,
    Evidence,
    EvidenceType,
    Finding,
    Hypothesis,
    HypothesisPriority,
    HypothesisStatus,
    Investigation,
    InvestigationResult,
    InvestigationStatus,
)


class TestAlertSeverity:
    """Tests for AlertSeverity enum."""

    def test_from_string_standard_values(self):
        """Test parsing standard severity values."""
        assert AlertSeverity.from_string("critical") == AlertSeverity.CRITICAL
        assert AlertSeverity.from_string("high") == AlertSeverity.HIGH
        assert AlertSeverity.from_string("medium") == AlertSeverity.MEDIUM
        assert AlertSeverity.from_string("low") == AlertSeverity.LOW
        assert AlertSeverity.from_string("info") == AlertSeverity.INFO

    def test_from_string_aliases(self):
        """Test parsing severity aliases."""
        # PagerDuty style
        assert AlertSeverity.from_string("p1") == AlertSeverity.CRITICAL
        assert AlertSeverity.from_string("p2") == AlertSeverity.HIGH
        assert AlertSeverity.from_string("p3") == AlertSeverity.MEDIUM
        
        # Other aliases
        assert AlertSeverity.from_string("crit") == AlertSeverity.CRITICAL
        assert AlertSeverity.from_string("major") == AlertSeverity.HIGH
        assert AlertSeverity.from_string("warning") == AlertSeverity.MEDIUM
        assert AlertSeverity.from_string("warn") == AlertSeverity.MEDIUM
        assert AlertSeverity.from_string("minor") == AlertSeverity.LOW

    def test_from_string_case_insensitive(self):
        """Test severity parsing is case insensitive."""
        assert AlertSeverity.from_string("CRITICAL") == AlertSeverity.CRITICAL
        assert AlertSeverity.from_string("Critical") == AlertSeverity.CRITICAL
        assert AlertSeverity.from_string("  critical  ") == AlertSeverity.CRITICAL

    def test_from_string_unknown_returns_medium(self):
        """Test unknown severity defaults to MEDIUM."""
        assert AlertSeverity.from_string("unknown") == AlertSeverity.MEDIUM
        assert AlertSeverity.from_string("asdf") == AlertSeverity.MEDIUM

    def test_numeric_priority(self):
        """Test numeric priority ordering."""
        assert AlertSeverity.CRITICAL.numeric_priority == 1
        assert AlertSeverity.HIGH.numeric_priority == 2
        assert AlertSeverity.MEDIUM.numeric_priority == 3
        assert AlertSeverity.LOW.numeric_priority == 4
        assert AlertSeverity.INFO.numeric_priority == 5


class TestAlert:
    """Tests for Alert model."""

    def test_create_minimal_alert(self):
        """Test creating alert with minimal required fields."""
        alert = Alert(name="TestAlert")
        
        assert alert.name == "TestAlert"
        assert alert.severity == AlertSeverity.MEDIUM
        assert alert.status == AlertStatus.FIRING
        assert alert.source == AlertSource.CUSTOM
        assert alert.id is not None
        assert alert.fingerprint is not None

    def test_create_full_alert(self):
        """Test creating alert with all fields."""
        alert = Alert(
            name="HighErrorRate",
            description="Error rate above 5%",
            severity=AlertSeverity.CRITICAL,
            status=AlertStatus.FIRING,
            source=AlertSource.PROMETHEUS,
            service="payment-service",
            namespace="production",
            cluster="prod-us-west-2",
            instance="payment-service-abc123",
            labels={"team": "platform", "env": "prod"},
            annotations={"runbook": "https://runbooks.example.com"},
        )
        
        assert alert.name == "HighErrorRate"
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.service == "payment-service"
        assert alert.labels["team"] == "platform"

    def test_severity_auto_parsing(self):
        """Test severity auto-parses from string."""
        alert = Alert(name="Test", severity="critical")
        assert alert.severity == AlertSeverity.CRITICAL
        
        alert = Alert(name="Test", severity="p1")
        assert alert.severity == AlertSeverity.CRITICAL

    def test_extract_common_labels(self):
        """Test service/namespace extraction from labels."""
        alert = Alert(
            name="Test",
            labels={
                "service": "api-gateway",
                "namespace": "staging",
                "cluster": "dev",
            },
        )
        
        assert alert.service == "api-gateway"
        assert alert.namespace == "staging"
        assert alert.cluster == "dev"

    def test_fingerprint_generation(self):
        """Test fingerprint is auto-generated."""
        alert1 = Alert(name="Test", service="svc1")
        alert2 = Alert(name="Test", service="svc1")
        alert3 = Alert(name="Test", service="svc2")
        
        # Same config should generate same fingerprint
        # Note: They're the same because fingerprint is based on name, service, etc.
        assert alert1.fingerprint is not None
        assert alert3.fingerprint != alert1.fingerprint

    def test_is_active(self):
        """Test is_active property."""
        firing = Alert(name="Test", status=AlertStatus.FIRING)
        investigating = Alert(name="Test", status=AlertStatus.INVESTIGATING)
        resolved = Alert(name="Test", status=AlertStatus.RESOLVED)
        
        assert firing.is_active is True
        assert investigating.is_active is True
        assert resolved.is_active is False

    def test_duration(self):
        """Test duration calculation."""
        now = datetime.now(timezone.utc)
        alert = Alert(
            name="Test",
            started_at=now,
        )
        
        # Duration should be small (just created)
        assert alert.duration is not None
        assert alert.duration >= 0

    def test_summary_property(self):
        """Test summary generation."""
        alert = Alert(
            name="HighCPU",
            service="api-gateway",
            namespace="production",
            severity=AlertSeverity.HIGH,
        )
        
        summary = alert.summary
        assert "HIGH" in summary
        assert "HighCPU" in summary
        assert "api-gateway" in summary

    def test_acknowledge(self):
        """Test acknowledging an alert."""
        alert = Alert(name="Test")
        alert.acknowledge("oncall@example.com")
        
        assert alert.status == AlertStatus.ACKNOWLEDGED
        assert alert.acknowledged_by == "oncall@example.com"
        assert alert.acknowledged_at is not None

    def test_resolve(self):
        """Test resolving an alert."""
        alert = Alert(name="Test")
        alert.resolve()
        
        assert alert.status == AlertStatus.RESOLVED
        assert alert.ended_at is not None

    def test_to_prompt_context(self):
        """Test prompt context formatting."""
        alert = Alert(
            name="HighErrorRate",
            service="payment-service",
            severity=AlertSeverity.CRITICAL,
            description="Error rate above 5%",
            labels={"team": "platform"},
        )
        
        context = alert.to_prompt_context()
        
        assert "Alert: HighErrorRate" in context
        assert "Severity: critical" in context
        assert "Service: payment-service" in context

    def test_from_alertmanager(self):
        """Test creating alert from AlertManager payload."""
        payload = {
            "status": "firing",
            "labels": {
                "alertname": "HighLatency",
                "service": "checkout",
                "severity": "high",
            },
            "annotations": {
                "summary": "High latency detected",
                "description": "P99 > 1s",
            },
            "startsAt": "2024-01-15T10:00:00Z",
            "fingerprint": "abc123",
        }
        
        alert = Alert.from_alertmanager(payload)
        
        assert alert.name == "HighLatency"
        assert alert.severity == AlertSeverity.HIGH
        assert alert.status == AlertStatus.FIRING
        assert alert.fingerprint == "abc123"

    def test_from_prometheus(self):
        """Test creating alert from Prometheus alert."""
        payload = {
            "state": "firing",
            "name": "HighCPU",
            "labels": {
                "alertname": "HighCPU",
                "severity": "warning",
            },
            "annotations": {
                "description": "CPU > 80%",
            },
        }
        
        alert = Alert.from_prometheus(payload)
        
        assert alert.name == "HighCPU"
        assert alert.source == AlertSource.PROMETHEUS

    def test_from_dict(self):
        """Test creating alert from generic dict."""
        data = {
            "title": "Service Down",
            "message": "Service is not responding",
            "priority": "high",
            "service_name": "auth-service",
        }
        
        alert = Alert.from_dict(data)
        
        assert alert.name == "Service Down"
        assert alert.description == "Service is not responding"
        assert alert.severity == AlertSeverity.HIGH

    def test_json_serialization(self):
        """Test JSON serialization/deserialization."""
        alert = Alert(
            name="TestAlert",
            service="test-service",
            severity=AlertSeverity.HIGH,
        )
        
        json_str = alert.model_dump_json()
        restored = Alert.model_validate_json(json_str)
        
        assert restored.name == alert.name
        assert restored.service == alert.service
        assert restored.severity == alert.severity


class TestHypothesis:
    """Tests for Hypothesis model."""

    def test_create_hypothesis(self):
        """Test creating a hypothesis."""
        h = Hypothesis(description="Memory leak causing OOM")
        
        assert h.description == "Memory leak causing OOM"
        assert h.priority == HypothesisPriority.MEDIUM
        assert h.status == HypothesisStatus.PENDING
        assert h.confidence == 0.0

    def test_confirm_hypothesis(self):
        """Test confirming a hypothesis."""
        h = Hypothesis(description="Test")
        h.confirm(confidence=0.85, reasoning="Evidence supports this")
        
        assert h.status == HypothesisStatus.CONFIRMED
        assert h.confidence == 0.85
        assert h.reasoning == "Evidence supports this"

    def test_reject_hypothesis(self):
        """Test rejecting a hypothesis."""
        h = Hypothesis(description="Test")
        h.reject(reasoning="No evidence found")
        
        assert h.status == HypothesisStatus.REJECTED
        assert h.confidence == 0.0
        assert h.reasoning == "No evidence found"

    def test_mark_inconclusive(self):
        """Test marking hypothesis as inconclusive."""
        h = Hypothesis(description="Test")
        h.mark_inconclusive(reasoning="Insufficient data")
        
        assert h.status == HypothesisStatus.INCONCLUSIVE
        assert h.reasoning == "Insufficient data"


class TestEvidence:
    """Tests for Evidence model."""

    def test_create_evidence(self):
        """Test creating evidence."""
        e = Evidence(
            type=EvidenceType.METRIC,
            source="prometheus",
            summary="CPU at 95%",
            data={"value": 0.95},
        )
        
        assert e.type == EvidenceType.METRIC
        assert e.source == "prometheus"
        assert e.summary == "CPU at 95%"

    def test_supports_hypothesis(self):
        """Test supports_hypothesis method."""
        e = Evidence(
            type=EvidenceType.LOG,
            source="loki",
            summary="Error found",
            data={},
            hypothesis_ids=["hyp-1", "hyp-2"],
        )
        
        assert e.supports_hypothesis("hyp-1") is True
        assert e.supports_hypothesis("hyp-3") is False


class TestFinding:
    """Tests for Finding model."""

    def test_create_finding(self):
        """Test creating a finding."""
        f = Finding(
            title="Pod crash detected",
            description="Payment pod crashed 5 times",
            severity=AlertSeverity.HIGH,
            category="kubernetes",
        )
        
        assert f.title == "Pod crash detected"
        assert f.severity == AlertSeverity.HIGH
        assert f.is_root_cause is False

    def test_finding_root_cause_flag(self):
        """Test root cause flag."""
        f = Finding(
            title="Memory leak",
            description="Root cause identified",
            is_root_cause=True,
            confidence=0.9,
        )
        
        assert f.is_root_cause is True
        assert f.confidence == 0.9


class TestAgentState:
    """Tests for AgentState model."""

    def test_create_agent_state(self):
        """Test creating agent state."""
        state = AgentState(agent_id="kubernetes")
        
        assert state.agent_id == "kubernetes"
        assert state.status == "pending"
        assert state.is_complete is False

    def test_is_complete(self):
        """Test is_complete property."""
        pending = AgentState(agent_id="test", status="pending")
        completed = AgentState(agent_id="test", status="completed")
        error = AgentState(agent_id="test", status="error")
        timeout = AgentState(agent_id="test", status="timeout")
        
        assert pending.is_complete is False
        assert completed.is_complete is True
        assert error.is_complete is True
        assert timeout.is_complete is True


class TestInvestigation:
    """Tests for Investigation model."""

    @pytest.fixture
    def sample_alert(self):
        """Create sample alert."""
        return Alert(
            name="HighErrorRate",
            service="payment-service",
            severity=AlertSeverity.CRITICAL,
        )

    def test_create_investigation(self, sample_alert):
        """Test creating investigation."""
        inv = Investigation(alert=sample_alert)
        
        assert inv.alert == sample_alert
        assert inv.status == InvestigationStatus.PENDING
        assert inv.iteration == 0
        assert inv.is_complete is False

    def test_start_investigation(self, sample_alert):
        """Test starting investigation."""
        inv = Investigation(alert=sample_alert)
        inv.start()
        
        assert inv.status == InvestigationStatus.TRIAGING
        assert inv.started_at is not None

    def test_complete_investigation(self, sample_alert):
        """Test completing investigation."""
        inv = Investigation(alert=sample_alert)
        inv.start()
        
        result = InvestigationResult(
            root_cause="Memory leak",
            summary="Investigation complete",
        )
        inv.complete(result)
        
        assert inv.status == InvestigationStatus.COMPLETED
        assert inv.completed_at is not None
        assert inv.result is not None
        assert inv.is_complete is True

    def test_fail_investigation(self, sample_alert):
        """Test failing investigation."""
        inv = Investigation(alert=sample_alert)
        inv.fail("Timeout exceeded")
        
        assert inv.status == InvestigationStatus.FAILED
        assert inv.is_complete is True

    def test_add_hypothesis(self, sample_alert):
        """Test adding hypothesis."""
        inv = Investigation(alert=sample_alert)
        h = Hypothesis(description="Test hypothesis")
        inv.add_hypothesis(h)
        
        assert len(inv.hypotheses) == 1
        assert inv.hypotheses[0].description == "Test hypothesis"

    def test_add_evidence(self, sample_alert):
        """Test adding evidence."""
        inv = Investigation(alert=sample_alert)
        e = Evidence(
            type=EvidenceType.METRIC,
            source="prometheus",
            summary="High CPU",
            data={},
        )
        inv.add_evidence(e)
        
        assert len(inv.evidence) == 1

    def test_add_finding(self, sample_alert):
        """Test adding finding."""
        inv = Investigation(alert=sample_alert)
        f = Finding(
            title="Pod crash",
            description="Crash detected",
        )
        inv.add_finding(f)
        
        assert len(inv.findings) == 1

    def test_should_continue(self, sample_alert):
        """Test should_continue logic."""
        inv = Investigation(alert=sample_alert)
        
        # Should continue when pending
        assert inv.should_continue() is True
        
        inv.start()
        # Should continue when triaging
        assert inv.should_continue() is True
        
        # Complete it
        inv.complete(InvestigationResult(summary="Done"))
        # Should not continue when completed
        assert inv.should_continue() is False

    def test_should_continue_respects_max_iterations(self, sample_alert):
        """Test max iterations limit."""
        inv = Investigation(alert=sample_alert, max_iterations=3)
        inv.start()
        inv.advance_to_investigation()
        
        # Add hypothesis to test
        h = Hypothesis(description="Test")
        inv.add_hypothesis(h)
        
        inv.iteration = 3
        assert inv.should_continue() is False

    def test_active_hypotheses(self, sample_alert):
        """Test active_hypotheses property."""
        inv = Investigation(alert=sample_alert)
        
        h1 = Hypothesis(description="Active")
        h2 = Hypothesis(description="Confirmed")
        h2.status = HypothesisStatus.CONFIRMED
        h3 = Hypothesis(description="Testing")
        h3.status = HypothesisStatus.TESTING
        
        inv.hypotheses = [h1, h2, h3]
        
        active = inv.active_hypotheses
        assert len(active) == 2  # h1 (pending) and h3 (testing)

    def test_confirmed_hypotheses(self, sample_alert):
        """Test confirmed_hypotheses property."""
        inv = Investigation(alert=sample_alert)
        
        h1 = Hypothesis(description="High conf")
        h1.confirm(0.9, "Strong evidence")
        
        h2 = Hypothesis(description="Low conf")
        h2.confirm(0.5, "Weak evidence")
        
        h3 = Hypothesis(description="Rejected")
        h3.reject("No evidence")
        
        inv.hypotheses = [h1, h2, h3]
        
        confirmed = inv.confirmed_hypotheses
        assert len(confirmed) == 2
        # Should be sorted by confidence (highest first)
        assert confirmed[0].confidence == 0.9

    def test_to_state_dict(self, sample_alert):
        """Test serialization to state dict."""
        inv = Investigation(alert=sample_alert)
        inv.start()
        
        state = inv.to_state_dict()
        
        assert "investigation_id" in state
        assert "alert" in state
        assert state["status"] == "triaging"

    def test_from_state_dict(self, sample_alert):
        """Test deserialization from state dict."""
        inv = Investigation(alert=sample_alert)
        inv.start()
        h = Hypothesis(description="Test")
        inv.add_hypothesis(h)
        
        state = inv.to_state_dict()
        restored = Investigation.from_state_dict(state)
        
        assert restored.id == inv.id
        assert restored.status == InvestigationStatus.TRIAGING
        assert len(restored.hypotheses) == 1

    def test_duration_seconds(self, sample_alert):
        """Test duration calculation."""
        inv = Investigation(alert=sample_alert)
        
        # Not started yet
        assert inv.duration_seconds is None
        
        inv.start()
        # Should have small duration
        assert inv.duration_seconds is not None
        assert inv.duration_seconds >= 0


class TestInvestigationResult:
    """Tests for InvestigationResult model."""

    def test_create_result(self):
        """Test creating investigation result."""
        result = InvestigationResult(
            root_cause="Memory leak in payment service",
            root_cause_confidence=0.85,
            summary="Investigation identified memory leak",
            contributing_factors=["High traffic", "Inefficient queries"],
            recommendations=["Increase memory limit", "Fix leak"],
        )
        
        assert result.root_cause == "Memory leak in payment service"
        assert result.root_cause_confidence == 0.85
        assert len(result.contributing_factors) == 2
        assert len(result.recommendations) == 2

    def test_result_requires_review(self):
        """Test requires_human_review flag."""
        result = InvestigationResult(
            summary="Low confidence result",
            requires_human_review=True,
        )
        
        assert result.requires_human_review is True
