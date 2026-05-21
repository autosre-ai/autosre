"""Tests for ReAct loop implementation.

ARCHIVED: This test file references old v1 API that has been refactored.
Skipped during pytest collection.
"""

import pytest

# Skip the entire module - archive_v1 references old API
pytestmark = pytest.mark.skip(reason="archive_v1: old API references, module archived")

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

# These imports are commented out as they reference old API
# from autosre.agents.subagents import (
#     Tool,
#     ToolCall,
#     ToolResult,
#     ReactConfig,
#     Message,
#     react_loop,
#     create_tool,
#     hash_tool_call,
#     trim_old_messages,
# )
# from autosre.agents.subagents import (
#     KubernetesSubagent,
#     MetricsSubagent,
#     LogsSubagent,
#     MockSubagent,
#     run_subagents_parallel,
# )
# from autosre.agents.state import InvestigationState, InvestigationStatus


class TestToolCallDeduplication:
    """Test tool call deduplication logic."""
    
    def test_hash_same_calls(self):
        """Same tool + args should produce same hash."""
        hash1 = hash_tool_call("get_pods", {"namespace": "default"})
        hash2 = hash_tool_call("get_pods", {"namespace": "default"})
        assert hash1 == hash2
    
    def test_hash_different_args(self):
        """Different args should produce different hash."""
        hash1 = hash_tool_call("get_pods", {"namespace": "default"})
        hash2 = hash_tool_call("get_pods", {"namespace": "production"})
        assert hash1 != hash2
    
    def test_hash_different_tools(self):
        """Different tools should produce different hash."""
        hash1 = hash_tool_call("get_pods", {"namespace": "default"})
        hash2 = hash_tool_call("get_events", {"namespace": "default"})
        assert hash1 != hash2
    
    def test_hash_arg_order_independent(self):
        """Arg order shouldn't matter."""
        hash1 = hash_tool_call("search", {"a": 1, "b": 2})
        hash2 = hash_tool_call("search", {"b": 2, "a": 1})
        assert hash1 == hash2


class TestContextManagement:
    """Test context trimming logic."""
    
    def test_trim_keeps_system_message(self):
        """System message should be preserved."""
        messages = [
            Message(role="system", content="System prompt"),
            Message(role="user", content="User message"),
            Message(role="assistant", content="Response"),
        ]
        
        trimmed = trim_old_messages(messages, max_tokens=50, keep_system=True, keep_recent=2)
        
        assert any(m.role == "system" and "System prompt" in m.content for m in trimmed)
    
    def test_trim_keeps_recent_messages(self):
        """Recent messages should be preserved."""
        messages = [
            Message(role="system", content="System"),
            Message(role="user", content="Old message 1"),
            Message(role="assistant", content="Old response 1"),
            Message(role="user", content="Recent message"),
            Message(role="assistant", content="Recent response"),
        ]
        
        trimmed = trim_old_messages(messages, max_tokens=100, keep_system=True, keep_recent=2)
        
        # Should have system + recent 2
        assert "Recent message" in trimmed[-2].content or "Recent response" in trimmed[-1].content
    
    def test_no_trim_when_under_limit(self):
        """Messages under limit should not be trimmed."""
        messages = [
            Message(role="user", content="Short message"),
        ]
        
        trimmed = trim_old_messages(messages, max_tokens=1000000, keep_recent=10)
        
        assert len(trimmed) == len(messages)


