"""
Agent integration layer for the episodic memory system.

Provides high-level functions for integrating memory into the
agent investigation workflow:
- Pre-investigation: Enhance prompts with relevant past experience
- Post-investigation: Store completed investigations for future learning
- Statistics: Monitor memory system health and usage
"""

import logging
import os
from typing import Any, Optional

from .models import (
    Episode,
    EpisodeCreate,
    KeyFinding,
    MemorySearchResult,
    MemoryStats,
    Severity,
    Strategy,
)

logger = logging.getLogger(__name__)

DEFAULT_ORG_ID = os.getenv("AUTOSRE_ORG_ID", "default")


# ---------------------------------------------------------------------------
# Pre-investigation: Enhance prompt with memory context
# ---------------------------------------------------------------------------

async def enhance_investigation_with_memory(
    prompt: str,
    service_name: str = "",
    alert_type: str = "",
    error_message: str = "",
    org_id: str = "",
    max_episodes: int = 3,
) -> str:
    """
    Enhance an investigation prompt with memory context from similar past investigations.
    
    Searches for similar episodes and relevant strategies, then prepends
    the context to the original prompt to guide the investigation.
    
    Args:
        prompt: The original investigation prompt
        service_name: Name of the affected service
        alert_type: Classified alert type
        error_message: Error message or symptoms
        org_id: Organization ID
        max_episodes: Maximum similar episodes to include
        
    Returns:
        Enhanced prompt with memory context prepended
        
    Example:
        ```python
        enhanced = await enhance_investigation_with_memory(
            prompt="API response times are elevated",
            service_name="api-gateway",
            alert_type="high_latency",
        )
        # enhanced now includes context from past latency investigations
        ```
    """
    from . import store
    from .strategy import get_cached_strategy, generate_and_cache_strategy
    
    org = org_id or DEFAULT_ORG_ID
    
    try:
        # Extract alert type if not provided
        detected_alert = alert_type or _extract_alert_type_from_prompt(prompt)
        detected_service = service_name or _extract_service_from_prompt(prompt)
        
        # Search for similar episodes
        similar = await store.search_similar(
            org_id=org,
            alert_type=detected_alert,
            service_name=detected_service,
            prompt=prompt,
            limit=max_episodes,
        )
        
        if not similar:
            return prompt
        
        # Build memory context
        memory_lines = ["## Past Investigation Memory\n"]
        memory_lines.append(
            f"Found {len(similar)} similar past investigation(s):\n"
        )
        
        for i, result in enumerate(similar, 1):
            ep = result.episode
            services = ", ".join(ep.services) if ep.services else "unknown"
            memory_lines.append(f"### Similar Investigation #{i}")
            memory_lines.append(f"- **Services**: {services}")
            memory_lines.append(f"- **Alert type**: {ep.alert_type}")
            memory_lines.append(f"- **Resolved**: {'Yes' if ep.resolved else 'No'}")
            if ep.root_cause:
                memory_lines.append(f"- **Root cause**: {ep.root_cause}")
            if ep.summary:
                memory_lines.append(f"- **Summary**: {ep.summary}")
            if ep.skills_used:
                memory_lines.append(f"- **Skills used**: {', '.join(ep.skills_used[:5])}")
            memory_lines.append(f"- **Effectiveness**: {ep.effectiveness_score:.0%}")
            memory_lines.append(f"- **Match reasons**: {', '.join(result.match_reasons)}")
            memory_lines.append("")
        
        # Try to get or generate strategy
        strategy = await get_cached_strategy(org, detected_alert, detected_service)
        if not strategy and len(similar) >= 2:
            # Try to generate a new strategy if we have enough episodes
            episodes = [r.episode for r in similar]
            strategy = await generate_and_cache_strategy(
                org_id=org,
                alert_type=detected_alert,
                service_name=detected_service,
                min_episodes=2,
            )
        
        if strategy:
            memory_lines.append("## Investigation Strategy (from past investigations)\n")
            memory_lines.append(strategy.strategy_text)
            memory_lines.append("")
        
        memory_context = "\n".join(memory_lines)
        logger.info(
            f"[MEMORY-INTEGRATION] Enhanced prompt with {len(similar)} episodes, "
            f"context size: {len(memory_context)} chars"
        )
        
        return f"{memory_context}\n---\n\n{prompt}"
    
    except Exception as e:
        logger.error(f"[MEMORY-INTEGRATION] Failed to enhance prompt: {e}")
        return prompt


