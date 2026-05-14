"""
Base agent abstract class for AutoSRE V2.

Provides the foundation for all investigation agents with:
- Async execution
- State management
- Tool integration
- LLM interaction patterns
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

from pydantic import BaseModel, Field

from autosre.core.alert import Alert
from autosre.core.investigation import Evidence, Finding, Hypothesis, Investigation
from autosre.core.llm_client import (
    LLMClient,
    LLMMessage,
    LLMResponse,
    ToolCall,
    ToolDefinition,
)
from autosre.utils.config import AgentConfig, get_config
from autosre.utils.logging import LogContext, get_logger, set_agent_id

logger = get_logger(__name__)


class AgentStatus(str, Enum):
    """Agent execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"
    TIMEOUT = "timeout"


@dataclass
class AgentResult:
    """
    Result of an agent's execution.

    Contains findings, evidence, and metadata from the investigation.
    """

    agent_id: str
    status: AgentStatus
    findings: list[Finding] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    summary: str = ""
    confidence: float = 0.0
    iterations: int = 0
    duration_seconds: float = 0.0
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        """Check if agent completed successfully."""
        return self.status == AgentStatus.COMPLETED

    @property
    def has_findings(self) -> bool:
        """Check if agent produced findings."""
        return len(self.findings) > 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "agent_id": self.agent_id,
            "status": self.status.value,
            "findings": [f.model_dump() for f in self.findings],
            "evidence": [e.model_dump() for e in self.evidence],
            "summary": self.summary,
            "confidence": self.confidence,
            "iterations": self.iterations,
            "duration_seconds": self.duration_seconds,
            "error": self.error,
            "metadata": self.metadata,
        }


class ToolRegistry:
    """
    Registry of tools available to agents.

    Manages tool definitions and handlers for LLM function calling.
    """

    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}
        self._handlers: dict[str, Callable] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        handler: Callable,
    ) -> None:
        """
        Register a tool.

        Args:
            name: Tool name
            description: Tool description for LLM
            parameters: JSON Schema for parameters
            handler: Function to call when tool is invoked
        """
        self._tools[name] = ToolDefinition(
            name=name,
            description=description,
            parameters=parameters,
            handler=handler,
        )
        self._handlers[name] = handler

    def get_definitions(self) -> list[ToolDefinition]:
        """Get all tool definitions."""
        return list(self._tools.values())

    async def execute(self, tool_call: ToolCall) -> Any:
        """
        Execute a tool call.

        Args:
            tool_call: Tool call from LLM

        Returns:
            Tool execution result
        """
        handler = self._handlers.get(tool_call.name)
        if not handler:
            return f"Unknown tool: {tool_call.name}"

        try:
            import asyncio
            if asyncio.iscoroutinefunction(handler):
                return await handler(**tool_call.arguments)
            else:
                return handler(**tool_call.arguments)
        except Exception as e:
            logger.error(
                "Tool execution error",
                tool=tool_call.name,
                error=str(e),
            )
            return f"Error executing {tool_call.name}: {e}"

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools


