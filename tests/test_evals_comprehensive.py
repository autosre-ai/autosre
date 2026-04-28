"""
Comprehensive tests for the evaluation framework.
"""

import pytest
import tempfile
import json
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, AsyncMock

from autosre.evals import (
    Scenario,
    ScenarioResult,
    EvalRunner,
    EvalStore,
    run_scenario,
    list_scenarios,
    get_results,
    load_scenario,
)
from autosre.evals.metrics import EvalMetrics, calculate_metrics


class TestScenarioModel:
    """Tests for Scenario model."""
    
    def test_create_minimal_scenario(self):
        """Test creating scenario with minimal fields."""
        scenario = Scenario(
            name="test-scenario",
            description="A test scenario",
            expected_root_cause="CPU spike from deployment"
        )
        
        assert scenario.name == "test-scenario"
        assert scenario.description == "A test scenario"
        assert scenario.difficulty == "medium"  # default
        assert scenario.services == []
        assert scenario.changes == []
    
    def test_create_full_scenario(self):
        """Test creating scenario with all fields."""
        scenario = Scenario(
            id="scenario-123",
            name="full-scenario",
            description="Full test scenario",
            difficulty="hard",
            setup_steps=["step1", "step2"],
            alert={"name": "HighCPU", "severity": "critical"},
            services=[{"name": "api", "namespace": "prod"}],
            changes=[{"type": "deployment", "service": "api"}],
            metrics={"cpu": 95},
            expected_root_cause="Bad deployment",
            expected_service="api",
            expected_runbook="rollback",
            expected_action="kubectl rollout undo",
            max_time_seconds=120
        )
        
        assert scenario.id == "scenario-123"
        assert scenario.difficulty == "hard"
        assert len(scenario.setup_steps) == 2
        assert scenario.alert["name"] == "HighCPU"
        assert scenario.max_time_seconds == 120
    
    def test_scenario_defaults(self):
        """Test scenario default values."""
        scenario = Scenario(
            name="minimal",
            description="Test",
            expected_root_cause="Something"
        )
        
        assert scenario.id == ""
        assert scenario.difficulty == "medium"
        assert scenario.max_time_seconds == 300
        assert scenario.expected_service is None
        assert scenario.expected_runbook is None


class TestScenarioResult:
    """Tests for ScenarioResult model."""
    
    def test_create_result(self):
        """Test creating scenario result."""
        result = ScenarioResult(
            scenario="test-scenario",
            success=True,
            root_cause_correct=True,
            service_correct=True
        )
        
        assert result.scenario == "test-scenario"
        assert result.success is True
        assert result.root_cause_correct is True
    
    def test_result_defaults(self):
        """Test result default values."""
        result = ScenarioResult(
            scenario="test",
            success=False
        )
        
        assert result.root_cause_correct is False
        assert result.service_correct is False
        assert result.runbook_correct is False
        assert result.action_correct is False
        assert result.accuracy == 0.0
    
    def test_compute_accuracy(self):
        """Test accuracy computation."""
        result = ScenarioResult(
            scenario="test",
            success=True,
            root_cause_correct=True,
            service_correct=True,
            runbook_correct=False,
            action_correct=False
        )
        
        accuracy = result.compute_accuracy()
        assert accuracy == 0.5  # 2 out of 4 correct
    
    def test_compute_accuracy_all_correct(self):
        """Test accuracy computation with all correct."""
        result = ScenarioResult(
            scenario="test",
            success=True,
            root_cause_correct=True,
            service_correct=True,
            runbook_correct=True,
            action_correct=True
        )
        
        accuracy = result.compute_accuracy()
        assert accuracy == 1.0
    
    def test_score_alias(self):
        """Test score property is alias for accuracy."""
        result = ScenarioResult(
            scenario="test",
            success=True,
            accuracy=0.75
        )
        
        assert result.score == 0.75
    
    def test_passed_alias(self):
        """Test passed property."""
        result = ScenarioResult(scenario="test", success=True)
        assert result.passed is True
        
        result = ScenarioResult(scenario="test", success=False)
        assert result.passed is False
    
    def test_result_run_at_auto_set(self):
        """Test run_at is automatically set."""
        result = ScenarioResult(scenario="test", success=True)
        
        assert result.run_at is not None
        assert isinstance(result.run_at, datetime)


class TestEvalStore:
    """Tests for EvalStore."""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            yield f.name
    
    def test_create_store(self, temp_db):
        """Test creating eval store."""
        store = EvalStore(temp_db)
        assert store.db_path == temp_db
    
    def test_store_default_path(self):
        """Test store with default path."""
        store = EvalStore()
        assert store.db_path is not None
        assert "evals.db" in store.db_path
    
    def test_save_and_get_result(self, temp_db):
        """Test saving and retrieving results."""
        store = EvalStore(temp_db)
        
        result = ScenarioResult(
            scenario="test-scenario",
            success=True,
            accuracy=0.8,
            root_cause_correct=True
        )
        
        store.save_result(result)
        results = store.get_results(scenario="test-scenario")
        
        assert len(results) >= 1
        assert results[0]["scenario"] == "test-scenario"
    
    def test_get_results_with_limit(self, temp_db):
        """Test getting results with limit."""
        store = EvalStore(temp_db)
        
        # Save multiple results
        for i in range(5):
            result = ScenarioResult(
                scenario=f"scenario-{i}",
                success=True
            )
            store.save_result(result)
        
        results = store.get_results(limit=3)
        assert len(results) <= 3