# ---------------------------------------------------------------------------
# Post-investigation: Store results
# ---------------------------------------------------------------------------

async def store_investigation_result(
    thread_id: str,
    prompt: str,
    result_text: str,
    success: bool,
    agent_run_id: Optional[str] = None,
    tool_calls_data: Optional[list[dict[str, Any]]] = None,
    duration_seconds: Optional[float] = None,
    org_id: str = "",
    team_node_id: Optional[str] = None,
    service_name: str = "",
    alert_type: str = "",
) -> Optional[Episode]:
    """
    Store a completed investigation as an episode.
    
    Extracts key information from the investigation result using LLM
    and stores it for future reference.
    
    Args:
        thread_id: Conversation thread ID
        prompt: Original investigation prompt
        result_text: Final investigation result/response
        success: Whether the investigation was successful
        agent_run_id: ID of the agent run
        tool_calls_data: List of tool call records
        duration_seconds: Total investigation duration
        org_id: Organization ID
        team_node_id: Team identifier
        service_name: Known service name (optional)
        alert_type: Known alert type (optional)
        
    Returns:
        The stored Episode, or None if storage failed
    """
    from . import store
    
    try:
        # Skip very short results
        if not result_text or len(result_text.strip()) < 50:
            logger.info(
                f"[MEMORY-INTEGRATION] Skipping short result: "
                f"result_len={len(result_text) if result_text else 0}"
            )
            return None
        
        org = org_id or DEFAULT_ORG_ID
        tool_calls = tool_calls_data or []
        
        # Extract information from result
        root_cause = await _extract_root_cause(result_text)
        resolved = _text_indicates_resolution(result_text)
        summary = await _extract_summary(prompt, result_text)
        detected_alert = alert_type or _extract_alert_type_from_prompt(prompt)
        detected_services = _extract_services(prompt, result_text, service_name)
        severity = _extract_severity(prompt)
        
        # Extract skills and findings from tool calls
        skills_used = _extract_skills_used(tool_calls)
        key_findings = _extract_key_findings(tool_calls)
        
        # Calculate effectiveness score
        effectiveness = 0.0
        if resolved and root_cause:
            effectiveness = 0.8
        elif resolved:
            effectiveness = 0.6
        elif root_cause:
            effectiveness = 0.5
        else:
            effectiveness = 0.3
        
        # Create episode
        episode = await store.store_episode(EpisodeCreate(
            agent_run_id=agent_run_id,
            org_id=org,
            team_node_id=team_node_id,
            alert_type=detected_alert,
            alert_description=prompt[:2000],
            severity=severity,
            services=detected_services,
            agents_used=["sre-agent"],
            skills_used=skills_used,
            key_findings=[kf.model_dump() for kf in key_findings],
            resolved=resolved,
            root_cause=root_cause,
            summary=summary,
            effectiveness_score=effectiveness,
            confidence=0.8 if resolved else 0.3,
            duration_seconds=duration_seconds,
        ))
        
        logger.info(
            f"[MEMORY-INTEGRATION] Stored episode {episode.id}: "
            f"{detected_alert}/{','.join(detected_services)} "
            f"(resolved={resolved}, effectiveness={effectiveness:.0%})"
        )
        
        return episode
    
    except Exception as e:
        logger.error(f"[MEMORY-INTEGRATION] Failed to store investigation: {e}")
        return None


# ---------------------------------------------------------------------------
# Statistics and Monitoring
# ---------------------------------------------------------------------------

async def get_memory_stats(org_id: str = "") -> MemoryStats:
    """
    Get comprehensive memory system statistics.
    
    Returns:
        MemoryStats with counts, averages, and breakdowns
    """
    from . import store
    
    org = org_id or DEFAULT_ORG_ID
    return await store.get_memory_stats(org)


