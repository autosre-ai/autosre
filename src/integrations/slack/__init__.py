"""
AutoSRE Slack Integration

Slack bot integration for the AutoSRE platform. Enables incident investigation
directly from Slack via mentions and slash commands.

Key Components:
- AutoSRESlackBot: Main bot class with Socket Mode support
- Message formatters: Block Kit formatting for rich messages
- Event handlers: Mention, command, and reaction handling
"""

from .bot import AutoSRESlackBot
from .messages import (
    format_investigation_start,
    format_progress_update,
    format_evidence_found,
    format_investigation_complete,
    format_error,
)
from .handlers import (
    handle_app_mention,
    handle_investigate_command,
    handle_reaction_added,
    handle_thread_reply,
)

__all__ = [
    "AutoSRESlackBot",
    "format_investigation_start",
    "format_progress_update",
    "format_evidence_found",
    "format_investigation_complete",
    "format_error",
    "handle_app_mention",
    "handle_investigate_command",
    "handle_reaction_added",
    "handle_thread_reply",
]
