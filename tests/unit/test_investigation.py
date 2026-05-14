"""Unit tests for Investigation model."""

from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError

from autosre.models.investigation import (
    AgentState,
    Finding,
    Hypothesis,
    Investigation,
    InvestigationPlan,
    InvestigationStatus,
    StructuredReport,
    SynthesisDecision,
)


class TestHypothesis:
    """Tests for Hypothesis model."""

    def test_create_hypothesis(self):
        """Test creating a hypothesis."""
        hypothesis = Hypothesis(
            hypothesis="Memory leak in service",
            priority="high",
            agents_to_test=["kubernetes", "metrics"],
            confidence=0.8,
        )
        
        assert hypothesis.hypothesis == "Memory leak in service"
        assert hypothesis.priority == "high"
        assert hypothesis.agents_to_test == ["kubernetes", "metrics"]
        assert hypothesis.confidence == 0.8

    def test_hypothesis_defaults(self):
        """Test hypothesis default values."""
        hypothesis = Hypothesis(hypothesis="Test")
        
        assert hypothesis.priority == "medium"
        assert hypothesis.agents_to_test == []
        assert hypothesis.confidence == 0.5

    def test_hypothesis_str(self):
        """Test hypothesis string representation."""
        hypothesis = Hypothesis(
            hypothesis="Test hypothesis",
            priority="high",
        )
        
        assert "[HIGH]" in str(hypothesis)
        assert "Test hypothesis" in str(hypothesis)

    def test_hypothesis_priority_validation(self):
        """Test hypothesis priority validation."""
        # Valid priorities
        for priority in ["high", "medium", "low"]:
            h = Hypothesis(hypothesis="Test", priority=priority)
            assert h.priority == priority
        
        # Invalid priority
        with pytest.raises(ValidationError):
            Hypothesis(hypothesis="Test", priority="invalid")

    def test_hypothesis_confidence_validation(self):
        """Test hypothesis confidence validation."""
        # Valid confidence
        h = Hypothesis(hypothesis="Test", confidence=0.5)
        assert h.confidence == 0.5
        
        # Invalid confidence (too low)
        with pytest.raises(ValidationError):
            Hypothesis(hypothesis="Test", confidence=-0.1)
        
        # Invalid confidence (too high)
        with pytest.raises(ValidationError):
            Hypothesis(hypothesis="Test", confidence=1.1)


class TestFinding:
    """Tests for Finding model."""

    def test_create_finding(self):
        """Test creating a finding."""
        finding = Finding(
            category="kubernetes",
            detail="Pod crash detected",
            evidence="kubectl logs output",
            severity="high",
            confidence=0.9,
        )
        
        assert finding.category == "kubernetes"
        assert finding.detail == "Pod crash detected"
        assert finding.severity == "high"
        assert finding.confidence == 0.9

    def test_finding_defaults(self):
        """Test finding default values."""
        finding = Finding(
            category="test",
            detail="Test finding",
        )
        
        assert finding.evidence is None
        assert finding.severity == "info"
        assert finding.confidence == 0.7
        assert finding.metadata == {}

    def test_finding_timestamp(self):
        """Test finding timestamp is set."""
        finding = Finding(category="test", detail="Test")
        
        assert finding.timestamp is not None
        assert isinstance(finding.timestamp, datetime)

    def test_finding_metadata(self):
        """Test finding metadata."""
        finding = Finding(
            category="test",
            detail="Test",
            metadata={"pod_name": "test-pod", "count": 5},
        )
        
        assert finding.metadata["pod_name"] == "test-pod"
        assert finding.metadata["count"] == 5


