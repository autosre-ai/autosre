"""
Triage Node — Mandatory first phase before investigation.

Based on Google SRE book principle: "STOP THE BLEEDING FIRST"

This node enforces:
1. Is the service impaired? (impact assessment)
2. What is the impact? (user/business impact)
3. Can we mitigate NOW? (immediate actions before root cause)

Investigation CANNOT proceed until triage is complete.
"""

import logging
from datetime import datetime, UTC, timezone
from enum import Enum
from typing import Any, Optional, Protocol

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class TriageStatus(str, Enum):
    """Triage lifecycle status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    MITIGATION_REQUIRED = "mitigation_required"
    MITIGATION_IN_PROGRESS = "mitigation_in_progress"
    MITIGATION_APPLIED = "mitigation_applied"
    MITIGATION_SKIPPED = "mitigation_skipped"
    COMPLETED = "completed"
    FAILED = "failed"


class ImpactSeverity(str, Enum):
    """Impact severity levels."""
    CRITICAL = "critical"     # Complete outage, all users affected
    HIGH = "high"             # Major degradation, many users affected
    MEDIUM = "medium"         # Partial degradation, some users affected
    LOW = "low"               # Minor issue, few users affected
    UNKNOWN = "unknown"       # Impact not yet determined


class MitigationOption(BaseModel):
    """A potential mitigation action."""
    action: str
    description: str
    estimated_impact: str
    risk_level: str = "low"  # low, medium, high
    requires_approval: bool = False
    automated: bool = False
    command: Optional[str] = None


class ImpactAssessment(BaseModel):
    """Assessment of incident impact."""
    severity: ImpactSeverity = ImpactSeverity.UNKNOWN
    users_affected: Optional[str] = None  # "all", "50%", "region:us-east", etc.
    revenue_impact: Optional[str] = None
    sla_violation: bool = False
    data_loss_risk: bool = False
    cascading_risk: bool = False  # Could this impact other services?
    description: str = ""


class TriageResult(BaseModel):
    """Result of the triage phase."""
    status: TriageStatus
    
    # Impact assessment
    is_service_impaired: bool
    impact: ImpactAssessment
    
    # Mitigation
    mitigation_considered: bool = False
    mitigation_options: list[MitigationOption] = Field(default_factory=list)
    mitigation_applied: Optional[MitigationOption] = None
    mitigation_skipped_reason: Optional[str] = None
    
    # Timing metrics (SRE book: track time-to-mitigation vs time-to-root-cause)
    triage_started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    triage_completed_at: Optional[datetime] = None
    mitigation_started_at: Optional[datetime] = None
    mitigation_completed_at: Optional[datetime] = None
    
    # Summary for investigation phase
    summary: str = ""
    recommended_focus_areas: list[str] = Field(default_factory=list)
    
    @property
    def time_to_triage_seconds(self) -> Optional[float]:
        """Time from triage start to completion."""
        if self.triage_completed_at and self.triage_started_at:
            return (self.triage_completed_at - self.triage_started_at).total_seconds()
        return None
    
    @property
    def time_to_mitigation_seconds(self) -> Optional[float]:
        """Time from triage start to mitigation applied."""
        if self.mitigation_completed_at and self.triage_started_at:
            return (self.mitigation_completed_at - self.triage_started_at).total_seconds()
        return None
    
    def can_proceed_to_investigation(self) -> bool:
        """Check if investigation phase can begin."""
        # Must have completed triage
        if self.status not in (
            TriageStatus.COMPLETED,
            TriageStatus.MITIGATION_APPLIED,
            TriageStatus.MITIGATION_SKIPPED,
        ):
            return False
        
        # Must have considered mitigation
        if not self.mitigation_considered:
            return False
        
        return True


class LLMProtocol(Protocol):
    """Protocol for LLM clients."""
    
    async def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        **kwargs: Any,
    ) -> Any:
        ...


TRIAGE_SYSTEM_PROMPT = """You are the TRIAGE agent for an AI SRE investigation system.

## YOUR CRITICAL RESPONSIBILITY
You are the FIRST responder. Your job is NOT to find root cause - it's to:
1. ASSESS: Is the service impaired? What's the impact?
2. MITIGATE: Can we STOP THE BLEEDING before investigating?

