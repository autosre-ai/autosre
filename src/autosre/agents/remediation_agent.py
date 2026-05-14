"""
Remediation Agent for AutoSRE V2.

Analyzes investigation findings and generates remediation recommendations.
Does NOT execute remediations - provides suggestions for human review.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from autosre.agents.base_agent import AgentResult, AgentStatus, BaseAgent
from autosre.core.alert import AlertSeverity
from autosre.core.investigation import Evidence, EvidenceType, Finding, Investigation
from autosre.core.knowledge_base import KnowledgeBase
from autosre.utils.logging import get_logger

logger = get_logger(__name__)


class RemediationAction(BaseModel):
    """A single remediation action."""

    action_type: str = Field(description="Type: restart, scale, rollback, config_change, etc.")
    description: str = Field(description="What to do")
    command: str | None = Field(default=None, description="Specific command if applicable")
    risk_level: str = Field(description="low, medium, high")
    expected_impact: str = Field(description="Expected effect of this action")
    prerequisites: list[str] = Field(default_factory=list, description="What to verify first")
    rollback_steps: list[str] = Field(default_factory=list, description="How to undo if needed")


class RemediationPlan(BaseModel):
    """Structured remediation plan."""

    root_cause_summary: str = Field(description="Summary of identified root cause")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in diagnosis")
    immediate_actions: list[RemediationAction] = Field(description="Actions to take now")
    follow_up_actions: list[RemediationAction] = Field(description="Actions for later")
    preventive_measures: list[str] = Field(description="How to prevent recurrence")
    requires_human_review: bool = Field(description="Whether human must approve")
    reasoning: str = Field(description="Explanation of the plan")


class RemediationAgent(BaseAgent):
    """
    Remediation agent for generating fix recommendations.

    Responsibilities:
    - Synthesize findings from investigation agents
    - Identify root cause
    - Generate remediation recommendations
    - Assess risk of proposed actions
    - Provide rollback procedures

    NOTE: This agent does NOT execute any changes.
    All recommendations require human review and approval.
    """

    agent_id = "remediation"
    agent_name = "Remediation Agent"
    description = "Generates remediation recommendations based on investigation findings"

    SYSTEM_PROMPT_TEMPLATE = """You are the Remediation Agent for an AI SRE investigation system.

Your role is to:
1. Analyze investigation findings
2. Identify the most likely root cause
3. Generate safe, actionable remediation recommendations
4. Assess risks and provide rollback procedures

## CRITICAL: YOU DO NOT EXECUTE ANY ACTIONS
You only RECOMMEND actions for human review and approval.
All recommendations must be safe, reversible, and well-documented.

## Alert Information
{alert_context}

## Investigation Findings
{findings_context}

## Past Similar Incidents (if any)
{knowledge_context}

## Output Format
Provide your recommendations in this JSON format:
{{
    "root_cause_summary": "Clear explanation of the root cause",
    "confidence": 0.85,
    "immediate_actions": [
        {{
            "action_type": "restart|scale|rollback|config_change|other",
            "description": "What to do",
            "command": "kubectl rollout restart deployment/foo -n bar",
            "risk_level": "low|medium|high",
            "expected_impact": "What will happen",
            "prerequisites": ["Verify X", "Check Y"],
            "rollback_steps": ["If it fails, do Z"]
        }}
    ],
    "follow_up_actions": [...],
    "preventive_measures": ["Add monitoring for X", "Implement circuit breaker"],
    "requires_human_review": true,
    "reasoning": "Why this plan"
}}