class TestAgentState:
    """Tests for AgentState model."""

    def test_create_agent_state(self):
        """Test creating agent state."""
        state = AgentState(name="kubernetes")
        
        assert state.name == "kubernetes"
        assert state.status == InvestigationStatus.PENDING
        assert state.findings == []

    def test_mark_started(self):
        """Test mark_started method."""
        state = AgentState(name="test")
        state.mark_started()
        
        assert state.status == InvestigationStatus.RUNNING
        assert state.started_at is not None

    def test_mark_completed(self):
        """Test mark_completed method."""
        state = AgentState(name="test")
        state.mark_started()
        state.mark_completed(summary="Done")
        
        assert state.status == InvestigationStatus.COMPLETED
        assert state.completed_at is not None
        assert state.summary == "Done"

    def test_mark_failed(self):
        """Test mark_failed method."""
        state = AgentState(name="test")
        state.mark_started()
        state.mark_failed("Error occurred")
        
        assert state.status == InvestigationStatus.FAILED
        assert state.error == "Error occurred"
        assert state.completed_at is not None

    def test_add_finding(self):
        """Test add_finding method."""
        state = AgentState(name="test")
        finding = Finding(category="test", detail="Test finding")
        
        state.add_finding(finding)
        
        assert len(state.findings) == 1
        assert state.findings[0] == finding

    def test_duration_seconds(self):
        """Test duration_seconds property."""
        state = AgentState(name="test")
        
        # No start time
        assert state.duration_seconds is None
        
        # Running
        state.started_at = datetime.utcnow() - timedelta(seconds=10)
        duration = state.duration_seconds
        assert 9 <= duration <= 12
        
        # Completed
        state.completed_at = datetime.utcnow()
        duration = state.duration_seconds
        assert 9 <= duration <= 12


class TestInvestigationPlan:
    """Tests for InvestigationPlan model."""

    def test_create_plan(self):
        """Test creating investigation plan."""
        plan = InvestigationPlan(
            hypotheses=[
                Hypothesis(hypothesis="Test", priority="high"),
            ],
            selected_agents=["kubernetes", "metrics"],
            reasoning="Test plan",
        )
        
        assert len(plan.hypotheses) == 1
        assert plan.selected_agents == ["kubernetes", "metrics"]

    def test_high_priority_count(self):
        """Test high_priority_count computed property."""
        plan = InvestigationPlan(
            hypotheses=[
                Hypothesis(hypothesis="H1", priority="high"),
                Hypothesis(hypothesis="H2", priority="high"),
                Hypothesis(hypothesis="H3", priority="medium"),
            ],
        )
        
        assert plan.high_priority_count == 2


class TestSynthesisDecision:
    """Tests for SynthesisDecision model."""

    def test_create_decision(self):
        """Test creating synthesis decision."""
        decision = SynthesisDecision(
            sufficient_evidence=True,
            confidence=0.85,
            summary="Root cause identified",
        )
        
        assert decision.sufficient_evidence is True
        assert decision.confidence == 0.85
        assert decision.summary == "Root cause identified"

    def test_decision_defaults(self):
        """Test decision default values."""
        decision = SynthesisDecision(sufficient_evidence=False)
        
        assert decision.confidence == 0.5
        assert decision.summary == ""
        assert decision.gaps == []
        assert decision.feedback == ""


class TestStructuredReport:
    """Tests for StructuredReport model."""

    def test_create_report(self):
        """Test creating structured report."""
        report = StructuredReport(
            title="Incident Report",
            severity="critical",
            services=["payment-service"],
            root_cause="Memory leak",
        )
        
        assert report.title == "Incident Report"
        assert report.severity == "critical"
        assert report.services == ["payment-service"]

    def test_add_action_item(self):
        """Test add_action_item method."""
        report = StructuredReport(title="Test")
        
        report.add_action_item(
            action="Increase memory limit",
            priority="high",
            owner="platform-team",
        )
        
        assert len(report.action_items) == 1
        assert report.action_items[0]["action"] == "Increase memory limit"
        assert report.action_items[0]["priority"] == "high"
        assert report.action_items[0]["status"] == "pending"


