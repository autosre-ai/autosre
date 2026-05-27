"""
Memory hint formatting for agent system prompts.

Fetches similar episodes and strategies from the memory store
and formats them as text for injection into agent prompts.
"""

import logging
from typing import Optional

from .models import Episode, Strategy

logger = logging.getLogger(__name__)


async def format_memory_hints_for_prompt(
    service_name: str,
    alert_type: str,
    skill_id: str = "sre-agent",
    org_id: str = "default",
    max_episodes: int = 3,
) -> Optional[str]:
    """
    Format memory hints as text suitable for injection into an agent's system prompt.
    
    Searches for similar episodes and strategies, then formats them
    into a concise markdown section that can be prepended to prompts.
    
    Args:
        service_name: Name of the service being investigated
        alert_type: Type of alert
        skill_id: ID of the skill/agent requesting hints
        org_id: Organization ID
        max_episodes: Maximum similar episodes to include
        
    Returns:
        Formatted hint text in markdown, or None if no relevant hints found
        
    Example:
        ```python
        hints = await format_memory_hints_for_prompt(
            service_name="api-gateway",
            alert_type="high_latency",
        )
        if hints:
            system_prompt = f"{hints}\n\n{base_system_prompt}"
        ```
    """
    if not service_name or not alert_type:
        return None
    
    try:
        from .integration import search_similar, get_strategies
        
        # Find similar past episodes
        results = await search_similar(
            prompt="",
            org_id=org_id,
            service_name=service_name,
            alert_type=alert_type,
            limit=max_episodes,
        )
        
        # Get cached strategies
        strategies = await get_strategies(
            org_id=org_id,
            alert_type=alert_type,
            service_name=service_name,
        )
        
        if not results and not strategies:
            return None
        
        lines = ["## Memory-Based Investigation Hints\n"]
        lines.append(
            f"Based on past investigations for **{service_name}** ({alert_type}):\n"
        )
        
        if results:
            lines.append("### Past Similar Episodes\n")
            for result in results:
                ep = result.episode
                status = "✅ resolved" if ep.resolved else "⏳ unresolved"
                root = ep.root_cause or "unknown"
                effectiveness = f"{ep.effectiveness_score:.0%}" if ep.effectiveness_score else "N/A"
                
                lines.append(f"- **[{status}]** Root cause: {root}")
                lines.append(f"  - Skills used: {', '.join(ep.skills_used[:3]) or 'N/A'}")
                lines.append(f"  - Effectiveness: {effectiveness}")
                if result.match_reasons:
                    lines.append(f"  - Match: {', '.join(result.match_reasons)}")
            lines.append("")
        
        if strategies:
            for strategy in strategies:
                if strategy.strategy_text:
                    lines.append("### Investigation Strategy\n")
                    lines.append(strategy.strategy_text)
                    lines.append("")
                    
                    if strategy.key_skills:
                        lines.append(f"**Recommended skills**: {', '.join(strategy.key_skills[:5])}")
                    if strategy.success_rate:
                        lines.append(f"**Historical success rate**: {strategy.success_rate:.0%}")
                    lines.append("")
        
        result = "\n".join(lines)
        logger.info(
            f"[MEMORY-HINTS] Formatted hints for {skill_id}: "
            f"{len(results)} episodes, {len(strategies)} strategies, "
            f"{len(result)} chars"
        )
        return result
    
    except Exception as e:
        logger.error(f"[MEMORY-HINTS] Failed to format hints: {e}")
        return None