class TestListScenarios:
    """Tests for list_scenarios function."""
    
    def test_list_returns_scenarios(self):
        """Test list_scenarios returns scenario data."""
        scenarios = list_scenarios()
        
        assert isinstance(scenarios, list)
        # Should have at least some built-in scenarios
        if scenarios:
            assert "name" in scenarios[0]
            assert "description" in scenarios[0]
    
    def test_scenarios_have_required_fields(self):
        """Test all scenarios have required fields."""
        scenarios = list_scenarios()
        
        for scenario in scenarios:
            assert "name" in scenario
            assert "description" in scenario


class TestLoadScenario:
    """Tests for load_scenario function."""
    
    def test_load_builtin_scenario(self):
        """Test loading built-in scenario."""
        scenarios = list_scenarios()
        if scenarios:
            name = scenarios[0]["name"]
            scenario = load_scenario(name)
            
            assert scenario is not None
            assert scenario.name == name
    
    def test_load_nonexistent_scenario(self):
        """Test loading nonexistent scenario returns None."""
        scenario = load_scenario("definitely-not-a-real-scenario-xyz")
        assert scenario is None


class TestEvalMetrics:
    """Tests for EvalMetrics."""
    
    def test_create_metrics(self):
        """Test creating eval metrics."""
        metrics = EvalMetrics(
            root_cause_accuracy=0.85,
            time_to_root_cause=15.5,
            runbook_accuracy=0.7,
            action_accuracy=0.9
        )
        
        assert metrics.root_cause_accuracy == 0.85
        assert metrics.time_to_root_cause == 15.5
        assert metrics.runbook_accuracy == 0.7
    
    def test_metrics_defaults(self):
        """Test metrics default values."""
        metrics = EvalMetrics()
        
        assert metrics.root_cause_accuracy == 0.0
        assert metrics.time_to_root_cause is None
        assert metrics.runbook_accuracy == 0.0
    
    def test_overall_accuracy(self):
        """Test overall accuracy calculation."""
        metrics = EvalMetrics(
            root_cause_accuracy=0.9,
            runbook_accuracy=0.8,
            action_accuracy=0.7
        )
        
        expected = (0.9 + 0.8 + 0.7) / 3
        assert metrics.overall_accuracy == pytest.approx(expected)
    
    def test_precision_and_recall(self):
        """Test precision and recall properties."""
        metrics = EvalMetrics(
            root_cause_accuracy=0.8,
            false_positives=2,
            false_negatives=1
        )
        
        assert metrics.precision >= 0
        assert metrics.recall >= 0
    
    def test_f1_score(self):
        """Test F1 score calculation."""
        metrics = EvalMetrics(
            root_cause_accuracy=0.8,
            false_positives=1,
            false_negatives=1
        )
        
        assert metrics.f1_score >= 0


class TestCalculateMetrics:
    """Tests for calculate_metrics function."""
    
    def test_calculate_with_scenario_and_result(self):
        """Test calculating metrics."""
        expected = {
            "root_cause": "CPU spike",
            "service": "api"
        }
        
        actual = {
            "root_cause": "CPU spike",
            "service": "api",
            "confidence": 0.9
        }
        
        timing = {
            "detection_time": 5.0,
            "root_cause_time": 10.0,
            "resolution_time": 15.0
        }
        
        metrics = calculate_metrics(expected, actual, timing)
        
        assert isinstance(metrics, EvalMetrics)
        assert metrics.time_to_root_cause == 10.0
    
    def test_calculate_with_exact_match(self):
        """Test metrics with exact root cause match."""
        expected = {"root_cause": "deployment rollout"}
        actual = {"root_cause": "deployment rollout"}
        timing = {}
        
        metrics = calculate_metrics(expected, actual, timing)
        assert metrics.root_cause_accuracy == 1.0
    
    def test_calculate_with_partial_match(self):
        """Test metrics with partial match."""
        expected = {"root_cause": "cpu"}
        actual = {"root_cause": "high cpu usage"}
        timing = {}
        
        metrics = calculate_metrics(expected, actual, timing)
        assert metrics.root_cause_accuracy == 0.7  # Partial match
    
    def test_calculate_with_no_match(self):
        """Test metrics with no match."""
        expected = {"root_cause": "deployment issue"}
        actual = {"root_cause": "network problem"}
        timing = {}
        
        metrics = calculate_metrics(expected, actual, timing)
        assert metrics.root_cause_accuracy == 0.0


class TestRunScenario:
    """Tests for run_scenario function."""
    
    @pytest.mark.asyncio
    async def test_run_builtin_scenario(self):
        """Test running a built-in scenario."""
        scenarios = list_scenarios()
        if scenarios:
            name = scenarios[0]["name"]
            result = await run_scenario(name)
            
            assert "success" in result
            assert "scenario" in result or "metrics" in result
    
    @pytest.mark.asyncio
    async def test_run_nonexistent_scenario(self):
        """Test running nonexistent scenario."""
        result = await run_scenario("nonexistent-scenario-xyz")
        
        # Should indicate failure
        assert result.get("success") is False or "error" in result.get("message", "").lower() or result.get("success") is not True


class TestEvalRunner:
    """Tests for EvalRunner class."""
    
    def test_create_runner(self):
        """Test creating eval runner."""
        runner = EvalRunner()
        assert runner is not None


class TestGetResults:
    """Tests for get_results function."""
    
    def test_get_results_returns_list(self):
        """Test get_results returns a list."""
        results = get_results()
        
        assert isinstance(results, list)
    
    def test_get_results_with_scenario_filter(self):
        """Test filtering results by scenario."""
        results = get_results(scenario="nonexistent-scenario")
        
        # Should return empty or filtered list
        assert isinstance(results, list)
    
    def test_get_results_with_limit(self):
        """Test limiting results."""
        results = get_results(limit=5)
        
        assert isinstance(results, list)
        assert len(results) <= 5
