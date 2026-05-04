"""
AutoSRE LLM Module

LLM routing and abstraction for different providers.
"""
from .router import LLMRouter

_router_instance = None

def get_router() -> LLMRouter:
    """Get or create the global LLM router instance."""
    global _router_instance
    if _router_instance is None:
        _router_instance = LLMRouter()
    return _router_instance

__all__ = ["LLMRouter", "get_router"]
