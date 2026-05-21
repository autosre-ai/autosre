"""
Memory Store Node

Persists the completed investigation as an episode for future memory lookups.
Extracts metadata and stores in the memory service.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def memory_store(state: dict) -> dict:
    """Store the completed investigation as an episode.
    
    Extracts metadata from the investigation and persists it to the
    memory service for future lookups.
    
    Args:
        state: Final graph state with conclusion, agent_states, etc.
        
    Returns:
        Empty dict (terminal node, no state updates needed)
    """
    alert = state.get("alert", {})
    conclusion = state.get("conclusion", "")
    structured_report = state.get("structured_report", {})
    thread_id = state.get("thread_id", "")
    investigation_id = state.get("investigation_id", "")
    agent_states = state.get("agent_states", {})
    
    # Skip if conclusion is too short
    if not conclusion or len(conclusion.strip()) < 50:
        logger.info("[MEMORY_STORE] Conclusion too short, skipping storage")
        return {}
    
    # Build episode data
    episode = _build_episode(
        alert=alert,
        conclusion=conclusion,
        structured_report=structured_report,
        thread_id=thread_id,
        investigation_id=investigation_id,
        agent_states=agent_states,
    )
    
    # Store episode
    try:
        _store_episode(episode)
        logger.info(f"[MEMORY_STORE] Episode stored for investigation {investigation_id[:8]}")
    except Exception as e:
        logger.error(f"[MEMORY_STORE] Failed to store episode: {e}")
    
    return {}


def _build_episode(
    alert: dict,
    conclusion: str,
    structured_report: dict,
    thread_id: str,
    investigation_id: str,
    agent_states: dict,
) -> dict[str, Any]:
    """Build episode data structure for storage."""
    
    # Extract tool calls from agent states
    tool_calls = []
    for agent_id, agent_state in agent_states.items():
        if isinstance(agent_state, dict):
            evidence = agent_state.get("evidence", [])
            for entry in evidence:
                tool_calls.append({
                    "agent": agent_id,
                    "tool": entry.get("tool", ""),
                    "args": entry.get("args", {}),
                })
    
    # Build prompt from alert
    prompt = f"{alert.get('name', '')}: {alert.get('description', str(alert))}"
    
    # Extract key info from structured report
    root_cause = structured_report.get("root_cause", {})
    if isinstance(root_cause, dict):
        root_cause_summary = root_cause.get("summary", "")
    else:
        root_cause_summary = str(root_cause)
    
    return {
        "thread_id": thread_id,
        "investigation_id": investigation_id,
        "prompt": prompt,
        "conclusion": conclusion[:5000],
        "success": True,
        
        # Alert metadata
        "service_name": alert.get("service", ""),
        "alert_type": alert.get("name", ""),
        "severity": alert.get("severity", "info"),
        
        # Investigation results
        "title": structured_report.get("title", ""),
        "root_cause": root_cause_summary,
        "status": structured_report.get("status", "inconclusive"),
        "executive_summary": structured_report.get("executive_summary", "")[:1000],
        
        # Skills/tools used
        "tool_calls": tool_calls,
        "skills_used": list(set(tc.get("tool", "").split("/")[0] for tc in tool_calls if tc.get("tool"))),
        
        # Agents involved
        "agents_used": list(agent_states.keys()),
    }


def _store_episode(episode: dict) -> bool:
    """Store episode in memory service.
    
    Returns True on success, raises on failure.
    """
    memory_service_url = os.getenv("MEMORY_SERVICE_URL", "")
    
    if not memory_service_url:
        logger.info("[MEMORY_STORE] Memory service not configured, skipping")
        return False
    
    resp = httpx.post(
        f"{memory_service_url}/api/v1/memory/episodes",
        json=episode,
        timeout=10.0,
    )
    resp.raise_for_status()
    return True
