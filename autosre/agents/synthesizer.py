"""
Synthesizer Agent — Combines evidence and decides loop or conclude.

Based on OpenSRE's nodes/synthesizer.py but simplified.
Evaluates collected evidence and determines if investigation should continue.
"""

import json
import logging
from typing import Optional

from pydantic import BaseModel, Field

from ..llm import BaseLLMClient, get_llm_client
from .state import (
    InvestigationState,
    SynthesisDecision,
)

logger = logging.getLogger(__name__)


SYNTHESIZER_SYSTEM_PROMPT = """You are the Synthesizer agent for an AI SRE investigation system.

Your role is to combine findings from multiple investigation subagents and decide:
1. Is there enough evidence to identify the root cause?
2. Or should we investigate further?

Review the findings below and respond with valid JSON matching this schema:
{schema}

Guidelines:
- Set sufficient_evidence=true ONLY if you can confidently identify a root cause
- Set confidence based on evidence quality (0.0-1.0)
- If evidence is insufficient, describe specific gaps and provide guidance
- Focus on actionable insights, not speculation"""


class SynthesizerOutput(BaseModel):
    """Structured output from synthesizer."""
    
    sufficient_evidence: bool = Field(
        description="Whether there is enough evidence to conclude the investigation"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence in the conclusion (0.0-1.0)"
    )
    summary: str = Field(
        description="Brief summary of combined findings"
    )
    root_cause: Optional[str] = Field(
        default=None,
        description="Identified root cause (if sufficient_evidence is true)"
    )
    gaps: list[str] = Field(
        default_factory=list,
        description="List of information gaps if evidence is insufficient"
    )
    feedback: str = Field(
        default="",
        description="Guidance for next investigation round if continuing"
    )


async def run_synthesizer(
    state: InvestigationState,
    llm_client: Optional[BaseLLMClient] = None,
) -> SynthesisDecision:
    """Synthesize evidence and decide whether to continue.
    
    Args:
        state: Current investigation state with agent results.
        llm_client: LLM client to use (uses default if None).
        
    Returns:
        Synthesis decision with evidence assessment.
    """
    if llm_client is None:
        llm_client = get_llm_client()
    
    # Build system prompt with schema
    schema_json = SynthesizerOutput.model_json_schema()
    system = SYNTHESIZER_SYSTEM_PROMPT.format(
        schema=json.dumps(schema_json, indent=2),
    )
    
    # Build findings summary
    prompt_parts = []
    
    # Alert info
    prompt_parts.append(f"## Alert\n```json\n{json.dumps(state.alert, indent=2)}\n```")
    
    # Hypotheses being tested
    if state.hypotheses:
        prompt_parts.append("\n## Hypotheses Under Investigation")
        for h in state.hypotheses:
            prompt_parts.append(h.to_prompt())
    
    # Agent findings
    prompt_parts.append(f"\n## Investigation Results (Iteration {state.iteration})")
    
    for agent_id, result in state.agent_results.items():
        prompt_parts.append(f"\n### {agent_id}")
        prompt_parts.append(f"- **Status**: {result.status.value}")
        prompt_parts.append(f"- **React loops**: {result.react_loops}")
        prompt_parts.append(f"- **Duration**: {result.duration_seconds:.1f}s")
        
        if result.error:
            prompt_parts.append(f"- **Error**: {result.error}")
        
        prompt_parts.append(f"- **Findings**:\n{result.findings or 'No findings'}")
        
        # Include evidence details
        if result.evidence:
            prompt_parts.append(f"- **Evidence ({len(result.evidence)} items)**:")
            for ev in result.evidence[:3]:  # Limit to 3 per agent
                prompt_parts.append(f"  - {ev.skill}: {ev.summary or ev.result[:200]}")
    
    # Previous synthesis feedback (if any)
    if state.synthesis:
        prompt_parts.append("\n## Previous Synthesis")
        prompt_parts.append(f"- Sufficient evidence: {state.synthesis.sufficient_evidence}")
        prompt_parts.append(f"- Confidence: {state.synthesis.confidence:.0%}")
        if state.synthesis.gaps:
            prompt_parts.append(f"- Gaps: {', '.join(state.synthesis.gaps)}")
    
    prompt_parts.append(f"\n---\nIteration: {state.iteration}/{state.max_iterations}. Synthesize findings and decide.")
    
    prompt = "\n".join(prompt_parts)
    
    try:
        # Get structured output from LLM
        output = await llm_client.complete_structured(
            prompt=prompt,
            output_type=SynthesizerOutput,
            system=system,
            max_tokens=1500,
            temperature=0.2,
        )
        
        decision = SynthesisDecision(
            sufficient_evidence=output.sufficient_evidence,
            confidence=output.confidence,
            summary=output.summary,
            root_cause=output.root_cause,
            gaps=output.gaps,
            feedback=output.feedback,
        )
        
        # Force conclusion at max iterations
        if state.iteration >= state.max_iterations - 1 and not decision.sufficient_evidence:
            logger.info(f"[SYNTHESIZER] Max iterations ({state.max_iterations}) reached, forcing conclusion")
            decision.sufficient_evidence = True
            if not decision.root_cause:
                decision.root_cause = "Unable to determine root cause within iteration limit"
        
        logger.info(
            f"[SYNTHESIZER] Iteration {state.iteration}: "
            f"sufficient={decision.sufficient_evidence}, confidence={decision.confidence:.0%}"
        )
        
        return decision
        
    except Exception as e:
        logger.error(f"[SYNTHESIZER] LLM call failed: {e}")
        
        # On error, conclude with available evidence
        return SynthesisDecision(
            sufficient_evidence=True,
            confidence=0.3,
            summary=f"Synthesis error: {e}. Proceeding with available evidence.",
            root_cause="Investigation inconclusive due to synthesis error",
            gaps=[],
            feedback="",
        )


def apply_synthesis_to_state(state: InvestigationState, decision: SynthesisDecision) -> None:
    """Apply synthesis decision to state (mutates state).
    
    If sufficient evidence: mark as completed.
    Otherwise: increment iteration and add feedback message.
    """
    state.synthesis = decision
    
    if decision.sufficient_evidence:
        from .state import InvestigationStatus
        state.status = InvestigationStatus.COMPLETED
        state.add_message("synthesizer", f"Investigation complete: {decision.summary}")
    else:
        state.iteration += 1
        
        feedback_msg = f"## Synthesizer Feedback (Iteration {state.iteration - 1})\n"
        feedback_msg += f"**Summary**: {decision.summary}\n"
        feedback_msg += f"**Confidence**: {decision.confidence:.0%}\n"
        if decision.gaps:
            feedback_msg += f"**Gaps**: {', '.join(decision.gaps)}\n"
        feedback_msg += f"**Guidance**: {decision.feedback}"
        
        state.add_message("synthesizer", feedback_msg)
