"""
Synthesizer Node

Combines findings from multiple investigation subagents and decides
whether to loop back for more investigation or proceed to writeup.
"""

from __future__ import annotations

import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from ..config import AgentConfig, build_llm, build_model_config
from ..state import SynthesisDecision

logger = logging.getLogger(__name__)


SYNTHESIZER_SYSTEM_PROMPT = """You are the Synthesizer agent for an AI SRE system.
Your role is to combine findings from multiple investigation subagents and decide:
1. Is there enough evidence to write a conclusion?
2. Or should we investigate further?

Review the findings below and respond with a JSON object:
{{
    "sufficient_evidence": true/false,
    "confidence": 0.0-1.0,
    "summary": "Brief summary of combined findings",
    "gaps": ["List of information gaps if evidence is insufficient"],
    "feedback": "If insufficient, provide specific guidance for the next investigation round"
}}

Guidelines:
- If multiple agents found consistent evidence pointing to a root cause, evidence is sufficient
- If agents found contradictory evidence, we may need more investigation
- If key areas weren't investigated (e.g., metrics show issues but logs weren't checked), identify gaps
- Confidence should reflect how certain we are about the root cause
"""


def synthesizer(state: dict) -> dict:
    """Combine subagent results and decide whether to loop or conclude.
    
    If evidence is sufficient or max iterations reached: set status to 'completed'.
    Otherwise: append feedback to messages and increment iteration for planner.
    
    Args:
        state: Current graph state with agent_states from subagents
        
    Returns:
        State update with status, iteration, and messages
    """
    agent_states = state.get("agent_states", {})
    iteration = state.get("iteration", 0)
    max_iterations = state.get("max_iterations", 3)
    team_config_raw = state.get("team_config", {})
    alert = state.get("alert", {})
    
    # Build LLM for synthesis
    agents_config = team_config_raw.get("agents", {})
    writeup_config = agents_config.get("writeup", agents_config.get("planner", {}))
    
    agent_config = AgentConfig(
        name="synthesizer",
        model=build_model_config(writeup_config),
    )
    
    # Build findings summary
    findings_text = _build_findings_summary(alert, agent_states, iteration)
    
    try:
        llm = build_llm(agent_config)
        msgs = [
            SystemMessage(content=SYNTHESIZER_SYSTEM_PROMPT),
            HumanMessage(content=findings_text),
        ]
        run_config = {"run_name": "synthesizer", "metadata": {"agent_id": "synthesizer"}}
        
        # Try structured output first
        try:
            llm_structured = llm.with_structured_output(SynthesisDecision)
            decision = llm_structured.invoke(msgs, config=run_config)
            synthesis = decision.model_dump()
            logger.info("[SYNTHESIZER] Used structured output")
        except Exception as struct_err:
            # Fallback to unstructured JSON parsing
            logger.warning(f"[SYNTHESIZER] Structured output failed: {struct_err}")
            synthesis = _parse_unstructured_response(llm, msgs, run_config, iteration, max_iterations)
        
        sufficient = synthesis.get("sufficient_evidence", False)
        
        # Force conclusion at max iterations
        if iteration >= max_iterations - 1:
            sufficient = True
            logger.info(f"[SYNTHESIZER] Max iterations ({max_iterations}) reached, forcing conclusion")
        
        if sufficient:
            logger.info(f"[SYNTHESIZER] Evidence sufficient at iteration {iteration}")
            return {
                "status": "completed",
                "messages": [{
                    "role": "synthesizer",
                    "content": synthesis.get("summary", "Investigation complete."),
                }],
            }
        else:
            feedback = synthesis.get("feedback", "Continue investigation.")
            gaps = synthesis.get("gaps", [])
            
            feedback_msg = _build_feedback_message(synthesis, iteration)
            
            logger.info(f"[SYNTHESIZER] Insufficient evidence, requesting iteration {iteration + 1}")
            
            return {
                "iteration": iteration + 1,
                "status": "running",
                "messages": [{"role": "synthesizer", "content": feedback_msg}],
            }
            
    except Exception as e:
        logger.error(f"[SYNTHESIZER] LLM call failed: {e}")
        # On error, conclude with available evidence
        return {
            "status": "completed",
            "messages": [{
                "role": "synthesizer",
                "content": f"Synthesis error: {e}. Proceeding with available evidence.",
            }],
        }


def _build_findings_summary(alert: dict, agent_states: dict, iteration: int) -> str:
    """Build a summary of all agent findings for the synthesizer."""
    parts = [
        f"## Alert\n{json.dumps(alert, indent=2)}\n",
        f"## Investigation Results (Iteration {iteration})\n",
    ]
    
    for agent_id, agent_state in agent_states.items():
        parts.append(f"### {agent_id}\n")
        if isinstance(agent_state, dict):
            parts.append(f"- **Status**: {agent_state.get('status', 'unknown')}\n")
            parts.append(f"- **React loops**: {agent_state.get('react_loops', 0)}\n")
            parts.append(f"- **Duration**: {agent_state.get('duration_seconds', 0):.1f}s\n")
            parts.append(f"- **Findings**:\n{agent_state.get('findings', 'No findings')}\n\n")
        else:
            logger.warning(f"[SYNTHESIZER] agent_states[{agent_id}] is {type(agent_state).__name__}")
            parts.append(f"- **Findings**:\n{agent_state}\n\n")
    
    return "".join(parts)


def _parse_unstructured_response(
    llm,
    msgs: list,
    run_config: dict,
    iteration: int,
    max_iterations: int,
) -> dict:
    """Parse unstructured LLM response as fallback."""
    response = llm.invoke(msgs, config=run_config)
    response_text = response.content
    
    try:
        # Extract JSON from markdown code blocks
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]
        
        return json.loads(response_text.strip())
    except json.JSONDecodeError:
        # Default to concluding if we're near max iterations
        return {
            "sufficient_evidence": iteration >= max_iterations - 1,
            "confidence": 0.5,
            "summary": response.content[:500] if response.content else "Investigation summary",
            "gaps": [],
            "feedback": "",
        }


def _build_feedback_message(synthesis: dict, iteration: int) -> str:
    """Build a feedback message for the planner."""
    lines = [
        f"## Synthesizer Feedback (Iteration {iteration})",
        f"**Summary**: {synthesis.get('summary', '')}",
        f"**Confidence**: {synthesis.get('confidence', 0)}",
    ]
    
    gaps = synthesis.get("gaps", [])
    if gaps:
        lines.append(f"**Gaps**: {', '.join(gaps)}")
    
    feedback = synthesis.get("feedback", "")
    if feedback:
        lines.append(f"**Guidance**: {feedback}")
    
    return "\n".join(lines)