async def get_all_episodes(
    org_id: str = "",
    limit: int = 50,
    alert_type: Optional[str] = None,
    service_name: Optional[str] = None,
    resolved: Optional[bool] = None,
) -> list[Episode]:
    """
    Get all stored episodes with optional filtering.
    
    Args:
        org_id: Organization ID
        limit: Maximum episodes to return
        alert_type: Filter by alert type
        service_name: Filter by service
        resolved: Filter by resolution status
        
    Returns:
        List of Episode objects
    """
    from . import store
    
    org = org_id or DEFAULT_ORG_ID
    return await store.list_episodes(
        org_id=org,
        alert_type=alert_type,
        service_name=service_name,
        resolved=resolved,
        limit=limit,
    )


async def search_similar(
    prompt: str,
    org_id: str = "",
    service_name: str = "",
    alert_type: str = "",
    limit: int = 5,
) -> list[MemorySearchResult]:
    """
    Search for similar past investigations.
    
    Args:
        prompt: Search prompt or alert description
        org_id: Organization ID
        service_name: Service to match
        alert_type: Alert type to match
        limit: Maximum results
        
    Returns:
        List of MemorySearchResult with similarity scores
    """
    from . import store
    
    org = org_id or DEFAULT_ORG_ID
    detected_alert = alert_type or _extract_alert_type_from_prompt(prompt)
    detected_service = service_name or _extract_service_from_prompt(prompt)
    
    return await store.search_similar(
        org_id=org,
        alert_type=detected_alert,
        service_name=detected_service,
        prompt=prompt,
        limit=limit,
    )


async def get_strategies(
    org_id: str = "",
    alert_type: str = "",
    service_name: str = "",
) -> list[Strategy]:
    """
    Get cached investigation strategies.
    
    Args:
        org_id: Organization ID
        alert_type: Filter by alert type
        service_name: Filter by service
        
    Returns:
        List of Strategy objects
    """
    from . import store
    
    org = org_id or DEFAULT_ORG_ID
    
    if alert_type:
        strategy = await store.get_strategy(org, alert_type, service_name or "*")
        return [strategy] if strategy else []
    else:
        return await store.list_strategies(org)


# ---------------------------------------------------------------------------
# Extraction Helpers
# ---------------------------------------------------------------------------

def _extract_alert_type_from_prompt(prompt: str) -> str:
    """Best-effort extraction of alert type from prompt text."""
    prompt_lower = prompt.lower()
    
    alert_keywords = {
        "503": "http_503",
        "500": "http_500",
        "404": "http_404",
        "timeout": "timeout",
        "oom": "out_of_memory",
        "out of memory": "out_of_memory",
        "memory": "memory_issue",
        "cpu": "cpu_issue",
        "latency": "high_latency",
        "slow": "high_latency",
        "error": "error",
        "crash": "crash",
        "down": "service_down",
        "unavailable": "service_down",
        "disk": "disk_pressure",
        "connection": "connection_failure",
    }
    
    for keyword, alert_type in alert_keywords.items():
        if keyword in prompt_lower:
            return alert_type
    
    return "unknown"


def _extract_service_from_prompt(prompt: str) -> str:
    """Best-effort extraction of service name from prompt text."""
    prompt_lower = prompt.lower()
    
    for keyword in ["service", "app", "application", "microservice"]:
        idx = prompt_lower.find(keyword)
        if idx > 0:
            words = prompt[:idx].strip().split()
            if words:
                return words[-1].strip(".,;:'\"")
    
    return "unknown"


def _extract_services(
    prompt: str,
    result_text: str,
    hint: str = "",
) -> list[str]:
    """Extract service names from investigation text."""
    if hint:
        return [hint]
    
    service = _extract_service_from_prompt(prompt)
    if service != "unknown":
        return [service]
    
    # Try to find service names in result
    result_service = _extract_service_from_prompt(result_text)
    if result_service != "unknown":
        return [result_service]
    
    return []


