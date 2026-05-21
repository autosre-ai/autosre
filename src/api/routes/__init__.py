"""AutoSRE API Routes."""

from .investigate import router as investigate_router
from .memory import router as memory_router
from .config import router as config_router
from .health import router as health_router
from .webhooks import pagerduty_router, configure_webhook_handler

__all__ = [
    "investigate_router",
    "memory_router",
    "config_router",
    "health_router",
    "pagerduty_router",
    "configure_webhook_handler",
]
