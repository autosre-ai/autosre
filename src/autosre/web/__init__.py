"""
AutoSRE Web Dashboard

A simple, powerful web UI for managing AutoSRE:
- System status at a glance
- Eval scenario management
- Context store browsing
- Agent activity monitoring
- Feedback submission

Built with FastAPI + HTMX + Tailwind for a fast, responsive experience.
"""

from autosre.web.app import create_app

__all__ = ["create_app"]
