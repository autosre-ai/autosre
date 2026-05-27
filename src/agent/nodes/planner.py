"""
Planner Node

LLM-driven hypothesis generation and agent selection.
Analyzes the alert and context to generate investigation hypotheses
and select which subagents should investigate.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from ..config import (
    AgentConfig,
    build_llm,
    build_model_config,
    build_prompt_config,
    get_available_subagents,
    TeamConfig,
)
from ..state import InvestigationPlan

logger = logging.getLogger(__name__)


PLANNER_SYSTEM_PROMPT = """You are the Planner agent for an AI SRE system. Your role is to:
1. Analyze the alert and available context (memory, knowledge graph)
2. Generate hypotheses about potential root causes
3. Select which investigation subagents to dispatch

You have access to these investigation subagents:
{available_agents}

Respond with a JSON object:
{{
    "hypotheses": [
        {{
            "hypothesis": "Description of potential root cause",
            "priority": "high|medium|low",
            "agents_to_test": ["agent_name_1", "agent_name_2"]
        }}
    ],
    "selected_agents": ["agent_name_1", "agent_name_2", ...],
    "reasoning": "Brief explanation of your investigation plan"
}}

IMPORTANT:
- selected_agents must be a subset of the available agents listed above
- Only select agents that are relevant to testing your hypotheses
- Generate 2-4 hypotheses covering different potential root causes
- Prioritize high-severity hypotheses that could explain user impact
"""


def planner(state: dict) -> dict:
    """Generate hypotheses and select subagents for investigation.
    
    On iteration 0: analyze alert + context to form initial hypotheses.
    On iteration 1+: incorporate feedback from synthesizer to refine plan.
    
    Args:
        state: Current graph state
        
    Returns:
        State update with hypotheses, selected_agents, and messages
    """
    alert = state.get("alert", {})
    memory_context = state.get("memory_context", {})
    kg_context_data = state.get("kg_context", {})
    team_config_raw = state.get("team_config", {})
    iteration = state.get("iteration", 0)
    messages = state.get("messages", [])
    
    # Build team config object
    team_config = _build_team_config(team_config_raw)
    
    # Get available subagents
    available_agents = get_available_subagents(team_config)
    
    # Filter out explicitly disabled subagents
    disabled_subagents = os.getenv("DISABLED_SUBAGENTS", "")
    if disabled_subagents:
        disabled_set = {s.strip() for s in disabled_subagents.split(",") if s.strip()}
        available_agents = [a for a in available_agents if a not in disabled_set]
    
    if not available_agents:
        available_agents = ["kubernetes", "metrics", "log_analysis", "traces"]
    
    # Get planner agent config
    planner_config_raw = team_config_raw.get("agents", {}).get("planner", {})
    planner_agent_config = AgentConfig(
        name="planner",
        prompt=build_prompt_config(planner_config_raw),
        model=build_model_config(planner_config_raw),
    )
    
    try:
        llm = build_llm(planner_agent_config)
    except Exception as e:
        logger.error(f"[PLANNER] Failed to build LLM: {e}")
        return _fallback_plan(available_agents, iteration, str(e))
    
    # Build the system prompt
    custom_system = planner_config_raw.get("prompt", {}).get("system", "")
    system_prompt = custom_system or PLANNER_SYSTEM_PROMPT
    system_prompt = system_prompt.replace("{available_agents}", ", ".join(available_agents))
    
    # Build user content
    user_content = _build_planner_prompt(
        alert=alert,
        memory_context=memory_context,
        kg_context_data=kg_context_data,
        iteration=iteration,
        messages=messages,
    )
    
    try:
        msgs = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content),
        ]
        run_config = {"run_name": "planner", "metadata": {"agent_id": "planner"}}
        
        # Try structured output first
        try:
            llm_structured = llm.with_structured_output(InvestigationPlan)
            plan_obj = llm_structured.invoke(msgs, config=run_config)
            hypotheses = [h.model_dump() for h in plan_obj.hypotheses]
            selected = [a for a in plan_obj.selected_agents if a in available_agents]
            reasoning = plan_obj.reasoning
            logger.info("[PLANNER] Used structured output successfully")
        except Exception as struct_err:
            # Fallback to unstructured JSON parsing
            logger.warning(f"[PLANNER] Structured output failed: {struct_err}")
            hypotheses, selected, reasoning = _parse_unstructured_response(
                llm, msgs, run_config, available_agents
            )
        
        # Normalize aliases and filter to available agents
        alias_map = {"k8s": "kubernetes", "logs": "log_analysis"}
        selected = [alias_map.get(a, a) for a in selected]
        selected = list(dict.fromkeys(a for a in selected if a in available_agents))
        
        if not selected:
            selected = available_agents
        
        # On first iteration, dispatch ALL available agents (parallel fan-out)
        if iteration == 0:
            selected = available_agents
        
        logger.info(
            f"[PLANNER] Iteration {iteration}: {len(hypotheses)} hypotheses, "
            f"dispatching {len(selected)} agents: {selected}"
        )
        
        return {
            "hypotheses": hypotheses,
            "selected_agents": selected,
            "iteration": iteration,
            "messages": [{"role": "planner", "content": f"Iteration {iteration}: {reasoning}"}],
        }
        
    except Exception as e:
        logger.error(f"[PLANNER] LLM call failed: {e}")
        return _fallback_plan(available_agents, iteration, str(e))


def _build_planner_prompt(
    alert: dict,
    memory_context: dict,
    kg_context_data: dict,
    iteration: int,
    messages: list,
) -> str:
    """Build the user prompt for the planner."""
    parts = []
    
    # Alert information
    parts.append(f"## Alert\n```json\n{json.dumps(alert, indent=2)}\n```\n")
    
    # Memory context (past similar incidents)
    if memory_context.get("has_similar_episodes"):
        parts.append(f"## Memory Context\n{memory_context.get('enhanced_prompt', '')}\n")
    
    # Knowledge graph context (service topology)
    if kg_context_data.get("available"):
        from .kg_context import format_kg_for_agent
        topology_str = format_kg_for_agent("planner", kg_context_data)
        parts.append(f"## Service Topology\n{topology_str}\n")
    
    # Previous iteration feedback
    if iteration > 0 and messages:
        parts.append(f"## Iteration {iteration} — Previous Feedback\n")
        for msg in messages[-3:]:
            if isinstance(msg, dict):
                parts.append(f"\n{msg.get('content', str(msg))}\n")
            else:
                parts.append(f"\n{msg}\n")
    
    parts.append(f"\n**Iteration**: {iteration}. Generate hypotheses and select agents to investigate.")
    
    return "\n".join(parts)


def _parse_unstructured_response(
    llm: Any,
    msgs: list,
    run_config: dict,
    available_agents: list[str],
) -> tuple[list[dict], list[str], str]:
    """Parse unstructured LLM response as fallback."""
    response = llm.invoke(msgs, config=run_config)
    response_text = response.content
    
    try:
        # Extract JSON from markdown code blocks
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]
        
        plan = json.loads(response_text.strip())
    except json.JSONDecodeError:
        # Can't parse JSON, use fallback
        logger.warning("[PLANNER] Failed to parse JSON, using fallback")
        return (
            [{"hypothesis": response.content[:200], "priority": "high", "agents_to_test": available_agents}],
            available_agents,
            "Fallback plan",
        )
    
    return (
        plan.get("hypotheses", []),
        plan.get("selected_agents", available_agents),
        plan.get("reasoning", "Investigation planned"),
    )


def _fallback_plan(
    available_agents: list[str],
    iteration: int,
    error_msg: str,
) -> dict:
    """Return a fallback plan when LLM fails."""
    return {
        "hypotheses": [
            {
                "hypothesis": f"Fallback plan due to error: {error_msg}",
                "priority": "high",
                "agents_to_test": available_agents,
            }
        ],
        "selected_agents": available_agents,
        "iteration": iteration,
        "messages": [{"role": "planner", "content": f"Fallback plan (error: {error_msg})"}],
    }


def _build_team_config(raw: dict) -> TeamConfig:
    """Build TeamConfig from raw dict."""
    from ..config import TeamConfig, AgentConfig, SkillsConfig
    
    agents = {}
    for name, cfg in raw.get("agents", {}).items():
        agents[name] = AgentConfig(
            enabled=cfg.get("enabled", True),
            name=name,
            sub_agents={k: bool(v) for k, v in cfg.get("sub_agents", {}).items()},
        )
    
    skills_data = raw.get("skills", {})
    return TeamConfig(
        agents=agents,
        skills=SkillsConfig(
            enabled=skills_data.get("enabled", ["*"]),
            disabled=skills_data.get("disabled", []),
        ),
        raw_config=raw,
    )
