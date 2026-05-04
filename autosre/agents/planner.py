"""
Planner Agent — Generates hypotheses and selects subagents.

Based on OpenSRE's nodes/planner.py but simplified.
Uses LLM to analyze alert and context, then outputs an investigation plan.
"""

import logging
from typing import Any, Optional

from pydantic import BaseModel, Field

from ..llm import BaseLLMClient, get_llm_client
from .state import (
    Hypothesis,
    InvestigationPlan,
    InvestigationState,
    Priority,
)

logger = logging.getLogger(__name__)


# Default available subagents
DEFAULT_SUBAGENTS = ["kubernetes", "metrics", "logs", "traces", "changes"]


PLANNER_SYSTEM_PROMPT = """You are the Planner agent for an AI SRE investigation system.

Your role is to:
1. Analyze the alert and available context (memory, topology)
2. Generate hypotheses about potential root causes
3. Select which investigation subagents to dispatch

Available investigation subagents:
{available_agents}

Each subagent specializes in:
- **kubernetes**: Pod logs, describe resources, events, exec commands
- **metrics**: Prometheus queries, anomaly detection, resource usage
- **logs**: Log search, grep patterns, tail logs
- **traces**: Distributed tracing, latency analysis
- **changes**: Recent deployments, config changes, git history

On the first iteration, dispatch ALL relevant agents to gather broad evidence.
On subsequent iterations, focus on agents that can fill identified gaps.

Respond with valid JSON matching this schema:
{schema}"""


class PlannerOutput(BaseModel):
    """Structured output from planner."""
    
    hypotheses: list[dict[str, Any]] = Field(
        description="List of hypotheses with hypothesis, priority (high/medium/low), and agents_to_test"
    )
    selected_agents: list[str] = Field(
        description="Agents to dispatch for this iteration"
    )
    reasoning: str = Field(
        description="Brief explanation of investigation strategy"
    )


async def run_planner(
    state: InvestigationState,
    available_agents: Optional[list[str]] = None,
    llm_client: Optional[BaseLLMClient] = None,
) -> InvestigationPlan:
    """Generate investigation plan from current state.
    
    Args:
        state: Current investigation state.
        available_agents: List of available subagent IDs.
        llm_client: LLM client to use (uses default if None).
        
    Returns:
        Investigation plan with hypotheses and selected agents.
    """
    if llm_client is None:
        llm_client = get_llm_client()
    
    if available_agents is None:
        available_agents = DEFAULT_SUBAGENTS
    
    # Build system prompt
    schema_json = PlannerOutput.model_json_schema()
    import json
    system = PLANNER_SYSTEM_PROMPT.format(
        available_agents=", ".join(available_agents),
        schema=json.dumps(schema_json, indent=2),
    )
    
    # Build user prompt with context
    prompt_parts = []
    
    # Alert info
    prompt_parts.append(f"## Alert\n```json\n{json.dumps(state.alert, indent=2)}\n```")
    
    # Memory context
    if state.memory_context.get("has_similar_episodes"):
        prompt_parts.append(f"\n## Memory Context\n{state.memory_context.get('enhanced_prompt', '')}")
    
    # Topology context
    if state.topology_context.get("available"):
        topo_lines = [
            f"\n## Service Topology",
            f"- Service: {state.topology_context.get('service', 'unknown')}",
            f"- Tier: {state.topology_context.get('tier', 'unknown')}",
        ]
        deps = state.topology_context.get('dependencies', [])
        if deps:
            topo_lines.append(f"- Dependencies: {', '.join(deps)}")
        dependents = state.topology_context.get('dependents', [])
        if dependents:
            topo_lines.append(f"- Dependents (blast radius): {', '.join(dependents[:5])}")
        prompt_parts.append("\n".join(topo_lines))
    
    # Previous iteration feedback
    if state.iteration > 0 and state.messages:
        prompt_parts.append(f"\n## Iteration {state.iteration} — Previous Feedback")
        for msg in state.messages[-3:]:
            prompt_parts.append(f"\n[{msg.get('role', 'system')}]: {msg.get('content', '')}")
    
    # Current hypotheses
    if state.hypotheses:
        prompt_parts.append("\n## Current Hypotheses")
        for h in state.hypotheses:
            prompt_parts.append(h.to_prompt())
    
    prompt_parts.append(f"\n---\nIteration: {state.iteration}. Generate hypotheses and select agents to investigate.")
    
    prompt = "\n".join(prompt_parts)
    
    try:
        # Get structured output from LLM
        output = await llm_client.complete_structured(
            prompt=prompt,
            output_type=PlannerOutput,
            system=system,
            max_tokens=2000,
            temperature=0.3,
        )
        
        # Convert to typed hypotheses
        hypotheses = []
        for h_data in output.hypotheses:
            priority_str = h_data.get("priority", "medium").lower()
            priority = Priority.HIGH if priority_str == "high" else Priority.LOW if priority_str == "low" else Priority.MEDIUM
            
            hypotheses.append(Hypothesis(
                hypothesis=h_data.get("hypothesis", ""),
                priority=priority,
                agents_to_test=h_data.get("agents_to_test", []),
            ))
        
        # Filter selected agents to only available ones
        selected = [a for a in output.selected_agents if a in available_agents]
        
        # On first iteration, always dispatch all available agents
        if state.iteration == 0:
            selected = available_agents
        
        # Ensure at least one agent selected
        if not selected:
            selected = available_agents[:3]
        
        plan = InvestigationPlan(
            hypotheses=hypotheses,
            selected_agents=selected,
            reasoning=output.reasoning,
        )
        
        logger.info(
            f"[PLANNER] Iteration {state.iteration}: "
            f"{len(hypotheses)} hypotheses, dispatching {len(selected)} agents: {selected}"
        )
        
        return plan
        
    except Exception as e:
        logger.error(f"[PLANNER] LLM call failed: {e}")
        
        # Fallback plan
        return InvestigationPlan(
            hypotheses=[
                Hypothesis(
                    hypothesis=f"Investigate {state.alert.get('name', 'alert')}",
                    priority=Priority.HIGH,
                    agents_to_test=available_agents,
                )
            ],
            selected_agents=available_agents,
            reasoning=f"Fallback plan due to error: {e}",
        )


def apply_plan_to_state(state: InvestigationState, plan: InvestigationPlan) -> None:
    """Apply a plan to the investigation state (mutates state)."""
    state.hypotheses = plan.hypotheses
    state.selected_agents = plan.selected_agents
    state.add_message("planner", f"Iteration {state.iteration}: {plan.reasoning}")