class TestInvestigation:
    """Tests for Investigation model."""

    def test_create_investigation(self, sample_alert):
        """Test creating investigation."""
        investigation = Investigation(
            alert=sample_alert,
        )
        
        assert investigation.investigation_id is not None
        assert investigation.thread_id is not None
        assert investigation.status == InvestigationStatus.PENDING
        assert investigation.iteration == 0

    def test_investigation_defaults(self):
        """Test investigation default values."""
        investigation = Investigation()
        
        assert investigation.alert == {}
        assert investigation.hypotheses == []
        assert investigation.agent_states == {}
        assert investigation.max_iterations == 3
        assert investigation.max_react_loops == 10

    def test_get_agent_state(self):
        """Test get_agent_state method."""
        investigation = Investigation()
        
        # Get creates if not exists
        state = investigation.get_agent_state("kubernetes")
        assert state.name == "kubernetes"
        assert "kubernetes" in investigation.agent_states
        
        # Get returns existing
        state2 = investigation.get_agent_state("kubernetes")
        assert state is state2

    def test_add_message(self):
        """Test add_message method."""
        investigation = Investigation()
        
        investigation.add_message(
            role="user",
            content="Test message",
            metadata={"key": "value"},
        )
        
        assert len(investigation.messages) == 1
        assert investigation.messages[0]["role"] == "user"
        assert investigation.messages[0]["content"] == "Test message"
        assert "timestamp" in investigation.messages[0]

    def test_mark_completed(self):
        """Test mark_completed method."""
        investigation = Investigation()
        report = StructuredReport(title="Test")
        
        investigation.mark_completed(
            conclusion="Root cause found",
            report=report,
        )
        
        assert investigation.status == InvestigationStatus.COMPLETED
        assert investigation.completed_at is not None
        assert investigation.conclusion == "Root cause found"
        assert investigation.structured_report is not None

    def test_mark_failed(self):
        """Test mark_failed method."""
        investigation = Investigation()
        
        investigation.mark_failed("Something went wrong")
        
        assert investigation.status == InvestigationStatus.FAILED
        assert investigation.completed_at is not None
        assert len(investigation.messages) >= 1
        assert "failed" in investigation.messages[-1]["content"].lower()

    def test_is_complete(self):
        """Test is_complete computed property."""
        investigation = Investigation()
        
        # Pending is not complete
        assert investigation.is_complete is False
        
        # Running is not complete
        investigation.status = InvestigationStatus.RUNNING
        assert investigation.is_complete is False
        
        # Completed is complete
        investigation.status = InvestigationStatus.COMPLETED
        assert investigation.is_complete is True
        
        # Failed is complete
        investigation.status = InvestigationStatus.FAILED
        assert investigation.is_complete is True

    def test_all_findings(self):
        """Test all_findings computed property."""
        investigation = Investigation()
        
        # Add findings through agent states
        k8s_state = investigation.get_agent_state("kubernetes")
        k8s_state.add_finding(Finding(category="k8s", detail="Finding 1"))
        k8s_state.add_finding(Finding(category="k8s", detail="Finding 2"))
        
        metrics_state = investigation.get_agent_state("metrics")
        metrics_state.add_finding(Finding(category="metrics", detail="Finding 3"))
        
        # Get all findings
        all_findings = investigation.all_findings
        
        assert len(all_findings) == 3
        categories = {f.category for f in all_findings}
        assert categories == {"k8s", "metrics"}

    def test_duration_seconds(self):
        """Test duration_seconds computed property."""
        investigation = Investigation(
            started_at=datetime.utcnow() - timedelta(minutes=5),
        )
        
        # Running
        duration = investigation.duration_seconds
        assert 295 <= duration <= 310

    def test_to_graph_state(self):
        """Test to_graph_state method."""
        investigation = Investigation(
            alert={"name": "Test"},
        )
        
        state = investigation.to_graph_state()
        
        assert isinstance(state, dict)
        assert state["alert"] == {"name": "Test"}
        assert "investigation_id" in state
        assert "thread_id" in state


class TestInvestigationStatus:
    """Tests for InvestigationStatus enum."""

    def test_status_values(self):
        """Test status enum values."""
        assert InvestigationStatus.PENDING.value == "pending"
        assert InvestigationStatus.RUNNING.value == "running"
        assert InvestigationStatus.COMPLETED.value == "completed"
        assert InvestigationStatus.FAILED.value == "failed"
        assert InvestigationStatus.CANCELLED.value == "cancelled"
        assert InvestigationStatus.TIMEOUT.value == "timeout"
