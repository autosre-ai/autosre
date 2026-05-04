"""
Writeup Agent — Generates final investigation report.

Based on OpenSRE's nodes/writeup.py but simplified.
Produces both markdown narrative and structured JSON report.
"""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field

from ..llm import BaseLLMClient, get_llm_client
from .state import (
    InvestigationState,
    InvestigationReport,
    InvestigationStatus,
)

logger = logging.getLogger(__name__)


WRITEUP_SYSTEM_PROMPT = """You are the Writeup agent for an AI SRE investigation system.
Generate a professional incident investigation report from the collected evidence.

Output Requirements:
1. A markdown narrative explaining what happened, root cause, and recommendations
2. A JSON structured report following the schema below

JSON Report Schema:
{schema}

Instructions:
- Be specific and technical in root cause explanations
- Include evidence citations where possible  
- Order timeline chronologically
- Prioritize actionable recommendations
- If root cause is uncertain, say so with confidence level

Write the markdown narrative first, then output a ```json code block with the structured report."""


class ReportImpact(BaseModel):
    """Impact section of report."""
    
    user_facing: str = ""
    service_impact: str = ""
    blast_radius: str = ""


class ReportRootCause(BaseModel):
    """Root cause section of report."""
    
    summary: str
    confidence: str = "probable"  # confirmed, probable, hypothesis
    details: str = ""


class ReportActionItem(BaseModel):
    """Action item in report."""
    
    priority: str = "short_term"  # immediate, short_term, long_term
    action: str


class ReportTimeline(BaseModel):
    """Timeline event."""
    
    time: str
    event: str


class StructuredReport(BaseModel):
    """Full structured report output."""
    
    title: str
    severity: str = "info"
    status: str = "resolved"
    affected_services: list[str] = Field(default_factory=list)
    executive_summary: str
    impact: Optional[ReportImpact] = None
    timeline: list[ReportTimeline] = Field(default_factory=list)
    root_cause: ReportRootCause
    action_items: list[ReportActionItem] = Field(default_factory=list)
    lessons_learned: list[str] = Field(default_factory=list)


async def run_writeup(
    state: InvestigationState,
    llm_client: Optional[BaseLLMClient] = None,
) -> tuple[str, dict[str, Any]]:
    """Generate final investigation report.
    
    Args:
        state: Completed investigation state.
        llm_client: LLM client to use.
        
    Returns:
        Tuple of (markdown_narrative, structured_report_dict)
    """
    if llm_client is None:
        llm_client = get_llm_client()
    
    # Build system prompt
    schema_json = StructuredReport.model_json_schema()
    system = WRITEUP_SYSTEM_PROMPT.format(
        schema=json.dumps(schema_json, indent=2)
    )
    
    # Build content for report
    prompt_parts = []
    
    # Alert info
    prompt_parts.append(f"## Alert\n```json\n{json.dumps(state.alert, indent=2)}\n```")
    
    # Service context
    if state.service_name:
        prompt_parts.append(f"\n**Service**: {state.service_name}")
    if state.alert_type:
        prompt_parts.append(f"**Alert Type**: {state.alert_type}")
    
    # Investigation findings
    prompt_parts.append("\n## Investigation Findings\n")
    
    for agent_id, result in state.agent_results.items():
        prompt_parts.append(f"### {agent_id}")
        if result.findings:
            findings = result.findings
            if len(findings) > 2500:
                findings = findings[:2500] + "\n... (truncated)"
            prompt_parts.append(findings)
        else:
            prompt_parts.append("No findings.")
        prompt_parts.append("")
    
    # Hypotheses tested
    if state.hypotheses:
        prompt_parts.append("\n## Hypotheses Tested")
        for h in state.hypotheses:
            status = "✓" if h.confirmed else "✗" if h.confirmed is False else "?"
            prompt_parts.append(f"- [{status}] {h.hypothesis}")
    
    # Synthesis conclusions
    if state.synthesis:
        prompt_parts.append("\n## Synthesis Conclusion")
        prompt_parts.append(f"- **Summary**: {state.synthesis.summary}")
        if state.synthesis.root_cause:
            prompt_parts.append(f"- **Root Cause**: {state.synthesis.root_cause}")
        prompt_parts.append(f"- **Confidence**: {state.synthesis.confidence:.0%}")
    
    prompt_parts.append("\n---\nGenerate a professional incident investigation report.")
    
    prompt = "\n".join(prompt_parts)
    
    try:
        response = await llm_client.complete(
            prompt=prompt,
            system=system,
            max_tokens=3000,
            temperature=0.3,
        )
        
        response_text = response.content
        
        # Strip thinking tags if present
        clean_text = re.sub(r"<think>[\s\S]*?</think>", "", response_text).strip()
        
        # Extract JSON from response
        structured_report = _extract_json(clean_text)
        
        # Extract markdown narrative
        narrative = _extract_narrative(clean_text)
        
        # Normalize the report
        structured_report = _normalize_report(structured_report, state)
        
        # Enrich from narrative if report is thin
        structured_report = _enrich_from_narrative(structured_report, narrative, state)
        
        logger.info(
            f"[WRITEUP] Generated report: title={structured_report.get('title', 'untitled')}"
        )
        
        return narrative, structured_report
        
    except Exception as e:
        logger.error(f"[WRITEUP] Generation failed: {e}")
        
        fallback_report = {
            "title": state.alert.get("name", "Investigation Report"),
            "severity": state.alert.get("severity", "info"),
            "status": "inconclusive",
            "affected_services": [state.service_name] if state.service_name else [],
            "executive_summary": f"Investigation completed with error: {e}",
            "root_cause": {
                "summary": "Unable to determine - report generation failed",
                "confidence": "hypothesis",
            },
        }
        
        return f"Investigation report generation failed: {e}", fallback_report


