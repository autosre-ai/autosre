"""
Base Subagent — Abstract base class for investigation subagents.

Each subagent specializes in a domain (kubernetes, metrics, logs, etc.)
and runs a ReAct loop to gather evidence.
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Optional

from pydantic import BaseModel, Field

from ..state import Evidence, SubagentResult, InvestigationStatus

logger = logging.getLogger(__name__)


class SubagentConfig(BaseModel):
    """Configuration for a subagent."""
    
    agent_id: str
    max_loops: int = 25
    timeout_seconds: float = 120.0
    
    # Domain-specific config
    skills: list[str] = Field(default_factory=list)
    system_prompt_extra: str = ""


SUBAGENT_BASE_PROMPT = """You are the {agent_name} investigation agent for an AI SRE system.

Your role is to INVESTIGATE a production incident by gathering evidence from your domain.
DO NOT take any remediation actions - investigation only.

## Alert
{alert}

## Hypotheses to Test
{hypotheses}

## Service Context
{service_context}

## Your Domain Capabilities
{capabilities}

## Investigation Guidelines
1. Start with the most likely hypothesis first
2. Gather concrete evidence (logs, metrics, events)
3. If you find nothing relevant in your domain, say so clearly
4. Do NOT fabricate data - report what you actually find
5. Summarize your findings with confidence level

{extra_instructions}"""


class BaseSubagent(ABC):
    """Abstract base for investigation subagents.
    
    Each subagent:
    1. Has domain-specific skills/tools
    2. Runs a ReAct loop to gather evidence
    3. Returns findings summary with evidence
    """
    
    agent_id: str = "base"
    agent_name: str = "Base Agent"
    capabilities_description: str = "General investigation"
    
    def __init__(self, config: Optional[SubagentConfig] = None):
        self.config = config or SubagentConfig(agent_id=self.agent_id)
        self._start_time: float = 0
        self._loop_count: int = 0
        self._evidence: list[Evidence] = []
        self._tool_calls: list[dict] = []
    
    @abstractmethod
    async def get_tools(self) -> list[Any]:
        """Return list of tools available to this subagent.
        
        Each tool should be a callable that takes parameters
        and returns string results.
        """
        pass
    
    @abstractmethod
    async def execute_tool(
        self,
        tool_name: str,
        **kwargs: Any,
    ) -> str:
        """Execute a tool call and return result."""
        pass
    
    def build_system_prompt(
        self,
        alert: dict[str, Any],
        hypotheses: list[str],
        service_context: str = "",
    ) -> str:
        """Build system prompt for this subagent."""
        return SUBAGENT_BASE_PROMPT.format(
            agent_name=self.agent_name,
            alert=alert,
            hypotheses="\n".join(f"- {h}" for h in hypotheses) if hypotheses else "None specified",
            service_context=service_context or "No service context available",
            capabilities=self.capabilities_description,
            extra_instructions=self.config.system_prompt_extra,
        )
    
    async def investigate(
        self,
        alert: dict[str, Any],
        hypotheses: list[str],
        service_context: str = "",
        llm_client: Optional[Any] = None,
    ) -> SubagentResult:
        """Run investigation loop.
        
        This is a simplified version that doesn't actually run LLM loops.
        Real implementation would use ReAct pattern with tool calls.
        
        For now, we just gather basic evidence and return.
        """
        self._start_time = time.time()
        self._loop_count = 0
        self._evidence = []
        self._tool_calls = []
        
        try:
            # Subclass implements actual investigation
            findings = await self._run_investigation(
                alert=alert,
                hypotheses=hypotheses,
                service_context=service_context,
                llm_client=llm_client,
            )
            
            duration = time.time() - self._start_time
            
            return SubagentResult(
                agent_id=self.agent_id,
                status=InvestigationStatus.COMPLETED,
                findings=findings,
                evidence=self._evidence,
                duration_seconds=duration,
                react_loops=self._loop_count,
            )
            
        except Exception as e:
            logger.error(f"[{self.agent_id}] Investigation failed: {e}")
            
            return SubagentResult(
                agent_id=self.agent_id,
                status=InvestigationStatus.FAILED,
                findings=f"Investigation failed: {e}",
                evidence=self._evidence,
                duration_seconds=time.time() - self._start_time,
                react_loops=self._loop_count,
                error=str(e),
            )
    
    @abstractmethod
    async def _run_investigation(
        self,
        alert: dict[str, Any],
        hypotheses: list[str],
        service_context: str,
        llm_client: Optional[Any],
    ) -> str:
        """Subclass implements actual investigation logic.
        
        Returns findings summary string.
        """
        pass
    
    def add_evidence(
        self,
        skill: str,
        query: str,
        result: str,
        relevance: float = 0.5,
    ) -> None:
        """Add evidence gathered during investigation."""
        self._evidence.append(Evidence(
            source=self.agent_id,
            skill=skill,
            query=query,
            result=result,
            relevance=relevance,
        ))
    
    def record_tool_call(
        self,
        tool_name: str,
        args: dict[str, Any],
        result: str,
    ) -> None:
        """Record a tool call for tracking."""
        self._tool_calls.append({
            "tool": tool_name,
            "args": args,
            "result": result[:500],  # Truncate for storage
            "loop": self._loop_count,
        })


class MockSubagent(BaseSubagent):
    """Mock subagent for testing."""
    
    agent_id = "mock"
    agent_name = "Mock Agent"
    capabilities_description = "Mock investigation for testing"
    
    async def get_tools(self) -> list[Any]:
        return []
    
    async def execute_tool(self, tool_name: str, **kwargs: Any) -> str:
        return f"Mock result for {tool_name}"
    
    async def _run_investigation(
        self,
        alert: dict[str, Any],
        hypotheses: list[str],
        service_context: str,
        llm_client: Optional[Any],
    ) -> str:
        self._loop_count = 1
        self.add_evidence(
            skill="mock_check",
            query="mock query",
            result="Mock evidence gathered",
            relevance=0.5,
        )
        return f"Mock investigation of alert: {alert.get('name', 'unknown')}"