class TestToolCreation:
    """Test tool creation helpers."""
    
    def test_create_tool_sync_executor(self):
        """Create tool with sync executor."""
        def my_tool(arg1: str) -> str:
            return f"Result: {arg1}"
        
        tool = create_tool(
            name="my_tool",
            description="A test tool",
            executor=my_tool,
            parameters={"type": "object", "properties": {"arg1": {"type": "string"}}},
        )
        
        assert tool.name == "my_tool"
        assert tool.description == "A test tool"
    
    @pytest.mark.asyncio
    async def test_tool_execution_success(self):
        """Test successful tool execution."""
        async def my_async_tool(value: int) -> str:
            return f"Got {value}"
        
        tool = create_tool(
            name="async_tool",
            description="Async tool",
            executor=my_async_tool,
        )
        
        result = await tool.execute(value=42)
        
        assert result.success is True
        assert "Got 42" in result.output
        assert result.duration_ms >= 0
    
    @pytest.mark.asyncio
    async def test_tool_execution_error(self):
        """Test tool execution with error."""
        def failing_tool() -> str:
            raise ValueError("Something went wrong")
        
        tool = create_tool(
            name="failing",
            description="Will fail",
            executor=failing_tool,
        )
        
        result = await tool.execute()
        
        assert result.success is False
        assert "Something went wrong" in result.error


class TestReactConfig:
    """Test ReAct configuration."""
    
    def test_default_config(self):
        """Default config should have sensible values."""
        config = ReactConfig()
        
        assert config.max_iterations == 15
        assert config.reflection_interval == 5
        assert config.max_no_findings_attempts == 3
        assert config.tool_retry_count == 1
    
    def test_custom_config(self):
        """Custom config values should be respected."""
        config = ReactConfig(
            max_iterations=10,
            reflection_interval=3,
            max_no_findings_attempts=5,
        )
        
        assert config.max_iterations == 10
        assert config.reflection_interval == 3
        assert config.max_no_findings_attempts == 5


class TestKubernetesSubagent:
    """Test Kubernetes subagent."""
    
    def test_init_defaults(self):
        """Test default initialization."""
        subagent = KubernetesSubagent()
        
        assert subagent.agent_id == "kubernetes"
        assert subagent.namespace == "default"
    
    def test_init_custom_namespace(self):
        """Test custom namespace."""
        subagent = KubernetesSubagent(namespace="production")
        
        assert subagent.namespace == "production"
    
    @pytest.mark.asyncio
    async def test_get_tools(self):
        """Test that tools are returned."""
        subagent = KubernetesSubagent(dry_run=True)
        tools = await subagent.get_tools()
        
        assert len(tools) > 0
        tool_names = [t.name for t in tools]
        assert "get_pods" in tool_names
        assert "get_pod_logs" in tool_names
        assert "describe_pod" in tool_names
        assert "get_events" in tool_names
    
    def test_hypothesis_generation(self):
        """Test hypothesis generation."""
        subagent = KubernetesSubagent()
        
        alert = {"name": "PodCrashLooping", "service": "payment-service"}
        hypothesis = subagent.get_hypothesis(alert, [])
        
        assert "payment-service" in hypothesis
        assert "pod" in hypothesis.lower()


class TestMetricsSubagent:
    """Test Metrics subagent."""
    
    def test_init_defaults(self):
        """Test default initialization."""
        subagent = MetricsSubagent()
        
        assert subagent.agent_id == "metrics"
        assert "prometheus" in subagent.prometheus_url
    
    @pytest.mark.asyncio
    async def test_get_tools(self):
        """Test that tools are returned."""
        subagent = MetricsSubagent(dry_run=True)
        tools = await subagent.get_tools()
        
        assert len(tools) > 0
        tool_names = [t.name for t in tools]
        assert "query_prometheus" in tool_names
        assert "get_error_rate" in tool_names
        assert "get_latency_percentiles" in tool_names


class TestLogsSubagent:
    """Test Logs subagent."""
    
    def test_init_defaults(self):
        """Test default initialization."""
        subagent = LogsSubagent()
        
        assert subagent.agent_id == "logs"
        assert subagent.backend == "elasticsearch"
    
    @pytest.mark.asyncio
    async def test_get_tools(self):
        """Test that tools are returned."""
        subagent = LogsSubagent(dry_run=True)
        tools = await subagent.get_tools()
        
        assert len(tools) > 0
        tool_names = [t.name for t in tools]
        assert "search_logs" in tool_names
        assert "get_errors" in tool_names
        assert "get_exceptions" in tool_names