## Guidelines
1. Prefer less risky actions (restart > rollback > scale down)
2. Always include rollback procedures
3. Document prerequisites clearly
4. If uncertain, recommend investigation before action
5. Set requires_human_review=true for any data-affecting changes
"""

    def __init__(
        self,
        knowledge_base: KnowledgeBase | None = None,
        **kwargs,
    ):
        """
        Initialize remediation agent.

        Args:
            knowledge_base: Knowledge base for similar incident lookup
            **kwargs: Passed to BaseAgent
        """
        super().__init__(**kwargs)
        self.knowledge_base = knowledge_base

    def get_system_prompt(self, investigation: Investigation) -> str:
        """Generate system prompt with investigation context."""
        alert = investigation.alert
        alert_context = alert.to_prompt_context()

        # Format findings
        findings_lines = []
        for finding in investigation.findings:
            findings_lines.append(f"### {finding.title}")
            findings_lines.append(f"Agent: {finding.agent_id}")
            findings_lines.append(f"Confidence: {finding.confidence:.0%}")
            findings_lines.append(finding.description)
            findings_lines.append("")

        # Add hypothesis conclusions
        for hypothesis in investigation.confirmed_hypotheses:
            findings_lines.append(f"### Confirmed: {hypothesis.description}")
            findings_lines.append(f"Confidence: {hypothesis.confidence:.0%}")
            if hypothesis.reasoning:
                findings_lines.append(f"Evidence: {hypothesis.reasoning}")
            findings_lines.append("")

        findings_context = "\n".join(findings_lines) or "No findings available."

        # Get knowledge context
        knowledge_context = "No similar incidents found."
        if self.knowledge_base:
            similar = self.knowledge_base.get_for_alert(
                alert_name=alert.name,
                service=alert.service,
                limit=3,
            )
            if similar:
                knowledge_context = "\n\n".join(
                    result.entry.to_prompt_context()
                    for result in similar
                )

        return self.SYSTEM_PROMPT_TEMPLATE.format(
            alert_context=alert_context,
            findings_context=findings_context,
            knowledge_context=knowledge_context,
        )

    async def execute(self, investigation: Investigation) -> AgentResult:
        """
        Generate remediation recommendations.

        Args:
            investigation: Completed investigation with findings

        Returns:
            AgentResult with remediation plan
        """
        start_time = datetime.now(timezone.utc)

        logger.info(
            "Generating remediation plan",
            alert_name=investigation.alert.name,
            findings_count=len(investigation.findings),
            confirmed_hypotheses=len(investigation.confirmed_hypotheses),
        )

        try:
            llm = await self._get_llm()

            # Build messages
            system_prompt = self.get_system_prompt(investigation)
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Based on the investigation findings, generate a remediation plan."},
            ]

            # Use structured output
            from autosre.core.llm_client import LLMMessage
            llm_messages = [LLMMessage(**m) for m in messages]

            plan = await llm.complete_structured(
                messages=llm_messages,
                response_model=RemediationPlan,
            )

            # Create evidence for the plan
            plan_evidence = Evidence(
                type=EvidenceType.CUSTOM,
                source="remediation_agent",
                data=plan.model_dump(),
                summary=f"Remediation plan: {len(plan.immediate_actions)} immediate actions",
            )
            investigation.add_evidence(plan_evidence)

            # Create finding
            action_summary = ", ".join(
                a.action_type for a in plan.immediate_actions[:3]
            )
            finding = Finding(
                title="Remediation Recommendations",
                description=plan.root_cause_summary,
                severity=self._assess_severity(plan),
                category="remediation",
                agent_id=self.agent_id,
                evidence_ids=[plan_evidence.id],
                confidence=plan.confidence,
                metadata={
                    "immediate_action_count": len(plan.immediate_actions),
                    "follow_up_action_count": len(plan.follow_up_actions),
                    "requires_human_review": plan.requires_human_review,
                    "action_types": action_summary,
                },
            )

            duration = (datetime.now(timezone.utc) - start_time).total_seconds()

            logger.info(
                "Remediation plan generated",
                immediate_actions=len(plan.immediate_actions),
                confidence=plan.confidence,
                requires_review=plan.requires_human_review,
                duration_seconds=duration,
            )

            return AgentResult(
                agent_id=self.agent_id,
                status=AgentStatus.COMPLETED,
                findings=[finding],
                evidence=[plan_evidence],
                summary=self._format_plan_summary(plan),
                confidence=plan.confidence,
                iterations=1,
                duration_seconds=duration,
                metadata={
                    "plan": plan.model_dump(),
                    "requires_human_review": plan.requires_human_review,
                },
            )

        except Exception as e:
            logger.error("Remediation planning failed", error=str(e))
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()

            return AgentResult(
                agent_id=self.agent_id,
                status=AgentStatus.ERROR,
                summary=f"Failed to generate remediation plan: {e}",
                duration_seconds=duration,
                error=str(e),
            )

    def _assess_severity(self, plan: RemediationPlan) -> AlertSeverity:
        """Assess severity based on remediation plan."""
        # High severity if high-risk actions needed
        if any(a.risk_level == "high" for a in plan.immediate_actions):
            return AlertSeverity.HIGH

        # Medium if moderate confidence or medium-risk actions
        if plan.confidence < 0.7 or any(
            a.risk_level == "medium" for a in plan.immediate_actions
        ):
            return AlertSeverity.MEDIUM

        return AlertSeverity.LOW

    def _format_plan_summary(self, plan: RemediationPlan) -> str:
        """Format remediation plan as readable summary."""
        lines = [
            f"## Root Cause",
            plan.root_cause_summary,
            f"\nConfidence: {plan.confidence:.0%}",
            "",
        ]

        if plan.immediate_actions:
            lines.append("## Immediate Actions")
            for i, action in enumerate(plan.immediate_actions, 1):
                lines.append(f"{i}. [{action.risk_level.upper()}] {action.description}")
                if action.command:
                    lines.append(f"   Command: `{action.command}`")
            lines.append("")

        if plan.follow_up_actions:
            lines.append("## Follow-up Actions")
            for i, action in enumerate(plan.follow_up_actions, 1):
                lines.append(f"{i}. {action.description}")
            lines.append("")

        if plan.preventive_measures:
            lines.append("## Preventive Measures")
            for measure in plan.preventive_measures:
                lines.append(f"- {measure}")
            lines.append("")

        if plan.requires_human_review:
            lines.append("⚠️ **This plan requires human review and approval.**")

        lines.append("")
        lines.append(f"Reasoning: {plan.reasoning}")

        return "\n".join(lines)

    async def quick_recommend(
        self,
        investigation: Investigation,
    ) -> list[RemediationAction]:
        """
        Generate quick recommendations without full plan.

        Useful for urgent incidents where speed matters.

        Args:
            investigation: Investigation context

        Returns:
            List of immediate action recommendations
        """
        # Use heuristics for common patterns
        recommendations = []
        alert = investigation.alert

        # Check for common patterns in findings
        all_findings_text = " ".join(
            f.description.lower() for f in investigation.findings
        )

        # OOM / Memory issues
        if "oom" in all_findings_text or "out of memory" in all_findings_text:
            recommendations.append(RemediationAction(
                action_type="scale",
                description="Increase memory limits for affected pods",
                risk_level="low",
                expected_impact="Pods will restart with higher memory limits",
                prerequisites=["Verify sufficient cluster resources"],
                rollback_steps=["Revert resource limits to previous values"],
            ))

        # High restart count
        if "restart" in all_findings_text and "crash" in all_findings_text:
            recommendations.append(RemediationAction(
                action_type="restart",
                description="Rolling restart of the deployment",
                command=f"kubectl rollout restart deployment/{alert.service} -n {alert.namespace}",
                risk_level="low",
                expected_impact="Pods will restart one by one",
                prerequisites=["Verify deployment has multiple replicas"],
                rollback_steps=["If issues persist, rollback to previous revision"],
            ))

        # Error rate spike
        if "error rate" in all_findings_text or "5xx" in all_findings_text:
            recommendations.append(RemediationAction(
                action_type="scale",
                description="Scale up replicas to handle load",
                command=f"kubectl scale deployment/{alert.service} -n {alert.namespace} --replicas=+2",
                risk_level="low",
                expected_impact="Additional pods will handle traffic",
                prerequisites=["Check if load is the issue (not a code bug)"],
                rollback_steps=["Scale back down after load normalizes"],
            ))

        # Recent deployment
        if "deploy" in all_findings_text or "rollout" in all_findings_text:
            recommendations.append(RemediationAction(
                action_type="rollback",
                description="Rollback to previous deployment",
                command=f"kubectl rollout undo deployment/{alert.service} -n {alert.namespace}",
                risk_level="medium",
                expected_impact="Service will revert to previous version",
                prerequisites=["Verify previous version was stable", "Check if issue correlates with deployment time"],
                rollback_steps=["Re-deploy the new version after fixing issues"],
            ))

        return recommendations
