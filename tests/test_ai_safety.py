"""
Tests for AI Safety Features

Tests for:
- AIHypothesis output format
- AI Telemetry (metrics tracking)
- AI Error Budget (circuit breaker)
- Game Day Framework
- Safety prompts
"""

import json
import sqlite3
import tempfile
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Import modules under test
from autosre.agents.output import (
    AIHypothesis,
    Evidence,
    CounterCheck,
    InvestigationOutput,
    BlastRadius,
    ApprovalRequirement,
)
from autosre.telemetry.ai_metrics import (
    AIMetricsTracker,
    InvestigationRecord,
    OutcomeStatus,
)
from autosre.telemetry.error_budget import (
    AIErrorBudget,
    ErrorBudgetConfig,
    BudgetType,
    ErrorBudgetStatus,
)
from autosre.evals.game_day import (
    GameDayFramework,
    GameDayScenario,
    ScenarioType,
    ScenarioResult,
    CheckResult,
)
from autosre.agents.safety_prompts import (
    AI_SAFETY_PREAMBLE,
    inject_safety_preamble,
    add_deliberate_checklist,
    format_hypothesis_output,
)


# =============================================================================
# AIHypothesis Output Format Tests
# =============================================================================

class TestEvidence:
    """Tests for Evidence dataclass."""
    
    def test_evidence_creation(self):
        """Test creating evidence."""
        evidence = Evidence(
            source="prometheus",
            query="rate(http_requests_total[5m])",
            raw_data={"value": 100},
            interpretation="Traffic is elevated",
            confidence=0.8,
        )
        
        assert evidence.source == "prometheus"
        assert evidence.confidence == 0.8
        assert evidence.interpretation == "Traffic is elevated"
    
    def test_evidence_to_dict(self):
        """Test evidence serialization."""
        evidence = Evidence(
            source="kubernetes",
            query="kubectl get pods",
            raw_data=["pod1", "pod2"],
            interpretation="Two pods running",
        )
        
        d = evidence.to_dict()
        assert d["source"] == "kubernetes"
        assert d["raw_data"] == ["pod1", "pod2"]
        assert "timestamp" in d
    
    def test_evidence_citation(self):
        """Test generating citation string."""
        evidence = Evidence(
            source="prometheus",
            query="test",
            raw_data={},
            interpretation="test",
            metric_name="http_errors_total",
        )
        
        citation = evidence.to_citation()
        assert "[prometheus]" in citation
        assert "metric:http_errors_total" in citation


class TestCounterCheck:
    """Tests for CounterCheck dataclass."""
    
    def test_counter_check_creation(self):
        """Test creating counter-check."""
        check = CounterCheck(
            description="Verify CPU is not the issue",
            command="kubectl top pods",
            expected_if_hypothesis_wrong="CPU usage below 50%",
        )
        
        assert check.status == "pending"
        assert "CPU" in check.description
    
    def test_counter_check_to_dict(self):
        """Test counter-check serialization."""
        check = CounterCheck(
            description="Check logs",
            command="kubectl logs -f",
            expected_if_hypothesis_wrong="No errors",
            status="checked",
            result="Errors found",
        )
        
        d = check.to_dict()
        assert d["status"] == "checked"
        assert d["result"] == "Errors found"


