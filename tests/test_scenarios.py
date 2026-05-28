"""
Tests for the demo scenarios module.
"""

import pytest
from datetime import datetime

from autosre.scenarios import load_scenario, list_available_scenarios


class TestScenarioLoading:
    """Test scenario loading functionality."""
    
    def test_list_available_scenarios(self):
        """Test that list_available_scenarios returns expected scenarios."""
        scenarios = list_available_scenarios()
        assert isinstance(scenarios, list)
        assert len(scenarios) >= 5  # We have at least 5 scenarios
        
        # Check core scenarios exist
        assert "redis-connection" in scenarios
        assert "memory-leak" in scenarios
        assert "latency-spike" in scenarios
        assert "cascading-failure" in scenarios
        assert "config-drift" in scenarios
    
    def test_load_scenario_redis_connection(self):
        """Test loading redis-connection scenario."""
        scenario = load_scenario("redis-connection")
        
        assert scenario["id"] == "redis-connection"
        assert scenario["name"] == "Redis Connection Pool Exhaustion"
        assert scenario["service"] == "checkout-service"
        assert scenario["severity"] == "high"
        assert "root_cause" in scenario
        assert "recommendations" in scenario
        assert len(scenario["recommendations"]) > 0
    
    def test_load_scenario_memory_leak(self):
        """Test loading memory-leak scenario."""
        scenario = load_scenario("memory-leak")
        
        assert scenario["id"] == "memory-leak"
        assert scenario["service"] == "api-gateway"
        assert scenario["severity"] == "critical"
        assert "evidence_summary" in scenario
        assert "timeline" in scenario
    
    def test_load_scenario_not_found(self):
        """Test loading non-existent scenario raises error."""
        with pytest.raises(FileNotFoundError):
            load_scenario("non-existent-scenario")
    
    def test_dynamic_timestamps_applied(self):
        """Test that timestamp placeholders are replaced."""
        scenario = load_scenario("memory-leak")
        
        # Timeline should have actual times, not {now-Xh} placeholders
        for event in scenario["timeline"]:
            assert "{now" not in event["time"]
            # Should be in HH:MM:SS format
            assert len(event["time"]) == 8
            assert event["time"][2] == ":"
            assert event["time"][5] == ":"
    
    def test_evidence_summary_timestamps(self):
        """Test that evidence_summary timestamps are replaced."""
        scenario = load_scenario("memory-leak")
        
        first_occurrence = scenario["evidence_summary"]["first_occurrence"]
        assert "{now" not in first_occurrence
        # Should be a time string
        assert ":" in first_occurrence


class TestScenarioContent:
    """Test scenario content structure."""
    
    def test_all_scenarios_have_required_fields(self):
        """Test that all scenarios have required fields."""
        required_fields = [
            "id", "name", "alert", "service", "severity", 
            "root_cause", "recommendations"
        ]
        
        for scenario_id in list_available_scenarios():
            scenario = load_scenario(scenario_id)
            for field in required_fields:
                assert field in scenario, f"{scenario_id} missing field: {field}"
    
    def test_all_scenarios_have_service_topology(self):
        """Test that all scenarios have service topology."""
        for scenario_id in list_available_scenarios():
            scenario = load_scenario(scenario_id)
            assert "service_topology" in scenario, f"{scenario_id} missing service_topology"
            topology = scenario["service_topology"]
            assert "dependencies" in topology
            assert "upstream" in topology
    
    def test_all_scenarios_have_hypotheses(self):
        """Test that all scenarios have hypotheses."""
        for scenario_id in list_available_scenarios():
            scenario = load_scenario(scenario_id)
            assert "hypotheses" in scenario, f"{scenario_id} missing hypotheses"
            assert len(scenario["hypotheses"]) >= 2
    
    def test_recommendations_are_actionable(self):
        """Test that recommendations are present and non-empty."""
        for scenario_id in list_available_scenarios():
            scenario = load_scenario(scenario_id)
            recs = scenario["recommendations"]
            assert len(recs) >= 2, f"{scenario_id} should have at least 2 recommendations"
            for rec in recs:
                assert len(rec) > 10, f"Recommendation in {scenario_id} too short: {rec}"
                assert not rec.startswith("{"), f"Recommendation in {scenario_id} has unprocessed placeholder"
