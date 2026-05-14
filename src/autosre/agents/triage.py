"""Triage Agent.

Responsible for initial alert assessment, severity classification,
service impact identification, and routing to specialist agents.
"""

import json
import logging
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from autosre.agents.base import (
    AgentCapability, AgentConfig, BaseAgent, ExecutionContext, ExecutionResult, LLMClient,
)
from autosre.agents.prompts import TRIAGE_SYSTEM_PROMPT, format_triage_prompt
from autosre.models.alert import Alert, AlertSeverity
from autosre.models.investigation import AgentState, Finding, Hypothesis, InvestigationStatus

logger = logging.getLogger(__name__)


class BlastRadius(BaseModel):
    """Service impact assessment."""
    direct_impact: list[str] = Field(default_factory=list)
    indirect_impact: list[str] = Field(default_factory=list)
    
    @property
    def total_services(self) -> int:
        return len(set(self.direct_impact + self.indirect_impact))


class TriageResult(BaseModel):
    """Structured output from triage assessment."""
    severity: str = Field(default="medium")
    urgency: str = Field(default="soon")
    affected_services: list[str] = Field(default_factory=list)
    blast_radius: BlastRadius = Field(default_factory=BlastRadius)
    initial_hypotheses: list[Hypothesis] = Field(default_factory=list)
    recommended_agents: list[str] = Field(default_factory=list)
    escalation_needed: bool = Field(default=False)
    escalation_reason: Optional[str] = Field(default=None)
    initial_actions: list[str] = Field(default_factory=list)
    reasoning: str = Field(default="")
    
    @property
    def is_critical(self) -> bool:
        return self.severity.lower() == "critical"


