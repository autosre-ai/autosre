"""
Tests for structured logging module.
"""

import pytest
import json
import logging
import io
from unittest.mock import patch, MagicMock

from autosre.logging import (
    StructuredFormatter,
    HumanFormatter,
    AutoSRELogger,
    configure_logging,
    get_logger,
    set_level,
)


class TestStructuredFormatter:
    """Tests for JSON structured formatter."""
    
    def test_basic_format(self):
        """Test basic JSON formatting."""
        formatter = StructuredFormatter()
        
        record = logging.LogRecord(
            name="autosre.test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        result = formatter.format(record)
        
        # Should be valid JSON
        parsed = json.loads(result)
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "autosre.test"
        assert parsed["message"] == "Test message"
        assert "timestamp" in parsed
    
    def test_format_with_extra(self):
        """Test formatting with extra fields."""
        formatter = StructuredFormatter()
        
        record = logging.LogRecord(
            name="autosre.test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Alert triggered",
            args=(),
            exc_info=None,
        )
        record.extra = {"alert_name": "HighCPU", "service": "api"}
        
        result = formatter.format(record)
        parsed = json.loads(result)
        
        assert parsed["alert_name"] == "HighCPU"
        assert parsed["service"] == "api"
    
    def test_format_with_exception(self):
        """Test formatting with exception info."""
        formatter = StructuredFormatter()
        
        try:
            raise ValueError("Test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()
        
        record = logging.LogRecord(
            name="autosre.test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=10,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )
        
        result = formatter.format(record)
        parsed = json.loads(result)
        
        assert "exception" in parsed
        assert "ValueError" in parsed["exception"]


class TestHumanFormatter:
    """Tests for human-readable formatter."""
    
    def test_basic_format(self):
        """Test basic human formatting."""
        formatter = HumanFormatter(use_colors=False)
        
        record = logging.LogRecord(
            name="autosre.test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        result = formatter.format(record)
        
        assert "INFO" in result
        assert "autosre.test" in result
        assert "Test message" in result
    
    def test_format_with_extra(self):
        """Test formatting with extra fields."""
        formatter = HumanFormatter(use_colors=False)
        
        record = logging.LogRecord(
            name="autosre.test",
            level=logging.WARNING,
            pathname="test.py",
            lineno=10,
            msg="Alert fired",
            args=(),
            exc_info=None,
        )
        record.extra = {"service": "api-gateway", "severity": "high"}
        
        result = formatter.format(record)
        
        assert "service=api-gateway" in result
        assert "severity=high" in result
    
    def test_colors_in_tty(self):
        """Test that colors are used when stderr is a TTY."""
        # Mock stderr.isatty() to return True
        with patch('sys.stderr') as mock_stderr:
            mock_stderr.isatty.return_value = True
            formatter = HumanFormatter(use_colors=True)
            assert formatter.use_colors is True
    
    def test_no_colors_in_non_tty(self):
        """Test that colors are disabled when not a TTY."""
        with patch('sys.stderr') as mock_stderr:
            mock_stderr.isatty.return_value = False
            formatter = HumanFormatter(use_colors=True)
            assert formatter.use_colors is False
    
    def test_colors_disabled_explicitly(self):
        """Test that colors can be disabled explicitly."""
        formatter = HumanFormatter(use_colors=False)
        assert formatter.use_colors is False


class TestAutoSRELogger:
    """Tests for custom logger adapter."""
    
    def test_process_extra_fields(self):
        """Test that extra fields are processed correctly."""
        base_logger = MagicMock()
        adapter = AutoSRELogger(base_logger, {})
        
        msg, kwargs = adapter.process(
            "Test message",
            {"alert_name": "HighCPU", "service": "api"}
        )
        
        assert msg == "Test message"
        assert "extra" in kwargs
        assert kwargs["extra"]["extra"]["alert_name"] == "HighCPU"
        assert kwargs["extra"]["extra"]["service"] == "api"
    
    def test_preserves_exc_info(self):
        """Test that exc_info is preserved."""
        base_logger = MagicMock()
        adapter = AutoSRELogger(base_logger, {})
        
        msg, kwargs = adapter.process(
            "Error",
            {"exc_info": True, "service": "api"}
        )
        
        assert kwargs["exc_info"] is True
        assert kwargs["extra"]["extra"]["service"] == "api"


class TestConfigureLogging:
    """Tests for configure_logging function."""
    
    def test_configure_default(self):
        """Test default configuration."""
        configure_logging()
        
        root = logging.getLogger("autosre")
        assert root.level == logging.INFO
        assert len(root.handlers) == 1
    
    def test_configure_json_format(self):
        """Test JSON format configuration."""
        stream = io.StringIO()
        configure_logging(format="json", stream=stream)
        
        root = logging.getLogger("autosre")
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0].formatter, StructuredFormatter)
    
    def test_configure_human_format(self):
        """Test human format configuration."""
        stream = io.StringIO()
        configure_logging(format="human", stream=stream)
        
        root = logging.getLogger("autosre")
        assert isinstance(root.handlers[0].formatter, HumanFormatter)
    
    def test_configure_level_string(self):
        """Test setting level from string."""
        configure_logging(level="DEBUG")
        
        root = logging.getLogger("autosre")
        assert root.level == logging.DEBUG
    
    def test_configure_level_int(self):
        """Test setting level from int."""
        configure_logging(level=logging.WARNING)
        
        root = logging.getLogger("autosre")
        assert root.level == logging.WARNING


class TestGetLogger:
    """Tests for get_logger function."""
    
    def test_get_logger_basic(self):
        """Test getting a logger."""
        logger = get_logger("test_module")
        
        assert isinstance(logger, AutoSRELogger)
    
    def test_get_logger_namespaced(self):
        """Test logger name is namespaced."""
        logger = get_logger("mymodule")
        
        # Should be under autosre namespace
        assert logger.logger.name.startswith("autosre")
    
    def test_get_logger_already_namespaced(self):
        """Test logger with autosre prefix is preserved."""
        logger = get_logger("autosre.agent.reasoner")
        
        assert logger.logger.name == "autosre.agent.reasoner"
    
    def test_logger_can_log(self):
        """Test that returned logger can log messages."""
        stream = io.StringIO()
        configure_logging(level="DEBUG", format="human", stream=stream)
        
        logger = get_logger("test_can_log")
        logger.info("Test message", key="value")
        
        output = stream.getvalue()
        assert "Test message" in output


class TestSetLevel:
    """Tests for set_level function."""
    
    def test_set_level_string(self):
        """Test setting level with string."""
        set_level("ERROR")
        
        root = logging.getLogger("autosre")
        assert root.level == logging.ERROR
    
    def test_set_level_int(self):
        """Test setting level with int."""
        set_level(logging.DEBUG)
        
        root = logging.getLogger("autosre")
        assert root.level == logging.DEBUG


class TestLoggingIntegration:
    """Integration tests for logging."""
    
    def test_json_output(self):
        """Test complete JSON logging output."""
        stream = io.StringIO()
        configure_logging(level="INFO", format="json", stream=stream)
        
        logger = get_logger("integration_test")
        logger.info("Alert received", alert_name="HighCPU", service="api")
        
        output = stream.getvalue()
        parsed = json.loads(output.strip())
        
        assert parsed["message"] == "Alert received"
        assert parsed["level"] == "INFO"
    
    def test_human_output(self):
        """Test complete human logging output."""
        stream = io.StringIO()
        configure_logging(level="INFO", format="human", stream=stream)
        
        logger = get_logger("human_test")
        logger.warning("Service degraded", service="payment")
        
        output = stream.getvalue()
        
        assert "WARNING" in output
        assert "Service degraded" in output
        assert "service=payment" in output
    
    def test_level_filtering(self):
        """Test that log level filtering works."""
        stream = io.StringIO()
        configure_logging(level="WARNING", format="human", stream=stream)
        
        logger = get_logger("level_test")
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        
        output = stream.getvalue()
        
        assert "Debug message" not in output
        assert "Info message" not in output
        assert "Warning message" in output
