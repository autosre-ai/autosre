"""
AutoSRE API Module

Provides REST API and WebSocket support for real-time investigation monitoring.
"""

from autosre.api.websocket import ConnectionManager, get_connection_manager

__all__ = ["ConnectionManager", "get_connection_manager"]