def _extract_json(text: str) -> dict[str, Any]:
    """Extract JSON object from response text."""
    try:
        if "```json" in text:
            json_block = text.split("```json")[1].split("```")[0]
            return json.loads(json_block.strip())
        elif "```" in text:
            json_block = text.split("```")[1].split("```")[0]
            return json.loads(json_block.strip())
        else:
            # Try to find raw JSON object
            match = re.search(r'\{[\s\S]*"title"[\s\S]*\}', text)
            if match:
                return json.loads(match.group())
    except (json.JSONDecodeError, IndexError) as e:
        logger.warning(f"[WRITEUP] JSON extraction failed: {e}")
    
    return {}


def _extract_narrative(text: str) -> str:
    """Extract markdown narrative from response."""
    narrative = text
    if "```json" in narrative:
        narrative = narrative.split("```json")[0].strip()
    elif "```" in narrative:
        parts = narrative.split("```")
        narrative = parts[0].strip()
    return narrative


def _normalize_report(report: dict, state: InvestigationState) -> dict[str, Any]:
    """Normalize report fields to expected schema."""
    
    # Handle camelCase to snake_case
    camel_map = {
        "rootCause": "root_cause",
        "actionItems": "action_items",
        "lessonsLearned": "lessons_learned",
        "affectedServices": "affected_services",
        "executiveSummary": "executive_summary",
    }
    for camel, snake in camel_map.items():
        if camel in report and snake not in report:
            report[snake] = report.pop(camel)
    
    # Handle aliases
    if "services" in report and "affected_services" not in report:
        report["affected_services"] = report.pop("services")
    
    # Normalize root_cause
    rc = report.get("root_cause")
    if isinstance(rc, str):
        report["root_cause"] = {"summary": rc, "confidence": "probable"}
    elif isinstance(rc, dict) and "summary" not in rc:
        summary = rc.get("analysis") or rc.get("description") or rc.get("primary") or ""
        report["root_cause"] = {
            "summary": summary or "See narrative",
            "confidence": rc.get("confidence", "probable"),
        }
    
    # Ensure title
    if not report.get("title"):
        report["title"] = state.alert.get("name", "Investigation Report")
    
    # Ensure severity
    if not report.get("severity"):
        report["severity"] = state.alert.get("severity", "info")
    
    # Ensure affected_services
    if not report.get("affected_services") and state.service_name:
        report["affected_services"] = [state.service_name]
    
    return report


