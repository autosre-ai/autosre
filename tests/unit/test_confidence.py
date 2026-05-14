"""Tests for confidence scoring system."""

import pytest
from pathlib import Path
from uuid import uuid4

from autosre.core.confidence import (
    ConfidenceCalculator,
    ConfidenceLevel,
    ConfidenceScore,
    Evidence,
    EvidenceType,
    HistoricalOutcome,
    RunbookMatchScore,
    get_calculator,
)


class TestConfidenceLevel:
    """Tests for ConfidenceLevel enum."""
    
    def test_from_score_very_high(self):
        assert ConfidenceLevel.from_score(95) == ConfidenceLevel.VERY_HIGH
        assert ConfidenceLevel.from_score(90) == ConfidenceLevel.VERY_HIGH
    
    def test_from_score_high(self):
        assert ConfidenceLevel.from_score(85) == ConfidenceLevel.HIGH
        assert ConfidenceLevel.from_score(75) == ConfidenceLevel.HIGH
    
    def test_from_score_medium(self):
        assert ConfidenceLevel.from_score(60) == ConfidenceLevel.MEDIUM
        assert ConfidenceLevel.from_score(50) == ConfidenceLevel.MEDIUM
    
    def test_from_score_low(self):
        assert ConfidenceLevel.from_score(30) == ConfidenceLevel.LOW
        assert ConfidenceLevel.from_score(25) == ConfidenceLevel.LOW
    
    def test_from_score_very_low(self):
        assert ConfidenceLevel.from_score(20) == ConfidenceLevel.VERY_LOW
        assert ConfidenceLevel.from_score(0) == ConfidenceLevel.VERY_LOW


class TestEvidence:
    """Tests for Evidence model."""
    
    def test_create_evidence(self):
        ev = Evidence(
            type=EvidenceType.RUNBOOK_MATCH,
            source="runbooks/cpu-high.md",
            summary="Matched CPU high runbook",
            data={"match_score": 0.85},
        )
        
        assert ev.id is not None
        assert ev.type == EvidenceType.RUNBOOK_MATCH
        assert ev.weight == 1.0
        assert ev.relevance_score == 0.5


class TestRunbookMatchScore:
    """Tests for RunbookMatchScore."""
    
    def test_calculate_overall(self):
        score = RunbookMatchScore(
            runbook_id="rb-001",
            runbook_name="cpu-high-runbook",
            alert_name_match=1.0,
            symptom_match=0.8,
            context_match=0.5,
            keyword_match=0.6,
        )
        
        overall = score.calculate_overall()
        
        # Weights: alert=0.3, symptom=0.35, context=0.2, keyword=0.15
        expected = 1.0 * 0.3 + 0.8 * 0.35 + 0.5 * 0.2 + 0.6 * 0.15
        assert abs(overall - expected) < 0.01
    
    def test_match_factors(self):
        score = RunbookMatchScore(
            runbook_id="rb-001",
            runbook_name="test",
            match_factors=["Alert name matches", "Found 3 keywords"],
            mismatch_factors=["Different namespace"],
        )
        
        assert len(score.match_factors) == 2
        assert len(score.mismatch_factors) == 1


class TestHistoricalOutcome:
    """Tests for HistoricalOutcome."""
    
    def test_success_rate(self):
        outcome = HistoricalOutcome(
            action_type="restart",
            alert_pattern="HighCPU",
            total_executions=10,
            successful_executions=8,
            failed_executions=2,
        )
        
        assert outcome.success_rate == 0.8
    
    def test_success_rate_zero_executions(self):
        outcome = HistoricalOutcome(
            action_type="restart",
            alert_pattern="HighCPU",
        )
        
        assert outcome.success_rate == 0.0
    
    def test_confidence_boost_not_enough_data(self):
        outcome = HistoricalOutcome(
            action_type="restart",
            alert_pattern="HighCPU",
            total_executions=2,
            successful_executions=2,
        )
        
        assert outcome.confidence_boost == 0.0
    
    def test_confidence_boost_high_success(self):
        from datetime import datetime, timezone
        
        outcome = HistoricalOutcome(
            action_type="restart",
            alert_pattern="HighCPU",
            total_executions=10,
            successful_executions=10,
            last_execution=datetime.now(timezone.utc),
        )
        
        boost = outcome.confidence_boost
        assert boost > 20  # High success + recent


