"""Planner agent - generates hypotheses and selects subagents.

Enhanced with Investigation Phases based on Google SRE book learnings:
- TRIAGE phase is MANDATORY first
- Changes subagent always runs early
- Mitigation must be considered before deep investigation
"""

import json
import logging
from enum import Enum
from typing import List, Optional

from .state import InvestigationState, InvestigationPlan, Hypothesis

logger = logging.getLogger(__name__)


class InvestigationPhase(str, Enum):
    """
    Investigation lifecycle phases.
    
    Order matters! You MUST complete each phase before proceeding.
    
    Based on Google SRE book principles:
    - STOP THE BLEEDING FIRST (triage + mitigate before investigate)
    - Don't hunt for root cause while users are suffering
    """
    TRIAGE = "triage"          # MANDATORY FIRST: Assess impact, consider mitigation
    MITIGATE = "mitigate"      # Apply immediate fixes if possible
    INVESTIGATE = "investigate" # Now find root cause
    REMEDIATE = "remediate"    # Apply permanent fix
    VERIFY = "verify"          # Confirm fix worked
    DOCUMENT = "document"      # Post-incident writeup


# CRITICAL: This prompt enforces triage-first policy
TRIAGE_FIRST_PROMPT = """## ⚠️  TRIAGE REQUIRED - DO NOT SKIP

Before investigating root cause, you MUST complete triage:

### Triage Checklist (ALL REQUIRED)
1. ☐ Is the service impaired? (yes/no/unknown)
2. ☐ What is the impact? (users affected, revenue, SLA risk)
3. ☐ Can we mitigate NOW? (rollback, scale, failover, circuit break)

### Available Immediate Mitigations
- rollback_deployment: Revert to last known good
- scale_horizontal: Add more replicas  
- scale_vertical: Increase resource limits
- failover_region: Switch to healthy region
- enable_circuit_breaker: Shed excess load
- disable_feature_flag: Turn off problematic feature
- restart_pods: Rolling restart

### Investigation Policy
❌ DO NOT proceed to root cause investigation until:
   - Impact is assessed
   - Mitigation options are documented (even if skipped)

✅ Once triage complete, investigate with:
   - changes subagent (ALWAYS run first - most incidents are caused by changes)
   - metrics subagent (golden signals)
   - kubernetes subagent
   - logs subagent

### The SRE Golden Rule
"A 2-minute mitigation that restores service is better than 
a 30-minute root cause analysis while users suffer."
"""


PLANNER_SYSTEM = """You are the Planner for an AI SRE investigation system.

Your job is to:
1. FIRST: Complete triage (assess impact, consider mitigation)
2. THEN: Generate hypotheses about potential root causes
3. FINALLY: Select which investigation agents to dispatch

{triage_prompt}

## Available Investigation Agents
{available_agents}

## Key Principles
- STOP THE BLEEDING FIRST
- Changes subagent should run early (most incidents are caused by changes)
- Check the Four Golden Signals (latency, traffic, errors, saturation)
- Use percentiles for latency (never averages)

## Current Phase: {current_phase}

Respond with JSON:
{{
    "triage_complete": true/false,
    "impact_assessment": {{
        "is_impaired": true/false,
        "severity": "critical|high|medium|low",
        "users_affected": "description",
        "mitigation_considered": true/false,
        "recommended_mitigation": "action or null"
    }},
    "hypotheses": [
        {{
            "hypothesis": "Description of potential cause",
            "priority": "high|medium|low",
            "agents_to_test": ["agent1", "agent2"],
            "confidence": 0.7
        }}
    ],
    "selected_agents": ["changes", "metrics", ...],
    "phase": "triage|mitigate|investigate|remediate|verify|document",
    "reasoning": "Brief explanation of your plan"
}}

Be specific and actionable. Focus on the most likely causes first.
"""

# Agents available for investigation
AVAILABLE_AGENTS = [
    "changes",     # Recent deployments, config changes - ALWAYS RUN FIRST
    "kubernetes",  # Pod logs, events, describes
    "metrics",     # Prometheus queries, golden signals
    "logs",        # Log search and analysis
    "traces",      # Distributed tracing
]