def _enrich_from_narrative(
    report: dict,
    narrative: str,
    state: InvestigationState,
) -> dict[str, Any]:
    """Enrich thin report from markdown narrative."""
    
    # Check if report needs enrichment
    has_summary = bool(report.get("executive_summary"))
    has_root_cause = bool(
        report.get("root_cause", {}).get("summary") 
        if isinstance(report.get("root_cause"), dict) 
        else report.get("root_cause")
    )
    
    if has_summary and has_root_cause:
        return report
    
    if not narrative or len(narrative) < 50:
        return report
    
    # Extract executive summary from narrative
    if not has_summary:
        summary = _extract_section(narrative, ["executive summary", "summary", "overview"])
        if summary:
            report["executive_summary"] = summary[:500]
        else:
            # Use first paragraph
            paragraphs = [
                p.strip() for p in narrative.split("\n\n") 
                if p.strip() and not p.strip().startswith("#")
            ]
            for p in paragraphs:
                clean = p.lstrip("*_- ")
                if len(clean) > 40 and not clean.startswith("```"):
                    report["executive_summary"] = clean[:500]
                    break
    
    # Extract root cause
    if not has_root_cause:
        rc_text = _extract_section(narrative, ["root cause", "cause", "primary root cause"])
        if rc_text:
            report["root_cause"] = {"summary": rc_text[:300], "confidence": "probable"}
    
    # Extract status from narrative
    if report.get("status") == "inconclusive":
        lower = narrative.lower()
        if any(w in lower for w in ["resolved", "remediated", "fix applied"]):
            report["status"] = "resolved"
        elif any(w in lower for w in ["mitigated", "partially"]):
            report["status"] = "mitigated"
        elif any(w in lower for w in ["ongoing", "still occurring", "persists"]):
            report["status"] = "ongoing"
    
    return report


def _extract_section(text: str, headings: list[str]) -> str:
    """Extract content from a markdown section."""
    lower = text.lower()
    
    for keyword in headings:
        # Try markdown heading
        pattern = rf"^#{1,4}\s+(?:\d+\.\s+)?{re.escape(keyword)}\b.*$"
        match = re.search(pattern, lower, re.MULTILINE | re.IGNORECASE)
        if match:
            after = text[match.end():].lstrip("\n")
            return _extract_until_next_heading(after)
        
        # Try bold marker
        pattern = rf"\*\*{re.escape(keyword)}\b[^*]*\*\*:?"
        match = re.search(pattern, lower, re.IGNORECASE)
        if match:
            after = text[match.end():].lstrip("\n :").strip()
            return _extract_until_next_heading(after)
    
    return ""


def _extract_until_next_heading(text: str) -> str:
    """Extract text until next heading."""
    lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("---"):
            break
        if not lines and not stripped:
            continue
        lines.append(stripped)
    
    result = " ".join(
        line.lstrip("*_- ") for line in lines 
        if line and not line.startswith("```")
    )
    return result.strip()


def finalize_report(
    state: InvestigationState,
    narrative: str,
    structured_report: dict[str, Any],
) -> InvestigationReport:
    """Create final InvestigationReport from writeup output."""
    return InvestigationReport(
        id=state.investigation_id,
        created_at=state.created_at,
        alert=state.alert,
        service_name=state.service_name,
        alert_type=state.alert_type,
        status=state.status,
        root_cause=structured_report.get("root_cause", {}).get("summary") 
            if isinstance(structured_report.get("root_cause"), dict)
            else structured_report.get("root_cause"),
        summary=structured_report.get("executive_summary", narrative[:500]),
        confidence=state.synthesis.confidence if state.synthesis else 0.5,
        hypotheses=state.hypotheses,
        evidence=state.all_evidence,
        iterations=state.iteration,
        duration_seconds=sum(r.duration_seconds for r in state.agent_results.values()),
        skills_used=state.get_all_skills_used(),
        agents_used=list(state.agent_results.keys()),
    )