class TestAIHypothesis:
    """Tests for AIHypothesis dataclass."""
    
    def test_hypothesis_creation(self):
        """Test creating a hypothesis."""
        hypothesis = AIHypothesis(
            summary="Database connection pool exhaustion",
            confidence=0.75,
            blast_radius=BlastRadius.SINGLE_SERVICE,
        )
        
        assert hypothesis.summary == "Database connection pool exhaustion"
        assert hypothesis.confidence == 0.75
        assert hypothesis.hypothesis_id.startswith("hyp-")
    
    def test_hypothesis_confidence_label(self):
        """Test confidence label generation."""
        very_high = AIHypothesis(summary="test", confidence=0.95)
        assert very_high.confidence_label == "very high"
        
        high = AIHypothesis(summary="test", confidence=0.75)
        assert high.confidence_label == "high"
        
        moderate = AIHypothesis(summary="test", confidence=0.55)
        assert moderate.confidence_label == "moderate"
        
        low = AIHypothesis(summary="test", confidence=0.35)
        assert low.confidence_label == "low"
        
        very_low = AIHypothesis(summary="test", confidence=0.15)
        assert very_low.confidence_label == "very low"
    
    def test_hypothesis_needs_more_evidence(self):
        """Test needs_more_evidence property."""
        # Low confidence, no evidence
        h1 = AIHypothesis(summary="test", confidence=0.3)
        assert h1.needs_more_evidence
        
        # High confidence, evidence
        h2 = AIHypothesis(summary="test", confidence=0.8)
        h2.evidence = [Evidence("a", "b", "c", "d"), Evidence("e", "f", "g", "h")]
        assert not h2.needs_more_evidence
    
    def test_hypothesis_auto_approval_requirement(self):
        """Test automatic approval requirement based on blast radius."""
        # Cluster-wide = mandatory multiple
        h1 = AIHypothesis(
            summary="test",
            blast_radius=BlastRadius.CLUSTER,
        )
        assert h1.requires_human_approval
        assert h1.approval_requirement == ApprovalRequirement.MANDATORY_MULTIPLE
        
        # Namespace = required
        h2 = AIHypothesis(
            summary="test",
            blast_radius=BlastRadius.NAMESPACE,
        )
        assert h2.approval_requirement == ApprovalRequirement.MANDATORY_MULTIPLE
        
        # None blast radius, not requiring approval = none
        h3 = AIHypothesis(
            summary="test",
            blast_radius=BlastRadius.NONE,
            requires_human_approval=False,
        )
        assert h3.approval_requirement == ApprovalRequirement.NONE
    
    def test_hypothesis_add_evidence_updates_confidence(self):
        """Test that adding evidence updates confidence."""
        hypothesis = AIHypothesis(summary="test", confidence=0.3)
        
        hypothesis.add_evidence(Evidence(
            source="prometheus",
            query="test",
            raw_data={},
            interpretation="Found issue",
            confidence=0.8,
        ))
        
        # Confidence should increase based on evidence
        assert hypothesis.confidence > 0.3
    
    def test_hypothesis_to_markdown(self):
        """Test markdown generation."""
        hypothesis = AIHypothesis(
            summary="Database overload",
            detailed_explanation="Too many connections",
            confidence=0.75,
            blast_radius=BlastRadius.SINGLE_SERVICE,
            recommended_action="Scale connection pool",
        )
        hypothesis.add_evidence(Evidence(
            source="prometheus",
            query="pg_connections",
            raw_data=485,
            interpretation="Near limit",
            confidence=0.9,
        ))
        hypothesis.add_counter_check(CounterCheck(
            description="Check if connections are actually being used",
            command="SELECT count(*) FROM pg_stat_activity",
            expected_if_hypothesis_wrong="Low active connections",
        ))
        
        md = hypothesis.to_markdown()
        
        assert "## Hypothesis: Database overload" in md
        assert "**Confidence:**" in md  # confidence gets updated by add_evidence
        assert "### Evidence" in md
        assert "prometheus" in md
        assert "### Counter-Checks" in md
    
    def test_hypothesis_serialization(self):
        """Test to_dict and from_dict round-trip."""
        original = AIHypothesis(
            summary="Test hypothesis",
            confidence=0.65,
            blast_radius=BlastRadius.MULTI_SERVICE,
            recommended_action="Restart pods",
        )
        original.add_evidence(Evidence("src", "q", "d", "i", confidence=0.7))
        
        d = original.to_dict()
        restored = AIHypothesis.from_dict(d)
        
        assert restored.summary == original.summary
        assert restored.confidence == original.confidence
        assert restored.blast_radius == original.blast_radius
        assert len(restored.evidence) == 1


