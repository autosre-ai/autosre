"""
AutoSRE CLI - Rich command-line interface.

Provides a beautiful, user-friendly CLI for AI-powered SRE operations:

Investigation & Analysis:
- run: Quick shortcut to start an investigation
- investigate: Full investigation commands (run, history, replay)
- chat: Interactive AI assistant for SRE questions
- demo: Demo scenarios for testing without real infrastructure

Memory & Learning:
- memory: Episodic memory management (search, list, stats)
- history: Browse past investigations

Configuration & Management:
- config: Configuration management
- model: AI model configuration (list, use, test)
- doctor: Health checks and diagnostics
- status: System status overview

Operations:
- serve: Webhook server for alert-driven investigations
- runbook: Runbook management and execution
- template: Investigation templates for common incidents
- agent: Autonomous agent for monitoring

Utilities:
- tutorial: Interactive onboarding
- benchmark: Performance testing
- plugin: Plugin management
- team: Team collaboration

Example:
    >>> from autosre.cli import main
    >>> main()  # Start CLI
"""

from autosre.cli.main import app, main

# Backwards compatibility
cli = main

__all__ = ["app", "main", "cli"]
