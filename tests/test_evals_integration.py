"""
Integration tests for the eval framework.
"""

import pytest
import tempfile
import os

from autosre.evals.framework import (
    Scenario,
    ScenarioResult,
    EvalStore,
    load_scenario,
    list_scenarios,
)
from autosre.evals.metrics import EvalMetrics


@pytest.fixture
def eval_store():
    """Create a temporary eval store."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "evals.db")
        yield EvalStore(db_path=db_path)


class TestScenarioLoading:
    """Test scenario loading from YAML files."""
    
    def test_list_scenarios(self):
        """Test listing available scenarios."""
        scenarios = list_scenarios()
        
        assert len(scenarios) >= 5
        
        # Check expected scenarios exist
        scenario_names = [s["name"] for s in scenarios]
        assert "high_cpu" in scenario_names
        assert "memory_leak" in scenario_names
        assert "deployment_rollback" in scenario_names
    
    def test_load_high_cpu_scenario(self):
        """Test loading the high CPU scenario."""
        scenario = load_scenario("high_cpu")
        
        assert scenario.name == "high_cpu"
        assert scenario.difficulty == "easy"
        assert "CPU" in scenario.description
    
    def test_load_memory_leak_scenario(self):
        """Test loading memory leak scenario."""
        scenario = load_scenario("memory_leak")
        
        assert scenario.name == "memory_leak"
    
    def test_load_nonexistent_scenario_returns_none(self):
        """Test loading a nonexistent scenario returns None."""
        scenario = load_scenario("nonexistent_scenario_xyz")
        assert scenario is None
    
    def test_scenario_has_alert(self):
        """Test scenarios have alert information."""
        scenario = load_scenario("high_cpu")
        
        assert scenario.alert is not None
        assert "name" in scenario.alert
        assert scenario.alert["service_name"] == "api-gateway"
    
    def test_scenario_has_services(self):
        """Test scenarios have service topology."""
        scenario = load_scenario("high_cpu")
        
        assert scenario.services is not None
        assert len(scenario.services) >= 1
    
    def test_scenario_has_expected_values(self):
        """Test scenarios have expected analysis values."""
        scenario = load_scenario("high_cpu")
        
        assert scenario.expected_root_cause is not None
        assert scenario.expected_service is not None


class TestScenarioResult:
    """Test ScenarioResult model."""
    
    def test_create_result(self):
        """Test creating a scenario result."""
        result = ScenarioResult(
            scenario="high_cpu",
            success=True,
            agent_root_cause="High CPU due to traffic spike",
        )
        
        assert result.scenario == "high_cpu"
        assert result.success is True
    
    def test_result_accuracy(self):
        """Test accuracy calculation."""
        result = ScenarioResult(
            scenario="test",
            success=True,
            root_cause_correct=True,
            service_correct=True,
            action_correct=False,
        )
        
        accuracy = result.compute_accuracy()
        
        # 2 out of 4 correct (runbook_correct defaults False)
        assert 0.25 <= accuracy <= 0.75


class TestEvalStore:
    """Test EvalStore persistence."""
    
    def test_save_and_retrieve(self, eval_store):
        """Test saving and retrieving results."""
        result = ScenarioResult(
            scenario="high_cpu",
            success=True,
            time_to_root_cause=30.0,
        )
        
        eval_store.save_result(result)
        
        results = eval_store.get_results()
        assert len(results) == 1
        assert results[0]["scenario"] == "high_cpu"
    
    def test_filter_by_scenario(self, eval_store):
        """Test filtering results by scenario."""
        # Add results for different scenarios
        for scenario in ["high_cpu", "memory_leak", "high_cpu"]:
            result = ScenarioResult(
                scenario=scenario,
                success=True,
            )
            eval_store.save_result(result)
        
        high_cpu_results = eval_store.get_results(scenario="high_cpu")
        assert len(high_cpu_results) == 2
        
        memory_results = eval_store.get_results(scenario="memory_leak")
        assert len(memory_results) == 1
    
    def test_scenario_stats(self, eval_store):
        """Test scenario statistics."""
        # Add mixed results
        for i in range(5):
            result = ScenarioResult(
                scenario="test",
                success=(i < 3),  # 3 successes, 2 failures
                time_to_root_cause=float(i * 10),
            )
            eval_store.save_result(result)
        
        stats = eval_store.get_scenario_stats("test")
        
        assert stats["total_runs"] == 5
        assert stats["successful_runs"] == 3
        assert stats["success_rate"] == 0.6


class TestEvalMetrics:
    """Test evaluation metrics class."""
    
    def test_create_metrics(self):
        """Test creating eval metrics."""
        from autosre.evals.metrics import EvalMetrics
        
        metrics = EvalMetrics()
        metrics.root_cause_accuracy = 0.8
        metrics.runbook_accuracy = 0.9
        
        assert metrics.root_cause_accuracy == 0.8
    
    def test_metrics_default_values(self):
        """Test default metric values."""
        from autosre.evals.metrics import EvalMetrics
        
        metrics = EvalMetrics()
        
        assert metrics.false_positives == 0
        assert metrics.root_cause_accuracy == 0.0


class TestEndToEndEval:
    """End-to-end eval workflow tests."""
    
    def test_full_eval_workflow(self, eval_store):
        """Test complete eval workflow."""
        # 1. List scenarios
        scenarios = list_scenarios()
        assert len(scenarios) > 0
        
        # 2. Load a scenario
        scenario = load_scenario("high_cpu")
        assert scenario is not None
        
        # 3. Create mock result (would normally run agent)
        result = ScenarioResult(
            scenario=scenario.name,
            success=True,
            agent_root_cause="High CPU from request validation",
            root_cause_correct=True,
            service_correct=True,
            action_correct=True,
            time_to_root_cause=45.0,
        )
        
        # 4. Save result
        eval_store.save_result(result)
        
        # 5. Get statistics
        stats = eval_store.get_scenario_stats(scenario.name)
        assert stats["total_runs"] == 1
        assert stats["success_rate"] == 1.0