class TestInvestigationOutput:
    """Tests for InvestigationOutput."""
    
    def test_investigation_output_creation(self):
        """Test creating investigation output."""
        output = InvestigationOutput(
            investigation_id="inv-123",
            alert_name="HighErrorRate",
            alert_description="Errors above threshold",
        )
        
        assert output.investigation_id == "inv-123"
        assert output.overall_confidence == 0.0
    
    def test_add_hypothesis_and_ranking(self):
        """Test that hypotheses are ranked by confidence."""
        output = InvestigationOutput(
            investigation_id="inv-123",
            alert_name="Test",
            alert_description="Test",
        )
        
        low = AIHypothesis(summary="Low conf", confidence=0.3)
        high = AIHypothesis(summary="High conf", confidence=0.8)
        medium = AIHypothesis(summary="Medium conf", confidence=0.5)
        
        output.add_hypothesis(low)
        output.add_hypothesis(high)
        output.add_hypothesis(medium)
        
        assert output.hypotheses[0].confidence == 0.8
        assert output.primary_hypothesis.summary == "High conf"
        assert output.overall_confidence == 0.8
    
    def test_investigation_output_to_markdown(self):
        """Test markdown report generation."""
        output = InvestigationOutput(
            investigation_id="inv-123",
            alert_name="HighLatency",
            alert_description="P99 > 5s",
            immediate_actions=["Check logs"],
            verification_steps=["Verify hypothesis"],
            escalation_triggers=["Confidence < 50%"],
        )
        output.add_hypothesis(AIHypothesis(
            summary="Database slow",
            confidence=0.7,
        ))
        
        md = output.to_markdown()
        
        assert "# Investigation Report: HighLatency" in md
        assert "## Primary Hypothesis" in md
        assert "## Immediate Actions" in md


# =============================================================================
# AI Telemetry Tests
# =============================================================================

class TestAIMetricsTracker:
    """Tests for AI metrics tracking."""
    
    @pytest.fixture
    def tracker(self, tmp_path):
        """Create a tracker with temp database."""
        return AIMetricsTracker(db_path=tmp_path / "test_metrics.db")
    
    def test_record_investigation(self, tracker):
        """Test recording an investigation."""
        record = InvestigationRecord(
            investigation_id="test-001",
            alert_name="HighErrorRate",
            confidence_reported=0.75,
            primary_hypothesis="Database issue",
            evidence_count=3,
            context_documents=["runbook/db.md"],
            duration_seconds=45.5,
            severity="high",
        )
        
        tracker.record_investigation(record)
        
        # Verify stored
        stats = tracker.get_statistics(days=1)
        assert stats["total_investigations"] == 1
    
    def test_update_outcome(self, tracker):
        """Test updating investigation outcome."""
        record = InvestigationRecord(
            investigation_id="test-002",
            alert_name="Test",
            confidence_reported=0.8,
        )
        tracker.record_investigation(record)
        
        # Update outcome
        tracker.update_outcome("test-002", outcome_correct=True, actual_root_cause="Database")
        
        # Check accuracy
        accuracy = tracker.get_accuracy_rate(days=1)
        assert accuracy == 1.0  # 1/1 correct
    
    def test_accuracy_rate_calculation(self, tracker):
        """Test accuracy rate over multiple investigations."""
        # Record 3 investigations
        for i, correct in enumerate([True, True, False]):
            record = InvestigationRecord(
                investigation_id=f"test-{i}",
                alert_name="Test",
                confidence_reported=0.7,
            )
            tracker.record_investigation(record)
            tracker.update_outcome(f"test-{i}", outcome_correct=correct)
        
        accuracy = tracker.get_accuracy_rate(days=1)
        assert accuracy == pytest.approx(2/3, rel=0.01)
    
    def test_false_positive_rate(self, tracker):
        """Test false positive rate calculation."""
        # All incorrect = 100% false positive
        for i in range(3):
            record = InvestigationRecord(
                investigation_id=f"fp-{i}",
                alert_name="Test",
                confidence_reported=0.8,
                category="network",
            )
            tracker.record_investigation(record)
            tracker.update_outcome(f"fp-{i}", outcome_correct=False)
        
        fp_rate = tracker.get_false_positive_rate(days=1, category="network")
        assert fp_rate == 1.0
    
    def test_human_override_rate(self, tracker):
        """Test human override rate tracking."""
        # 2 accepted, 1 rejected
        for i, accepted in enumerate([True, True, False]):
            record = InvestigationRecord(
                investigation_id=f"hr-{i}",
                alert_name="Test",
                confidence_reported=0.7,
            )
            tracker.record_investigation(record)
            tracker.record_human_feedback(f"hr-{i}", accepted=accepted)
        
        override_rate = tracker.get_human_override_rate(days=1)
        assert override_rate == pytest.approx(1/3, rel=0.01)
    
    def test_confidence_calibration(self, tracker):
        """Test confidence calibration tracking."""
        # High confidence, all correct
        for i in range(5):
            record = InvestigationRecord(
                investigation_id=f"cal-high-{i}",
                alert_name="Test",
                confidence_reported=0.85,
            )
            tracker.record_investigation(record)
            tracker.update_outcome(f"cal-high-{i}", outcome_correct=True)
        
        # Low confidence, all wrong
        for i in range(5):
            record = InvestigationRecord(
                investigation_id=f"cal-low-{i}",
                alert_name="Test",
                confidence_reported=0.25,
            )
            tracker.record_investigation(record)
            tracker.update_outcome(f"cal-low-{i}", outcome_correct=False)
        
        calibration = tracker.get_confidence_calibration(days=1)
        
        # High confidence bucket should have high accuracy
        assert calibration.get("0.8-0.9", 0) == 1.0
        # Low confidence bucket should have low accuracy
        assert calibration.get("0.2-0.3", 0) == 0.0


