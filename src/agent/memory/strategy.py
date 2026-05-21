"""
LLM-based investigation strategy generation from past episodes.

Analyzes multiple investigation episodes to synthesize common patterns,
effective approaches, and anti-patterns into actionable strategies.
"""

import logging
import os
from typing import Optional

from .models import Episode, Strategy, StrategyCreate

logger = logging.getLogger(__name__)


async def generate_strategy(
    episodes: list[Episode],
    alert_type: str,
    service_name: str = "*",
) -> Optional[str]:
    """
    Generate an investigation strategy from past episodes using LLM.
    
    Analyzes the provided episodes to identify:
    - Common root causes
    - Effective investigation steps
    - Key skills/tools that work well
    - Anti-patterns to avoid
    
    Args:
        episodes: List of past episodes to analyze
        alert_type: The alert type to generate strategy for
        service_name: Service name or "*" for generic strategy
        
    Returns:
        Strategy text in markdown format, or None if generation fails
    """
    if not episodes:
        logger.warning("[STRATEGY] No episodes provided for strategy generation")
        return None
    
    if len(episodes) < 2:
        logger.info("[STRATEGY] Need at least 2 episodes to generate meaningful strategy")
        return None
    
    # Build episode summaries for the prompt
    episode_summaries = []
    for i, ep in enumerate(episodes, 1):
        resolved = "RESOLVED" if ep.resolved else "UNRESOLVED"
        root_cause = ep.root_cause or "Not identified"
        skills = ", ".join(ep.skills_used[:5]) if ep.skills_used else "none recorded"
        summary = ep.summary or "No summary"
        services = ", ".join(ep.services) if ep.services else "unknown"
        effectiveness = f"{ep.effectiveness_score:.0%}" if ep.effectiveness_score else "N/A"
        
        episode_summaries.append(
            f"Episode {i} [{resolved}] (effectiveness: {effectiveness}):\n"
            f"  Services: {services}\n"
            f"  Skills used: {skills}\n"
            f"  Root cause: {root_cause}\n"
            f"  Summary: {summary}"
        )
    
    episodes_text = "\n\n".join(episode_summaries)
    
    prompt = (
        f'Analyze these {len(episodes)} past investigation episodes for "{alert_type}" '
        f'alerts affecting "{service_name}" and generate a concise investigation strategy.\n\n'
        f"{episodes_text}\n\n"
        "Generate a markdown strategy with these sections:\n"
        "1. **Common Root Causes** - patterns seen across episodes\n"
        "2. **Recommended Investigation Steps** - ordered by effectiveness\n"
        "3. **Key Skills/Commands** - tools that worked well\n"
        "4. **Anti-patterns** - approaches that didn't help\n\n"
        "Be specific and actionable. Keep it under 300 words.\n\nStrategy:"
    )
    
    try:
        strategy_text = await _llm_completion(prompt, max_tokens=500)
        if strategy_text:
            logger.info(
                f"[STRATEGY] Generated strategy for {alert_type}/{service_name}: "
                f"{len(strategy_text)} chars from {len(episodes)} episodes"
            )
        return strategy_text
    except Exception as e:
        logger.error(f"[STRATEGY] LLM call failed: {e}")
        return None


async def get_cached_strategy(
    org_id: str,
    alert_type: str,
    service_name: str = "*",
) -> Optional[Strategy]:
    """
    Get a cached strategy from the database.
    
    This is a convenience wrapper around store.get_strategy().
    
    Args:
        org_id: Organization ID
        alert_type: Alert type to look up
        service_name: Service name or "*" for any
        
    Returns:
        The cached Strategy if found and not expired, None otherwise
    """
    from . import store
    
    return await store.get_strategy(org_id, alert_type, service_name)


async def generate_and_cache_strategy(
    org_id: str,
    alert_type: str,
    service_name: str = "*",
    team_node_id: Optional[str] = None,
    min_episodes: int = 2,
    max_episodes: int = 10,
) -> Optional[Strategy]:
    """
    Generate a strategy from recent episodes and cache it.
    
    Fetches recent episodes, generates a strategy via LLM, and stores
    the result in the database for future use.
    
    Args:
        org_id: Organization ID
        alert_type: Alert type to generate strategy for
        service_name: Service name or "*" for generic
        team_node_id: Optional team identifier
        min_episodes: Minimum episodes required to generate
        max_episodes: Maximum episodes to analyze
        
    Returns:
        The generated and cached Strategy, or None if insufficient data
    """
    from . import store
    
    # Check for existing valid strategy first
    existing = await store.get_strategy(org_id, alert_type, service_name)
    if existing:
        logger.info(f"[STRATEGY] Using cached strategy for {alert_type}/{service_name}")
        return existing
    
    # Fetch recent episodes for this alert type
    episodes = await store.list_episodes(
        org_id=org_id,
        alert_type=alert_type,
        service_name=service_name if service_name != "*" else None,
        limit=max_episodes,
    )
    
    if len(episodes) < min_episodes:
        logger.info(
            f"[STRATEGY] Not enough episodes for {alert_type}/{service_name}: "
            f"{len(episodes)} < {min_episodes}"
        )
        return None
    
    # Generate strategy
    strategy_text = await generate_strategy(episodes, alert_type, service_name)
    if not strategy_text:
        return None
    
    # Extract structured data from strategy text
    common_causes, steps, skills, antipatterns = _parse_strategy_sections(strategy_text)
    
    # Store the strategy
    strategy = await store.upsert_strategy(StrategyCreate(
        org_id=org_id,
        team_node_id=team_node_id,
        alert_type=alert_type,
        service_name=service_name,
        strategy_text=strategy_text,
        source_episode_ids=[ep.id for ep in episodes],
        episode_count=len(episodes),
    ))
    
    # Add parsed sections
    strategy.common_root_causes = common_causes
    strategy.recommended_steps = steps
    strategy.key_skills = skills
    strategy.anti_patterns = antipatterns
    
    # Calculate success rate
    resolved_count = sum(1 for ep in episodes if ep.resolved)
    strategy.success_rate = resolved_count / len(episodes) if episodes else 0.0
    
    # Calculate average resolution time
    times = [ep.duration_seconds for ep in episodes if ep.duration_seconds]
    if times:
        strategy.avg_resolution_time = sum(times) / len(times)
    
    return strategy