## The SRE Golden Rule
"The first priority is to RESTORE SERVICE, not to find root cause."

## Triage Questions (MUST ANSWER ALL)
1. **Is the service impaired?** 
   - Users experiencing errors/latency?
   - Partial or complete outage?
   
2. **What is the impact?**
   - How many users affected?
   - Revenue impact?
   - SLA violation risk?
   - Data loss risk?
   
3. **Can we mitigate NOW?**
   - Rollback recent deployment?
   - Scale up resources?
   - Failover to healthy region?
   - Rate limit or circuit break?
   - Feature flag disable?

## Available Mitigation Actions
Based on the incident type, suggest from:
- rollback_deployment: Revert to last known good
- scale_horizontal: Add more replicas
- scale_vertical: Increase resource limits
- failover_region: Switch traffic to healthy region
- enable_circuit_breaker: Shed load to protect system
- disable_feature_flag: Turn off problematic feature
- rate_limit: Reduce traffic to degraded service
- restart_pods: Rolling restart
- drain_node: Move workloads off bad node

## Response Format (JSON)
{{
    "is_service_impaired": true/false,
    "impact": {{
        "severity": "critical|high|medium|low|unknown",
        "users_affected": "description of user impact",
        "sla_violation": true/false,
        "data_loss_risk": true/false,
        "description": "summary of impact"
    }},
    "mitigation_options": [
        {{
            "action": "action_name",
            "description": "what this does",
            "estimated_impact": "expected outcome",
            "risk_level": "low|medium|high",
            "requires_approval": true/false
        }}
    ],
    "recommended_immediate_action": "action_name or null",
    "recommended_focus_areas": ["area1", "area2"],
    "reasoning": "brief explanation"
}}

REMEMBER: A successful triage that mitigates impact in 2 minutes is better than
a perfect root cause analysis that takes 30 minutes while users suffer.
"""


TRIAGE_PROMPT_TEMPLATE = """## Incident Alert
{alert_json}

## Service Information
{service_context}

## Current Golden Signals
{golden_signals}

## Recent Changes (last 24h)
{recent_changes}

---

Perform triage assessment. Answer:
1. Is the service impaired?
2. What is the impact?
3. Can we mitigate NOW? What options do we have?

