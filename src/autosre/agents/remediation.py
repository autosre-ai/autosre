"""Remediation Agent.

Responsible for suggesting fixes, generating runbook steps,
risk assessment for actions, and rollback planning.
"""

import json
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from autosre.agents.base import (
    AgentCapability, AgentConfig, BaseAgent, ExecutionContext, ExecutionResult, LLMClient,
)
from autosre.agents.prompts import REMEDIATION_SYSTEM_PROMPT, format_remediation_prompt
from autosre.models.investigation import AgentState, Finding, InvestigationStatus

logger = logging.getLogger(__name__)


class ActionCategory(str, Enum):
    OBSERVE = "observe"
    MITIGATE = "mitigate"
    REMEDIATE = "remediate"
    ESCALATE = "escalate"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RemediationAction(BaseModel):
    """A single remediation action."""
    action: str = Field(..., description="Description of the action")
    category: ActionCategory = Field(default=ActionCategory.OBSERVE)
    risk_level: RiskLevel = Field(default=RiskLevel.LOW)
    command: Optional[str] = Field(default=None)
    expected_outcome: str = Field(default="")
    verification: str = Field(default="")
    rollback: Optional[str] = Field(default=None)
    blast_radius: str = Field(default="single service")
    automation_ready: bool = Field(default=False)
    requires_approval: bool = Field(default=True)
    
    @property
    def is_safe(self) -> bool:
        return self.risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM) and self.rollback is not None


class RunbookStep(BaseModel):
    """A step in a runbook procedure."""
    step: int = Field(..., description="Step number")
    action: str = Field(..., description="What to do")
    commands: list[str] = Field(default_factory=list)
    verification: str = Field(default="")
    if_fails: Optional[str] = Field(default=None)


class Escalation(BaseModel):
    """Escalation information."""
    needed: bool = Field(default=False)
    reason: Optional[str] = Field(default=None)
    suggested_teams: list[str] = Field(default_factory=list)
    priority: str = Field(default="P3")
    immediate: bool = Field(default=False)


class RemediationOutput(BaseModel):
    """Structured output from remediation planning."""
    root_cause_summary: str = Field(default="Unknown")
    recommended_actions: list[RemediationAction] = Field(default_factory=list)
    runbook_steps: list[RunbookStep] = Field(default_factory=list)
    escalation: Escalation = Field(default_factory=Escalation)
    monitoring_recommendations: list[str] = Field(default_factory=list)
    prevention_recommendations: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    
    @property
    def safe_actions(self) -> list[RemediationAction]:
        return [a for a in self.recommended_actions if a.is_safe]
    
    @property
    def requires_human_approval(self) -> bool:
        return any(a.requires_approval for a in self.recommended_actions)


