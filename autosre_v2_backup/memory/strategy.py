"""
Strategy Generator — Generate investigation strategies from past episodes.

Based on OpenSRE's memory/strategy_generator.py but simplified.
Uses LLM to analyze patterns across similar past investigations.
"""

import logging
from typing import Optional

from .episodic import EpisodicMemory, Episode, Strategy

logger = logging.getLogger(__name__)


STRATEGY_PROMPT = """Analyze these {count} past investigation episodes for "{alert_type}" alerts affecting "{service_name}" and generate a concise investigation strategy.

{episodes_text}

Generate a markdown strategy with these sections:
1. **Common Root Causes** - patterns seen across episodes
2. **Recommended Investigation Steps** - ordered by effectiveness
3. **Key Skills/Commands** - tools that worked well
4. **Anti-patterns** - approaches that didn't help (if any)

Be specific and actionable. Keep it under 300 words.

Strategy:"""


def format_episode_for_prompt(episode: Episode, index: int) -> str:
    """Format a single episode for the strategy prompt."""
    resolved = "RESOLVED" if episode.resolved else "UNRESOLVED"
    skills = ", ".join(episode.skills_used[:5]) if episode.skills_used else "none recorded"
    services = ", ".join(episode.services) if episode.services else episode.service_name or "unknown"
    
    lines = [
        f"Episode {index} [{resolved}]:",
        f"  Services: {services}",
        f"  Skills used: {skills}",
    ]
    
    if episode.root_cause:
        lines.append(f"  Root cause: {episode.root_cause}")
    if episode.summary:
        lines.append(f"  Summary: {episode.summary}")
    if episode.effectiveness_score:
        lines.append(f"  Effectiveness: {episode.effectiveness_score:.0%}")
    
    return "\n".join(lines)


async def generate_strategy(
    episodes: list[Episode],
    alert_type: str,
    service_name: str,
    llm_client: Optional[object] = None,
) -> Optional[str]:
    """Generate an investigation strategy from past episodes.
    
    Args:
        episodes: List of similar past episodes to analyze.
        alert_type: Type of alert being investigated.
        service_name: Name of affected service (or "*" for any).
        llm_client: LLM client for generation (uses default if None).
        
    Returns:
        Generated strategy text, or None if generation fails.
    """
    if len(episodes) < 2:
        logger.info(f"[STRATEGY] Need at least 2 episodes, got {len(episodes)}")
        return None
    
    # Build episode summaries
    episode_summaries = [
        format_episode_for_prompt(ep, i) 
        for i, ep in enumerate(episodes, 1)
    ]
    episodes_text = "\n\n".join(episode_summaries)
    
    prompt = STRATEGY_PROMPT.format(
        count=len(episodes),
        alert_type=alert_type,
        service_name=service_name if service_name != "*" else "any service",
        episodes_text=episodes_text,
    )
    
    # If no LLM client provided, try to import and use default
    if llm_client is None:
        try:
            from autosre.llm import get_llm_client
            llm_client = get_llm_client()
        except ImportError:
            logger.warning("[STRATEGY] LLM client not available, skipping generation")
            return None
    
    try:
        response = await llm_client.complete(
            prompt=prompt,
            max_tokens=500,
            temperature=0.3,
        )
        strategy_text = response.strip()
        
        logger.info(
            f"[STRATEGY] Generated strategy for {alert_type}/{service_name}: "
            f"{len(strategy_text)} chars from {len(episodes)} episodes"
        )
        return strategy_text
        
    except Exception as e:
        logger.error(f"[STRATEGY] Generation failed: {e}")
        return None


