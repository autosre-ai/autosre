"""Request logging middleware for AutoSRE API."""

from __future__ import annotations

import logging
import time
import uuid
from typing import TYPE_CHECKING, Any, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

if TYPE_CHECKING:
    from starlette.types import ASGIApp

logger = logging.getLogger("autosre.api")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log all incoming requests with timing and response info.

    Captures request details, response status, and timing information
    for observability and debugging.
    """

    def __init__(
        self,
        app: ASGIApp,
        log_request_body: bool = False,
        log_response_body: bool = False,
        exclude_paths: list[str] | None = None,
        sensitive_headers: list[str] | None = None,
    ) -> None:
        """Initialize request logging middleware.

        Args:
            app: The ASGI application.
            log_request_body: Whether to log request bodies.
            log_response_body: Whether to log response bodies.
            exclude_paths: Paths to exclude from logging (e.g., /health).
            sensitive_headers: Headers to redact from logs.
        """
        super().__init__(app)
        self.log_request_body = log_request_body
        self.log_response_body = log_response_body
        self.exclude_paths = exclude_paths or ["/health", "/ready", "/metrics"]
        self.sensitive_headers = set(
            h.lower()
            for h in (sensitive_headers or ["authorization", "cookie", "x-api-key"])
        )

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Any],
    ) -> Response:
        """Process and log the request/response cycle.

        Args:
            request: The incoming request.
            call_next: The next middleware/handler in the chain.

        Returns:
            The response from the handler.
        """
        # Skip excluded paths
        if request.url.path in self.exclude_paths:
            return await call_next(request)

        # Generate request ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        # Extract request info
        request_info = self._build_request_info(request, request_id)

        # Log request start
        logger.info(
            "Request started",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "event": "request_start",
                **request_info,
            },
        )

        # Time the request
        start_time = time.perf_counter()
        error_detail: str | None = None

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            # Log exception and re-raise
            error_detail = str(e)
            status_code = 500
            raise
        finally:
            # Calculate duration
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Get user info if available
            user_id = None
            if hasattr(request.state, "user"):
                user_id = request.state.user.id

            # Log request completion
            log_data = {
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "duration_ms": round(duration_ms, 2),
                "user_id": user_id,
                "event": "request_complete",
            }

            if error_detail:
                log_data["error"] = error_detail

            log_level = self._get_log_level(status_code)
            logger.log(
                log_level,
                f"Request completed: {request.method} {request.url.path} "
                f"-> {status_code} ({duration_ms:.2f}ms)",
                extra=log_data,
            )

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        return response

    def _build_request_info(
        self,
        request: Request,
        request_id: str,
    ) -> dict[str, Any]:
        """Build a dictionary of request information for logging.

        Args:
            request: The incoming request.
            request_id: The request ID.

        Returns:
            Dictionary of request metadata.
        """
        # Safely extract headers, redacting sensitive ones
        headers = {}
        for key, value in request.headers.items():
            if key.lower() in self.sensitive_headers:
                headers[key] = "[REDACTED]"
            else:
                headers[key] = value

        # Extract client info
        client_host = None
        client_port = None
        if request.client:
            client_host = request.client.host
            client_port = request.client.port

        return {
            "client_host": client_host,
            "client_port": client_port,
            "query_params": dict(request.query_params),
            "headers": headers if logger.isEnabledFor(logging.DEBUG) else None,
            "content_type": request.headers.get("content-type"),
            "content_length": request.headers.get("content-length"),
            "user_agent": request.headers.get("user-agent"),
        }

    def _get_log_level(self, status_code: int) -> int:
        """Determine log level based on status code.

        Args:
            status_code: HTTP status code.

        Returns:
            Logging level constant.
        """
        if status_code >= 500:
            return logging.ERROR
        elif status_code >= 400:
            return logging.WARNING
        else:
            return logging.INFO


class StructuredLogFormatter(logging.Formatter):
    """JSON-structured log formatter for production use.

    Outputs logs in a structured JSON format suitable for
    log aggregation systems like ELK, Loki, or CloudWatch.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.

        Args:
            record: The log record.

        Returns:
            JSON-formatted log string.
        """
        import json

        log_data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add extra fields from record
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        if hasattr(record, "method"):
            log_data["method"] = record.method
        if hasattr(record, "path"):
            log_data["path"] = record.path
        if hasattr(record, "status_code"):
            log_data["status_code"] = record.status_code
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id
        if hasattr(record, "event"):
            log_data["event"] = record.event

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def setup_logging(
    level: int = logging.INFO,
    structured: bool = False,
) -> None:
    """Configure logging for the API.

    Args:
        level: Logging level.
        structured: Whether to use structured JSON logging.
    """
    handler = logging.StreamHandler()

    if structured:
        handler.setFormatter(StructuredLogFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
        )

    # Configure API logger
    api_logger = logging.getLogger("autosre.api")
    api_logger.setLevel(level)
    api_logger.addHandler(handler)
    api_logger.propagate = False
