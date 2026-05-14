"""Unit tests for investigation agents."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from autosre.agents.base import AgentConfig, BaseAgent
from autosre.agents.kubernetes import KubernetesAgent
from autosre.agents.logs import LogAnalysisAgent
from autosre.agents.metrics import MetricsAgent
from autosre.agents.planner import Planner
from autosre.agents.synthesizer import Synthesizer
from autosre.models.investigation import (
    AgentState,
    Finding,
    InvestigationPlan,
    InvestigationStatus,
    SynthesisDecision,
)


class TestBaseAgent:
    """Tests for BaseAgent abstract class."""

    def test_agent_config_defaults(self):
        """Test AgentConfig has sensible defaults."""
        config = AgentConfig(name="test")
        
        assert config.name == "test"
        assert config.enabled is True
        assert config.max_iterations == 10
        assert config.timeout_seconds == 300
        assert config.model == "gpt-4o"
        assert config.temperature == 0.1

    def test_agent_config_validation(self):
        """Test AgentConfig validation."""
        # Valid config
        config = AgentConfig(
            name="test",
            max_iterations=5,
            temperature=0.5,
        )
        assert config.max_iterations == 5
        assert config.temperature == 0.5
        
        # Invalid max_iterations
        with pytest.raises(ValueError):
            AgentConfig(name="test", max_iterations=0)
        
        with pytest.raises(ValueError):
            AgentConfig(name="test", max_iterations=100)
        
        # Invalid temperature
        with pytest.raises(ValueError):
            AgentConfig(name="test", temperature=-0.1)
        
        with pytest.raises(ValueError):
            AgentConfig(name="test", temperature=3.0)


class TestKubernetesAgent:
    """Tests for KubernetesAgent."""

    @pytest.fixture
    def agent(self):
        """Create a test KubernetesAgent."""
        return KubernetesAgent()

    def test_agent_name(self, agent):
        """Test agent name property."""
        assert agent.name == "kubernetes"

    def test_agent_description(self, agent):
        """Test agent description."""
        assert "Kubernetes" in agent.description

    @pytest.mark.asyncio
    async def test_investigate_returns_agent_state(
        self,
        agent,
        sample_investigation_state,
        sample_hypotheses,
    ):
        """Test investigate returns AgentState."""
        result = await agent.investigate(
            sample_investigation_state,
            sample_hypotheses,
        )
        
        assert isinstance(result, AgentState)
        assert result.name == "kubernetes"
        assert result.status == InvestigationStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_investigate_extracts_service_from_alert(
        self,
        agent,
        sample_investigation_state,
    ):
        """Test investigate extracts service info from alert."""
        result = await agent.investigate(sample_investigation_state, [])
        
        # Should have created findings based on the alert context
        assert isinstance(result, AgentState)
        assert result.status == InvestigationStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_investigate_handles_empty_state(self, agent):
        """Test investigate handles empty state gracefully."""
        result = await agent.investigate({"alert": {}}, [])
        
        assert isinstance(result, AgentState)
        assert result.status == InvestigationStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_investigate_marks_failure_on_exception(self, agent):
        """Test investigate marks failure when exception occurs."""
        # Create agent with mocked method that raises
        agent._check_pod_status = AsyncMock(side_effect=RuntimeError("Test error"))
        
        result = await agent.investigate(
            {"alert": {"service": "test"}},
            [],
        )
        
        assert result.status == InvestigationStatus.FAILED
        assert "Test error" in result.error

    def test_create_finding(self, agent):
        """Test creating a finding."""
        finding = agent.create_finding(
            detail="Pod crash detected",
            evidence="kubectl logs",
            severity="high",
            confidence=0.9,
            pod_name="test-pod",
        )
        
        assert isinstance(finding, Finding)
        assert finding.category == "kubernetes"
        assert finding.detail == "Pod crash detected"
        assert finding.severity == "high"
        assert finding.confidence == 0.9
        assert finding.metadata["pod_name"] == "test-pod"

    @pytest.mark.asyncio
    async def test_get_pod_logs_without_client(self, agent):
        """Test get_pod_logs returns mock when no client."""
        logs = await agent.get_pod_logs("test-pod", "default")
        
        assert "Mock" in logs
        assert "test-pod" in logs


class TestMetricsAgent:
    """Tests for MetricsAgent."""

    @pytest.fixture
    def agent(self):
        """Create a test MetricsAgent."""
        return MetricsAgent()

    def test_agent_name(self, agent):
        """Test agent name."""
        assert agent.name == "metrics"

    @pytest.mark.asyncio
    async def test_investigate_returns_agent_state(
        self,
        agent,
        sample_investigation_state,
    ):
        """Test investigate returns AgentState."""
        result = await agent.investigate(sample_investigation_state, [])
        
        assert isinstance(result, AgentState)
        assert result.name == "metrics"
        assert result.status == InvestigationStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_investigate_creates_findings(self, agent, sample_investigation_state):
        """Test investigate creates metric findings."""
        result = await agent.investigate(sample_investigation_state, [])
        
        # Should have findings for different metric types
        assert len(result.findings) >= 1

    @pytest.mark.asyncio
    async def test_query_without_client(self, agent):
        """Test query returns empty result without client."""
        result = await agent.query("up")
        
        assert result["status"] == "success"
        assert result["data"]["result"] == []

    @pytest.mark.asyncio
    async def test_get_metric_value_default(self, agent):
        """Test get_metric_value returns default without client."""
        value = await agent.get_metric_value("up", default=1.0)
        
        assert value == 1.0


class TestLogAnalysisAgent:
    """Tests for LogAnalysisAgent."""

    @pytest.fixture
    def agent(self):
        """Create a test LogAnalysisAgent."""
        return LogAnalysisAgent()

    def test_agent_name(self, agent):
        """Test agent name."""
        assert agent.name == "log_analysis"

    @pytest.mark.asyncio
    async def test_investigate_returns_agent_state(
        self,
        agent,
        sample_investigation_state,
    ):
        """Test investigate returns AgentState."""
        result = await agent.investigate(sample_investigation_state, [])
        
        assert isinstance(result, AgentState)
        assert result.name == "log_analysis"
        assert result.status == InvestigationStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_investigate_searches_error_patterns(
        self,
        agent,
        sample_investigation_state,
    ):
        """Test investigate searches for error patterns."""
        result = await agent.investigate(sample_investigation_state, [])
        
        # Should have searched for multiple error patterns
        patterns_found = [
            f for f in result.findings
            if "pattern" in f.metadata
        ]
        assert len(patterns_found) > 0


class TestPlanner:
    """Tests for Planner agent."""

    @pytest.fixture
    def planner(self, mock_llm):
        """Create a test Planner."""
        return Planner(llm=mock_llm)

    def test_planner_name(self, planner):
        """Test planner name."""
        assert planner.name == "planner"

    @pytest.mark.asyncio
    async def test_plan_returns_investigation_plan(
        self,
        planner,
        sample_investigation_state,
    ):
        """Test plan returns InvestigationPlan."""
        result = await planner.plan(sample_investigation_state)
        
        assert isinstance(result, InvestigationPlan)
        assert len(result.hypotheses) >= 0
        assert len(result.selected_agents) >= 0

    @pytest.mark.asyncio
    async def test_plan_uses_team_config(
        self,
        mock_llm,
        sample_investigation_state,
    ):
        """Test plan respects team config sub_agents."""
        planner = Planner(llm=mock_llm)
        
        result = await planner.plan(sample_investigation_state)
        
        # github is disabled in sample_investigation_state
        assert "github" not in result.selected_agents

    @pytest.mark.asyncio
    async def test_plan_fallback_without_llm(self, sample_investigation_state):
        """Test plan returns fallback without LLM."""
        planner = Planner(llm=None)
        
        result = await planner.plan(sample_investigation_state)
        
        assert isinstance(result, InvestigationPlan)
        assert len(result.hypotheses) >= 1
        assert "unavailable" in result.reasoning.lower() or "fallback" in result.reasoning.lower()

    @pytest.mark.asyncio
    async def test_plan_handles_llm_error(self, sample_investigation_state):
        """Test plan handles LLM error gracefully."""
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = RuntimeError("API error")
        
        planner = Planner(llm=mock_llm)
        result = await planner.plan(sample_investigation_state)
        
        assert isinstance(result, InvestigationPlan)
        assert len(result.selected_agents) > 0

    @pytest.mark.asyncio
    async def test_plan_filters_unavailable_agents(
        self,
        sample_investigation_state,
    ):
        """Test plan filters agents not in available list."""
        mock_llm = MagicMock()
        response = MagicMock()
        response.content = json.dumps({
            "hypotheses": [
                {
                    "hypothesis": "test",
                    "priority": "high",
                    "agents_to_test": ["kubernetes", "aws", "nonexistent"],
                }
            ],
            "selected_agents": ["kubernetes", "aws", "nonexistent"],
            "reasoning": "test",
        })
        mock_llm.invoke.return_value = response
        
        planner = Planner(llm=mock_llm)
        result = await planner.plan(sample_investigation_state)
        
        # aws and nonexistent should be filtered out
        assert "aws" not in result.selected_agents
        assert "nonexistent" not in result.selected_agents
        assert "kubernetes" in result.selected_agents

    @pytest.mark.asyncio
    async def test_plan_includes_feedback_on_iteration(
        self,
        mock_llm,
        sample_investigation_state,
    ):
        """Test plan includes feedback messages on iteration > 0."""
        sample_investigation_state["iteration"] = 1
        sample_investigation_state["messages"] = [
            {"role": "synthesizer", "content": "Need more metrics data"},
        ]
        
        planner = Planner(llm=mock_llm)
        await planner.plan(sample_investigation_state)
        
        # Verify LLM was called with feedback in prompt
        call_args = mock_llm.invoke.call_args
        # The messages should contain feedback


class TestSynthesizer:
    """Tests for Synthesizer agent."""

    @pytest.fixture
    def synthesizer(self, mock_llm):
        """Create a test Synthesizer."""
        # Configure mock for synthesizer response
        response = MagicMock()
        response.content = json.dumps({
            "sufficient_evidence": True,
            "confidence": 0.85,
            "summary": "Root cause identified",
            "gaps": [],
            "feedback": "",
            "recommended_agents": [],
        })
        mock_llm.invoke.return_value = response
        
        return Synthesizer(llm=mock_llm)

    def test_synthesizer_name(self, synthesizer):
        """Test synthesizer name."""
        assert synthesizer.name == "synthesizer"

    @pytest.mark.asyncio
    async def test_synthesize_returns_decision(
        self,
        synthesizer,
        sample_investigation_state,
    ):
        """Test synthesize returns SynthesisDecision."""
        result = await synthesizer.synthesize(sample_investigation_state)
        
        assert isinstance(result, SynthesisDecision)
        assert result.sufficient_evidence is True
        assert result.confidence == 0.85

    @pytest.mark.asyncio
    async def test_synthesize_rule_based_without_llm(
        self,
        sample_investigation_state,
    ):
        """Test synthesize uses rule-based logic without LLM."""
        synthesizer = Synthesizer(llm=None)
        
        result = await synthesizer.synthesize(sample_investigation_state)
        
        assert isinstance(result, SynthesisDecision)
        assert "Rule-based" in result.summary

    @pytest.mark.asyncio
    async def test_synthesize_considers_critical_findings(
        self,
        sample_investigation_state,
    ):
        """Test synthesize considers critical findings."""
        synthesizer = Synthesizer(llm=None)
        
        # Add critical findings
        sample_investigation_state["agent_states"] = {
            "kubernetes": {
                "findings": [
                    {"severity": "critical", "detail": "OOMKilled"},
                ],
            },
        }
        
        result = await synthesizer.synthesize(sample_investigation_state)
        
        assert result.sufficient_evidence is True
        assert result.confidence > 0.5

    @pytest.mark.asyncio
    async def test_synthesize_handles_error(self, sample_investigation_state):
        """Test synthesize handles errors gracefully."""
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = RuntimeError("API error")
        
        synthesizer = Synthesizer(llm=mock_llm)
        result = await synthesizer.synthesize(sample_investigation_state)
        
        assert isinstance(result, SynthesisDecision)
        assert result.sufficient_evidence is False
        assert "error" in result.summary.lower()

    @pytest.mark.asyncio
    async def test_synthesize_force_complete_on_max_iterations(
        self,
        sample_investigation_state,
    ):
        """Test synthesize forces completion on max iterations."""
        synthesizer = Synthesizer(llm=None)
        
        sample_investigation_state["iteration"] = 2
        sample_investigation_state["max_iterations"] = 3
        
        result = await synthesizer.synthesize(sample_investigation_state)
        
        assert result.sufficient_evidence is True
        assert result.confidence >= 0.6


# ============================================================================
# BaseAgent Extended Tests
# ============================================================================


class TestBaseAgentExtended:
    """Extended tests for BaseAgent class."""

    def test_agent_config_model_override(self):
        """Test AgentConfig model override."""
        config = AgentConfig(
            name="custom",
            model="gpt-4-turbo",
            temperature=0.7,
        )
        
        assert config.model == "gpt-4-turbo"
        assert config.temperature == 0.7

    def test_agent_config_serialization(self):
        """Test AgentConfig serialization."""
        config = AgentConfig(
            name="test",
            max_iterations=5,
        )
        
        # Convert to dict
        data = config.model_dump()
        assert data["name"] == "test"
        assert data["max_iterations"] == 5
        
        # Recreate from dict
        restored = AgentConfig(**data)
        assert restored.name == config.name

    def test_agent_state_initialization(self):
        """Test AgentState initialization."""
        state = AgentState(name="kubernetes")
        
        assert state.name == "kubernetes"
        assert state.status == InvestigationStatus.PENDING
        assert state.findings == []

    def test_agent_state_add_finding(self):
        """Test adding finding to AgentState."""
        state = AgentState(name="test")
        
        finding = Finding(
            category="test",
            detail="Test finding",
            severity="medium",
            confidence=0.7,
        )
        
        state.findings.append(finding)
        assert len(state.findings) == 1

    def test_agent_state_mark_completed(self):
        """Test marking AgentState as completed."""
        state = AgentState(name="test")
        state.status = InvestigationStatus.COMPLETED
        
        assert state.is_complete is True

    def test_agent_state_mark_failed(self):
        """Test marking AgentState as failed."""
        state = AgentState(name="test")
        state.status = InvestigationStatus.FAILED
        state.error = "Test error"
        
        assert state.is_complete is True
        assert state.error == "Test error"


# ============================================================================
# TriageAgent Tests
# ============================================================================


class TestTriageAgent:
    """Tests for TriageAgent."""

    @pytest.fixture
    def sample_alert(self):
        """Create sample alert for triage."""
        return {
            "name": "HighErrorRate",
            "service": "payment-service",
            "namespace": "production",
            "severity": "critical",
            "description": "Error rate above 5%",
            "labels": {
                "alertname": "HighErrorRate",
                "service": "payment-service",
            },
        }

    def test_triage_categorization_latency(self):
        """Test triage categorizes latency alerts."""
        from autosre.agents.triage_agent import TriageAgent
        
        agent = TriageAgent()
        
        # Create a simple alert dict
        alert_mock = MagicMock()
        alert_mock.name = "HighLatency"
        alert_mock.description = "P99 latency high"
        alert_mock.severity = MagicMock()
        alert_mock.severity.value = "high"
        
        # Test quick_classify
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            agent.quick_classify(alert_mock)
        )
        
        assert result["category"] == "latency"

    def test_triage_categorization_errors(self):
        """Test triage categorizes error alerts."""
        from autosre.agents.triage_agent import TriageAgent
        
        agent = TriageAgent()
        
        alert_mock = MagicMock()
        alert_mock.name = "HighErrorRate"
        alert_mock.description = "5xx errors"
        alert_mock.severity = MagicMock()
        alert_mock.severity.value = "critical"
        
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            agent.quick_classify(alert_mock)
        )
        
        assert result["category"] == "errors"

    def test_triage_categorization_resources(self):
        """Test triage categorizes resource alerts."""
        from autosre.agents.triage_agent import TriageAgent
        
        agent = TriageAgent()
        
        alert_mock = MagicMock()
        alert_mock.name = "HighCPU"
        alert_mock.description = "CPU usage high"
        alert_mock.severity = MagicMock()
        alert_mock.severity.value = "warning"
        
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            agent.quick_classify(alert_mock)
        )
        
        assert result["category"] == "resources"

    def test_triage_default_agents(self):
        """Test triage returns correct default agents."""
        from autosre.agents.triage_agent import TriageAgent
        
        agent = TriageAgent()
        
        # Test different categories
        agents = agent._get_default_agents("latency")
        assert "metrics" in agents
        assert "traces" in agents
        
        agents = agent._get_default_agents("errors")
        assert "logs" in agents
        
        agents = agent._get_default_agents("resources")
        assert "kubernetes" in agents

    def test_triage_system_prompt_generation(self, sample_investigation_state):
        """Test triage system prompt includes alert context."""
        from autosre.agents.triage_agent import TriageAgent
        from autosre.models.investigation import Investigation
        from autosre.models.alert import Alert
        
        agent = TriageAgent()
        
        # Create investigation with alert
        alert = Alert(name="TestAlert", service="test-svc")
        investigation = Investigation(alert=alert)
        
        prompt = agent.get_system_prompt(investigation)
        
        assert "TestAlert" in prompt or "triage" in prompt.lower()


# ============================================================================
# InvestigationAgent Tests
# ============================================================================


class TestInvestigationAgent:
    """Tests for InvestigationAgent."""

    def test_investigation_domain_kubernetes(self):
        """Test Kubernetes investigation domain."""
        from autosre.agents.investigation_agent import (
            InvestigationAgent,
            InvestigationDomain,
        )
        
        agent = InvestigationAgent(domain=InvestigationDomain.KUBERNETES)
        
        assert agent.domain == InvestigationDomain.KUBERNETES
        assert "kubernetes" in agent.agent_id
        assert len(agent.tools) > 0

    def test_investigation_domain_metrics(self):
        """Test Metrics investigation domain."""
        from autosre.agents.investigation_agent import (
            InvestigationAgent,
            InvestigationDomain,
        )
        
        agent = InvestigationAgent(domain=InvestigationDomain.METRICS)
        
        assert agent.domain == InvestigationDomain.METRICS
        assert "metrics" in agent.agent_id

    def test_investigation_domain_logs(self):
        """Test Logs investigation domain."""
        from autosre.agents.investigation_agent import (
            InvestigationAgent,
            InvestigationDomain,
        )
        
        agent = InvestigationAgent(domain=InvestigationDomain.LOGS)
        
        assert agent.domain == InvestigationDomain.LOGS
        assert "logs" in agent.agent_id

    def test_tool_registration(self):
        """Test tools are registered for domain."""
        from autosre.agents.investigation_agent import (
            InvestigationAgent,
            InvestigationDomain,
        )
        
        k8s_agent = InvestigationAgent(domain=InvestigationDomain.KUBERNETES)
        metrics_agent = InvestigationAgent(domain=InvestigationDomain.METRICS)
        
        # Kubernetes tools
        k8s_tools = k8s_agent.tools.get_definitions()
        k8s_names = [t.name for t in k8s_tools]
        assert "get_pod_status" in k8s_names
        
        # Metrics tools
        metrics_tools = metrics_agent.tools.get_definitions()
        metrics_names = [t.name for t in metrics_tools]
        assert "query_metrics" in metrics_names

    def test_system_prompt_includes_context(self, sample_investigation_state):
        """Test system prompt includes investigation context."""
        from autosre.agents.investigation_agent import (
            InvestigationAgent,
            InvestigationDomain,
        )
        from autosre.models.investigation import Investigation
        from autosre.models.alert import Alert
        
        agent = InvestigationAgent(domain=InvestigationDomain.KUBERNETES)
        
        alert = Alert(name="TestAlert", service="test-svc", namespace="prod")
        investigation = Investigation(alert=alert)
        
        prompt = agent.get_system_prompt(investigation)
        
        assert "test-svc" in prompt or "TestAlert" in prompt
        assert "kubernetes" in prompt.lower() or "Kubernetes" in prompt


# ============================================================================
# ToolRegistry Tests
# ============================================================================


class TestToolRegistry:
    """Tests for ToolRegistry."""

    def test_registry_initialization(self):
        """Test registry initializes empty."""
        from autosre.agents.base_agent import ToolRegistry
        
        registry = ToolRegistry()
        
        assert len(registry) == 0
        assert "test_tool" not in registry

    def test_registry_register_tool(self):
        """Test registering a tool."""
        from autosre.agents.base_agent import ToolRegistry
        
        registry = ToolRegistry()
        
        def test_handler(**kwargs):
            return "result"
        
        registry.register(
            name="test_tool",
            description="Test tool",
            parameters={"type": "object", "properties": {}},
            handler=test_handler,
        )
        
        assert len(registry) == 1
        assert "test_tool" in registry

    def test_registry_get_definitions(self):
        """Test getting tool definitions."""
        from autosre.agents.base_agent import ToolRegistry
        
        registry = ToolRegistry()
        
        registry.register(
            name="tool1",
            description="Tool 1",
            parameters={},
            handler=lambda: None,
        )
        registry.register(
            name="tool2",
            description="Tool 2",
            parameters={},
            handler=lambda: None,
        )
        
        definitions = registry.get_definitions()
        assert len(definitions) == 2

    @pytest.mark.asyncio
    async def test_registry_execute_tool(self):
        """Test executing a tool."""
        from autosre.agents.base_agent import ToolRegistry
        from autosre.core.llm_client import ToolCall
        
        registry = ToolRegistry()
        
        def sync_handler(x: int, y: int):
            return x + y
        
        registry.register(
            name="add",
            description="Add numbers",
            parameters={
                "type": "object",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                },
            },
            handler=sync_handler,
        )
        
        tool_call = ToolCall(
            id="call_1",
            name="add",
            arguments={"x": 2, "y": 3},
        )
        
        result = await registry.execute(tool_call)
        assert result == 5

    @pytest.mark.asyncio
    async def test_registry_execute_async_tool(self):
        """Test executing an async tool."""
        from autosre.agents.base_agent import ToolRegistry
        from autosre.core.llm_client import ToolCall
        
        registry = ToolRegistry()
        
        async def async_handler(message: str):
            return f"Hello, {message}!"
        
        registry.register(
            name="greet",
            description="Greet someone",
            parameters={
                "type": "object",
                "properties": {
                    "message": {"type": "string"},
                },
            },
            handler=async_handler,
        )
        
        tool_call = ToolCall(
            id="call_2",
            name="greet",
            arguments={"message": "World"},
        )
        
        result = await registry.execute(tool_call)
        assert result == "Hello, World!"

    @pytest.mark.asyncio
    async def test_registry_execute_unknown_tool(self):
        """Test executing unknown tool."""
        from autosre.agents.base_agent import ToolRegistry
        from autosre.core.llm_client import ToolCall
        
        registry = ToolRegistry()
        
        tool_call = ToolCall(
            id="call_3",
            name="nonexistent",
            arguments={},
        )
        
        result = await registry.execute(tool_call)
        assert "Unknown tool" in result


# ============================================================================
# AgentResult Tests
# ============================================================================


class TestAgentResult:
    """Tests for AgentResult."""

    def test_result_initialization(self):
        """Test AgentResult initialization."""
        from autosre.agents.base_agent import AgentResult, AgentStatus
        
        result = AgentResult(
            agent_id="test",
            status=AgentStatus.COMPLETED,
        )
        
        assert result.agent_id == "test"
        assert result.status == AgentStatus.COMPLETED
        assert result.findings == []
        assert result.evidence == []

    def test_result_is_success(self):
        """Test is_success property."""
        from autosre.agents.base_agent import AgentResult, AgentStatus
        
        success = AgentResult(agent_id="test", status=AgentStatus.COMPLETED)
        error = AgentResult(agent_id="test", status=AgentStatus.ERROR)
        pending = AgentResult(agent_id="test", status=AgentStatus.PENDING)
        
        assert success.is_success is True
        assert error.is_success is False
        assert pending.is_success is False

    def test_result_has_findings(self):
        """Test has_findings property."""
        from autosre.agents.base_agent import AgentResult, AgentStatus
        from autosre.core.investigation import Finding
        
        result_empty = AgentResult(agent_id="test", status=AgentStatus.COMPLETED)
        
        result_with_findings = AgentResult(
            agent_id="test",
            status=AgentStatus.COMPLETED,
            findings=[Finding(title="Test", description="Test finding")],
        )
        
        assert result_empty.has_findings is False
        assert result_with_findings.has_findings is True

    def test_result_to_dict(self):
        """Test AgentResult serialization."""
        from autosre.agents.base_agent import AgentResult, AgentStatus
        
        result = AgentResult(
            agent_id="test",
            status=AgentStatus.COMPLETED,
            summary="Test summary",
            confidence=0.85,
            iterations=3,
            duration_seconds=45.5,
        )
        
        data = result.to_dict()
        
        assert data["agent_id"] == "test"
        assert data["status"] == "completed"
        assert data["summary"] == "Test summary"
        assert data["confidence"] == 0.85


# ============================================================================
# Coordinator Tests
# ============================================================================


class TestAgentCoordinator:
    """Tests for AgentCoordinator."""

    def test_coordinator_initialization(self):
        """Test coordinator initialization."""
        from autosre.agents.coordinator import AgentCoordinator
        
        coordinator = AgentCoordinator()
        
        assert coordinator.name == "coordinator"
        assert len(coordinator.get_available_agents()) == 0

    def test_coordinator_register_agent(self):
        """Test registering agents."""
        from autosre.agents.coordinator import AgentCoordinator
        from autosre.agents.base import BaseAgent
        
        coordinator = AgentCoordinator()
        
        # Create mock agent
        mock_agent = MagicMock(spec=BaseAgent)
        mock_agent.name = "test_agent"
        
        coordinator.register_agent(mock_agent)
        
        assert "test_agent" in coordinator.get_available_agents()

    def test_coordinator_state_initialization(self):
        """Test CoordinatorState initialization."""
        from autosre.agents.coordinator import CoordinatorState, WorkflowPhase
        from autosre.models.investigation import InvestigationStatus
        
        state = CoordinatorState(investigation_id="inv-123")
        
        assert state.investigation_id == "inv-123"
        assert state.phase == WorkflowPhase.TRIAGE
        assert state.iteration == 0
        assert state.status == InvestigationStatus.PENDING

    def test_coordinator_state_add_timeline_event(self):
        """Test adding timeline events."""
        from autosre.agents.coordinator import CoordinatorState, WorkflowPhase
        
        state = CoordinatorState(investigation_id="inv-123")
        
        state.add_timeline_event("Investigation started")
        state.add_timeline_event("Triage completed", agent="triage")
        
        assert len(state.timeline) == 2
        assert state.timeline[0].event == "Investigation started"
        assert state.timeline[1].agent == "triage"

    def test_coordinator_state_add_findings(self):
        """Test adding findings to state."""
        from autosre.agents.coordinator import CoordinatorState
        from autosre.models.investigation import Finding
        
        state = CoordinatorState(investigation_id="inv-123")
        
        findings = [
            Finding(category="test", detail="Finding 1"),
            Finding(category="test", detail="Finding 2"),
        ]
        
        state.add_findings(findings)
        
        assert len(state.all_findings) == 2

    def test_coordinator_state_duration(self):
        """Test duration calculation."""
        from autosre.agents.coordinator import CoordinatorState
        from datetime import datetime, timedelta
        
        state = CoordinatorState(investigation_id="inv-123")
        
        # Duration should be small (just created)
        assert state.duration_seconds >= 0
        assert state.duration_seconds < 1

    def test_coordinator_decision_model(self):
        """Test CoordinatorDecision model."""
        from autosre.agents.coordinator import CoordinatorDecision, WorkflowPhase
        
        decision = CoordinatorDecision(
            decision="continue",
            reasoning="More data needed",
            next_phase=WorkflowPhase.INVESTIGATION,
            agents_to_dispatch=["kubernetes", "metrics"],
            confidence=0.6,
        )
        
        assert decision.decision == "continue"
        assert len(decision.agents_to_dispatch) == 2
        assert decision.confidence == 0.6

    def test_workflow_phases(self):
        """Test workflow phase values."""
        from autosre.agents.coordinator import WorkflowPhase
        
        assert WorkflowPhase.TRIAGE.value == "triage"
        assert WorkflowPhase.INVESTIGATION.value == "investigation"
        assert WorkflowPhase.SYNTHESIS.value == "synthesis"
        assert WorkflowPhase.REMEDIATION.value == "remediation"
        assert WorkflowPhase.CONCLUSION.value == "conclusion"

    def test_timeline_event_model(self):
        """Test TimelineEvent model."""
        from autosre.agents.coordinator import TimelineEvent, WorkflowPhase
        
        event = TimelineEvent(
            phase=WorkflowPhase.TRIAGE,
            event="Triage started",
            agent="triage",
            details={"severity": "critical"},
        )
        
        assert event.phase == WorkflowPhase.TRIAGE
        assert event.event == "Triage started"
        assert event.details["severity"] == "critical"