def format_episode_as_context(episode: Episode) -> str:
    """
    Format a single episode as context text.
    
    Args:
        episode: The episode to format
        
    Returns:
        Formatted markdown text describing the episode
    """
    services = ", ".join(episode.services) if episode.services else "unknown"
    status = "Resolved" if episode.resolved else "Unresolved"
    
    lines = [
        f"### Past Investigation: {episode.alert_type}",
        f"- **Services**: {services}",
        f"- **Status**: {status}",
    ]
    
    if episode.root_cause:
        lines.append(f"- **Root cause**: {episode.root_cause}")
    
    if episode.summary:
        lines.append(f"- **Summary**: {episode.summary}")
    
    if episode.skills_used:
        lines.append(f"- **Skills used**: {', '.join(episode.skills_used[:5])}")
    
    if episode.effectiveness_score:
        lines.append(f"- **Effectiveness**: {episode.effectiveness_score:.0%}")
    
    if episode.key_findings:
        lines.append("- **Key findings**:")
        for finding in episode.key_findings[:3]:
            lines.append(f"  - [{finding.skill}] {finding.finding[:100]}...")
    
    return "\n".join(lines)


def format_strategy_as_context(strategy: Strategy) -> str:
    """
    Format a strategy as context text.
    
    Args:
        strategy: The strategy to format
        
    Returns:
        Formatted markdown text describing the strategy
    """
    lines = [
        f"### Investigation Strategy: {strategy.alert_type}",
        f"(Based on {strategy.episode_count} past investigations)\n",
    ]
    
    if strategy.strategy_text:
        lines.append(strategy.strategy_text)
    
    if strategy.common_root_causes:
        lines.append("\n**Common root causes**:")
        for cause in strategy.common_root_causes[:5]:
            lines.append(f"- {cause}")
    
    if strategy.recommended_steps:
        lines.append("\n**Recommended steps**:")
        for i, step in enumerate(strategy.recommended_steps[:5], 1):
            lines.append(f"{i}. {step}")
    
    if strategy.key_skills:
        lines.append(f"\n**Key skills**: {', '.join(strategy.key_skills[:5])}")
    
    if strategy.anti_patterns:
        lines.append("\n**Avoid**:")
        for pattern in strategy.anti_patterns[:3]:
            lines.append(f"- ❌ {pattern}")
    
    if strategy.success_rate:
        lines.append(f"\n**Historical success rate**: {strategy.success_rate:.0%}")
    
    return "\n".join(lines)


async def get_investigation_hints(
    service_name: str,
    alert_type: str,
    org_id: str = "default",
) -> dict:
    """
    Get structured investigation hints (not formatted text).
    
    Returns a dictionary with episodes and strategies that can be
    used for structured processing rather than prompt injection.
    
    Args:
        service_name: Name of the service being investigated
        alert_type: Type of alert
        org_id: Organization ID
        
    Returns:
        Dictionary with 'episodes' and 'strategies' lists
    """
    try:
        from .integration import search_similar, get_strategies
        
        results = await search_similar(
            prompt="",
            org_id=org_id,
            service_name=service_name,
            alert_type=alert_type,
            limit=5,
        )
        
        strategies = await get_strategies(
            org_id=org_id,
            alert_type=alert_type,
            service_name=service_name,
        )
        
        return {
            "episodes": [
                {
                    "id": str(r.episode.id),
                    "alert_type": r.episode.alert_type,
                    "services": r.episode.services,
                    "resolved": r.episode.resolved,
                    "root_cause": r.episode.root_cause,
                    "skills_used": r.episode.skills_used,
                    "effectiveness_score": r.episode.effectiveness_score,
                    "similarity_score": r.similarity_score,
                    "match_reasons": r.match_reasons,
                }
                for r in results
            ],
            "strategies": [
                {
                    "id": str(s.id),
                    "alert_type": s.alert_type,
                    "service_name": s.service_name,
                    "strategy_text": s.strategy_text,
                    "common_root_causes": s.common_root_causes,
                    "recommended_steps": s.recommended_steps,
                    "key_skills": s.key_skills,
                    "success_rate": s.success_rate,
                }
                for s in strategies
            ],
        }
    
    except Exception as e:
        logger.error(f"[MEMORY-HINTS] Failed to get hints: {e}")
        return {"episodes": [], "strategies": []}