class Planner:
    """Plans investigation by generating hypotheses and selecting agents.
    
    Enhanced with:
    - Mandatory triage phase
    - Phase tracking
    - Changes agent prioritization
    """
    
    def __init__(self, llm_router=None):
        from ..llm import get_router
        self.llm = llm_router or get_router()
        self._current_phase = InvestigationPhase.TRIAGE
    
    @property
    def current_phase(self) -> InvestigationPhase:
        return self._current_phase
    
    def advance_phase(self, to_phase: Optional[InvestigationPhase] = None) -> InvestigationPhase:
        """Advance to next phase or specific phase."""
        if to_phase:
            self._current_phase = to_phase
        else:
            # Auto-advance through phases
            phase_order = list(InvestigationPhase)
            current_idx = phase_order.index(self._current_phase)
            if current_idx < len(phase_order) - 1:
                self._current_phase = phase_order[current_idx + 1]
        
        logger.info(f"[PLANNER] Advanced to phase: {self._current_phase}")
        return self._current_phase
    
    async def plan(
        self,
        state: InvestigationState,
        triage_result: Optional[dict] = None,
    ) -> InvestigationPlan:
        """Generate investigation plan from current state.
        
        Args:
            state: Current investigation state
            triage_result: Result from triage node (if completed)
            
        Returns:
            InvestigationPlan with hypotheses and selected agents
        """
        
        # Determine if triage is complete
        triage_complete = triage_result is not None and triage_result.get("mitigation_considered", False)
        
        # Build prompt
        prompt = self._build_prompt(state, triage_result)
        
        # Include triage prompt if not complete
        triage_prompt = TRIAGE_FIRST_PROMPT if not triage_complete else ""
        
        system = PLANNER_SYSTEM.format(
            triage_prompt=triage_prompt,
            available_agents=", ".join(AVAILABLE_AGENTS),
            current_phase=self._current_phase.value,
        )
        
        try:
            response = await self.llm.complete(prompt, system=system)
            plan = self._parse_response(response.content)
            
            # Validate selected agents
            plan.selected_agents = [
                a for a in plan.selected_agents 
                if a in AVAILABLE_AGENTS
            ]
            
            # ALWAYS include changes agent if investigating
            if self._current_phase == InvestigationPhase.INVESTIGATE:
                if "changes" not in plan.selected_agents:
                    plan.selected_agents.insert(0, "changes")
            
            # On first iteration, be aggressive - try all relevant agents
            if state.iteration == 0 and len(plan.selected_agents) < 2:
                plan.selected_agents = self._default_agents(state.alert)
            
            logger.info(
                f"[PLANNER] Phase {self._current_phase.value}, Iteration {state.iteration}: "
                f"{len(plan.hypotheses)} hypotheses, "
                f"agents: {plan.selected_agents}"
            )
            
            return plan
            
        except Exception as e:
            logger.error(f"[PLANNER] Failed: {e}")
            return self._fallback_plan(state)
    
    def _build_prompt(
        self,
        state: InvestigationState,
        triage_result: Optional[dict] = None,
    ) -> str:
        """Build prompt for planner."""
        parts = [f"## Alert\n{state.alert.model_dump_json(indent=2)}"]
        
        if triage_result:
            parts.append(f"## Triage Result\n{json.dumps(triage_result, indent=2, default=str)}")
        
        if state.memory_context:
            parts.append(f"## Past Incidents\n{state.memory_context}")
        
        if state.topology_context:
            parts.append(f"## Service Topology\n{state.topology_context}")
        
        if state.iteration > 0 and state.agent_results:
            parts.append("## Previous Findings")
            for agent_id, result in state.agent_results.items():
                parts.append(f"### {agent_id}\n{result.summary}")
        
        parts.append(f"\nCurrent Phase: {self._current_phase.value}")
        parts.append(f"Iteration: {state.iteration}/{state.max_iterations}")
        
        if self._current_phase == InvestigationPhase.TRIAGE:
            parts.append("\n**ACTION REQUIRED: Complete triage before investigating.**")
        else:
            parts.append("\nGenerate hypotheses and select agents to investigate.")
        
        return "\n\n".join(parts)
    
    def _parse_response(self, content: str) -> InvestigationPlan:
        """Parse LLM response into InvestigationPlan."""
        try:
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            data = json.loads(content.strip())
            
            hypotheses = [
                Hypothesis(**h) for h in data.get("hypotheses", [])
            ]
            
            # Update phase based on response
            if data.get("phase"):
                try:
                    self._current_phase = InvestigationPhase(data["phase"])
                except ValueError:
                    pass
            
            return InvestigationPlan(
                hypotheses=hypotheses,
                selected_agents=data.get("selected_agents", []),
                reasoning=data.get("reasoning", ""),
            )
        except Exception as e:
            logger.warning(f"[PLANNER] Parse failed: {e}")
            raise
    
    def _default_agents(self, alert) -> List[str]:
        """Default agent selection based on alert type.
        
        ALWAYS includes changes agent first.
        """
        # Changes agent FIRST - most incidents are caused by changes
        return ["changes", "kubernetes", "metrics", "logs"]
    
    def _fallback_plan(self, state: InvestigationState) -> InvestigationPlan:
        """Fallback plan when LLM fails."""
        return InvestigationPlan(
            hypotheses=[
                Hypothesis(
                    hypothesis="General investigation - LLM planning failed",
                    priority="high",
                    agents_to_test=["changes", "kubernetes", "metrics", "logs"],
                )
            ],
            selected_agents=["changes", "kubernetes", "metrics", "logs"],
            reasoning="Fallback plan due to planning error",
        )


def create_planner(llm_router=None) -> Planner:
    """Factory function to create a Planner."""
    return Planner(llm_router=llm_router)


def require_triage_complete(
    triage_result: Optional[dict],
    current_phase: InvestigationPhase,
) -> None:
    """
    Enforcement function - raises if trying to investigate without triage.
    
    Call this before starting investigation phase.
    
    Raises:
        RuntimeError: If triage not complete
    """
    if current_phase == InvestigationPhase.INVESTIGATE:
        if triage_result is None:
            raise RuntimeError(
                "Cannot start investigation: Triage phase not complete. "
                "Run triage first to assess impact and consider mitigation."
            )
        if not triage_result.get("mitigation_considered", False):
            raise RuntimeError(
                "Cannot start investigation: Mitigation not considered. "
                "You must document mitigation options (even if you choose to skip them) "
                "before investigating root cause."
            )
