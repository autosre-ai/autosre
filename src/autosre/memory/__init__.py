"""
AutoSRE Memory Module - Episodic memory for incident investigations.

This module provides SQLite-based episodic memory storage that enables AutoSRE
to learn from past investigations. The memory system stores and retrieves
episodes from past incidents, allowing the AI agent to:

- Recall similar incidents when investigating new issues
- Learn from successful resolutions and apply them to new incidents  
- Build strategies based on patterns across incidents
- Improve investigation accuracy over time

Key Components:
    Episode: A single investigation episode with symptoms, root cause, and resolution.
    Strategy: A learned investigation strategy based on past episodes.
    MemoryQuery: Query parameters for searching the memory store.
    EpisodicMemory: The main memory storage class with FTS5 search.

Example:
    >>> from autosre.memory import EpisodicMemory, Episode
    >>> memory = EpisodicMemory()
    >>> episodes = memory.search_similar("http_5xx", service="checkout")
    >>> stats = memory.get_stats()
"""

from .models import Episode, Strategy, MemoryQuery
from .episodic import EpisodicMemory

__all__ = ["Episode", "Strategy", "MemoryQuery", "EpisodicMemory"]
