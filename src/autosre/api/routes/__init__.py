"""
API Routes Module

Contains all API route definitions including REST and WebSocket endpoints.
"""

from autosre.api.routes.ws import router as ws_router

__all__ = ["ws_router"]