async def get_or_generate_strategy(
    memory: EpisodicMemory,
    alert_type: str,
    service_name: str = "*",
    min_episodes: int = 2,
    max_episodes: int = 5,
    llm_client: Optional[object] = None,
) -> Optional[Strategy]:
    """Get cached strategy or generate a new one.
    
    1. Check for cached strategy in memory
    2. If missing, find similar episodes
    3. Generate new strategy via LLM
    4. Cache and return
    
    Args:
        memory: Episodic memory instance.
        alert_type: Type of alert to get strategy for.
        service_name: Service name (or "*" for generic).
        min_episodes: Minimum episodes needed to generate strategy.
        max_episodes: Maximum episodes to use for generation.
        llm_client: Optional LLM client override.
        
    Returns:
        Strategy if found/generated, None otherwise.
    """
    # Check cache first
    cached = memory.get_strategy(alert_type, service_name)
    if cached:
        logger.info(f"[STRATEGY] Found cached strategy for {alert_type}/{service_name}")
        return cached
    
    # Find similar episodes
    episodes = memory.search_similar(
        alert_type=alert_type,
        service_name=service_name if service_name != "*" else "",
        limit=max_episodes,
    )
    
    if len(episodes) < min_episodes:
        logger.info(
            f"[STRATEGY] Not enough episodes ({len(episodes)}/{min_episodes}) "
            f"for {alert_type}/{service_name}"
        )
        return None
    
    # Generate new strategy
    strategy_text = await generate_strategy(
        episodes=episodes,
        alert_type=alert_type,
        service_name=service_name,
        llm_client=llm_client,
    )
    
    if not strategy_text:
        return None
    
    # Cache the strategy
    strategy = Strategy(
        alert_type=alert_type,
        service_name=service_name,
        strategy_text=strategy_text,
        source_episode_ids=[ep.id for ep in episodes],
        episode_count=len(episodes),
    )
    
    memory.store_strategy(strategy)
    return strategy


def enhance_prompt_with_memory(
    prompt: str,
    memory: EpisodicMemory,
    service_name: str = "",
    alert_type: str = "",
    strategy: Optional[Strategy] = None,
    similar_episodes: Optional[list[Episode]] = None,
    max_episodes: int = 3,
) -> str:
    """Enhance investigation prompt with memory context.
    
    Similar to OpenSRE's enhance_investigation_with_memory, prepends
    relevant past investigations and strategies to the prompt.
    
    Args:
        prompt: Original investigation prompt.
        memory: Episodic memory instance.
        service_name: Service being investigated.
        alert_type: Type of alert.
        strategy: Pre-fetched strategy (optional).
        similar_episodes: Pre-fetched episodes (optional).
        max_episodes: Maximum similar episodes to include.
        
    Returns:
        Enhanced prompt with memory context prepended.
    """
    # Find similar episodes if not provided
    if similar_episodes is None:
        similar_episodes = memory.search_similar(
            alert_type=alert_type,
            service_name=service_name,
            limit=max_episodes,
        )
    
    if not similar_episodes and not strategy:
        return prompt
    
    # Build memory context
    lines = ["## Past Investigation Memory\n"]
    
    if similar_episodes:
        lines.append(f"Found {len(similar_episodes)} similar past investigation(s):\n")
        
        for i, ep in enumerate(similar_episodes, 1):
            services = ", ".join(ep.services) if ep.services else ep.service_name or "unknown"
            resolved = "Yes" if ep.resolved else "No"
            
            lines.append(f"### Similar Investigation #{i}")
            lines.append(f"- **Services**: {services}")
            lines.append(f"- **Alert type**: {ep.alert_type}")
            lines.append(f"- **Resolved**: {resolved}")
            
            if ep.root_cause:
                lines.append(f"- **Root cause**: {ep.root_cause}")
            if ep.summary:
                lines.append(f"- **Summary**: {ep.summary}")
            if ep.skills_used:
                lines.append(f"- **Skills used**: {', '.join(ep.skills_used[:5])}")
            if ep.effectiveness_score:
                lines.append(f"- **Effectiveness**: {ep.effectiveness_score:.0%}")
            lines.append("")
    
    if strategy:
        lines.append("## Investigation Strategy (from past investigations)\n")
        lines.append(strategy.strategy_text)
        lines.append("")
    
    memory_context = "\n".join(lines)
    
    logger.info(
        f"[MEMORY] Enhanced prompt with {len(similar_episodes)} episodes, "
        f"strategy={'yes' if strategy else 'no'} ({len(memory_context)} chars)"
    )
    
    return f"{memory_context}\n---\n\n{prompt}"
