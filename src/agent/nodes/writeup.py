"""
Writeup Node

Generates a structured investigation report from the investigation findings.
Produces both a markdown narrative and a JSON structured report.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from ..config import AgentConfig, build_llm, build_model_config

logger = logging.getLogger(__name__)


WRITEUP_SYSTEM_PROMPT = """You are the Writeup agent for an AI SRE system.
Generate a structured incident investigation report from the investigation findings.

Respond with BOTH:
1. A markdown narrative (conclusion)
2. A JSON structured report

## JSON Report Schema
```json
{{
    "title": "Brief incident title",
    "severity": "critical|high|medium|low|info",
    "status": "resolved|mitigated|ongoing|inconclusive",
    "affected_services": ["service-name"],
    "executive_summary": "2-3 sentence summary of what happened, the root cause, and current status.",
    "impact": {{
        "user_facing": "Description of user-visible impact",
        "service_impact": "Description of service-level impact",
        "blast_radius": "Scope of affected systems"
    }},
    "timeline": [
        {{"time": "HH:MM", "event": "Description"}}
    ],
    "root_cause": {{
        "summary": "Concise root cause statement",
        "confidence": "confirmed|probable|hypothesis",
        "details": "Detailed explanation with evidence"
    }},
    "action_items": [
        {{"priority": "immediate|short_term|long_term", "action": "Specific recommended action"}}
    ],
    "lessons_learned": ["Key takeaway or improvement suggestion"]
}}
```

