"""
Writeup Agent — Generates final investigation report.

Takes investigation state and produces a structured report with:
- Root cause identification
- Summary of findings
- Evidence collected
- Recommendations
"""

import json
import logging
from typing import Optional

from pydantic import BaseModel, Field

from ..llm import BaseLLMClient, get_llm_client
from .state import (
    InvestigationReport,
    InvestigationState,
    InvestigationStatus,
)

logger = logging.getLogger(__name__)


WRITEUP_SYSTEM_PROMPT = """You are the Writeup agent for an AI SRE investigation system.

Your role is to synthesize all investigation findings into a clear, actionable report.

Generate a JSON response matching this schema:
{schema}

Guidelines:
- Be specific about the root cause — avoid vague statements
- Summarize key evidence that supports the root cause
- Include severity assessment (critical, high, medium, low)
- Suggest specific next steps if remediation is needed
- Keep the summary concise but complete"""


class WriteupOutput(BaseModel):
    """Structured output from writeup agent."""
    
    root_cause: str = Field(
        description="Specific identification of the root cause"
    )
    summary: str = Field(
        description="Concise summary of the investigation (2-4 sentences)"
    )
    severity: str = Field(
        description="Severity level: critical, high, medium, low"
    )
    key_findings: list[str] = Field(
        default_factory=list,
        description="List of key findings that support the root cause"
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="Recommended next steps or remediation actions"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence in the root cause (0.0-1.0)"
    )


async def run_writeup(
    state: InvestigationState,
    llm_client: Optional[BaseLLMClient] = None,
) -> InvestigationReport:
    """Generate final investigation report.
    
    Args:
        state: Investigation state with all findings.
        llm_client: LLM client to use (uses default if None).
        
    Returns:
        Complete InvestigationReport.
    """
    if llm_client is None:
        llm_client = get_llm_client()
    
    # Build system prompt with schema
    schema_json = WriteupOutput.model_json_schema()
    system = WRITEUP_SYSTEM_PROMPT.format(
        schema=json.dumps(schema_json, indent=2),
    )
    
    # Build prompt with all investigation context
    prompt_parts = []
    
    # Alert info
    prompt_parts.append(f"## Alert\n```json\n{json.dumps(state.alert, indent=2)}\n```")
    
    # Service context
    if state.topology_context.get("available"):
        ctx = state.topology_context
        prompt_parts.append(f"\n## Service Context")
        prompt_parts.append(f"- Service: {ctx.get('service', state.service_name)}")
        prompt_parts.append(f"- Tier: {ctx.get('tier', 'unknown')}")
        deps = ctx.get("dependencies", [])
        if deps:
            prompt_parts.append(f"- Dependencies: {', '.join(deps)}")
    
    # Hypotheses tested
    if state.hypotheses:
        prompt_parts.append("\n## Hypotheses Tested")
        for h in state.hypotheses:
            status = "✓" if h.confirmed else "✗" if h.confirmed is False else "?"
            prompt_parts.append(f"- [{status}] {h.hypothesis} (confidence: {h.confidence:.0%})")
    
    # Synthesis result
    if state.synthesis:
        prompt_parts.append("\n## Synthesis Result")
        prompt_parts.append(f"- Sufficient evidence: {state.synthesis.sufficient_evidence}")
        prompt_parts.append(f"- Confidence: {state.synthesis.confidence:.0%}")
        prompt_parts.append(f"- Summary: {state.synthesis.summary}")
        if state.synthesis.root_cause:
            prompt_parts.append(f"- Root cause: {state.synthesis.root_cause}")
    
    # Agent findings
    prompt_parts.append("\n## Agent Findings")
    for agent_id, result in state.agent_results.items():
        prompt_parts.append(f"\n### {agent_id}")
        prompt_parts.append(f"- Status: {result.status.value}")
        prompt_parts.append(f"- Duration: {result.duration_seconds:.1f}s")
        prompt_parts.append(f"- Findings:\n{result.findings[:2000]}")
    
    # Evidence summary
    if state.all_evidence:
        prompt_parts.append(f"\n## Evidence Collected ({len(state.all_evidence)} items)")
        for ev in state.all_evidence[:10]:
            prompt_parts.append(f"- [{ev.source}/{ev.skill}]: {ev.summary or ev.result[:200]}")
    
    # Investigation stats
    prompt_parts.append(f"\n## Investigation Stats")
    prompt_parts.append(f"- Iterations: {state.iteration}")
    prompt_parts.append(f"- Agents used: {', '.join(state.agent_results.keys())}")
    prompt_parts.append(f"- Skills used: {', '.join(state.get_all_skills_used())}")
    
    prompt_parts.append("\n---\nGenerate the final investigation report.")
    
    prompt = "\n".join(prompt_parts)
    
    try:
        # Get structured output from LLM
        output = await llm_client.complete_structured(
            prompt=prompt,
            output_type=WriteupOutput,
            system=system,
            max_tokens=2000,
            temperature=0.2,
        )
        
        # Build report
        report = InvestigationReport(
            id=state.investigation_id,
            created_at=state.created_at,
            alert=state.alert,
            service_name=state.service_name,
            alert_type=state.alert_type,
            status=state.status,
            root_cause=output.root_cause,
            summary=output.summary,
            confidence=output.confidence,
            hypotheses=state.hypotheses,
            evidence=state.all_evidence,
            iterations=state.iteration,
            duration_seconds=sum(r.duration_seconds for r in state.agent_results.values()),
            skills_used=state.get_all_skills_used(),
            agents_used=list(state.agent_results.keys()),
        )
        
        logger.info(
            f"[WRITEUP] Generated report: {output.root_cause[:100]}... "
            f"(confidence: {output.confidence:.0%})"
        )
        
        return report
        
    except Exception as e:
        logger.error(f"[WRITEUP] LLM call failed: {e}")
        
        # Return basic report from state
        return state.finalize_report()


def format_report_markdown(report: InvestigationReport) -> str:
    """Format report as markdown for display."""
    lines = [
        f"# Investigation Report: {report.alert_type}",
        "",
        f"**Service:** {report.service_name}",
        f"**Status:** {report.status.value}",
        f"**Confidence:** {report.confidence:.0%}",
        f"**Duration:** {report.duration_seconds:.1f}s",
        "",
        "## Root Cause",
        "",
        report.root_cause or "Not identified",
        "",
        "## Summary",
        "",
        report.summary,
        "",
    ]
    
    if report.hypotheses:
        lines.append("## Hypotheses Tested")
        lines.append("")
        for h in report.hypotheses:
            status = "✓" if h.confirmed else "✗" if h.confirmed is False else "?"
            lines.append(f"- [{status}] {h.hypothesis}")
        lines.append("")
    
    if report.evidence:
        lines.append(f"## Evidence ({len(report.evidence)} items)")
        lines.append("")
        for ev in report.evidence[:10]:
            lines.append(f"- **{ev.source}/{ev.skill}**: {ev.summary or ev.result[:100]}")
        lines.append("")
    
    lines.append("## Investigation Details")
    lines.append("")
    lines.append(f"- **Iterations:** {report.iterations}")
    lines.append(f"- **Agents:** {', '.join(report.agents_used)}")
    lines.append(f"- **Skills:** {', '.join(report.skills_used)}")
    lines.append(f"- **Created:** {report.created_at.isoformat()}")
    
    return "\n".join(lines)
