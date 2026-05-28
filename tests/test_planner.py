"""Tests for Investigation Planner."""
import json
import pytest

from autosre.agents.planner_v1 import Planner, InvestigationStep, LLMClient


class TestInvestigationStep:
    """Tests for InvestigationStep dataclass."""
    
    def test_step_creation(self):
        """Test creating an investigation step."""
        step = InvestigationStep(
            id="test_step",
            action="gather_metrics",
            target="api-service",
            reason="Test reason",
        )
        assert step.id == "test_step"
        assert step.action == "gather_metrics"
        assert step.target == "api-service"
        assert step.priority == 1
        assert step.dependencies == []
        assert step.completed is False
        assert step.result is None
    
    def test_step_with_dependencies(self):
        """Test step with dependencies."""
        step = InvestigationStep(
            id="step2",
            action="check_logs",
            target="api-service",
            reason="Find errors",
            priority=2,
            dependencies=["step1"],
        )
        assert step.dependencies == ["step1"]


class TestPlanner:
    """Tests for Planner class."""
    
    def test_available_actions(self):
        """Test that available actions are defined."""
        planner = Planner()
        assert len(planner.AVAILABLE_ACTIONS) > 0
        assert "gather_metrics" in planner.AVAILABLE_ACTIONS
        assert "check_logs" in planner.AVAILABLE_ACTIONS
    
    @pytest.mark.asyncio
    async def test_heuristic_plan_latency(self):
        """Test heuristic plan for latency alert."""
        planner = Planner()
        
        alert = {
            "alert_type": "latency",
            "service": "api-service",
            "message": "High latency detected",
        }
        
        steps = planner._generate_heuristic_plan(alert, None)
        
        # Should have multiple steps
        assert len(steps) >= 3
        
        # First step should be metrics
        assert steps[0].action == "gather_metrics"
        
        # Should include traces for latency
        trace_steps = [s for s in steps if s.action == "check_traces"]
        assert len(trace_steps) > 0
    
    @pytest.mark.asyncio
    async def test_heuristic_plan_error(self):
        """Test heuristic plan for error alert."""
        planner = Planner()
        
        alert = {
            "alert_type": "error_rate",
            "service": "checkout-service",
            "message": "500 errors increased",
        }
        
        steps = planner._generate_heuristic_plan(alert, None)
        
        # Should include logs for error investigation
        log_steps = [s for s in steps if s.action == "check_logs"]
        assert len(log_steps) > 0
    
    @pytest.mark.asyncio
    async def test_heuristic_plan_memory(self):
        """Test heuristic plan for memory alert."""
        planner = Planner()
        
        alert = {
            "alert_type": "resource",
            "service": "api-gateway",
            "message": "OOM killed pod",
        }
        
        steps = planner._generate_heuristic_plan(alert, None)
        
        # Should check Kubernetes for OOM
        k8s_steps = [s for s in steps if s.action == "check_kubernetes"]
        assert len(k8s_steps) > 0
    
    @pytest.mark.asyncio
    async def test_plan_without_llm(self):
        """Test planning falls back to heuristics when no LLM."""
        planner = Planner()
        # Force no LLM client
        planner._llm_client = LLMClient()
        planner._llm_client.provider = None
        planner._llm_client.client = None
        
        alert = {
            "alert_type": "latency",
            "service": "test-service",
            "message": "Slow response",
        }
        
        steps = await planner.plan(alert, None, [])
        
        assert len(steps) > 0
        assert steps[0].action == "gather_metrics"
    
    def test_parse_plan_response_valid(self):
        """Test parsing valid LLM response."""
        planner = Planner()
        
        response = '''
        [
            {"id": "step1", "action": "gather_metrics", "target": "api", "reason": "Check metrics", "priority": 1, "dependencies": []},
            {"id": "step2", "action": "check_logs", "target": "api", "reason": "Check logs", "priority": 2, "dependencies": ["step1"]}
        ]
        '''
        
        steps = planner._parse_plan_response(response)
        
        assert len(steps) == 2
        assert steps[0].id == "step1"
        assert steps[0].action == "gather_metrics"
        assert steps[1].dependencies == ["step1"]
    
    def test_parse_plan_response_with_text(self):
        """Test parsing LLM response with surrounding text."""
        planner = Planner()
        
        response = '''
        Here's my investigation plan:
        [
            {"id": "step1", "action": "gather_metrics", "target": "api", "reason": "Check metrics", "priority": 1, "dependencies": []}
        ]
        This should help identify the issue.
        '''
        
        steps = planner._parse_plan_response(response)
        
        assert len(steps) == 1
        assert steps[0].action == "gather_metrics"
    
    def test_parse_plan_response_invalid_action(self):
        """Test that invalid actions are skipped."""
        planner = Planner()
        
        response = '''
        [
            {"id": "step1", "action": "invalid_action", "target": "api", "reason": "Bad", "priority": 1, "dependencies": []},
            {"id": "step2", "action": "gather_metrics", "target": "api", "reason": "Good", "priority": 1, "dependencies": []}
        ]
        '''
        
        steps = planner._parse_plan_response(response)
        
        # Only valid action should remain
        assert len(steps) == 1
        assert steps[0].action == "gather_metrics"
    
    def test_parse_plan_response_invalid_json(self):
        """Test parsing invalid JSON returns empty list."""
        planner = Planner()
        
        response = "This is not valid JSON"
        
        steps = planner._parse_plan_response(response)
        
        assert steps == []
    
    @pytest.mark.asyncio
    async def test_replan_with_deploy_finding(self):
        """Test replanning when deployment is found."""
        planner = Planner()
        
        # Mock context with service name
        class MockContext:
            service_name = "api-service"
        
        findings = {
            "evidence": [
                {
                    "source": "changes",
                    "data": {
                        "recent_deploys": [
                            {"service": "api-service", "version": "v1.2.3"}
                        ]
                    }
                }
            ]
        }
        
        steps = await planner.replan(MockContext(), findings)
        
        # Should add investigation of the deploy
        assert len(steps) > 0
        assert any(s.id == "investigate_deploy" for s in steps)
    
    @pytest.mark.asyncio
    async def test_replan_with_oom(self):
        """Test replanning when OOM is detected."""
        planner = Planner()
        
        class MockContext:
            service_name = "api-service"
        
        findings = {
            "evidence": [
                {
                    "source": "kubernetes",
                    "data": {
                        "pod_status": "OOMKilled"
                    }
                }
            ]
        }
        
        steps = await planner.replan(MockContext(), findings)
        
        # Should add resource investigation
        assert len(steps) > 0
        assert any(s.id == "investigate_resources" for s in steps)


class TestLLMClient:
    """Tests for LLMClient class."""
    
    def test_client_creation(self):
        """Test LLM client can be created."""
        client = LLMClient()
        # Should not raise, even if no LLM available
        assert isinstance(client.available, bool)
    
    def test_client_unavailable(self):
        """Test client reports unavailable when no providers."""
        client = LLMClient()
        client.provider = None
        client.client = None
        
        assert client.available is False
    
    @pytest.mark.asyncio
    async def test_generate_returns_none_when_unavailable(self):
        """Test generate returns None when no LLM."""
        client = LLMClient()
        client.provider = None
        client.client = None
        
        result = await client.generate("test prompt")
        
        assert result is None