class TriageAgent(BaseAgent):
    """Agent responsible for initial alert triage."""
    
    DEFAULT_AGENTS = ["kubernetes", "metrics", "logs"]
    
    def __init__(self, config: Optional[AgentConfig] = None, llm: Optional[LLMClient] = None):
        default_config = AgentConfig(
            name="triage", capabilities=[AgentCapability.TRIAGE],
            max_iterations=1, timeout_seconds=30, temperature=0.3,
        )
        super().__init__(config=config or default_config, llm=llm)
    
    @property
    def name(self) -> str:
        return "triage"
    
    async def execute(self, context: ExecutionContext) -> ExecutionResult:
        if not await self.validate_context(context):
            return ExecutionResult(state=self._create_failed_state("No alert provided"))
        
        alert = context.alert
        self.add_observation(source="alert", data=alert, confidence=1.0)
        
        if not self.llm:
            result = self._rule_based_triage(alert, context)
        else:
            result = await self._llm_triage(alert, context)
        
        findings = self._create_findings_from_triage(result)
        state = self._create_completed_state(findings=findings, summary=result.reasoning)
        
        return ExecutionResult(
            state=state, output=result, observations=self._observations,
            next_agents=result.recommended_agents, should_continue=not result.escalation_needed,
        )
    
    async def _llm_triage(self, alert: dict[str, Any], context: ExecutionContext) -> TriageResult:
        service_context = self._format_service_context(context.kg_context)
        historical_context = self._format_historical_context(context.memory_context)
        user_prompt = format_triage_prompt(alert=alert, service_context=service_context, historical_context=historical_context)
        
        messages = [{"role": "system", "content": TRIAGE_SYSTEM_PROMPT}, {"role": "user", "content": user_prompt}]
        
        try:
            response = await self.llm.generate(messages=messages, temperature=self.config.temperature, structured_output=TriageResult)
            if isinstance(response, TriageResult):
                return response
            return self._parse_triage_response(response)
        except Exception as e:
            logger.error(f"[triage] LLM failed: {e}")
            return self._rule_based_triage(alert, context)
    
    def _rule_based_triage(self, alert: dict[str, Any], context: ExecutionContext) -> TriageResult:
        name = alert.get("name", "").lower()
        severity = alert.get("severity", "warning").lower()
        service = alert.get("service") or alert.get("labels", {}).get("service", "unknown")
        
        assessed_severity = severity
        if any(word in name for word in ["critical", "down", "outage"]):
            assessed_severity = "critical"
        elif any(word in name for word in ["error", "failed"]):
            assessed_severity = "high"
        
        urgency = "immediate" if assessed_severity == "critical" else ("soon" if assessed_severity == "high" else "scheduled")
        
        recommended_agents = list(self.DEFAULT_AGENTS)
        if "cpu" in name or "memory" in name:
            recommended_agents = ["metrics", "kubernetes"]
        elif "latency" in name:
            recommended_agents = ["metrics", "traces", "logs"]
        elif "error" in name:
            recommended_agents = ["logs", "metrics"]
        
        hypotheses = self._generate_hypotheses_from_rules(alert)
        
        return TriageResult(
            severity=assessed_severity, urgency=urgency, affected_services=[service] if service != "unknown" else [],
            blast_radius=BlastRadius(direct_impact=[service] if service != "unknown" else []),
            initial_hypotheses=hypotheses, recommended_agents=recommended_agents,
            escalation_needed=(assessed_severity == "critical"), reasoning=f"Rule-based triage: {assessed_severity}",
        )
    
    def _generate_hypotheses_from_rules(self, alert: dict[str, Any]) -> list[Hypothesis]:
        name = alert.get("name", "").lower()
        hypotheses = []
        
        if "cpu" in name:
            hypotheses.append(Hypothesis(hypothesis="High CPU usage", priority="high", agents_to_test=["metrics", "kubernetes"], confidence=0.6))
        if "memory" in name or "oom" in name:
            hypotheses.append(Hypothesis(hypothesis="Memory leak or OOM", priority="high", agents_to_test=["kubernetes", "metrics"], confidence=0.7))
        if "error" in name:
            hypotheses.append(Hypothesis(hypothesis="Application error", priority="high", agents_to_test=["logs", "kubernetes"], confidence=0.6))
        if "latency" in name:
            hypotheses.append(Hypothesis(hypothesis="Downstream dependency issue", priority="high", agents_to_test=["traces", "metrics"], confidence=0.6))
        
        if not hypotheses:
            hypotheses.append(Hypothesis(hypothesis="Unknown issue", priority="high", agents_to_test=self.DEFAULT_AGENTS, confidence=0.3))
        
        return hypotheses
    
    def _format_service_context(self, kg_context: dict[str, Any]) -> str:
        if not kg_context.get("available"):
            return "No service topology available."
        service_info = kg_context.get("service_info", {})
        if not service_info:
            return "No service topology available."
        return f"Service: {service_info.get('resolved_name', 'unknown')}"
    
    def _format_historical_context(self, memory_context: dict[str, Any]) -> str:
        if not memory_context.get("has_similar_episodes"):
            return "No historical context."
        return memory_context.get("enhanced_prompt", "Previous similar incidents found.")
    
    def _create_findings_from_triage(self, result: TriageResult) -> list[Finding]:
        findings = [self.create_finding(detail=f"Triage: {result.severity} severity, {result.urgency} urgency", evidence=result.reasoning, severity=result.severity, confidence=0.8)]
        if result.escalation_needed:
            findings.append(self.create_finding(detail=f"Escalation: {result.escalation_reason}", severity="critical", confidence=0.9))
        return findings
    
    def _parse_triage_response(self, response: Any) -> TriageResult:
        response_text = str(response.content if hasattr(response, "content") else response)
        try:
            json_text = response_text.split("```json")[1].split("```")[0] if "```json" in response_text else response_text
            data = json.loads(json_text.strip())
            hypotheses = [Hypothesis(hypothesis=h.get("hypothesis", str(h)), priority=h.get("priority", "medium"), agents_to_test=h.get("agents_to_dispatch", []), confidence=h.get("confidence", 0.5)) for h in data.get("initial_hypotheses", [])]
            return TriageResult(
                severity=data.get("severity", "medium"), urgency=data.get("urgency", "soon"),
                affected_services=data.get("affected_services", []), initial_hypotheses=hypotheses,
                recommended_agents=data.get("recommended_agents", self.DEFAULT_AGENTS),
                escalation_needed=data.get("escalation_needed", False), reasoning=data.get("reasoning", ""),
            )
        except Exception:
            return TriageResult(severity="medium", urgency="soon", recommended_agents=self.DEFAULT_AGENTS)
