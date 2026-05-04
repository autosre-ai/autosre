"""
AutoSRE CLI - Rich command-line interface.

Provides a beautiful, user-friendly CLI for managing AutoSRE:
- Context management (services, ownership, changes)
- Evaluation scenarios
- Sandbox environments
- Agent operations
"""

from autosre.cli.main import app, main, cli

__all__ = ["app", "main", "cli"]
