"""
Base Subagent — Abstract base class for investigation subagents.

Each subagent specializes in a domain (kubernetes, metrics, logs, etc.)
and runs a ReAct loop to gather evidence.
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Optional, Protocol

from pydantic import BaseModel, Field

from .react import (
    Tool,
    ReactConfig,
    Evidence,
    SubagentResult,
    react_loop,
    create_tool,
)

logger = logging.getLogger(__name__)


class LLMProtocol(Protocol):
    """Protocol for LLM clients."""
    
    async def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> Any:
        """Generate completion for a prompt."""
        ...


class SubagentConfig(BaseModel):
    """Configuration for a subagent."""
    
    agent_id: str
    max_loops: int = 15
    timeout_seconds: float = 120.0
    
    # Domain-specific config
    skills: list[str] = Field(default_factory=list)
    system_prompt_extra: str = ""
    
    # ReAct configuration
    reflection_interval: int = 5
    max_no_findings_attempts: int = 3
    tool_retry_count: int = 1


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
    
    Subclasses must implement:
    - get_tools(): Return list of Tool objects
    - get_hypothesis(): Build hypothesis string from alert/context
    """
    
    agent_id: str = "base"
    agent_name: str = "Base Agent"
    capabilities_description: str = "General investigation"
    
    def __init__(self, config: Optional[SubagentConfig] = None):
        self.config = config or SubagentConfig(agent_id=self.agent_id)
        self._evidence: list[Evidence] = []
    
    @abstractmethod
    async def get_tools(self) -> list[Tool]:
        """Return list of Tool objects available to this subagent.
        
        Each Tool should have:
        - name: Unique identifier
        - description: What it does
        - parameters: JSON schema
        - executor: Function to call
        """
        pass
    
    def get_hypothesis(
        self,
        alert: dict[str, Any],
        hypotheses: list[str],
        service_context: str = "",
    ) -> str:
        """Build the hypothesis string for the ReAct loop.
        
        Override to customize how the investigation is framed.
        """
        if hypotheses:
            return f"Testing hypotheses: {'; '.join(hypotheses)}"
        
        alert_name = alert.get("name", alert.get("alert_name", "Unknown alert"))
        service = alert.get("service", alert.get("labels", {}).get("service", "unknown"))
        return f"Investigating {alert_name} for service {service}"
    
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
        llm_client: Optional[LLMProtocol] = None,
    ) -> SubagentResult:
        """Run investigation using the ReAct loop.
        
        This is the main entry point for subagent execution.
        
        Args:
            alert: The alert being investigated
            hypotheses: List of hypotheses to test
            service_context: Service topology/context info
            llm_client: Optional LLM client
            
        Returns:
            SubagentResult with findings and evidence
        """
        start_time = time.time()
        
        try:
            # Get tools for this subagent
            tools = await self.get_tools()
            
            if not tools:
                return SubagentResult(
                    agent_id=self.agent_id,
                    status="completed",
                    findings=f"No tools available for {self.agent_name}. Cannot investigate.",
                    evidence=[],
                    duration_seconds=time.time() - start_time,
                    react_loops=0,
                )
            
            # Build hypothesis
            hypothesis = self.get_hypothesis(alert, hypotheses, service_context)
            
            # Build ReAct config from subagent config
            react_config = ReactConfig(
                max_iterations=self.config.max_loops,
                reflection_interval=self.config.reflection_interval,
                max_no_findings_attempts=self.config.max_no_findings_attempts,
                tool_retry_count=self.config.tool_retry_count,
            )
            
            # Run the ReAct loop
            result = await react_loop(
                hypothesis=hypothesis,
                tools=tools,
                alert=alert,
                service_context=service_context,
                llm=llm_client,
                config=react_config,
                agent_id=self.agent_id,
            )
            
            return result
            
        except asyncio.TimeoutError:
            logger.error(f"[{self.agent_id}] Investigation timed out")
            return SubagentResult(
                agent_id=self.agent_id,
                status="failed",
                findings=f"Investigation timed out after {self.config.timeout_seconds}s",
                evidence=self._evidence,
                duration_seconds=time.time() - start_time,
                react_loops=0,
                error="Timeout",
            )
            
        except Exception as e:
            logger.error(f"[{self.agent_id}] Investigation failed: {e}")
            return SubagentResult(
                agent_id=self.agent_id,
                status="failed",
                findings=f"Investigation failed: {e}",
                evidence=self._evidence,
                duration_seconds=time.time() - start_time,
                react_loops=0,
                error=str(e),
            )
    
    # ----- Legacy methods for backwards compatibility -----
    
    async def execute_tool(
        self,
        tool_name: str,
        **kwargs: Any,
    ) -> str:
        """Execute a tool call and return result.
        
        Deprecated: Tools now execute through the ReAct loop.
        This is kept for backwards compatibility during migration.
        """
        tools = await self.get_tools()
        for tool in tools:
            if tool.name == tool_name:
                result = await tool.execute(**kwargs)
                return result.output if result.success else f"Error: {result.error}"
        return f"Unknown tool: {tool_name}"
    
    def add_evidence(
        self,
        skill: str,
        query: str,
        result: str,
        relevance: float = 0.5,
    ) -> None:
        """Add evidence gathered during investigation.
        
        Deprecated: Evidence is now collected by the ReAct loop.
        """
        self._evidence.append(Evidence(
            source=self.agent_id,
            skill=skill,
            query=query,
            result=result,
            relevance=relevance,
        ))


