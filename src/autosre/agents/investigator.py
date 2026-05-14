"""Investigation Agent.

Responsible for collecting observations, forming hypotheses,
testing hypotheses with evidence, and generating root cause analysis.
"""

import json
import logging
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from autosre.agents.base import (
    AgentCapability, AgentConfig, BaseAgent, ExecutionContext, ExecutionResult, LLMClient, Observation,
)
from autosre.agents.prompts import DOMAIN_GUIDANCE, get_investigation_prompt, format_investigation_prompt
from autosre.models.investigation import AgentState, Finding, Hypothesis, InvestigationStatus

logger = logging.getLogger(__name__)


class HypothesisAssessment(BaseModel):
    """Assessment of a single hypothesis."""
    hypothesis: str = Field(..., description="The hypothesis being assessed")
    assessment: str = Field(default="possible", description="confirmed/likely/possible/unlikely/ruled_out")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    supporting_evidence: list[str] = Field(default_factory=list)
    contradicting_evidence: list[str] = Field(default_factory=list)


class InvestigationOutput(BaseModel):
    """Structured output from investigation."""
    summary: str = Field(default="")
    findings: list[Finding] = Field(default_factory=list)
    hypothesis_assessments: list[HypothesisAssessment] = Field(default_factory=list)
    root_cause_candidate: Optional[str] = Field(default=None)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    gaps: list[str] = Field(default_factory=list)
    recommended_next_steps: list[str] = Field(default_factory=list)


class ToolCall(BaseModel):
    """Record of a tool call made during investigation."""
    tool_name: str = Field(..., description="Name of tool called")
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: Optional[str] = Field(default=None)
    success: bool = Field(default=True)
    duration_ms: Optional[float] = Field(default=None)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class InvestigationAgent(BaseAgent):
    """Base class for domain-specific investigation agents."""
    
    MAX_TOOL_CALLS = 25
    
    def __init__(self, domain: str = "general", config: Optional[AgentConfig] = None, llm: Optional[LLMClient] = None):
        self._domain = domain
        default_config = AgentConfig(
            name=f"{domain}_investigator", capabilities=[AgentCapability.INVESTIGATE, AgentCapability.OBSERVE],
            max_iterations=self.MAX_TOOL_CALLS, timeout_seconds=300, temperature=0.1,
        )
        super().__init__(config=config or default_config, llm=llm)
        self._tool_calls: list[ToolCall] = []
        self._seen_call_keys: set[str] = set()
    
    @property
    def name(self) -> str:
        return f"{self._domain}_investigator"
    
    @property
    def domain(self) -> str:
        return self._domain
    
    def get_domain_guidance(self) -> str:
        return DOMAIN_GUIDANCE.get(self._domain, "General investigation agent.")
    
    def get_domain_tools(self) -> list[Any]:
        return self._tools
    
    async def execute(self, context: ExecutionContext) -> ExecutionResult:
        if not await self.validate_context(context):
            return ExecutionResult(state=self._create_failed_state("Invalid context"))
        
        self._tool_calls = []
        self._seen_call_keys = set()
        tools = self.get_domain_tools()
        
        if not self.llm:
            logger.warning(f"[{self.name}] No LLM available")
            return ExecutionResult(state=self._create_completed_state(findings=[], summary="No LLM available"))
        
        system_prompt = get_investigation_prompt(domain=self._domain, custom_prompt=self.config.system_prompt)
        user_prompt = format_investigation_prompt(
            alert=context.alert, domain=self._domain, hypotheses=[h.model_dump() for h in context.hypotheses],
            service_topology=self._format_kg_context(context.kg_context),
            previous_findings=self._format_previous_findings(context.previous_findings),
        )
        
        output = await self._run_investigation(system_prompt=system_prompt, user_prompt=user_prompt, tools=tools, hypotheses=context.hypotheses)
        state = self._create_completed_state(findings=output.findings, summary=output.summary)
        
        return ExecutionResult(state=state, output=output, observations=self._observations)
    
    async def _run_investigation(self, system_prompt: str, user_prompt: str, tools: list[Any], hypotheses: list[Hypothesis]) -> InvestigationOutput:
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
        
        try:
            final_response, tool_history = await self.llm.generate_with_tools(messages=messages, tools=tools, max_iterations=self.config.max_iterations)
            for call in tool_history:
                self.add_observation(source=f"tool:{call.get('tool', 'unknown')}", data=call.get("result", ""), confidence=0.9 if call.get("success", True) else 0.5)
            return self._parse_investigation_output(response=final_response, hypotheses=hypotheses, tool_history=tool_history)
        except Exception as e:
            logger.error(f"[{self.name}] Investigation failed: {e}")
            return InvestigationOutput(summary=f"Investigation failed: {e}", confidence=0.0, gaps=["Investigation could not complete"])
    
    def _parse_investigation_output(self, response: str, hypotheses: list[Hypothesis], tool_history: list[dict[str, Any]]) -> InvestigationOutput:
        findings = []
        hypothesis_assessments = []
        
        try:
            if "```json" in response:
                json_text = response.split("```json")[1].split("```")[0]
                data = json.loads(json_text.strip())
                for f in data.get("findings", []):
                    findings.append(Finding(category=self._domain, detail=f.get("detail", str(f)), evidence=f.get("evidence"), severity=f.get("severity", "info"), confidence=f.get("confidence", 0.7)))
                return InvestigationOutput(
                    summary=data.get("summary", response[:500]), findings=findings, confidence=data.get("confidence", 0.5),
                    gaps=data.get("gaps", []), recommended_next_steps=data.get("recommended_next_steps", []),
                )
        except Exception:
            pass
        
        # Fallback
        findings = self._extract_findings_from_text(response)
        return InvestigationOutput(summary=response[:1000] if len(response) > 1000 else response, findings=findings, confidence=0.5)
    
    def _extract_findings_from_text(self, text: str) -> list[Finding]:
        if not text.strip():
            return []
        return [Finding(category=self._domain, detail=f"Investigation completed: {text[:200]}", severity="info", confidence=0.5)]
    
    def _format_kg_context(self, kg_context: dict[str, Any]) -> str:
        if not kg_context.get("available"):
            return "No service topology available."
        service_info = kg_context.get("service_info", {})
        return f"Service: {service_info.get('resolved_name', 'unknown')}"
    
    def _format_previous_findings(self, findings: list[Finding]) -> str:
        if not findings:
            return "No previous findings."
        return "\n".join(f"- [{f.category}] {f.detail}" for f in findings)


# Domain-specific investigators
class KubernetesInvestigator(InvestigationAgent):
    def __init__(self, config: Optional[AgentConfig] = None, llm: Optional[LLMClient] = None):
        super().__init__(domain="kubernetes", config=config, llm=llm)
    
    @property
    def name(self) -> str:
        return "kubernetes"


class MetricsInvestigator(InvestigationAgent):
    def __init__(self, config: Optional[AgentConfig] = None, llm: Optional[LLMClient] = None):
        super().__init__(domain="metrics", config=config, llm=llm)
    
    @property
    def name(self) -> str:
        return "metrics"


class LogsInvestigator(InvestigationAgent):
    def __init__(self, config: Optional[AgentConfig] = None, llm: Optional[LLMClient] = None):
        super().__init__(domain="logs", config=config, llm=llm)
    
    @property
    def name(self) -> str:
        return "log_analysis"


class TracesInvestigator(InvestigationAgent):
    def __init__(self, config: Optional[AgentConfig] = None, llm: Optional[LLMClient] = None):
        super().__init__(domain="traces", config=config, llm=llm)
    
    @property
    def name(self) -> str:
        return "traces"