Respond with JSON."""


class TriageNode:
    """
    Triage Node — First phase of any investigation.
    
    Enforces SRE best practice: STOP THE BLEEDING FIRST.
    
    This node:
    1. Assesses service impairment and impact
    2. Generates mitigation options
    3. Blocks investigation until mitigation is considered
    4. Tracks time-to-mitigation metrics
    
    Usage:
        triage = TriageNode(llm_client=llm)
        result = await triage.run(alert, context)
        
        if not result.can_proceed_to_investigation():
            # Handle mitigation first
            await apply_mitigation(result.mitigation_options[0])
            result = await triage.mark_mitigation_applied(result, option)
    """
    
    def __init__(
        self,
        llm_client: Optional[LLMProtocol] = None,
        golden_signals_skill: Optional[Any] = None,
        changes_subagent: Optional[Any] = None,
        auto_approve_low_risk: bool = False,
    ):
        """
        Initialize triage node.
        
        Args:
            llm_client: LLM for assessment
            golden_signals_skill: Skill to check golden signals
            changes_subagent: Subagent to check recent changes
            auto_approve_low_risk: Auto-apply low-risk mitigations
        """
        self.llm = llm_client
        self.golden_signals = golden_signals_skill
        self.changes_agent = changes_subagent
        self.auto_approve_low_risk = auto_approve_low_risk
    
    async def run(
        self,
        alert: dict[str, Any],
        service_context: Optional[dict[str, Any]] = None,
        existing_golden_signals: Optional[dict[str, Any]] = None,
        existing_changes: Optional[list[dict[str, Any]]] = None,
    ) -> TriageResult:
        """
        Run triage phase for an incident.
        
        Args:
            alert: The incoming alert
            service_context: Service topology/config info
            existing_golden_signals: Pre-fetched golden signals (skip fetch)
            existing_changes: Pre-fetched recent changes (skip fetch)
            
        Returns:
            TriageResult with assessment and mitigation options
        """
        start_time = datetime.now(UTC)
        logger.info(f"[TRIAGE] Starting triage for alert: {alert.get('name', 'unknown')}")
        
        try:
            # Gather context in parallel
            golden_signals_str = ""
            changes_str = ""
            
            if existing_golden_signals:
                golden_signals_str = self._format_golden_signals(existing_golden_signals)
            elif self.golden_signals:
                try:
                    service = alert.get("service") or alert.get("labels", {}).get("service")
                    if service:
                        gs_result = await self.golden_signals.check_all_signals(service)
                        golden_signals_str = self._format_golden_signals(gs_result)
                except Exception as e:
                    logger.warning(f"[TRIAGE] Failed to fetch golden signals: {e}")
                    golden_signals_str = "Unable to fetch golden signals"
            else:
                golden_signals_str = "Golden signals skill not configured"
            
            if existing_changes:
                changes_str = self._format_changes(existing_changes)
            elif self.changes_agent:
                try:
                    changes_result = await self.changes_agent.get_recent_changes(
                        service=alert.get("service"),
                        hours=24,
                    )
                    changes_str = self._format_changes(changes_result)
                except Exception as e:
                    logger.warning(f"[TRIAGE] Failed to fetch recent changes: {e}")
                    changes_str = "Unable to fetch recent changes"
            else:
                changes_str = "Changes subagent not configured"
            
            # Build prompt
            import json
            prompt = TRIAGE_PROMPT_TEMPLATE.format(
                alert_json=json.dumps(alert, indent=2, default=str),
                service_context=json.dumps(service_context or {}, indent=2, default=str),
                golden_signals=golden_signals_str,
                recent_changes=changes_str,
            )
            
            # Get LLM assessment
            if self.llm:
                response = await self.llm.complete(
                    prompt,
                    system=TRIAGE_SYSTEM_PROMPT,
                    temperature=0.1,
                )
                assessment = self._parse_response(response.content)
            else:
                # Fallback to heuristic assessment
                assessment = self._heuristic_assessment(alert)
            
            # Build result
            result = TriageResult(
                status=TriageStatus.COMPLETED,
                is_service_impaired=assessment.get("is_service_impaired", True),
                impact=ImpactAssessment(
                    severity=ImpactSeverity(assessment.get("impact", {}).get("severity", "unknown")),
                    users_affected=assessment.get("impact", {}).get("users_affected"),
                    sla_violation=assessment.get("impact", {}).get("sla_violation", False),
                    data_loss_risk=assessment.get("impact", {}).get("data_loss_risk", False),
                    description=assessment.get("impact", {}).get("description", ""),
                ),
                mitigation_considered=True,
                mitigation_options=[
                    MitigationOption(**opt)
                    for opt in assessment.get("mitigation_options", [])
                ],
                triage_started_at=start_time,
                triage_completed_at=datetime.now(UTC),
                summary=assessment.get("reasoning", ""),
                recommended_focus_areas=assessment.get("recommended_focus_areas", []),
            )
            
            # If high-severity with mitigation options, mark as requiring mitigation
            if (
                result.impact.severity in (ImpactSeverity.CRITICAL, ImpactSeverity.HIGH)
                and result.mitigation_options
            ):
                result.status = TriageStatus.MITIGATION_REQUIRED
            
            logger.info(
                f"[TRIAGE] Completed: impaired={result.is_service_impaired}, "
                f"severity={result.impact.severity}, "
                f"mitigation_options={len(result.mitigation_options)}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"[TRIAGE] Failed: {e}")
            return TriageResult(
                status=TriageStatus.FAILED,
                is_service_impaired=True,  # Assume worst case
                impact=ImpactAssessment(
                    severity=ImpactSeverity.UNKNOWN,
                    description=f"Triage failed: {e}",
                ),
                mitigation_considered=False,
                triage_started_at=start_time,
                summary=f"Triage failed with error: {e}",
            )
    
    def mark_mitigation_applied(
        self,
        result: TriageResult,
        option: MitigationOption,
    ) -> TriageResult:
        """Mark a mitigation as applied."""
        result.mitigation_applied = option
        result.mitigation_completed_at = datetime.now(UTC)
        result.status = TriageStatus.MITIGATION_APPLIED
        
        logger.info(
            f"[TRIAGE] Mitigation applied: {option.action}, "
            f"time_to_mitigation={result.time_to_mitigation_seconds:.2f}s"
        )
        
        return result
    
    def skip_mitigation(
        self,
        result: TriageResult,
        reason: str,
    ) -> TriageResult:
        """Skip mitigation with documented reason."""
        result.mitigation_skipped_reason = reason
        result.status = TriageStatus.MITIGATION_SKIPPED
        
        logger.info(f"[TRIAGE] Mitigation skipped: {reason}")
        
        return result
    
    def _parse_response(self, content: str) -> dict[str, Any]:
        """Parse LLM response."""
        import json
        
        try:
            # Extract JSON from response
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            return json.loads(content.strip())
        except Exception as e:
            logger.warning(f"[TRIAGE] Failed to parse LLM response: {e}")
            return {}
    
    def _heuristic_assessment(self, alert: dict[str, Any]) -> dict[str, Any]:
        """Fallback heuristic when LLM unavailable."""
        severity = alert.get("severity", "warning")
        
        severity_map = {
            "critical": ImpactSeverity.CRITICAL,
            "high": ImpactSeverity.HIGH,
            "warning": ImpactSeverity.MEDIUM,
            "info": ImpactSeverity.LOW,
        }
        
        return {
            "is_service_impaired": severity in ("critical", "high", "warning"),
            "impact": {
                "severity": severity_map.get(severity, ImpactSeverity.UNKNOWN).value,
                "users_affected": "unknown",
                "sla_violation": severity == "critical",
                "data_loss_risk": False,
                "description": f"Alert severity: {severity}",
            },
            "mitigation_options": [
                {
                    "action": "restart_pods",
                    "description": "Rolling restart of affected pods",
                    "estimated_impact": "May temporarily increase latency",
                    "risk_level": "low",
                    "requires_approval": False,
                },
            ] if severity in ("critical", "high") else [],
            "recommended_focus_areas": ["logs", "metrics", "recent_changes"],
            "reasoning": "Heuristic assessment based on alert severity",
        }
    
    def _format_golden_signals(self, signals: dict[str, Any]) -> str:
        """Format golden signals for prompt."""
        lines = []
        for signal, data in signals.items():
            if isinstance(data, dict):
                value = data.get("value", data.get("current", "N/A"))
                status = data.get("status", "unknown")
                lines.append(f"- {signal}: {value} ({status})")
            else:
                lines.append(f"- {signal}: {data}")
        return "\n".join(lines) if lines else "No golden signals data"
    
    def _format_changes(self, changes: list[dict[str, Any]]) -> str:
        """Format recent changes for prompt."""
        if not changes:
            return "No recent changes found"
        
        lines = []
        for change in changes[:10]:  # Limit to 10 most recent
            change_type = change.get("type", "unknown")
            timestamp = change.get("timestamp", "unknown")
            description = change.get("description", change.get("message", ""))
            lines.append(f"- [{change_type}] {timestamp}: {description[:100]}")
        
        return "\n".join(lines)


# Utility functions for integration

def create_triage_node(
    llm_client: Optional[Any] = None,
    golden_signals_skill: Optional[Any] = None,
    changes_subagent: Optional[Any] = None,
) -> TriageNode:
    """Factory function to create a TriageNode."""
    return TriageNode(
        llm_client=llm_client,
        golden_signals_skill=golden_signals_skill,
        changes_subagent=changes_subagent,
    )


def block_investigation_without_triage(triage_result: Optional[TriageResult]) -> None:
    """
    Guard function to enforce triage-first policy.
    
    Raises:
        RuntimeError: If triage not completed or mitigation not considered
    """
    if triage_result is None:
        raise RuntimeError(
            "Investigation blocked: Triage phase must run first. "
            "SRE principle: STOP THE BLEEDING FIRST."
        )
    
    if not triage_result.can_proceed_to_investigation():
        raise RuntimeError(
            f"Investigation blocked: Triage not complete. "
            f"Status: {triage_result.status}, "
            f"Mitigation considered: {triage_result.mitigation_considered}. "
            "Complete triage and consider mitigation before investigating root cause."
        )
