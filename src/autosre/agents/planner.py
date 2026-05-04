"""Planner agent - generates hypotheses and selects subagents."""

import json
import logging
from typing import List

from .state import InvestigationState, InvestigationPlan, Hypothesis

logger = logging.getLogger(__name__)

PLANNER_SYSTEM = """You are the Planner for an AI SRE investigation system.

Your job is to:
1. Analyze the alert and available context
2. Generate hypotheses about potential root causes
3. Select which investigation agents to dispatch

Available investigation agents:
{available_agents}

Respond with JSON:
{{
    "hypotheses": [
        {{
            "hypothesis": "Description of potential cause",
            "priority": "high|medium|low",
            "agents_to_test": ["agent1", "agent2"],
            "confidence": 0.7
        }}
    ],
    "selected_agents": ["agent1", "agent2"],
    "reasoning": "Brief explanation of your plan"
}}

Be specific and actionable. Focus on the most likely causes first.
"""

AVAILABLE_AGENTS = [
    "kubernetes",  # Pod logs, events, describes
    "metrics",     # Prometheus queries, anomaly detection
    "logs",        # Log search and analysis
    "traces",      # Distributed tracing
    "changes",     # Recent deployments, config changes
]


class Planner:
    """Plans investigation by generating hypotheses and selecting agents."""
    
    def __init__(self, llm_router=None):
        from ..llm import get_router
        self.llm = llm_router or get_router()
    
    async def plan(self, state: InvestigationState) -> InvestigationPlan:
        """Generate investigation plan from current state."""
        
        # Build prompt
        prompt = self._build_prompt(state)
        system = PLANNER_SYSTEM.format(
            available_agents=", ".join(AVAILABLE_AGENTS)
        )
        
        try:
            response = await self.llm.complete(prompt, system=system)
            plan = self._parse_response(response.content)
            
            # Validate selected agents
            plan.selected_agents = [
                a for a in plan.selected_agents 
                if a in AVAILABLE_AGENTS
            ]
            
            # On first iteration, be aggressive - try all relevant agents
            if state.iteration == 0 and len(plan.selected_agents) < 2:
                plan.selected_agents = self._default_agents(state.alert)
            
            logger.info(
                f"[PLANNER] Iteration {state.iteration}: "
                f"{len(plan.hypotheses)} hypotheses, "
                f"agents: {plan.selected_agents}"
            )
            
            return plan
            
        except Exception as e:
            logger.error(f"[PLANNER] Failed: {e}")
            return self._fallback_plan(state)
    
    def _build_prompt(self, state: InvestigationState) -> str:
        """Build prompt for planner."""
        parts = [f"## Alert\n{state.alert.model_dump_json(indent=2)}"]
        
        if state.memory_context:
            parts.append(f"## Past Incidents\n{state.memory_context}")
        
        if state.topology_context:
            parts.append(f"## Service Topology\n{state.topology_context}")
        
        if state.iteration > 0 and state.agent_results:
            parts.append("## Previous Findings")
            for agent_id, result in state.agent_results.items():
                parts.append(f"### {agent_id}\n{result.summary}")
        
        parts.append(f"\nIteration: {state.iteration}/{state.max_iterations}")
        parts.append("Generate hypotheses and select agents to investigate.")
        
        return "\n\n".join(parts)
    
    def _parse_response(self, content: str) -> InvestigationPlan:
        """Parse LLM response into InvestigationPlan."""
        # Extract JSON from response
        try:
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            data = json.loads(content.strip())
            
            hypotheses = [
                Hypothesis(**h) for h in data.get("hypotheses", [])
            ]
            
            return InvestigationPlan(
                hypotheses=hypotheses,
                selected_agents=data.get("selected_agents", []),
                reasoning=data.get("reasoning", ""),
            )
        except Exception as e:
            logger.warning(f"[PLANNER] Parse failed: {e}")
            raise
    
    def _default_agents(self, alert) -> List[str]:
        """Default agent selection based on alert type."""
        # Always include these for any investigation
        return ["kubernetes", "metrics", "logs"]
    
    def _fallback_plan(self, state: InvestigationState) -> InvestigationPlan:
        """Fallback plan when LLM fails."""
        return InvestigationPlan(
            hypotheses=[
                Hypothesis(
                    hypothesis="General investigation - LLM planning failed",
                    priority="high",
                    agents_to_test=["kubernetes", "metrics", "logs"],
                )
            ],
            selected_agents=["kubernetes", "metrics", "logs"],
            reasoning="Fallback plan due to planning error",
        )
