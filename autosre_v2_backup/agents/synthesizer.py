"""
Synthesizer Agent — Combines subagent findings and decides whether to loop.

Based on OpenSRE's nodes/synthesizer.py but simplified.
Uses LLM to analyze evidence and determine if root cause is found.
"""

import json
import logging
from typing import Optional

from pydantic import BaseModel, Field

from ..llm import BaseLLMClient, get_llm_client
from .state import (
    InvestigationState,
    InvestigationStatus,
    SynthesisDecision,
)

logger = logging.getLogger(__name__)


SYNTHESIZER_SYSTEM_PROMPT = """You are the Synthesizer agent for an AI SRE investigation system.

Your role is to combine findings from multiple investigation subagents and decide:
1. Is there enough evidence to determine the root cause?
2. Or should we investigate further?

Review the findings below and respond with valid JSON:
{schema}

Guidelines:
- sufficient_evidence: true only if you have HIGH confidence in the root cause
- confidence: 0.0-1.0 based on quality and consistency of evidence
- root_cause: specific technical explanation if evidence is sufficient
- gaps: list specific missing information if insufficient
- feedback: actionable guidance for next iteration if continuing"""


class SynthesizerOutput(BaseModel):
    """Structured output from synthesizer."""
    
    sufficient_evidence: bool = Field(
        description="Whether evidence is sufficient to conclude investigation"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence level in conclusions (0.0-1.0)"
    )
    summary: str = Field(
        description="Brief summary of combined findings"
    )
    root_cause: Optional[str] = Field(
        default=None,
        description="Root cause if evidence is sufficient"
    )
    gaps: list[str] = Field(
        default_factory=list,
        description="Information gaps if evidence insufficient"
    )
    feedback: str = Field(
        default="",
        description="Guidance for next investigation round if continuing"
    )


async def run_synthesizer(
    state: InvestigationState,
    llm_client: Optional[BaseLLMClient] = None,
    force_conclude: bool = False,
) -> SynthesisDecision:
    """Synthesize investigation findings and decide next steps.
    
    Args:
        state: Current investigation state with subagent results.
        llm_client: LLM client to use (uses default if None).
        force_conclude: If True, force conclusion regardless of confidence.
        
    Returns:
        SynthesisDecision indicating whether to continue or conclude.
    """
    if llm_client is None:
        llm_client = get_llm_client()
    
    # Build system prompt with schema
    schema_json = SynthesizerOutput.model_json_schema()
    system = SYNTHESIZER_SYSTEM_PROMPT.format(
        schema=json.dumps(schema_json, indent=2)
    )
    
    # Build findings summary
    prompt_parts = []
    
    # Alert context
    prompt_parts.append(f"## Alert\n```json\n{json.dumps(state.alert, indent=2)}\n```")
    
    # Iteration info
    prompt_parts.append(f"\n## Investigation Status")
    prompt_parts.append(f"- Iteration: {state.iteration} / {state.max_iterations}")
    prompt_parts.append(f"- Agents dispatched: {', '.join(state.selected_agents)}")
    
    # Subagent results
    prompt_parts.append(f"\n## Subagent Findings\n")
    
    for agent_id, result in state.agent_results.items():
        prompt_parts.append(f"### {agent_id}")
        prompt_parts.append(f"- **Status**: {result.status.value}")
        prompt_parts.append(f"- **Duration**: {result.duration_seconds:.1f}s")
        prompt_parts.append(f"- **ReAct loops**: {result.react_loops}")
        
        if result.error:
            prompt_parts.append(f"- **Error**: {result.error}")
        
        if result.findings:
            # Truncate very long findings
            findings = result.findings
            if len(findings) > 3000:
                findings = findings[:3000] + "\n... (truncated)"
            prompt_parts.append(f"\n**Findings**:\n{findings}\n")
        else:
            prompt_parts.append("- No findings reported\n")
    
    # Hypotheses status
    if state.hypotheses:
        prompt_parts.append("\n## Hypotheses Under Investigation")
        for h in state.hypotheses:
            prompt_parts.append(h.to_prompt())
    
    # Previous synthesizer feedback
    synth_messages = [m for m in state.messages if m.get("role") == "synthesizer"]
    if synth_messages:
        prompt_parts.append("\n## Previous Analysis")
        for msg in synth_messages[-2:]:
            prompt_parts.append(msg.get("content", ""))
    
    prompt_parts.append("\n---\nAnalyze the findings and determine if we can conclude the investigation.")
    
    prompt = "\n".join(prompt_parts)
    
    try:
        output = await llm_client.complete_structured(
            prompt=prompt,
            output_type=SynthesizerOutput,
            system=system,
            max_tokens=1500,
            temperature=0.2,
        )
        
        # Force conclusion at max iterations
        sufficient = output.sufficient_evidence
        if force_conclude or state.iteration >= state.max_iterations - 1:
            sufficient = True
            logger.info(
                f"[SYNTHESIZER] Forcing conclusion at iteration {state.iteration}"
            )
        
        decision = SynthesisDecision(
            sufficient_evidence=sufficient,
            confidence=output.confidence,
            summary=output.summary,
            root_cause=output.root_cause,
            gaps=output.gaps,
            feedback=output.feedback,
        )
        
        logger.info(
            f"[SYNTHESIZER] Iteration {state.iteration}: "
            f"sufficient={sufficient}, confidence={output.confidence:.0%}"
        )
        
        return decision
        
    except Exception as e:
        logger.error(f"[SYNTHESIZER] LLM call failed: {e}")
        
        # On error, conclude with available evidence
        return SynthesisDecision(
            sufficient_evidence=True,
            confidence=0.3,
            summary=f"Synthesis error: {e}. Concluding with available evidence.",
            root_cause=None,
            gaps=[str(e)],
            feedback="",
        )


def apply_synthesis_to_state(
    state: InvestigationState,
    decision: SynthesisDecision,
) -> None:
    """Apply synthesis decision to state (mutates state)."""
    state.synthesis = decision
    
    if decision.sufficient_evidence:
        state.status = InvestigationStatus.COMPLETED
        state.add_message("synthesizer", f"Investigation complete: {decision.summary}")
    else:
        state.iteration += 1
        feedback_msg = f"## Synthesizer Feedback (Iteration {state.iteration - 1})\n"
        feedback_msg += f"**Summary**: {decision.summary}\n"
        feedback_msg += f"**Confidence**: {decision.confidence:.0%}\n"
        if decision.gaps:
            feedback_msg += f"**Gaps**: {', '.join(decision.gaps)}\n"
        feedback_msg += f"**Guidance**: {decision.feedback}\n"
        
        state.add_message("synthesizer", feedback_msg)