def _extract_severity(prompt: str) -> Severity:
    """Assess severity from prompt context."""
    prompt_lower = prompt.lower()
    
    if any(w in prompt_lower for w in ["critical", "down", "outage", "p1", "sev1", "production"]):
        return Severity.CRITICAL
    if any(w in prompt_lower for w in ["warning", "degraded", "slow", "p2", "sev2"]):
        return Severity.WARNING
    
    return Severity.INFO


def _text_indicates_resolution(text: str) -> bool:
    """Check if investigation text indicates resolution."""
    text_lower = text.lower()
    
    resolution_indicators = [
        "root cause",
        "identified",
        "resolved",
        "found the issue",
        "solution",
        "the issue was",
        "caused by",
        "due to",
        "fixed",
    ]
    
    return any(indicator in text_lower for indicator in resolution_indicators)


def _extract_skills_used(tool_calls: list[dict[str, Any]]) -> list[str]:
    """Extract skill names from tool call data."""
    skills = set()
    
    for tc in tool_calls:
        tool_name = tc.get("tool_name", "")
        
        if tool_name == "Skill":
            tool_input = tc.get("tool_input", {})
            if isinstance(tool_input, dict):
                skill_name = tool_input.get("skill", "")
                if skill_name:
                    skills.add(skill_name)
            elif isinstance(tool_input, str):
                skills.add(tool_input[:64])
        elif tool_name:
            # Also track other tool names
            skills.add(tool_name.lower())
    
    return sorted(skills)


def _extract_key_findings(tool_calls: list[dict[str, Any]]) -> list[KeyFinding]:
    """Extract key findings from tool calls with significant output."""
    findings = []
    
    for tc in tool_calls:
        output = tc.get("tool_output", "")
        if not output or len(str(output)) < 50:
            continue
        
        tool_name = tc.get("tool_name", "unknown")
        
        # Only capture certain tool types as findings
        if tool_name not in ("Skill", "Bash", "prometheus", "logs", "kubectl"):
            continue
        
        skill_name = ""
        if tool_name == "Skill" and isinstance(tc.get("tool_input"), dict):
            skill_name = tc["tool_input"].get("skill", "")
        
        findings.append(KeyFinding(
            skill=skill_name or tool_name,
            query=str(tc.get("tool_input", ""))[:500],
            finding=str(output)[:2000],
        ))
    
    return findings[:10]  # Limit to 10


async def _extract_root_cause(result_text: str) -> Optional[str]:
    """Extract concise root cause from investigation result."""
    # Look for explicit root cause statements
    result_lower = result_text.lower()
    
    indicators = [
        "root cause:",
        "root cause is",
        "caused by",
        "the issue was",
        "the problem was",
        "due to",
    ]
    
    for indicator in indicators:
        idx = result_lower.find(indicator)
        if idx >= 0:
            # Extract the sentence containing the root cause
            start = idx
            end = min(idx + 500, len(result_text))
            
            # Find sentence end
            for terminator in [".", "\n\n", "\n-", "\n*"]:
                term_idx = result_text.find(terminator, idx + len(indicator))
                if term_idx > 0 and term_idx < end:
                    end = term_idx + 1
                    break
            
            root_cause = result_text[start:end].strip()
            if len(root_cause) > 20:
                return root_cause[:500]
    
    return None


async def _extract_summary(prompt: str, result_text: str) -> Optional[str]:
    """Extract a brief investigation summary."""
    # Try to find conclusion or summary section
    result_lower = result_text.lower()
    
    for marker in ["## summary", "## conclusion", "in summary", "to summarize"]:
        idx = result_lower.find(marker)
        if idx >= 0:
            start = idx + len(marker)
            end = min(start + 500, len(result_text))
            
            # Find section end
            next_header = result_text.find("\n#", start)
            if next_header > 0 and next_header < end:
                end = next_header
            
            summary = result_text[start:end].strip().strip(":")
            if len(summary) > 20:
                return summary[:500]
    
    # Fallback: use first substantive paragraph of result
    paragraphs = result_text.split("\n\n")
    for para in paragraphs:
        para = para.strip()
        if len(para) > 50 and not para.startswith("#"):
            return para[:500]
    
    return None