class TestMockSubagent:
    """Test mock subagent for testing."""
    
    @pytest.mark.asyncio
    async def test_investigate(self):
        """Test mock investigation."""
        subagent = MockSubagent()
        
        # Create mock LLM that returns finish immediately
        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(return_value=MagicMock(
            content='{"action": "finish", "summary": "Mock findings", "confidence": 0.8}'
        ))
        
        result = await subagent.investigate(
            alert={"name": "TestAlert"},
            hypotheses=["Test hypothesis"],
            llm_client=mock_llm,
        )
        
        assert result.agent_id == "mock"
        assert result.status == InvestigationStatus.COMPLETED


class TestParallelExecution:
    """Test parallel subagent execution."""
    
    @pytest.mark.asyncio
    async def test_run_multiple_subagents(self):
        """Test running multiple subagents in parallel."""
        state = InvestigationState(
            alert={"name": "TestAlert", "service": "test-service"},
            service_name="test-service",
        )
        
        # Create mock subagents
        subagents = [
            MockSubagent(),
            MockSubagent(),
        ]
        
        # Mock the LLM for all subagents
        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(return_value=MagicMock(
            content='{"action": "finish", "summary": "Done", "confidence": 0.5}'
        ))
        
        results = await run_subagents_parallel(
            state=state,
            subagents=subagents,
            llm_client=mock_llm,
            timeout=30.0,
        )
        
        assert len(results) == 2
        for result in results:
            assert result.agent_id == "mock"


class TestReactLoopIntegration:
    """Integration tests for the full ReAct loop."""
    
    @pytest.mark.asyncio
    async def test_react_loop_immediate_finish(self):
        """Test ReAct loop that finishes immediately."""
        # Create a simple tool
        async def check_status() -> str:
            return "Everything is fine"
        
        tools = [
            create_tool(
                name="check_status",
                description="Check system status",
                executor=check_status,
            )
        ]
        
        state = InvestigationState(
            alert={"name": "TestAlert"},
            service_name="test",
        )
        
        # Mock LLM to finish immediately
        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(return_value=MagicMock(
            content='{"action": "finish", "summary": "No issues found", "confidence": 0.9}'
        ))
        
        config = ReactConfig(max_iterations=5)
        
        result = await react_loop(
            hypothesis="Test if everything is working",
            tools=tools,
            state=state,
            llm=mock_llm,
            config=config,
            agent_id="test",
        )
        
        assert result.status == InvestigationStatus.COMPLETED
        assert "No issues found" in result.findings
    
    @pytest.mark.asyncio
    async def test_react_loop_with_tool_calls(self):
        """Test ReAct loop that makes tool calls before finishing."""
        call_count = 0
        
        async def check_status() -> str:
            nonlocal call_count
            call_count += 1
            return f"Status check {call_count}: OK"
        
        tools = [
            create_tool(
                name="check_status",
                description="Check system status",
                executor=check_status,
            )
        ]
        
        state = InvestigationState(
            alert={"name": "TestAlert"},
            service_name="test",
        )
        
        # Mock LLM to make one tool call then finish
        responses = [
            MagicMock(content='{"action": "tool_call", "tool_call": {"name": "check_status", "arguments": {}, "reasoning": "Check status"}}'),
            MagicMock(content='{"action": "finish", "summary": "Status is OK", "confidence": 0.9}'),
        ]
        
        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(side_effect=responses)
        
        config = ReactConfig(max_iterations=5)
        
        result = await react_loop(
            hypothesis="Test status",
            tools=tools,
            state=state,
            llm=mock_llm,
            config=config,
            agent_id="test",
        )
        
        assert result.status == InvestigationStatus.COMPLETED
        assert call_count == 1  # Tool was called once
        assert len(result.evidence) == 1  # One piece of evidence


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
