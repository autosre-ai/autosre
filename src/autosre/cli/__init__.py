"""
AutoSRE CLI - Rich command-line interface.

Provides a beautiful, user-friendly CLI for AI-powered SRE operations:
- investigate: AI-driven incident investigation
- memory: Episodic memory management
- config: Configuration management
- demo: Demo scenarios for testing
"""

from autosre.cli.main import app, main

# Backwards compatibility
cli = main

__all__ = ["app", "main", "cli"]
