"""
Triage Agent for AutoSRE V2.

Performs initial alert classification, severity assessment, and
hypothesis generation for incident investigation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from autosre.agents.base_agent import AgentResult, AgentStatus, BaseAgent
from autosre.core.alert import Alert, AlertSeverity
from autosre.core.investigation import (
    Evidence,
    EvidenceType,
    Finding,
    Hypothesis,
    HypothesisPriority,
    Investigation,
)
from autosre.core.knowledge_base import KnowledgeBase
from autosre.utils.logging import get_logger

logger = get_logger(__name__)


class TriageResult(BaseModel):
    """Structured output from triage analysis."""

    alert_category: str = Field(description="Category: latency, errors, resources, availability, etc.")
    severity_assessment: str = Field(description="Assessed severity: critical, high, medium, low")
    affected_components: list[str] = Field(description="List of affected services/components")
    hypotheses: list[dict[str, Any]] = Field(description="Initial hypotheses with priority and agents")
    recommended_agents: list[str] = Field(description="Agents to involve: kubernetes, metrics, logs, traces")
    urgency_score: float = Field(ge=0.0, le=1.0, description="Urgency score 0-1")
    summary: str = Field(description="Brief triage summary")


class TriageAgent(BaseAgent):
    """
    Triage agent for initial alert assessment.

    Responsibilities:
    - Classify alert type and category
    - Assess true severity
    - Generate initial hypotheses
    - Recommend investigation agents
    - Gather initial context
    """

    agent_id = "triage"
    agent_name = "Triage Agent"
    description = "Performs initial alert classification and hypothesis generation"

    SYSTEM_PROMPT_TEMPLATE = """You are the Triage Agent for an AI SRE investigation system.

Your role is to:
1. Analyze incoming alerts and classify them
2. Assess the true severity and urgency
3. Generate hypotheses about potential root causes
4. Recommend which investigation agents to involve

## Alert Information
{alert_context}

## Past Similar Incidents (if any)
{knowledge_context}

## Available Investigation Agents
- kubernetes: Kubernetes cluster, pods, deployments, events
- metrics: Prometheus metrics, error rates, latency, resource usage
- logs: Log analysis, error patterns, stack traces
- traces: Distributed tracing, service dependencies

## Output Format
Respond with your analysis in the following JSON format:
{{
    "alert_category": "latency|errors|resources|availability|connectivity|other",
    "severity_assessment": "critical|high|medium|low",
    "affected_components": ["service1", "component2"],
    "hypotheses": [
        {{
            "description": "What might be causing this",
            "priority": "high|medium|low",
            "agents_to_test": ["kubernetes", "metrics"],
            "reasoning": "Why this hypothesis"
        }}
    ],
    "recommended_agents": ["kubernetes", "metrics", "logs"],
    "urgency_score": 0.8,
    "summary": "Brief triage summary"
}}