def _parse_strategy_sections(text: str) -> tuple[list[str], list[str], list[str], list[str]]:
    """
    Parse structured sections from strategy markdown text.
    
    Returns:
        Tuple of (common_causes, steps, skills, antipatterns)
    """
    common_causes: list[str] = []
    steps: list[str] = []
    skills: list[str] = []
    antipatterns: list[str] = []
    
    current_section = None
    
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        
        line_lower = line.lower()
        
        # Detect section headers
        if "common root cause" in line_lower or "root causes" in line_lower:
            current_section = "causes"
        elif "recommended" in line_lower or "investigation steps" in line_lower:
            current_section = "steps"
        elif "key skills" in line_lower or "commands" in line_lower:
            current_section = "skills"
        elif "anti-pattern" in line_lower or "avoid" in line_lower:
            current_section = "antipatterns"
        elif line.startswith("-") or line.startswith("*") or line.startswith("1"):
            # Extract list item content
            item = line.lstrip("-*0123456789.").strip()
            if item and current_section:
                if current_section == "causes":
                    common_causes.append(item)
                elif current_section == "steps":
                    steps.append(item)
                elif current_section == "skills":
                    skills.append(item)
                elif current_section == "antipatterns":
                    antipatterns.append(item)
    
    return common_causes, steps, skills, antipatterns


async def _llm_completion(prompt: str, max_tokens: int = 500) -> Optional[str]:
    """
    Call LLM for text completion.
    
    Uses environment configuration to determine which LLM provider to use.
    Falls back gracefully if LLM is unavailable.
    """
    # Try to use the project's LLM infrastructure if available
    try:
        from autosre.llm import get_llm_client
        
        client = get_llm_client()
        response = await client.complete(prompt, max_tokens=max_tokens)
        return response.strip() if response else None
    except ImportError:
        pass
    
    # Fallback: Try httpx to call an LLM API directly
    try:
        import httpx
        
        llm_api_url = os.getenv("LLM_API_URL")
        llm_api_key = os.getenv("LLM_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
        
        if not llm_api_url or not llm_api_key:
            logger.warning("[STRATEGY] No LLM API configured, skipping strategy generation")
            return None
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                llm_api_url,
                headers={"Authorization": f"Bearer {llm_api_key}"},
                json={
                    "model": os.getenv("MEMORY_LLM_MODEL", "claude-haiku-4-5-20251001"),
                    "max_tokens": max_tokens,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            response.raise_for_status()
            data = response.json()
            
            # Handle Anthropic format
            if "content" in data and isinstance(data["content"], list):
                return data["content"][0].get("text", "")
            # Handle OpenAI format
            if "choices" in data:
                return data["choices"][0].get("message", {}).get("content", "")
            
            return None
    except Exception as e:
        logger.error(f"[STRATEGY] LLM API call failed: {e}")
        return None


async def refresh_stale_strategies(
    org_id: str,
    min_episodes: int = 2,
) -> list[Strategy]:
    """
    Refresh strategies that have expired or are close to expiring.
    
    This can be called periodically to keep strategies up to date.
    
    Args:
        org_id: Organization ID
        min_episodes: Minimum episodes required to regenerate
        
    Returns:
        List of refreshed strategies
    """
    from datetime import datetime, timedelta
    from . import store
    
    # Get strategies expiring within 24 hours
    strategies = await store.list_strategies(org_id, include_expired=True)
    
    refreshed = []
    threshold = datetime.utcnow() + timedelta(hours=24)
    
    for strategy in strategies:
        if strategy.expires_at and strategy.expires_at < threshold:
            logger.info(f"[STRATEGY] Refreshing expired strategy: {strategy.alert_type}/{strategy.service_name}")
            new_strategy = await generate_and_cache_strategy(
                org_id=org_id,
                alert_type=strategy.alert_type,
                service_name=strategy.service_name,
                team_node_id=strategy.team_node_id,
                min_episodes=min_episodes,
            )
            if new_strategy:
                refreshed.append(new_strategy)
    
    return refreshed