class MockSubagent(BaseSubagent):
    """Mock subagent for testing."""
    
    agent_id = "mock"
    agent_name = "Mock Agent"
    capabilities_description = "Mock investigation for testing"
    
    async def get_tools(self) -> list[Tool]:
        """Return mock tools."""
        async def mock_check(**kwargs: Any) -> str:
            return f"Mock result for args: {kwargs}"
        
        return [
            create_tool(
                name="mock_check",
                description="Mock tool that returns placeholder data",
                executor=mock_check,
                parameters={
                    "type": "object",
                    "properties": {
                        "target": {"type": "string", "description": "Target to check"},
                    },
                },
            ),
        ]
    
    def get_hypothesis(
        self,
        alert: dict[str, Any],
        hypotheses: list[str],
        service_context: str = "",
    ) -> str:
        return f"Mock investigation of alert: {alert.get('name', 'unknown')}"


# ----- Parallel Execution -----

async def run_subagents_parallel(
    alert: dict[str, Any],
    subagents: list[BaseSubagent],
    hypotheses: Optional[list[str]] = None,
    service_context: str = "",
    llm_client: Optional[LLMProtocol] = None,
    timeout: float = 120.0,
) -> list[SubagentResult]:
    """Run multiple subagents in parallel.
    
    Args:
        alert: Alert being investigated.
        subagents: List of subagent instances to run.
        hypotheses: Hypotheses to test.
        service_context: Service topology context.
        llm_client: Optional LLM client (uses default if None).
        timeout: Timeout in seconds for all subagents.
        
    Returns:
        List of SubagentResult from each subagent.
    """
    hyp_strings = hypotheses or []
    
    # Create tasks
    async def run_with_timeout(subagent: BaseSubagent) -> SubagentResult:
        try:
            return await asyncio.wait_for(
                subagent.investigate(
                    alert=alert,
                    hypotheses=hyp_strings,
                    service_context=service_context,
                    llm_client=llm_client,
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            return SubagentResult(
                agent_id=subagent.agent_id,
                status="timeout",
                findings=f"Subagent timed out after {timeout}s",
                error="Timeout",
            )
        except Exception as e:
            return SubagentResult(
                agent_id=subagent.agent_id,
                status="failed",
                findings=f"Subagent failed: {e}",
                error=str(e),
            )
    
    tasks = [run_with_timeout(subagent) for subagent in subagents]
    
    # Run in parallel
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Convert exceptions to failed results
    final_results: list[SubagentResult] = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            final_results.append(SubagentResult(
                agent_id=subagents[i].agent_id,
                status="failed",
                findings=f"Subagent failed: {result}",
                error=str(result),
            ))
        else:
            final_results.append(result)
    
    return final_results