Write the markdown narrative first, then a JSON code block with the structured report.
IMPORTANT: Follow the schema exactly. Use the exact field names and enum values shown above.
"""


def writeup(state: dict) -> dict:
    """Generate structured investigation report.
    
    Produces both a markdown narrative (conclusion) and structured JSON report
    that can be displayed in a UI or stored for future reference.
    
    Args:
        state: Current graph state with agent_states, hypotheses, etc.
        
    Returns:
        State update with conclusion (markdown) and structured_report (JSON)
    """
    alert = state.get("alert", {})
    agent_states = state.get("agent_states", {})
    hypotheses = state.get("hypotheses", [])
    messages = state.get("messages", [])
    team_config_raw = state.get("team_config", {})
    
    # Build LLM
    agents_config = team_config_raw.get("agents", {})
    writeup_raw = agents_config.get("writeup", {})
    
    agent_config = AgentConfig(
        name="writeup",
        model=build_model_config(writeup_raw),
    )
    
    # Build input content
    content = _build_writeup_input(alert, agent_states, hypotheses, messages)
    
    try:
        llm = build_llm(agent_config)
        
        custom_system = writeup_raw.get("prompt", {}).get("system", "")
        system_prompt = custom_system or WRITEUP_SYSTEM_PROMPT
        
        response = llm.invoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=content),
            ],
            config={"run_name": "writeup", "metadata": {"agent_id": "writeup"}},
        )
        
        response_text = response.content
        logger.info(f"[WRITEUP] LLM response length: {len(response_text)} chars")
        
        # Strip <think>...</think> reasoning tags
        clean_text = re.sub(r"<think>[\s\S]*?</think>", "", response_text).strip()
        
        # Extract JSON report from response
        structured_report = _extract_json_report(clean_text)
        
        # Extract markdown narrative
        conclusion = _extract_narrative(clean_text)
        
        if not structured_report:
            logger.warning("[WRITEUP] No structured JSON found, building from narrative")
            structured_report = _build_fallback_report(alert, conclusion)
        
        # Normalize the report
        structured_report = _normalize_report(structured_report, alert)
        
        # Enrich from narrative if report is thin
        structured_report = _enrich_from_narrative(structured_report, conclusion, alert)
        
        logger.info(
            f"[WRITEUP] Report: title={structured_report.get('title', 'untitled')}, "
            f"keys={list(structured_report.keys())}"
        )
        
        return {
            "conclusion": conclusion,
            "structured_report": structured_report,
        }
        
    except Exception as e:
        logger.error(f"[WRITEUP] Failed: {e}")
        return {
            "conclusion": f"Report generation failed: {e}\n\nRaw findings in agent states.",
            "structured_report": {
                "title": alert.get("name", "Investigation Report"),
                "severity": alert.get("severity", "info"),
                "status": "inconclusive",
                "error": str(e),
            },
        }


def _build_writeup_input(
    alert: dict,
    agent_states: dict,
    hypotheses: list,
    messages: list,
) -> str:
    """Build the input content for the writeup LLM."""
    parts = [f"## Alert\n```json\n{json.dumps(alert, indent=2)}\n```\n"]
    
    parts.append("## Investigation Findings\n")
    for agent_id, agent_state in agent_states.items():
        parts.append(f"### {agent_id}\n")
        if isinstance(agent_state, dict):
            parts.append(f"{agent_state.get('findings', 'No findings')}\n\n")
        else:
            parts.append(f"{agent_state}\n\n")
    
    if hypotheses:
        parts.append("## Hypotheses Tested\n")
        for h in hypotheses:
            if isinstance(h, dict):
                parts.append(f"- {h.get('hypothesis', str(h))}\n")
            else:
                parts.append(f"- {h}\n")
        parts.append("\n")
    
    if messages:
        parts.append("## Investigation Notes\n")
        for msg in messages[-5:]:
            if isinstance(msg, dict):
                parts.append(f"- [{msg.get('role', '?')}] {msg.get('content', '')[:200]}\n")
        parts.append("\n")
    
    parts.append("Generate the incident report with markdown narrative and JSON structured report.")
    
    return "".join(parts)


def _extract_json_report(text: str) -> dict[str, Any] | None:
    """Extract JSON report from LLM response."""
    try:
        if "```json" in text:
            json_block = text.split("```json")[1].split("```")[0]
            return json.loads(json_block.strip())
        elif "```" in text:
            json_block = text.split("```")[1].split("```")[0]
            return json.loads(json_block.strip())
        else:
            # Try to find raw JSON
            json_match = re.search(r'\{[^{}]*"title"[^{}]*\}', text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
    except (json.JSONDecodeError, IndexError):
        pass
    return None


def _extract_narrative(text: str) -> str:
    """Extract markdown narrative from LLM response."""
    narrative = text
    if "```json" in narrative:
        narrative = narrative.split("```json")[0].strip()
    elif "```" in narrative:
        narrative = narrative.split("```")[0].strip()
    return narrative


def _build_fallback_report(alert: dict, narrative: str) -> dict[str, Any]:
    """Build a minimal report when JSON extraction fails."""
    return {
        "title": alert.get("name") or "Investigation Report",
        "severity": alert.get("severity", "info"),
        "status": "inconclusive",
        "affected_services": [s for s in [alert.get("service")] if s],
        "executive_summary": narrative[:500] if narrative else "",
        "root_cause": {
            "summary": "See narrative report",
            "confidence": "hypothesis",
        },
        "action_items": [],
    }


def _normalize_report(report: dict, alert: dict) -> dict:
    """Normalize LLM-generated report to match expected schema."""
    
    # camelCase -> snake_case
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
    
    # Ensure title
    if not report.get("title"):
        report["title"] = alert.get("name") or "Investigation Report"
    
    # Ensure severity
    if not report.get("severity"):
        report["severity"] = alert.get("severity", "info")
    
    # Normalize root_cause
    rc = report.get("root_cause")
    if isinstance(rc, str):
        report["root_cause"] = {"summary": rc, "confidence": "probable"}
    elif isinstance(rc, dict) and "summary" not in rc:
        summary = rc.get("analysis") or rc.get("description") or ""
        if not summary:
            summary = json.dumps(rc, indent=2) if rc else "See narrative"
        report["root_cause"] = {
            "summary": summary,
            "confidence": rc.get("confidence", "probable"),
        }
    
    # Normalize action_items priority
    priority_map = {
        "critical": "immediate",
        "high": "immediate",
        "medium": "short_term",
        "low": "long_term",
    }
    for item in report.get("action_items", []):
        p = item.get("priority", "").lower()
        if p in priority_map:
            item["priority"] = priority_map[p]
    
    return report


def _enrich_from_narrative(report: dict, narrative: str, alert: dict) -> dict:
    """Enrich thin report with info extracted from narrative."""
    if not narrative or len(narrative) < 50:
        return report
    
    # Extract executive summary if missing
    if not report.get("executive_summary"):
        # Find first substantial paragraph
        paragraphs = [p.strip() for p in narrative.split("\n\n") if p.strip() and not p.strip().startswith("#")]
        for p in paragraphs:
            clean = p.lstrip("*_- ")
            if len(clean) > 40 and not clean.startswith("```"):
                report["executive_summary"] = clean[:500]
                break
    
    # Ensure affected_services from alert
    if not report.get("affected_services"):
        svc = alert.get("service")
        if svc:
            report["affected_services"] = [svc]
    
    # Final safety: if still no summary, use narrative
    if not report.get("executive_summary"):
        report["executive_summary"] = narrative[:500]
    
    return report