class BaseAgent(ABC):
    """
    Abstract base class for investigation agents.

    Implements the ReAct (Reasoning + Acting) pattern with:
    - Thought generation
    - Tool execution
    - Observation processing
    - Iterative refinement
    """

    # Class attributes for subclasses to override
    agent_id: str = "base"
    agent_name: str = "Base Agent"
    description: str = "Abstract base agent"

    def __init__(
        self,
        config: AgentConfig | None = None,
        tools: ToolRegistry | None = None,
    ):
        """
        Initialize agent.

        Args:
            config: Agent configuration
            tools: Tool registry (creates default if not provided)
        """
        self.config = config or get_config().agents.investigation
        self.tools = tools or ToolRegistry()
        self._llm = None
        self._messages: list[LLMMessage] = []
        self._tool_call_history: set[str] = set()  # For deduplication
        self._current_investigation: Investigation | None = None

        # Register default tools
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """Register default tools. Override in subclasses for domain-specific tools."""
        pass

    async def _get_llm(self):
        """Get or create LLM client."""
        if self._llm is None:
            llm_config = get_config().get_llm_config_for_agent(self.agent_id)
            self._llm = LLMClient.create(llm_config)
        return self._llm

    @abstractmethod
    def get_system_prompt(self, investigation: Investigation) -> str:
        """
        Generate system prompt for the agent.

        Args:
            investigation: Current investigation context

        Returns:
            System prompt string
        """
        ...

    @abstractmethod
    async def execute(self, investigation: Investigation) -> AgentResult:
        """
        Execute the agent's investigation.

        Args:
            investigation: Investigation context

        Returns:
            AgentResult with findings
        """
        ...

    async def run_react_loop(
        self,
        investigation: Investigation,
        initial_message: str,
        max_iterations: int | None = None,
    ) -> AgentResult:
        """
        Run the ReAct loop for investigation.

        Implements the standard reasoning + acting pattern with
        tool calling and iterative refinement.

        Args:
            investigation: Investigation context
            initial_message: Initial user message
            max_iterations: Maximum iterations (default: from config)

        Returns:
            AgentResult with collected findings
        """
        self._current_investigation = investigation
        start_time = datetime.now(timezone.utc)
        max_iter = max_iterations or self.config.max_iterations

        # Initialize messages
        system_prompt = self.get_system_prompt(investigation)
        self._messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=initial_message),
        ]

        findings: list[Finding] = []
        evidence: list[Evidence] = []
        iterations = 0

        with LogContext(
            investigation_id=investigation.id,
            agent_id=self.agent_id,
        ):
            try:
                llm = await self._get_llm()

                for iteration in range(max_iter):
                    iterations = iteration + 1

                    logger.debug(
                        "Starting iteration",
                        iteration=iterations,
                        max_iterations=max_iter,
                    )

                    # Get LLM response
                    response = await llm.complete_with_retry(
                        messages=self._messages,
                        tools=self.tools.get_definitions() if len(self.tools) > 0 else None,
                    )

                    # Add response to history
                    self._messages.append(LLMMessage(
                        role="assistant",
                        content=response.content or "",
                        tool_calls=[{
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.name, "arguments": str(tc.arguments)},
                        } for tc in response.tool_calls] if response.tool_calls else None,
                    ))

                    # If no tool calls, agent is done
                    if not response.has_tool_calls:
                        logger.info(
                            "Agent completed",
                            iteration=iterations,
                            has_content=bool(response.content),
                        )
                        break

                    # Execute tool calls
                    for tool_call in response.tool_calls:
                        # Check for duplicate calls
                        call_key = f"{tool_call.name}:{str(sorted(tool_call.arguments.items()))}"
                        if call_key in self._tool_call_history:
                            tool_result = "DUPLICATE: You already made this exact call. Use the previous result."
                            logger.debug("Skipped duplicate tool call", tool=tool_call.name)
                        else:
                            self._tool_call_history.add(call_key)
                            tool_result = await self.tools.execute(tool_call)

                            # Collect evidence
                            if tool_result and not str(tool_result).startswith("Error"):
                                evidence.append(Evidence(
                                    type="custom",
                                    source=tool_call.name,
                                    query=str(tool_call.arguments),
                                    data=tool_result,
                                    summary=f"Tool {tool_call.name} result",
                                ))

                        # Add tool result to messages
                        self._messages.append(LLMMessage(
                            role="tool",
                            content=str(tool_result)[:10000],  # Truncate large results
                            tool_call_id=tool_call.id,
                        ))

                    # Add reflection checkpoint every 5 iterations
                    if iterations % 5 == 0:
                        self._messages.append(LLMMessage(
                            role="user",
                            content=self._get_reflection_prompt(),
                        ))

                else:
                    # Hit max iterations
                    logger.warning(
                        "Agent hit max iterations",
                        max_iterations=max_iter,
                    )

                # Extract final summary
                summary = await self._extract_summary()
                confidence = await self._estimate_confidence(summary)

                # Parse findings from summary
                findings = await self._extract_findings(summary, evidence)

                duration = (datetime.now(timezone.utc) - start_time).total_seconds()

                return AgentResult(
                    agent_id=self.agent_id,
                    status=AgentStatus.COMPLETED,
                    findings=findings,
                    evidence=evidence,
                    summary=summary,
                    confidence=confidence,
                    iterations=iterations,
                    duration_seconds=duration,
                )

            except Exception as e:
                logger.error("Agent execution error", error=str(e))
                duration = (datetime.now(timezone.utc) - start_time).total_seconds()

                return AgentResult(
                    agent_id=self.agent_id,
                    status=AgentStatus.ERROR,
                    summary=f"Error during investigation: {e}",
                    iterations=iterations,
                    duration_seconds=duration,
                    error=str(e),
                )

    def _get_reflection_prompt(self) -> str:
        """Get prompt for mid-investigation reflection."""
        return """
REFLECTION CHECKPOINT: Before continuing, briefly assess:
1. What have you learned so far?
2. Which hypotheses can you confirm or eliminate?
3. What is the most valuable next action?
4. Are you making progress or going in circles?

State your assessment concisely, then continue investigating.
"""

    async def _extract_summary(self) -> str:
        """Extract summary from final assistant message."""
        for msg in reversed(self._messages):
            if msg.role == "assistant" and msg.content and not msg.tool_calls:
                return msg.content

        # No clean final message, request one
        llm = await self._get_llm()
        self._messages.append(LLMMessage(
            role="user",
            content="Provide a concise summary of your investigation findings.",
        ))

        response = await llm.complete_with_retry(self._messages)
        return response.content or "No summary available"

    async def _estimate_confidence(self, summary: str) -> float:
        """Estimate confidence level from summary."""
        # Simple heuristic - could use LLM for more accurate estimation
        confidence_indicators = {
            "high confidence": 0.9,
            "confident": 0.8,
            "likely": 0.7,
            "probably": 0.6,
            "possibly": 0.5,
            "uncertain": 0.3,
            "unclear": 0.3,
            "inconclusive": 0.2,
        }

        summary_lower = summary.lower()
        for indicator, score in confidence_indicators.items():
            if indicator in summary_lower:
                return score

        return 0.5  # Default moderate confidence

    async def _extract_findings(
        self,
        summary: str,
        evidence: list[Evidence],
    ) -> list[Finding]:
        """Extract structured findings from summary."""
        # For base implementation, create a single finding
        # Subclasses can override for more sophisticated extraction
        if not summary or summary == "No summary available":
            return []

        return [Finding(
            title=f"{self.agent_name} Investigation Result",
            description=summary,
            agent_id=self.agent_id,
            evidence_ids=[e.id for e in evidence],
            confidence=await self._estimate_confidence(summary),
        )]

    def reset(self) -> None:
        """Reset agent state for new investigation."""
        self._messages = []
        self._tool_call_history = set()
        self._current_investigation = None