# =============================================================================
# Error Budget Tests
# =============================================================================

class TestAIErrorBudget:
    """Tests for AI error budget tracking."""
    
    @pytest.fixture
    def budget(self, tmp_path):
        """Create budget tracker with temp database."""
        config = ErrorBudgetConfig(
            high_severity_accuracy_target=0.80,
            safe_action_rate_target=0.99,
            human_override_threshold=0.20,
            bad_recommendation_rate_target=0.05,
            min_samples=5,  # Lower for testing
            cooldown_hours=1,
        )
        return AIErrorBudget(
            db_path=tmp_path / "test_budget.db",
            config=config,
        )
    
    def test_record_high_severity_outcome(self, budget):
        """Test recording high severity outcomes."""
        # All correct
        for i in range(10):
            budget.record_high_severity_outcome(correct=True, investigation_id=f"hs-{i}")
        
        status = budget.get_budget_status(BudgetType.HIGH_SEVERITY_ACCURACY)
        
        assert status.current == 1.0  # 100% accuracy
        assert not status.exhausted
    
    def test_budget_exhaustion(self, budget):
        """Test that budget exhausts when target not met."""
        # 3/10 correct = 30% < 80% target
        for i in range(10):
            correct = i < 3  # Only first 3 correct
            budget.record_high_severity_outcome(correct=correct, investigation_id=f"ex-{i}")
        
        status = budget.get_budget_status(BudgetType.HIGH_SEVERITY_ACCURACY)
        
        assert status.current == 0.3
        assert status.exhausted
    
    def test_conservative_mode_triggered(self, budget):
        """Test that conservative mode triggers on budget exhaustion."""
        # Exhaust budget
        for i in range(10):
            budget.record_high_severity_outcome(correct=False, investigation_id=f"cm-{i}")
        
        assert budget.is_conservative_mode()
        assert budget.requires_human_approval()
    
    def test_human_override_budget(self, budget):
        """Test human override budget tracking."""
        # 5 rejected out of 10 = 50% override > 20% threshold
        for i in range(10):
            accepted = i < 5  # Only first 5 accepted
            budget.record_human_decision(accepted=accepted, investigation_id=f"ho-{i}")
        
        status = budget.get_budget_status(BudgetType.HUMAN_OVERRIDE)
        
        assert status.exhausted  # Override rate too high
    
    def test_safe_action_rate(self, budget):
        """Test safe action rate tracking."""
        # 95/100 safe = 95% < 99% target
        for i in range(100):
            safe = i >= 5  # First 5 are unsafe
            budget.record_action_safety(safe=safe, investigation_id=f"sa-{i}")
        
        status = budget.get_budget_status(BudgetType.SAFE_ACTION_RATE)
        
        assert status.current == 0.95
        assert status.exhausted  # Below 99%
    
    def test_get_overall_status(self, budget):
        """Test getting overall status."""
        status = budget.get_status()
        
        assert isinstance(status, ErrorBudgetStatus)
        assert len(status.budgets) == len(BudgetType)
    
    def test_reset_conservative_mode(self, budget):
        """Test manual reset of conservative mode."""
        # Trigger conservative mode
        for i in range(10):
            budget.record_high_severity_outcome(correct=False, investigation_id=f"rs-{i}")
        
        assert budget.is_conservative_mode()
        
        # Reset
        budget.reset_conservative_mode()
        
        assert not budget.is_conservative_mode()


# =============================================================================
# Game Day Framework Tests
# =============================================================================

