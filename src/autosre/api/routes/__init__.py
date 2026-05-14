"""API Routes Package.

Contains all route modules for the AutoSRE API.
"""

from autosre.api.routes import (
    alerts,
    chat,
    health,
    investigations,
    runbooks,
    webhooks,
)

__all__ = [
    "alerts",
    "chat",
    "health",
    "investigations",
    "runbooks",
    "webhooks",
]
