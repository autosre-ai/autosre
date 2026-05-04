"""
AutoSRE Logging - Structured, configurable logging.

Usage:
    from autosre.logging import get_logger, configure_logging
    
    logger = get_logger(__name__)
    logger.info("Processing alert", alert_name="HighCPU", service="api-gateway")
"""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Optional


class StructuredFormatter(logging.Formatter):
    """JSON-structured log formatter for production use."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add extra fields
        if hasattr(record, "extra"):
            log_data.update(record.extra)
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, default=str)


class HumanFormatter(logging.Formatter):
    """Human-readable log formatter for development."""
    
    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"
    
    def __init__(self, use_colors: bool = True):
        super().__init__()
        self.use_colors = use_colors and sys.stderr.isatty()
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record for human readability."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        level = record.levelname
        
        if self.use_colors:
            color = self.COLORS.get(level, "")
            level_str = f"{color}{level:8}{self.RESET}"
        else:
            level_str = f"{level:8}"
        
        message = record.getMessage()
        
        # Format extra fields
        extra_parts = []
        if hasattr(record, "extra") and record.extra:
            for key, value in record.extra.items():
                extra_parts.append(f"{key}={value}")
        
        extra_str = " " + " ".join(extra_parts) if extra_parts else ""
        
        result = f"{timestamp} {level_str} [{record.name}] {message}{extra_str}"
        
        # Add exception if present
        if record.exc_info:
            result += "\n" + self.formatException(record.exc_info)
        
        return result


class AutoSRELogger(logging.LoggerAdapter):
    """Custom logger adapter that supports structured logging."""
    
    def process(self, msg: str, kwargs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """Process log message to add structured fields."""
        extra = kwargs.pop("extra", {})
        
        # Move any extra kwargs to the extra dict
        for key in list(kwargs.keys()):
            if key not in ("exc_info", "stack_info", "stacklevel"):
                extra[key] = kwargs.pop(key)
        
        # Store extra in the record
        kwargs["extra"] = {"extra": extra}
        
        return msg, kwargs


# Global configuration
_configured = False
_log_format: str = "human"  # "human" or "json"
_log_level: int = logging.INFO


def configure_logging(
    level: str | int = "INFO",
    format: str = "human",
    stream: Optional[Any] = None,
) -> None:
    """
    Configure AutoSRE logging.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format: Output format ("human" for development, "json" for production)
        stream: Output stream (defaults to stderr)
    """
    global _configured, _log_format, _log_level
    
    # Convert string level to int
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)
    
    _log_level = level
    _log_format = format
    
    # Get root autosre logger
    root = logging.getLogger("autosre")
    root.setLevel(level)
    
    # Remove existing handlers
    root.handlers.clear()
    
    # Create handler
    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setLevel(level)
    
    # Set formatter based on format
    if format == "json":
        handler.setFormatter(StructuredFormatter())
    else:
        handler.setFormatter(HumanFormatter())
    
    root.addHandler(handler)
    _configured = True


def get_logger(name: str) -> AutoSRELogger:
    """
    Get a logger for the given module name.
    
    Args:
        name: Module name (typically __name__)
        
    Returns:
        Configured logger adapter
    """
    global _configured
    
    # Auto-configure with defaults if not configured
    if not _configured:
        configure_logging()
    
    # Create logger under autosre namespace
    if not name.startswith("autosre"):
        name = f"autosre.{name}"
    
    logger = logging.getLogger(name)
    return AutoSRELogger(logger, {})


def set_level(level: str | int) -> None:
    """Set the log level globally."""
    global _log_level
    
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)
    
    _log_level = level
    logging.getLogger("autosre").setLevel(level)


# Export convenience functions
__all__ = [
    "get_logger",
    "configure_logging",
    "set_level",
    "AutoSRELogger",
    "StructuredFormatter",
    "HumanFormatter",
]