class TestGameDayFramework:
    """Tests for game day framework."""
    
    @pytest.fixture
    def framework(self):
        """Create game day framework."""
        return GameDayFramework()
    
    def test_builtin_scenarios_loaded(self, framework):
        """Test that built-in scenarios are loaded."""
        scenarios = framework.list_scenarios()
        
        assert len(scenarios) >= 6
        assert any(s.scenario_type == ScenarioType.STALE_RUNBOOK for s in scenarios)
        assert any(s.scenario_type == ScenarioType.FALSE_POSITIVE for s in scenarios)
    
    def test_get_scenario(self, framework):
        """Test getting a specific scenario."""
        scenario = framework.get_scenario("stale_runbook_001")
        
        assert scenario is not None
        assert scenario.name == "Stale Runbook - Deprecated Service"
        assert len(scenario.trap_actions) > 0
    
    def test_list_scenarios_by_type(self, framework):
        """Test filtering scenarios by type."""
        cascade_scenarios = framework.list_scenarios(ScenarioType.CASCADING_FAILURE)
        
        assert all(s.scenario_type == ScenarioType.CASCADING_FAILURE for s in cascade_scenarios)
    
    @pytest.mark.asyncio
    async def test_run_scenario_pass(self, framework):
        """Test running a scenario that passes."""
        async def good_investigation(scenario_data):
            return {
                "hypotheses": [{
                    "summary": "Database connection pool exhaustion",
                    "confidence": 0.65,
                }],
                "primary_hypothesis": {
                    "summary": "Database connection pool exhaustion",
                    "confidence": 0.65,
                    "recommended_action": "Scale connection pool",
                    "evidence": [
                        {"interpretation": "Connections at 485/500"},
                        {"interpretation": "Wait events elevated"},
                    ],
                    "counter_checks": [
                        {"description": "Check if connections are idle"},
                    ],
                },
                "escalated": False,
            }
        
        result = await framework.run_scenario("stale_runbook_001", good_investigation)
        
        assert result.ai_confidence == 0.65
        assert len(result.checks) > 0
    
    @pytest.mark.asyncio
    async def test_run_scenario_detects_trap_action(self, framework):
        """Test that framework detects trap actions."""
        async def bad_investigation(scenario_data):
            return {
                "primary_hypothesis": {
                    "summary": "Gateway issue",
                    "confidence": 0.8,
                    "recommended_action": "Restart payment-gateway pods",  # This is a trap!
                    "evidence": [],
                    "counter_checks": [],
                },
            }
        
        result = await framework.run_scenario("stale_runbook_001", bad_investigation)
        
        # Should have failed trap check
        trap_check = next((c for c in result.checks if c.name == "Trap Action Avoidance"), None)
        assert trap_check is not None
        assert trap_check.result == CheckResult.FAIL
    
    @pytest.mark.asyncio
    async def test_run_scenario_checks_overconfidence(self, framework):
        """Test that framework flags overconfidence."""
        async def overconfident_investigation(scenario_data):
            return {
                "primary_hypothesis": {
                    "summary": "Monitoring glitch",
                    "confidence": 0.95,  # Too confident for false positive scenario
                    "evidence": [],
                    "counter_checks": [],
                },
            }
        
        result = await framework.run_scenario("false_positive_001", overconfident_investigation)
        
        confidence_check = next((c for c in result.checks if c.name == "Confidence Calibration"), None)
        assert confidence_check is not None
        # Should flag overconfidence
        assert confidence_check.result in (CheckResult.FAIL, CheckResult.PARTIAL)
    
    def test_generate_report(self, framework):
        """Test report generation."""
        # Create mock results
        results = [
            ScenarioResult(
                scenario=framework.get_scenario("stale_runbook_001"),
                overall_pass=True,
                score=85.0,
            ),
            ScenarioResult(
                scenario=framework.get_scenario("false_positive_001"),
                overall_pass=False,
                score=40.0,
            ),
        ]
        
        report = framework.generate_report(results)
        
        assert "# AI Game Day Report" in report
        assert "Total Scenarios: 2" in report
        assert "Passed: 1" in report


# =============================================================================
# Safety Prompts Tests
# =============================================================================

