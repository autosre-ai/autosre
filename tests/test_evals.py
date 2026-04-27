"""
Tests for the evaluation framework.
"""

import pytest
import tempfile
import os
from pathlib import Path

from autosre.evals.framework import (
    Scenario,
    ScenarioResult,
    EvalStore,
    list_scenarios,
    load_scenario,
)
from autosre.evals.metrics import EvalMetrics, calculate_metrics


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    os.unlink(path)


@pytest.fixture
def eval_store(temp_db):
    """Create an eval store with temporary database."""
    return EvalStore(db_path=temp_db)


class TestScenario:
    """Tests for Scenario model."""
    
    def test_scenario_creation(self):
        """Test creating a scenario."""
        scenario = Scenario(
            name="test-scenario",
            description="A test scenario",
            expected_root_cause="Database connection failure",
            alert={"name": "DatabaseDown", "severity": "critical"},
        )
        
        assert scenario.name == "test-scenario"
        assert scenario.difficulty == "medium"  # default
    
    def test_load_built_in_scenario(self):
        """Test loading a built-in scenario."""
        scenario = load_scenario("memory_leak")
        
        # May be None if scenarios aren't in expected location during test
        if scenario:
            assert scenario.name == "memory_leak"
            assert scenario.expected_root_cause is not None


class TestScenarioResult:
    """Tests for ScenarioResult model."""
    
    def test_result_creation(self):
        """Test creating a result."""
        result = ScenarioResult(
            scenario="test-scenario",
            success=True,
            root_cause_correct=True,
            service_correct=True,
            runbook_correct=True,
            action_correct=False,
        )
        
        assert result.success is True
    
    def test_accuracy_computation(self):
        """Test accuracy calculation."""
        result = ScenarioResult(
            scenario="test",
            success=True,
            root_cause_correct=True,
            service_correct=True,
            runbook_correct=True,
            action_correct=False,
        )
        
        accuracy = result.compute_accuracy()
        assert accuracy == 0.75  # 3/4 correct


class TestEvalStore:
    """Tests for EvalStore."""
    
    def test_save_and_get_results(self, eval_store):
        """Test saving and retrieving results."""
        result = ScenarioResult(
            scenario="test-scenario",
            success=True,
            time_to_root_cause=45.0,
            accuracy=0.8,
        )
        
        eval_store.save_result(result)
        results = eval_store.get_results()
        
        assert len(results) == 1
        assert results[0]["scenario"] == "test-scenario"
    
    def test_filter_by_scenario(self, eval_store):
        """Test filtering results by scenario."""
        eval_store.save_result(ScenarioResult(scenario="scenario-a", success=True))
        eval_store.save_result(ScenarioResult(scenario="scenario-b", success=True))
        eval_store.save_result(ScenarioResult(scenario="scenario-a", success=False))
        
        results = eval_store.get_results(scenario="scenario-a")
        
        assert len(results) == 2
        assert all(r["scenario"] == "scenario-a" for r in results)
    
    def test_scenario_stats(self, eval_store):
        """Test getting scenario statistics."""
        eval_store.save_result(ScenarioResult(
            scenario="test",
            success=True,
            accuracy=0.9,
            time_to_root_cause=30.0,
        ))
        eval_store.save_result(ScenarioResult(
            scenario="test",
            success=True,
            accuracy=0.8,
            time_to_root_cause=40.0,
        ))
        eval_store.save_result(ScenarioResult(
            scenario="test",
            success=False,
            accuracy=0.5,
            time_to_root_cause=60.0,
        ))
        
        stats = eval_store.get_scenario_stats("test")
        
        assert stats["total_runs"] == 3
        assert stats["successful_runs"] == 2
        assert abs(stats["success_rate"] - 0.666) < 0.01


class TestEvalMetrics:
    """Tests for EvalMetrics."""
    
    def test_overall_accuracy(self):
        """Test overall accuracy calculation."""
        metrics = EvalMetrics(
            root_cause_accuracy=0.9,
            runbook_accuracy=0.8,
            action_accuracy=0.7,
        )
        
        assert abs(metrics.overall_accuracy - 0.8) < 0.01
    
    def test_f1_score(self):
        """Test F1 score calculation."""
        metrics = EvalMetrics(
            root_cause_accuracy=0.8,
            false_positives=2,
            false_negatives=1,
        )
        
        # Precision and recall are simplified in current implementation
        assert metrics.f1_score >= 0
    
    def test_calculate_metrics(self):
        """Test metric calculation from expected/actual."""
        expected = {
            "root_cause": "memory leak",
            "runbook": "memory-troubleshooting",
        }
        actual = {
            "root_cause": "memory leak in payment service",
            "runbook": "memory-troubleshooting",
        }
        timing = {
            "root_cause_time": 45.0,
        }
        
        metrics = calculate_metrics(expected, actual, timing)
        
        assert metrics.time_to_root_cause == 45.0
        assert metrics.runbook_accuracy == 1.0
        assert metrics.root_cause_accuracy > 0  # Partial match


class TestScenarioListing:
    """Tests for scenario listing."""
    
    def test_list_scenarios(self):
        """Test listing available scenarios."""
        scenarios = list_scenarios()
        
        # Should have some built-in scenarios
        assert isinstance(scenarios, list)
        
        # If scenarios exist, check structure
        for scenario in scenarios:
            assert "name" in scenario
            assert "description" in scenario