Focus on:
- Accurate categorization based on alert name and labels
- Realistic severity assessment (don't over-escalate)
- Specific, testable hypotheses
- Efficient agent selection (start narrow, expand if needed)
"""

    def __init__(
        self,
        knowledge_base: KnowledgeBase | None = None,
        **kwargs,
    ):
        """
        Initialize triage agent.

        Args:
            knowledge_base: Knowledge base for similar incident lookup
            **kwargs: Passed to BaseAgent
        """
        super().__init__(**kwargs)
        self.knowledge_base = knowledge_base

    def get_system_prompt(self, investigation: Investigation) -> str:
        """Generate system prompt with alert context."""
        alert = investigation.alert
        alert_context = alert.to_prompt_context()

        # Get knowledge context if available
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
            knowledge_context=knowledge_context,
        )

    async def execute(self, investigation: Investigation) -> AgentResult:
        """
        Execute triage analysis.

        Args:
            investigation: Investigation to triage

        Returns:
            AgentResult with hypotheses and recommendations
        """
        start_time = datetime.now(timezone.utc)

        logger.info(
            "Starting triage",
            alert_name=investigation.alert.name,
            alert_severity=investigation.alert.severity.value,
        )

        try:
            llm = await self._get_llm()

            # Build messages
            system_prompt = self.get_system_prompt(investigation)
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Analyze this alert and provide your triage assessment."},
            ]

            # Use structured output
            from autosre.core.llm_client import LLMMessage
            llm_messages = [LLMMessage(**m) for m in messages]

            result = await llm.complete_structured(
                messages=llm_messages,
                response_model=TriageResult,
            )

            # Convert to hypotheses
            hypotheses = []
            for h in result.hypotheses:
                hypotheses.append(Hypothesis(
                    description=h.get("description", ""),
                    priority=HypothesisPriority(h.get("priority", "medium")),
                    agents_to_test=h.get("agents_to_test", []),
                    test_plan=h.get("reasoning"),
                    created_by=self.agent_id,
                ))

            # Add hypotheses to investigation
            for h in hypotheses:
                investigation.add_hypothesis(h)

            # Create evidence from triage
            triage_evidence = Evidence(
                type=EvidenceType.CUSTOM,
                source="triage_agent",
                data=result.model_dump(),
                summary=f"Triage assessment: {result.alert_category}, urgency {result.urgency_score:.1f}",
            )
            investigation.add_evidence(triage_evidence)

            # Create finding
            finding = Finding(
                title="Triage Assessment",
                description=result.summary,
                severity=AlertSeverity.from_string(result.severity_assessment),
                category=result.alert_category,
                agent_id=self.agent_id,
                evidence_ids=[triage_evidence.id],
                confidence=result.urgency_score,
            )

            duration = (datetime.now(timezone.utc) - start_time).total_seconds()

            logger.info(
                "Triage complete",
                category=result.alert_category,
                hypothesis_count=len(hypotheses),
                recommended_agents=result.recommended_agents,
                duration_seconds=duration,
            )

            return AgentResult(
                agent_id=self.agent_id,
                status=AgentStatus.COMPLETED,
                findings=[finding],
                evidence=[triage_evidence],
                summary=result.summary,
                confidence=result.urgency_score,
                iterations=1,
                duration_seconds=duration,
                metadata={
                    "alert_category": result.alert_category,
                    "severity_assessment": result.severity_assessment,
                    "recommended_agents": result.recommended_agents,
                    "hypothesis_count": len(hypotheses),
                },
            )

        except Exception as e:
            logger.error("Triage failed", error=str(e))
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()

            # Create fallback hypotheses
            investigation.add_hypothesis(Hypothesis(
                description=f"Investigate {investigation.alert.name} alert",
                priority=HypothesisPriority.HIGH,
                agents_to_test=["kubernetes", "metrics", "logs"],
                created_by=self.agent_id,
            ))

            return AgentResult(
                agent_id=self.agent_id,
                status=AgentStatus.ERROR,
                summary=f"Triage failed: {e}. Using fallback investigation plan.",
                duration_seconds=duration,
                error=str(e),
                metadata={
                    "recommended_agents": ["kubernetes", "metrics", "logs"],
                },
            )

    async def quick_classify(self, alert: Alert) -> dict[str, Any]:
        """
        Quick alert classification without full triage.

        Useful for routing or filtering.

        Args:
            alert: Alert to classify

        Returns:
            Classification dict with category and priority
        """
        # Use heuristics for quick classification
        name_lower = alert.name.lower()
        desc_lower = alert.description.lower()

        # Category detection
        category = "other"
        if any(w in name_lower for w in ["latency", "slow", "duration", "response_time"]):
            category = "latency"
        elif any(w in name_lower for w in ["error", "5xx", "failure", "exception"]):
            category = "errors"
        elif any(w in name_lower for w in ["cpu", "memory", "disk", "resource"]):
            category = "resources"
        elif any(w in name_lower for w in ["down", "unavailable", "unhealthy"]):
            category = "availability"
        elif any(w in name_lower for w in ["network", "connection", "timeout"]):
            category = "connectivity"

        # Priority based on severity and category
        priority = "medium"
        if alert.severity in (AlertSeverity.CRITICAL, AlertSeverity.HIGH):
            priority = "high"
        elif alert.severity == AlertSeverity.LOW:
            priority = "low"

        # Boost priority for availability issues
        if category == "availability" and priority != "high":
            priority = "high"

        return {
            "category": category,
            "priority": priority,
            "severity": alert.severity.value,
            "recommended_agents": self._get_default_agents(category),
        }

    def _get_default_agents(self, category: str) -> list[str]:
        """Get default agents for a category."""
        agents_by_category = {
            "latency": ["metrics", "traces", "logs"],
            "errors": ["logs", "metrics", "kubernetes"],
            "resources": ["metrics", "kubernetes"],
            "availability": ["kubernetes", "metrics", "logs"],
            "connectivity": ["kubernetes", "logs", "traces"],
            "other": ["kubernetes", "metrics", "logs"],
        }
        return agents_by_category.get(category, ["kubernetes", "metrics", "logs"])
