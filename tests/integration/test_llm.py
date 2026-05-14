"""Integration tests for LLM client.

Tests LLM client functionality including:
- Provider abstraction
- Retry logic
- Structured output
- Tool calling
- Token tracking
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel, Field

from autosre.core.llm_client import (
    BaseLLMClient,
    LLMMessage,
    LLMProvider,
    LLMResponse,
    ToolCall,
    ToolDefinition,
)


# ============================================================================
# Mock LLM Response Models
# ============================================================================


class MockHypothesis(BaseModel):
    """Mock hypothesis for structured output tests."""

    hypothesis: str
    priority: str
    agents_to_test: list[str]
    confidence: float = 0.5


class MockInvestigationPlan(BaseModel):
    """Mock investigation plan for structured output tests."""

    hypotheses: list[MockHypothesis]
    selected_agents: list[str]
    reasoning: str


class MockRootCauseAnalysis(BaseModel):
    """Mock root cause analysis output."""

    root_cause: str
    confidence: float
    evidence: list[str]
    remediation_steps: list[str]


# ============================================================================
# LLM Message Tests
# ============================================================================


class TestLLMMessage:
    """Tests for LLMMessage dataclass."""

    def test_message_basic(self):
        """Test basic message creation."""
        msg = LLMMessage(role="user", content="Hello")

        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.name is None
        assert msg.tool_call_id is None
        assert msg.tool_calls is None

    def test_message_with_name(self):
        """Test message with name (for tool messages)."""
        msg = LLMMessage(
            role="tool",
            content='{"result": "success"}',
            name="get_pod_status",
            tool_call_id="call_123",
        )

        assert msg.name == "get_pod_status"
        assert msg.tool_call_id == "call_123"

    def test_message_with_tool_calls(self):
        """Test assistant message with tool calls."""
        msg = LLMMessage(
            role="assistant",
            content="",
            tool_calls=[
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "query_metrics", "arguments": "{}"},
                }
            ],
        )

        assert len(msg.tool_calls) == 1
        assert msg.tool_calls[0]["function"]["name"] == "query_metrics"


class TestToolDefinition:
    """Tests for ToolDefinition dataclass."""

    def test_tool_definition_basic(self):
        """Test basic tool definition."""
        tool = ToolDefinition(
            name="get_pod_status",
            description="Get the status of Kubernetes pods",
            parameters={
                "type": "object",
                "properties": {
                    "namespace": {"type": "string"},
                    "label_selector": {"type": "string"},
                },
                "required": ["namespace"],
            },
        )

        assert tool.name == "get_pod_status"
        assert "namespace" in tool.parameters["properties"]
        assert tool.handler is None

    def test_tool_definition_with_handler(self):
        """Test tool definition with handler function."""

        def mock_handler(namespace: str) -> str:
            return f"Pods in {namespace}"

        tool = ToolDefinition(
            name="get_pods",
            description="Get pods",
            parameters={"type": "object"},
            handler=mock_handler,
        )

        assert tool.handler is not None
        assert tool.handler(namespace="default") == "Pods in default"


class TestToolCall:
    """Tests for ToolCall dataclass."""

    def test_tool_call_basic(self):
        """Test basic tool call."""
        call = ToolCall(
            id="call_abc123",
            name="query_metrics",
            arguments={"query": "up", "step": "1m"},
        )

        assert call.id == "call_abc123"
        assert call.name == "query_metrics"
        assert call.arguments["query"] == "up"


class TestLLMResponse:
    """Tests for LLMResponse dataclass."""

    def test_response_basic(self):
        """Test basic LLM response."""
        response = LLMResponse(
            content="Analysis complete.",
            model="gpt-4o",
            input_tokens=100,
            output_tokens=50,
            latency_ms=1500.0,
        )

        assert response.content == "Analysis complete."
        assert response.total_tokens == 150
        assert response.has_tool_calls is False

    def test_response_with_tool_calls(self):
        """Test LLM response with tool calls."""
        response = LLMResponse(
            content="",
            tool_calls=[
                ToolCall(id="1", name="get_pods", arguments={}),
                ToolCall(id="2", name="query_metrics", arguments={}),
            ],
            finish_reason="tool_calls",
        )

        assert response.has_tool_calls is True
        assert len(response.tool_calls) == 2

    def test_response_token_tracking(self):
        """Test token tracking in response."""
        response = LLMResponse(
            content="Test",
            input_tokens=1000,
            output_tokens=500,
        )

        assert response.total_tokens == 1500


# ============================================================================
# LLM Client Base Tests
# ============================================================================


class MockLLMClient(BaseLLMClient):
    """Mock LLM client for testing."""

    def __init__(self, config=None):
        self.config = config or MagicMock()
        self.config.max_retries = 3
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._request_count = 0
        self._responses = []
        self._response_index = 0

    def set_responses(self, responses: list[LLMResponse]):
        """Set sequence of responses for testing."""
        self._responses = responses
        self._response_index = 0

    async def complete(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
    ) -> LLMResponse:
        """Mock completion."""
        self._request_count += 1

        if self._responses:
            response = self._responses[self._response_index]
            self._response_index = min(
                self._response_index + 1, len(self._responses) - 1
            )
            return response

        return LLMResponse(
            content="Mock response",
            model="mock-model",
            input_tokens=len(str(messages)) // 4,
            output_tokens=50,
        )

    async def complete_structured(
        self,
        messages: list[LLMMessage],
        response_model: type,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ):
        """Mock structured completion."""
        raise NotImplementedError("Use with mock")


class TestBaseLLMClient:
    """Tests for base LLM client functionality."""

    @pytest.fixture
    def client(self):
        """Create mock LLM client."""
        return MockLLMClient()

    @pytest.mark.asyncio
    async def test_complete_basic(self, client):
        """Test basic completion."""
        messages = [
            LLMMessage(role="user", content="What's happening?"),
        ]

        response = await client.complete(messages)

        assert response.content == "Mock response"
        assert client._request_count == 1

    @pytest.mark.asyncio
    async def test_complete_with_tools(self, client):
        """Test completion with tools."""
        messages = [LLMMessage(role="user", content="Get pod status")]

        tools = [
            ToolDefinition(
                name="get_pods",
                description="Get pods",
                parameters={"type": "object"},
            )
        ]

        client.set_responses([
            LLMResponse(
                content="",
                tool_calls=[ToolCall(id="1", name="get_pods", arguments={})],
            )
        ])

        response = await client.complete(messages, tools=tools)

        assert response.has_tool_calls
        assert response.tool_calls[0].name == "get_pods"

    @pytest.mark.asyncio
    async def test_complete_with_retry_success(self, client):
        """Test retry on transient failure."""
        call_count = 0

        async def flaky_complete(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Transient error")
            return LLMResponse(content="Success after retry")

        client.complete = flaky_complete

        response = await client.complete_with_retry([LLMMessage(role="user", content="test")])

        assert response.content == "Success after retry"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_complete_with_retry_exhausted(self, client):
        """Test retry exhaustion."""

        async def always_fail(*args, **kwargs):
            raise Exception("Persistent error")

        client.complete = always_fail

        with pytest.raises(Exception) as exc_info:
            await client.complete_with_retry([LLMMessage(role="user", content="test")])

        assert "Persistent error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_token_tracking(self, client):
        """Test cumulative token tracking."""
        client.set_responses([
            LLMResponse(content="R1", input_tokens=100, output_tokens=50),
            LLMResponse(content="R2", input_tokens=150, output_tokens=75),
        ])

        await client.complete([LLMMessage(role="user", content="Q1")])
        await client.complete([LLMMessage(role="user", content="Q2")])

        assert client._request_count == 2


# ============================================================================
# Structured Output Tests
# ============================================================================


class TestStructuredOutput:
    """Tests for structured output functionality."""

    @pytest.fixture
    def mock_client(self):
        """Create mock client with structured output support."""
        client = MagicMock()
        client.complete_structured = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_structured_output_hypothesis(self, mock_client):
        """Test structured output for hypothesis generation."""
        expected = MockInvestigationPlan(
            hypotheses=[
                MockHypothesis(
                    hypothesis="Memory leak in payment pods",
                    priority="high",
                    agents_to_test=["kubernetes", "metrics"],
                    confidence=0.8,
                )
            ],
            selected_agents=["kubernetes", "metrics"],
            reasoning="Error rate correlates with memory growth",
        )

        mock_client.complete_structured.return_value = expected

        messages = [
            LLMMessage(role="system", content="You are an SRE agent."),
            LLMMessage(role="user", content="Analyze this alert..."),
        ]

        result = await mock_client.complete_structured(
            messages=messages,
            response_model=MockInvestigationPlan,
        )

        assert len(result.hypotheses) == 1
        assert result.hypotheses[0].priority == "high"
        assert "kubernetes" in result.selected_agents

    @pytest.mark.asyncio
    async def test_structured_output_root_cause(self, mock_client):
        """Test structured output for root cause analysis."""
        expected = MockRootCauseAnalysis(
            root_cause="Memory leak in payment service causing OOMKilled",
            confidence=0.9,
            evidence=[
                "Container memory usage at 95%",
                "OOMKilled events in pod history",
                "Memory growth trend over 24h",
            ],
            remediation_steps=[
                "Increase memory limit",
                "Fix memory leak in code",
                "Add memory alerts",
            ],
        )

        mock_client.complete_structured.return_value = expected

        result = await mock_client.complete_structured(
            messages=[LLMMessage(role="user", content="Synthesize findings")],
            response_model=MockRootCauseAnalysis,
        )

        assert result.confidence == 0.9
        assert len(result.remediation_steps) == 3


# ============================================================================
# Tool Calling Integration Tests
# ============================================================================


class TestToolCallingIntegration:
    """Integration tests for tool calling."""

    @pytest.fixture
    def client_with_tools(self):
        """Create client with tool handling."""
        client = MockLLMClient()
        return client

    @pytest.mark.asyncio
    async def test_tool_call_flow(self, client_with_tools):
        """Test complete tool call flow."""
        # First response: tool call
        tool_response = LLMResponse(
            content="",
            tool_calls=[
                ToolCall(
                    id="call_1",
                    name="get_pod_status",
                    arguments={"namespace": "production", "service": "payment"},
                )
            ],
            finish_reason="tool_calls",
        )

        # Second response: final answer
        final_response = LLMResponse(
            content="Found 3 pods: 2 Running, 1 CrashLoopBackOff",
            finish_reason="stop",
        )

        client_with_tools.set_responses([tool_response, final_response])

        # Initial request
        messages = [
            LLMMessage(role="user", content="Check payment service pods"),
        ]

        response = await client_with_tools.complete(messages)

        assert response.has_tool_calls
        assert response.tool_calls[0].name == "get_pod_status"

        # Simulate tool execution and continue
        messages.append(
            LLMMessage(
                role="tool",
                content='{"running": 2, "failed": 1}',
                tool_call_id="call_1",
            )
        )

        response = await client_with_tools.complete(messages)

        assert not response.has_tool_calls
        assert "CrashLoopBackOff" in response.content

    @pytest.mark.asyncio
    async def test_multiple_tool_calls(self, client_with_tools):
        """Test handling multiple tool calls in one response."""
        response = LLMResponse(
            content="",
            tool_calls=[
                ToolCall(id="1", name="get_pods", arguments={"namespace": "prod"}),
                ToolCall(id="2", name="query_metrics", arguments={"query": "up"}),
                ToolCall(id="3", name="search_logs", arguments={"pattern": "error"}),
            ],
            finish_reason="tool_calls",
        )

        client_with_tools.set_responses([response])

        result = await client_with_tools.complete([
            LLMMessage(role="user", content="Investigate the issue")
        ])

        assert len(result.tool_calls) == 3
        tool_names = [tc.name for tc in result.tool_calls]
        assert "get_pods" in tool_names
        assert "query_metrics" in tool_names
        assert "search_logs" in tool_names


# ============================================================================
# Provider Tests
# ============================================================================


class TestLLMProvider:
    """Tests for LLM provider enum."""

    def test_provider_values(self):
        """Test provider enum values."""
        assert LLMProvider.OPENAI.value == "openai"
        assert LLMProvider.ANTHROPIC.value == "anthropic"
        assert LLMProvider.OLLAMA.value == "ollama"

    def test_provider_comparison(self):
        """Test provider comparison."""
        assert LLMProvider.OPENAI == LLMProvider.OPENAI
        assert LLMProvider.OPENAI != LLMProvider.ANTHROPIC


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestLLMErrorHandling:
    """Tests for LLM client error handling."""

    @pytest.fixture
    def client(self):
        """Create mock client."""
        return MockLLMClient()

    @pytest.mark.asyncio
    async def test_rate_limit_retry(self, client):
        """Test retry on rate limit errors."""
        call_count = 0

        async def rate_limited_complete(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Rate limit exceeded")
            return LLMResponse(content="Success")

        client.complete = rate_limited_complete

        response = await client.complete_with_retry([
            LLMMessage(role="user", content="test")
        ])

        assert response.content == "Success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_invalid_response_handling(self, client):
        """Test handling of invalid responses."""
        client.set_responses([
            LLMResponse(content=None, finish_reason="error")
        ])

        response = await client.complete([
            LLMMessage(role="user", content="test")
        ])

        assert response.content is None

    @pytest.mark.asyncio
    async def test_context_length_exceeded(self, client):
        """Test handling of context length errors."""

        async def context_exceeded(*args, **kwargs):
            raise Exception("Context length exceeded")

        client.complete = context_exceeded

        with pytest.raises(Exception) as exc_info:
            await client.complete_with_retry([
                LLMMessage(role="user", content="x" * 100000)
            ])

        assert "Context length" in str(exc_info.value)


# ============================================================================
# Configuration Tests
# ============================================================================


class TestLLMClientConfiguration:
    """Tests for LLM client configuration."""

    def test_config_defaults(self):
        """Test default configuration values."""
        config = MagicMock()
        config.temperature = 0.1
        config.max_tokens = 4096
        config.max_retries = 3

        client = MockLLMClient(config)

        assert client.config.temperature == 0.1
        assert client.config.max_tokens == 4096

    def test_config_override(self):
        """Test configuration overrides."""
        config = MagicMock()
        config.temperature = 0.7
        config.max_tokens = 8192

        client = MockLLMClient(config)

        assert client.config.temperature == 0.7
        assert client.config.max_tokens == 8192


# ============================================================================
# Conversation History Tests
# ============================================================================


class TestConversationHistory:
    """Tests for conversation history management."""

    @pytest.fixture
    def client(self):
        """Create client with tracking."""
        return MockLLMClient()

    @pytest.mark.asyncio
    async def test_multi_turn_conversation(self, client):
        """Test multi-turn conversation handling."""
        client.set_responses([
            LLMResponse(content="Hello! How can I help?"),
            LLMResponse(content="I see you're asking about the payment service."),
            LLMResponse(content="The issue is a memory leak."),
        ])

        messages = []

        # Turn 1
        messages.append(LLMMessage(role="user", content="Hi"))
        response = await client.complete(messages)
        messages.append(LLMMessage(role="assistant", content=response.content))

        # Turn 2
        messages.append(LLMMessage(role="user", content="Check payment service"))
        response = await client.complete(messages)
        messages.append(LLMMessage(role="assistant", content=response.content))

        # Turn 3
        messages.append(LLMMessage(role="user", content="What's the root cause?"))
        response = await client.complete(messages)

        assert len(messages) == 5
        assert "memory leak" in response.content

    @pytest.mark.asyncio
    async def test_system_message_handling(self, client):
        """Test system message in conversation."""
        client.set_responses([LLMResponse(content="Analysis complete.")])

        messages = [
            LLMMessage(role="system", content="You are an SRE assistant."),
            LLMMessage(role="user", content="Analyze this alert"),
        ]

        response = await client.complete(messages)

        assert response.content == "Analysis complete."


# ============================================================================
# Latency and Performance Tests
# ============================================================================


class TestLLMPerformance:
    """Tests for LLM client performance tracking."""

    @pytest.fixture
    def client(self):
        """Create client."""
        return MockLLMClient()

    @pytest.mark.asyncio
    async def test_latency_tracking(self, client):
        """Test latency tracking in responses."""
        client.set_responses([
            LLMResponse(content="Fast", latency_ms=100.0),
            LLMResponse(content="Slow", latency_ms=5000.0),
        ])

        r1 = await client.complete([LLMMessage(role="user", content="1")])
        r2 = await client.complete([LLMMessage(role="user", content="2")])

        assert r1.latency_ms == 100.0
        assert r2.latency_ms == 5000.0

    @pytest.mark.asyncio
    async def test_token_counting(self, client):
        """Test token counting accuracy."""
        client.set_responses([
            LLMResponse(
                content="Short response",
                input_tokens=50,
                output_tokens=10,
            ),
            LLMResponse(
                content="Longer, more detailed response with analysis",
                input_tokens=200,
                output_tokens=150,
            ),
        ])

        r1 = await client.complete([LLMMessage(role="user", content="Short")])
        r2 = await client.complete([LLMMessage(role="user", content="Long query")])

        assert r1.total_tokens == 60
        assert r2.total_tokens == 350


# ============================================================================
# Edge Cases
# ============================================================================


class TestLLMEdgeCases:
    """Edge case tests for LLM client."""

    @pytest.fixture
    def client(self):
        """Create client."""
        return MockLLMClient()

    @pytest.mark.asyncio
    async def test_empty_message_list(self, client):
        """Test handling empty message list."""
        response = await client.complete([])

        assert response is not None

    @pytest.mark.asyncio
    async def test_very_long_message(self, client):
        """Test handling very long messages."""
        long_content = "x" * 50000  # 50K characters

        response = await client.complete([
            LLMMessage(role="user", content=long_content)
        ])

        assert response is not None

    @pytest.mark.asyncio
    async def test_unicode_content(self, client):
        """Test handling unicode content."""
        unicode_content = "检查服务状态 🔥 日本語テスト"

        response = await client.complete([
            LLMMessage(role="user", content=unicode_content)
        ])

        assert response is not None

    @pytest.mark.asyncio
    async def test_special_characters(self, client):
        """Test handling special characters."""
        special_content = "Error: `kubectl get pods -n production | grep -E 'Error|CrashLoop'`"

        response = await client.complete([
            LLMMessage(role="user", content=special_content)
        ])

        assert response is not None
