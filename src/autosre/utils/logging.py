"""
Structured logging for AutoSRE V2.

Provides JSON-formatted logging with context tracking, correlation IDs,
and integration with common observability tools.
"""

from __future__ import annotations

import json
import logging
import sys
import traceback
from contextvars import ContextVar
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

# Context variables for request/investigation tracking
correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)
investigation_id_var: ContextVar[str | None] = ContextVar("investigation_id", default=None)
agent_id_var: ContextVar[str | None] = ContextVar("agent_id", default=None)


class StructuredFormatter(logging.Formatter):
    """
    JSON formatter with structured context.

    Outputs log records as JSON with consistent fields for
    easy parsing by log aggregation tools.
    """

    def __init__(
        self,
        include_timestamp: bool = True,
        include_caller: bool = True,
        extra_fields: dict[str, Any] | None = None,
    ):
        super().__init__()
        self.include_timestamp = include_timestamp
        self.include_caller = include_caller
        self.extra_fields = extra_fields or {}

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_entry: dict[str, Any] = {
            "level": record.levelname.lower(),
            "message": record.getMessage(),
            "logger": record.name,
        }

        # Timestamp
        if self.include_timestamp:
            log_entry["timestamp"] = datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat()

        # Caller info
        if self.include_caller:
            log_entry["caller"] = {
                "file": record.pathname,
                "line": record.lineno,
                "function": record.funcName,
            }

        # Context variables
        if correlation_id := correlation_id_var.get():
            log_entry["correlation_id"] = correlation_id
        if investigation_id := investigation_id_var.get():
            log_entry["investigation_id"] = investigation_id
        if agent_id := agent_id_var.get():
            log_entry["agent_id"] = agent_id

        # Exception info
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": traceback.format_exception(*record.exc_info),
            }

        # Extra fields from record
        for key, value in record.__dict__.items():
            if key.startswith("_") or key in (
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "pathname", "process", "processName", "relativeCreated",
                "stack_info", "exc_info", "exc_text", "thread", "threadName",
                "message", "taskName",
            ):
                continue
            log_entry[key] = value

        # Static extra fields
        log_entry.update(self.extra_fields)

        return json.dumps(log_entry, default=str, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    """Human-readable formatter for development."""

    COLORS = {
        "DEBUG": "\033[36m",    # Cyan
        "INFO": "\033[32m",     # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",    # Red
        "CRITICAL": "\033[35m", # Magenta
    }
    RESET = "\033[0m"

    def __init__(self, use_colors: bool = True):
        super().__init__()
        self.use_colors = use_colors and sys.stderr.isatty()

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as human-readable text."""
        timestamp = datetime.fromtimestamp(
            record.created, tz=timezone.utc
        ).strftime("%Y-%m-%d %H:%M:%S")

        level = record.levelname
        if self.use_colors:
            color = self.COLORS.get(level, "")
            level = f"{color}{level}{self.RESET}"

        # Build context string
        context_parts = []
        if correlation_id := correlation_id_var.get():
            context_parts.append(f"corr={correlation_id[:8]}")
        if investigation_id := investigation_id_var.get():
            context_parts.append(f"inv={investigation_id[:8]}")
        if agent_id := agent_id_var.get():
            context_parts.append(f"agent={agent_id}")

        context = f" [{', '.join(context_parts)}]" if context_parts else ""

        # Format message
        message = f"{timestamp} | {level:8} | {record.name}{context} | {record.getMessage()}"

        # Add exception if present
        if record.exc_info:
            message += "\n" + "".join(traceback.format_exception(*record.exc_info))

        return message


class LoggerAdapter(logging.LoggerAdapter):
    """
    Logger adapter with context support.

    Allows adding extra context to log records without modifying
    the underlying logger.
    """

    def __init__(self, logger: logging.Logger, extra: dict[str, Any] | None = None):
        super().__init__(logger, extra or {})

    def process(
        self, msg: str, kwargs: dict[str, Any]
    ) -> tuple[str, dict[str, Any]]:
        """Process log message with extra context."""
        extra = kwargs.get("extra", {})
        extra.update(self.extra)
        kwargs["extra"] = extra
        return msg, kwargs

    def with_context(self, **context: Any) -> LoggerAdapter:
        """Create a new adapter with additional context."""
        new_extra = {**self.extra, **context}
        return LoggerAdapter(self.logger, new_extra)


_loggers: dict[str, LoggerAdapter] = {}
_setup_done = False


def setup_logging(
    level: str = "INFO",
    format: str = "json",
    include_timestamp: bool = True,
    include_caller: bool = True,
) -> None:
    """
    Configure logging for AutoSRE.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format: Output format ('json' or 'text')
        include_timestamp: Include timestamp in output
        include_caller: Include caller info in output
    """
    global _setup_done

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create handler
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(getattr(logging, level.upper()))

    # Set formatter
    if format.lower() == "json":
        formatter = StructuredFormatter(
            include_timestamp=include_timestamp,
            include_caller=include_caller,
        )
    else:
        formatter = TextFormatter(use_colors=True)

    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # Reduce noise from external libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("kubernetes").setLevel(logging.WARNING)

    _setup_done = True


@lru_cache(maxsize=100)
def get_logger(name: str) -> LoggerAdapter:
    """
    Get a logger with the given name.

    Creates LoggerAdapter instances for context support.
    Caches loggers for performance.

    Args:
        name: Logger name (usually __name__)

    Returns:
        LoggerAdapter instance
    """
    global _setup_done

    if not _setup_done:
        # Auto-setup with defaults if not already done
        setup_logging()

    if name not in _loggers:
        logger = logging.getLogger(name)
        _loggers[name] = LoggerAdapter(logger)

    return _loggers[name]


class LogContext:
    """
    Context manager for temporary log context.

    Usage:
        with LogContext(correlation_id="abc123", investigation_id="inv-456"):
            logger.info("Processing request")  # Includes context
    """

    def __init__(
        self,
        correlation_id: str | None = None,
        investigation_id: str | None = None,
        agent_id: str | None = None,
    ):
        self.correlation_id = correlation_id
        self.investigation_id = investigation_id
        self.agent_id = agent_id
        self._tokens: list = []

    def __enter__(self) -> LogContext:
        if self.correlation_id:
            self._tokens.append(correlation_id_var.set(self.correlation_id))
        if self.investigation_id:
            self._tokens.append(investigation_id_var.set(self.investigation_id))
        if self.agent_id:
            self._tokens.append(agent_id_var.set(self.agent_id))
        return self

    def __exit__(self, *args: Any) -> None:
        for token in self._tokens:
            # Reset to previous value
            token.var.reset(token)


def set_correlation_id(correlation_id: str) -> None:
    """Set the correlation ID for the current context."""
    correlation_id_var.set(correlation_id)


def set_investigation_id(investigation_id: str) -> None:
    """Set the investigation ID for the current context."""
    investigation_id_var.set(investigation_id)


def set_agent_id(agent_id: str) -> None:
    """Set the agent ID for the current context."""
    agent_id_var.set(agent_id)