class TestConfidenceScore:
    """Tests for ConfidenceScore."""
    
    def test_create_confidence_score(self):
        score = ConfidenceScore(
            score=75.0,
            reasoning="High CPU matches restart pattern",
        )
        
        assert score.id is not None
        assert score.score == 75.0
        assert score.level == ConfidenceLevel.HIGH
    
    def test_add_evidence(self):
        score = ConfidenceScore(
            score=50.0,
            reasoning="Test",
            runbook_match_score=60.0,
            alert_pattern_score=50.0,
            historical_success_score=40.0,
            context_relevance_score=50.0,
        )
        
        ev = Evidence(
            type=EvidenceType.METRIC_ANALYSIS,
            source="prometheus",
            summary="CPU at 95%",
            confidence_contribution=10.0,
        )
        
        score.add_evidence(ev)
        
        assert len(score.evidence) == 1
        # Score should be recalculated
        assert score.score != 50.0
    
    def test_to_summary(self):
        score = ConfidenceScore(
            score=80.0,
            reasoning="High CPU indicates need for restart",
            runbook_match_score=85.0,
            positive_factors=["Runbook match found"],
            negative_factors=["Production environment"],
        )
        
        summary = score.to_summary()
        
        assert "80.0%" in summary
        assert "HIGH" in summary.upper()
        assert "Runbook match found" in summary


class TestConfidenceCalculator:
    """Tests for ConfidenceCalculator."""
    
    def test_calculate_runbook_match(self, tmp_path: Path):
        calc = ConfidenceCalculator(history_store_path=tmp_path / "history.json")
        
        score = calc.calculate_runbook_match(
            alert_name="HighCPUUsage",
            alert_description="CPU usage above 90% for 5 minutes",
            alert_labels={"service": "api", "env": "prod"},
            runbook_content="""
            # High CPU Runbook
            When CPU is high, restart the service.
            Monitor for 5 minutes after restart.
            """,
            runbook_metadata={
                "id": "rb-001",
                "name": "High CPU Runbook",
                "alerts": ["HighCPUUsage"],
                "labels": {"service": "api"},
            },
        )
        
        assert score.alert_name_match == 1.0  # Exact match
        assert score.overall_score > 0.5
        assert "Runbook explicitly handles" in score.match_factors[0]
    
    def test_calculate_pattern_score(self, tmp_path: Path):
        calc = ConfidenceCalculator(history_store_path=tmp_path / "history.json")
        
        similar_alerts = [
            {"resolved": True, "resolution_type": "restart", "days_ago": 2},
            {"resolved": True, "resolution_type": "restart", "days_ago": 5},
            {"resolved": True, "resolution_type": "restart", "days_ago": 10},
            {"resolved": False},
        ]
        
        score = calc.calculate_pattern_score(
            alert_name="HighCPU",
            alert_labels={},
            similar_alerts=similar_alerts,
        )
        
        # 3/4 resolved = 75% resolution rate
        assert score > 50
    
    def test_record_and_retrieve_outcome(self, tmp_path: Path):
        calc = ConfidenceCalculator(history_store_path=tmp_path / "history.json")
        
        # Record outcomes
        calc.record_outcome("restart", "HighCPU", success=True)
        calc.record_outcome("restart", "HighCPU", success=True)
        calc.record_outcome("restart", "HighCPU", success=False)
        
        boost, outcome = calc.get_historical_score("restart", "HighCPU")
        
        assert outcome is not None
        assert outcome.total_executions == 3
        assert outcome.successful_executions == 2
        assert abs(outcome.success_rate - 0.67) < 0.1
    
    def test_full_calculate(self, tmp_path: Path):
        calc = ConfidenceCalculator(history_store_path=tmp_path / "history.json")
        
        # Record some history
        for _ in range(5):
            calc.record_outcome("restart", "HighCPU", success=True)
        
        runbook_match = RunbookMatchScore(
            runbook_id="rb-001",
            runbook_name="CPU Runbook",
            alert_name_match=1.0,
            symptom_match=0.8,
        )
        runbook_match.calculate_overall()
        
        confidence = calc.calculate(
            action_type="restart",
            alert_name="HighCPU",
            alert_description="CPU at 95%",
            alert_labels={"severity": "critical", "env": "production"},
            reasoning="High CPU indicates service overload, restart recommended",
            runbook_match=runbook_match,
            similar_alerts=[
                {"resolved": True, "resolution_type": "restart"},
                {"resolved": True, "resolution_type": "restart"},
            ],
            model_used="gpt-4o",
        )
        
        assert confidence.score > 0
        assert confidence.level in ConfidenceLevel
        assert len(confidence.evidence) > 0
        assert "High severity alert" in " ".join(confidence.positive_factors)
        assert confidence.model_used == "gpt-4o"


class TestGetCalculator:
    """Tests for global calculator accessor."""
    
    def test_get_calculator(self, tmp_path: Path):
        calc = get_calculator(tmp_path / "history.json")
        assert calc is not None
        assert isinstance(calc, ConfidenceCalculator)
