"""
Memory Lookup Node

Searches for similar past investigations and generates investigation strategies
based on episodic memory from the memory service.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def memory_lookup(state: dict) -> dict:
    """Search for similar past investigations.
    
    Uses the memory service to find relevant past episodes.
    Results are stored in state.memory_context for use by the planner.
    
    Args:
        state: Current graph state with 'alert' field
        
    Returns:
        State update with 'memory_context' containing past episode info
    """
    alert = state.get("alert", {})
    
    # Extract search parameters from alert
    service_name = alert.get("service", "")
    alert_type = alert.get("name", "")
    description = alert.get("description", "")
    
    # Build search text
    search_text = f"{alert_type}: {description}" if description else str(alert)
    
    try:
        # Try to get memory context from memory service
        memory_context = _search_similar_episodes(
            search_text=search_text,
            service_name=service_name,
            alert_type=alert_type,
        )
        
        logger.info(
            f"[MEMORY] Lookup complete: "
            f"similar_episodes={memory_context.get('has_similar_episodes', False)}"
        )
        
        return {"memory_context": memory_context}
        
    except Exception as e:
        logger.warning(f"[MEMORY] Lookup failed: {e}")
        return {
            "memory_context": {
                "enhanced_prompt": "",
                "has_similar_episodes": False,
                "error": str(e),
            }
        }


def _search_similar_episodes(
    search_text: str,
    service_name: str = "",
    alert_type: str = "",
) -> dict[str, Any]:
    """Search memory service for similar past episodes.
    
    Args:
        search_text: Text to search for (alert description)
        service_name: Optional service name to filter by
        alert_type: Optional alert type to filter by
        
    Returns:
        Dict with memory context including enhanced_prompt if similar episodes found
    """
    memory_service_url = os.getenv("MEMORY_SERVICE_URL", "")
    
    if not memory_service_url:
        # Memory service not configured - return empty context
        return {
            "enhanced_prompt": "",
            "has_similar_episodes": False,
        }
    
    try:
        resp = httpx.post(
            f"{memory_service_url}/api/v1/memory/search",
            json={
                "prompt": search_text,
                "service_name": service_name,
                "alert_type": alert_type,
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()
        
        results = data.get("results", [])
        if not results:
            return {
                "enhanced_prompt": "",
                "has_similar_episodes": False,
            }
        
        # Build enhanced prompt from similar episodes
        enhanced_parts = [
            "## Similar Past Investigations\n",
            "These past investigations may provide helpful context:\n\n",
        ]
        
        for i, episode in enumerate(results[:3], 1):
            enhanced_parts.append(f"### Episode {i}: {episode.get('title', 'Unknown')}\n")
            enhanced_parts.append(f"- **Service**: {episode.get('service_name', 'N/A')}\n")
            enhanced_parts.append(f"- **Alert Type**: {episode.get('alert_type', 'N/A')}\n")
            enhanced_parts.append(f"- **Outcome**: {episode.get('outcome', 'N/A')}\n")
            if episode.get("root_cause"):
                enhanced_parts.append(f"- **Root Cause**: {episode['root_cause']}\n")
            if episode.get("key_findings"):
                enhanced_parts.append(f"- **Key Findings**: {episode['key_findings']}\n")
            enhanced_parts.append("\n")
        
        # Also get strategies if available
        strategies = _get_strategies(memory_service_url, alert_type, service_name)
        if strategies:
            enhanced_parts.append("## Investigation Strategies\n")
            for strategy in strategies[:2]:
                enhanced_parts.append(f"- {strategy}\n")
        
        return {
            "enhanced_prompt": "".join(enhanced_parts),
            "has_similar_episodes": True,
            "episode_count": len(results),
        }
        
    except Exception as e:
        logger.warning(f"[MEMORY] Memory service search failed: {e}")
        return {
            "enhanced_prompt": "",
            "has_similar_episodes": False,
            "error": str(e),
        }


def _get_strategies(
    memory_service_url: str,
    alert_type: str = "",
    service_name: str = "",
) -> list[str]:
    """Get investigation strategies from memory service."""
    try:
        resp = httpx.get(
            f"{memory_service_url}/api/v1/memory/strategies",
            params={"alert_type": alert_type, "service_name": service_name},
            timeout=5.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("strategies", [])
    except Exception:
        return []
