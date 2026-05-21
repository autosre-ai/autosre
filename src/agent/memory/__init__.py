"""
AutoSRE Episodic Memory System.

Provides memory-enhanced investigation capabilities by storing and learning
from past incidents. The system:

1. **Stores Episodes**: Records completed investigations with context, tools used,
   findings, and outcomes.

2. **Learns Strategies**: Synthesizes investigation strategies from multiple
   episodes using LLM analysis.

3. **Enhances Investigations**: Provides relevant context from past similar
   investigations to guide new ones.

Usage:
    ```python
    from agent.memory import (
        enhance_investigation_with_memory,
        store_investigation_result,
        get_memory_stats,
        format_memory_hints_for_prompt,
    )
    
    # Before investigation: enhance prompt with memory context
    enhanced_prompt = await enhance_investigation_with_memory(
        prompt="API latency is high",
        service_name="api-gateway",
        alert_type="high_latency",
    )
    
    # After investigation: store the result
    episode = await store_investigation_result(
        thread_id="thread-123",
        prompt=prompt,
        result_text=investigation_result,
        success=True,
    )
    
    # Check memory stats
    stats = await get_memory_stats()
    ```
"""

from .models import (
    Episode,
    EpisodeCreate,
    EpisodeUpdate,
    KeyFinding,
    MemorySearchResult,
    MemoryStats,
    Severity,
    Strategy,
    StrategyCreate,
    AlertType,
)

from .integration import (
    enhance_investigation_with_memory,
    store_investigation_result,
    get_memory_stats,
    get_all_episodes,
    search_similar,
    get_strategies,
)

from .hints import (
    format_memory_hints_for_prompt,
    format_episode_as_context,
    format_strategy_as_context,
    get_investigation_hints,
)

from .strategy import (
    generate_strategy,
    get_cached_strategy,
    generate_and_cache_strategy,
    refresh_stale_strategies,
)

from .store import (
    get_pool,
    close_pool,
    store_episode,
    get_episode,
    update_episode,
    list_episodes,
    delete_episode,
    store_strategy,
    get_strategy,
    upsert_strategy,
    list_strategies,
)

__all__ = [
    # Models
    "Episode",
    "EpisodeCreate",
    "EpisodeUpdate",
    "KeyFinding",
    "MemorySearchResult",
    "MemoryStats",
    "Severity",
    "Strategy",
    "StrategyCreate",
    "AlertType",
    # Integration (high-level API)
    "enhance_investigation_with_memory",
    "store_investigation_result",
    "get_memory_stats",
    "get_all_episodes",
    "search_similar",
    "get_strategies",
    # Hints
    "format_memory_hints_for_prompt",
    "format_episode_as_context",
    "format_strategy_as_context",
    "get_investigation_hints",
    # Strategy generation
    "generate_strategy",
    "get_cached_strategy",
    "generate_and_cache_strategy",
    "refresh_stale_strategies",
    # Store (low-level API)
    "get_pool",
    "close_pool",
    "store_episode",
    "get_episode",
    "update_episode",
    "list_episodes",
    "delete_episode",
    "store_strategy",
    "get_strategy",
    "upsert_strategy",
    "list_strategies",
]
