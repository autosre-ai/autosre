"""API Middleware for AutoSRE V2.

Provides authentication, logging, error handling, and rate limiting.
"""

from autosre.api.middleware.auth import (
    JWTAuth,
    get_current_user,
    require_role,
)
from autosre.api.middleware.errors import ErrorHandlerMiddleware
from autosre.api.middleware.logging import RequestLoggingMiddleware
from autosre.api.middleware.ratelimit import RateLimitMiddleware

__all__ = [
    "JWTAuth",
    "get_current_user",
    "require_role",
    "ErrorHandlerMiddleware",
    "RequestLoggingMiddleware",
    "RateLimitMiddleware",
]