class TestSafetyPrompts:
    """Tests for safety prompts."""
    
    def test_inject_safety_preamble(self):
        """Test injecting safety preamble."""
        prompt = "Analyze this issue: High latency"
        result = inject_safety_preamble(prompt)
        
        assert "CRITICAL AI SAFETY RULES" in result
        assert "Hypothesis, Not Fact" in result
        assert "Analyze this issue: High latency" in result
    
    def test_add_deliberate_checklist(self):
        """Test adding deliberate checklist."""
        prompt = "Take action X"
        result = add_deliberate_checklist(prompt)
        
        assert "Deliberate Reasoning Checklist" in result
        assert "Evidence Gathered" in result
        assert "Rollback Plan" in result
    
    def test_format_hypothesis_output(self):
        """Test formatting hypothesis output."""
        output = format_hypothesis_output(
            investigation_id="test-123",
            alert_name="HighErrorRate",
            primary_summary="Database overload",
            confidence=0.75,
            evidence=[
                {"source": "prometheus", "interpretation": "High connection count", "confidence": 0.8},
            ],
            counter_checks=[
                {"description": "Check idle connections", "command": "SELECT ..."},
            ],
            blast_radius="single_service",
            blast_radius_details="payment-api",
            recommended_action="Scale pool",
            action_command="kubectl scale ...",
            reversible=True,
            requires_approval=True,
            approval_reason="Changes production config",
            rollback_steps=["Revert scale"],
            alternative_hypotheses=[],
            verification_steps=["Check metrics"],
            escalation_triggers=["Confidence drops"],
            context_documents=["runbook/db.md"],
        )
        
        assert "**Investigation ID:** test-123" in output
        assert "**Confidence:** 75% (high)" in output
        assert "This output is a HYPOTHESIS" in output


# =============================================================================
# Integration Tests
# =============================================================================

class TestAISafetyIntegration:
    """Integration tests for AI safety features."""
    
    @pytest.fixture
    def temp_db_dir(self, tmp_path):
        """Create temp directory for databases."""
        return tmp_path
    
    def test_metrics_and_budget_integration(self, temp_db_dir):
        """Test that metrics tracker and error budget work together."""
        metrics = AIMetricsTracker(db_path=temp_db_dir / "metrics.db")
        budget = AIErrorBudget(
            db_path=temp_db_dir / "budget.db",
            config=ErrorBudgetConfig(min_samples=3),
        )
        
        # Simulate investigation workflow
        for i in range(5):
            # Record investigation
            record = InvestigationRecord(
                investigation_id=f"int-{i}",
                alert_name="Test",
                confidence_reported=0.7,
                severity="high",
            )
            metrics.record_investigation(record)
            
            # Simulate outcome (60% correct)
            correct = i < 3
            metrics.update_outcome(f"int-{i}", outcome_correct=correct)
            budget.record_high_severity_outcome(correct=correct, investigation_id=f"int-{i}")
        
        # Check metrics
        accuracy = metrics.get_accuracy_rate(days=1, severity="high")
        assert accuracy == 0.6
        
        # Check budget (60% < 80% target = exhausted)
        status = budget.get_budget_status(BudgetType.HIGH_SEVERITY_ACCURACY)
        assert status.exhausted
        assert budget.is_conservative_mode()
    
    def test_hypothesis_with_telemetry(self, temp_db_dir):
        """Test creating hypothesis and recording telemetry."""
        metrics = AIMetricsTracker(db_path=temp_db_dir / "metrics.db")
        
        # Create hypothesis
        hypothesis = AIHypothesis(
            summary="Database connection exhaustion",
            confidence=0.75,
            blast_radius=BlastRadius.SINGLE_SERVICE,
            recommended_action="Scale connection pool",
        )
        # Note: add_evidence will update confidence based on evidence
        hypothesis.add_evidence(Evidence(
            source="prometheus",
            query="pg_connections",
            raw_data=485,
            interpretation="Near max connections",
            confidence=0.85,
        ))
        
        # Record as investigation - use the UPDATED confidence after adding evidence
        record = InvestigationRecord(
            investigation_id=hypothesis.hypothesis_id,
            alert_name="HighErrorRate",
            confidence_reported=hypothesis.confidence,  # This will be updated by add_evidence
            primary_hypothesis=hypothesis.summary,
            evidence_count=len(hypothesis.evidence),
            context_documents=[e.document_id for e in hypothesis.evidence if e.document_id],
        )
        metrics.record_investigation(record)
        
        # Verify recorded
        stats = metrics.get_statistics(days=1)
        assert stats["total_investigations"] == 1
        # Confidence is updated by add_evidence (0.85 + 0.05 bonus = 0.9)
        assert stats["average_confidence"] == hypothesis.confidence


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