class RemediationAgent(BaseAgent):
    """Agent responsible for remediation planning."""
    
    SAFE_KUBERNETES_OPS = ["kubectl get", "kubectl describe", "kubectl logs", "kubectl top"]
    DANGEROUS_OPS = ["delete", "scale --replicas=0", "drain", "cordon", "apply -f", "patch"]
    
    def __init__(self, config: Optional[AgentConfig] = None, llm: Optional[LLMClient] = None):
        default_config = AgentConfig(name="remediation", capabilities=[AgentCapability.REMEDIATE], max_iterations=1, timeout_seconds=60, temperature=0.2)
        super().__init__(config=config or default_config, llm=llm)
    
    @property
    def name(self) -> str:
        return "remediation"
    
    async def execute(self, context: ExecutionContext) -> ExecutionResult:
        if not await self.validate_context(context):
            return ExecutionResult(state=self._create_failed_state("Invalid context"))
        
        findings_summary = self._summarize_findings(context.previous_findings)
        root_cause = self._identify_root_cause(context.previous_findings)
        service_context = self._format_service_context(context.kg_context)
        current_state = self._assess_current_state(context)
        constraints = self._get_constraints(context.team_config)
        
        if not self.llm:
            output = self._rule_based_remediation(alert=context.alert, findings=context.previous_findings, root_cause=root_cause)
        else:
            output = await self._llm_remediation(findings_summary, root_cause, service_context, current_state, constraints)
        
        output = self._apply_safety_rules(output)
        findings = self._create_findings_from_plan(output)
        state = self._create_completed_state(findings=findings, summary=f"Remediation: {len(output.recommended_actions)} actions")
        
        return ExecutionResult(state=state, output=output, observations=self._observations, should_continue=not output.escalation.needed)
    
    async def _llm_remediation(self, findings_summary: str, root_cause: str, service_context: str, current_state: str, constraints: str) -> RemediationOutput:
        user_prompt = format_remediation_prompt(findings_summary=findings_summary, root_cause=root_cause, service_context=service_context, constraints=constraints)
        messages = [{"role": "system", "content": REMEDIATION_SYSTEM_PROMPT}, {"role": "user", "content": user_prompt}]
        
        try:
            response = await self.llm.generate(messages=messages, temperature=self.config.temperature, structured_output=RemediationOutput)
            if isinstance(response, RemediationOutput):
                return response
            return self._parse_remediation_response(response, root_cause)
        except Exception as e:
            logger.error(f"[remediation] LLM failed: {e}")
            return RemediationOutput(root_cause_summary=root_cause, escalation=Escalation(needed=True, reason=f"LLM failed: {e}"))
    
    def _rule_based_remediation(self, alert: dict[str, Any], findings: list[Finding], root_cause: str) -> RemediationOutput:
        actions = []
        alert_name = alert.get("name", "").lower()
        
        if "cpu" in alert_name:
            actions.append(RemediationAction(action="Check CPU usage", category=ActionCategory.OBSERVE, risk_level=RiskLevel.LOW, command="kubectl top pods -n <namespace>", automation_ready=True, requires_approval=False))
        if "memory" in alert_name or "oom" in alert_name:
            actions.append(RemediationAction(action="Check memory and OOM events", category=ActionCategory.OBSERVE, risk_level=RiskLevel.LOW, command="kubectl top pods && kubectl get events --field-selector reason=OOMKilled", automation_ready=True, requires_approval=False))
        if "restart" in alert_name:
            actions.append(RemediationAction(action="Check pod logs", category=ActionCategory.OBSERVE, risk_level=RiskLevel.LOW, command="kubectl logs <pod> --previous", automation_ready=True, requires_approval=False))
            actions.append(RemediationAction(action="Rollback deployment", category=ActionCategory.REMEDIATE, risk_level=RiskLevel.MEDIUM, command="kubectl rollout undo deployment/<name>", rollback="kubectl rollout undo deployment/<name>", requires_approval=True))
        
        if not actions:
            actions.append(RemediationAction(action="Gather diagnostics", category=ActionCategory.OBSERVE, risk_level=RiskLevel.LOW, command="kubectl get pods,events -n <namespace>", automation_ready=True, requires_approval=False))
        
        runbook = [RunbookStep(step=i+1, action=a.action, commands=[a.command] if a.command else [], verification=a.verification) for i, a in enumerate(actions)]
        return RemediationOutput(root_cause_summary=root_cause, recommended_actions=actions, runbook_steps=runbook, confidence=0.5)
    
    def _apply_safety_rules(self, output: RemediationOutput) -> RemediationOutput:
        for action in output.recommended_actions:
            if action.command:
                cmd_lower = action.command.lower()
                if any(op in cmd_lower for op in self.DANGEROUS_OPS):
                    action.risk_level = RiskLevel.HIGH
                    action.requires_approval = True
                    if not action.rollback:
                        action.rollback = "Manual intervention required"
                if any(op in cmd_lower for op in self.SAFE_KUBERNETES_OPS):
                    action.risk_level = RiskLevel.LOW
                    action.requires_approval = False
                    action.automation_ready = True
        return output
    
    def _summarize_findings(self, findings: list[Finding]) -> str:
        if not findings:
            return "No findings available."
        lines = []
        by_severity = {}
        for f in findings:
            by_severity.setdefault(f.severity, []).append(f)
        for sev in ["critical", "high", "medium", "low", "info"]:
            if sev in by_severity:
                lines.append(f"## {sev.upper()}")
                for f in by_severity[sev]:
                    lines.append(f"- [{f.category}] {f.detail}")
        return "\n".join(lines)
    
    def _identify_root_cause(self, findings: list[Finding]) -> str:
        if not findings:
            return "Unknown - no findings available"
        critical = [f for f in findings if f.severity in ("critical", "high") and f.confidence > 0.7]
        if critical:
            return max(critical, key=lambda f: f.confidence).detail
        return findings[0].detail
    
    def _format_service_context(self, kg_context: dict[str, Any]) -> str:
        if not kg_context.get("available"):
            return "No service context available."
        service_info = kg_context.get("service_info", {})
        return f"Service: {service_info.get('resolved_name', 'unknown')}"
    
    def _assess_current_state(self, context: ExecutionContext) -> str:
        sev_counts = {}
        for f in context.previous_findings:
            sev_counts[f.severity] = sev_counts.get(f.severity, 0) + 1
        if sev_counts.get("critical", 0) > 0:
            return "CRITICAL"
        if sev_counts.get("high", 0) > 0:
            return "DEGRADED"
        return "OPERATIONAL"
    
    def _get_constraints(self, team_config: dict[str, Any]) -> str:
        remediation_config = team_config.get("remediation", {})
        constraints = []
        if remediation_config.get("require_approval", True):
            constraints.append("All changes require human approval")
        if remediation_config.get("read_only", False):
            constraints.append("Read-only mode")
        return "\n".join(constraints) if constraints else "Standard safety rules"
    
    def _create_findings_from_plan(self, output: RemediationOutput) -> list[Finding]:
        findings = [self.create_finding(detail=f"Root cause: {output.root_cause_summary}", severity="high", confidence=output.confidence)]
        for action in output.recommended_actions:
            findings.append(self.create_finding(detail=f"Action: {action.action}", evidence=f"Risk: {action.risk_level.value}", severity="info", confidence=0.8))
        if output.escalation.needed:
            findings.append(self.create_finding(detail=f"Escalation: {output.escalation.reason}", severity="high", confidence=0.9))
        return findings
    
    def _parse_remediation_response(self, response: Any, root_cause: str) -> RemediationOutput:
        response_text = str(response.content if hasattr(response, "content") else response)
        try:
            json_text = response_text.split("```json")[1].split("```")[0] if "```json" in response_text else response_text
            data = json.loads(json_text.strip())
            actions = [RemediationAction(
                action=a.get("action", ""), category=ActionCategory(a.get("category", "observe").lower()),
                risk_level=RiskLevel(a.get("risk_level", "low").lower()), command=a.get("command"),
                expected_outcome=a.get("expected_outcome", ""), verification=a.get("verification", ""),
                rollback=a.get("rollback"), automation_ready=a.get("automation_ready", False), requires_approval=a.get("requires_approval", True),
            ) for a in data.get("recommended_actions", [])]
            runbook = [RunbookStep(step=s.get("step", i+1), action=s.get("action", ""), commands=s.get("commands", []), verification=s.get("verification", "")) for i, s in enumerate(data.get("runbook_steps", []))]
            esc = data.get("escalation", {})
            return RemediationOutput(
                root_cause_summary=data.get("root_cause_summary", root_cause), recommended_actions=actions, runbook_steps=runbook,
                escalation=Escalation(needed=esc.get("needed", False), reason=esc.get("reason"), suggested_teams=esc.get("suggested_teams", []), priority=esc.get("severity", "P3")),
                confidence=0.7,
            )
        except Exception:
            return RemediationOutput(root_cause_summary=root_cause, confidence=0.3)
