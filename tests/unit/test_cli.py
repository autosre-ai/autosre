"""Unit tests for CLI commands and output formatting."""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

import pytest


# ============================================================================
# Output Formatting Tests
# ============================================================================


class TestOutputFormatting:
    """Tests for CLI output formatting utilities."""

    def test_format_table_basic(self):
        """Test basic table formatting."""
        # Test with rich if available
        try:
            from rich.table import Table
            from rich.console import Console
            
            table = Table(title="Test Table")
            table.add_column("Name", style="cyan")
            table.add_column("Value", style="green")
            table.add_row("key1", "value1")
            table.add_row("key2", "value2")
            
            console = Console(force_terminal=False, width=80)
            with console.capture() as capture:
                console.print(table)
            
            output = capture.get()
            assert "key1" in output
            assert "value1" in output
        except ImportError:
            pytest.skip("rich not available")

    def test_format_json_output(self):
        """Test JSON output formatting."""
        data = {
            "status": "success",
            "alerts": [
                {"name": "HighCPU", "severity": "warning"},
                {"name": "HighLatency", "severity": "critical"},
            ],
        }
        
        output = json.dumps(data, indent=2)
        
        assert '"status": "success"' in output
        assert "HighCPU" in output
        assert "HighLatency" in output

    def test_format_alert_summary(self):
        """Test alert summary formatting."""
        alert = {
            "name": "HighErrorRate",
            "severity": "critical",
            "service": "payment-service",
            "status": "firing",
        }
        
        # Simple text formatting
        summary = f"[{alert['severity'].upper()}] {alert['name']} - {alert['service']} ({alert['status']})"
        
        assert "CRITICAL" in summary
        assert "HighErrorRate" in summary
        assert "payment-service" in summary

    def test_format_investigation_status(self):
        """Test investigation status formatting."""
        investigation = {
            "id": "inv-123",
            "status": "running",
            "iteration": 2,
            "max_iterations": 3,
            "duration_seconds": 45.5,
        }
        
        status_line = (
            f"Investigation {investigation['id']}: {investigation['status']} "
            f"(iteration {investigation['iteration']}/{investigation['max_iterations']}, "
            f"{investigation['duration_seconds']:.1f}s)"
        )
        
        assert "inv-123" in status_line
        assert "running" in status_line
        assert "2/3" in status_line


# ============================================================================
# CLI Argument Parsing Tests
# ============================================================================


class TestArgumentParsing:
    """Tests for CLI argument parsing."""

    def test_parse_severity_filter(self):
        """Test parsing severity filter argument."""
        severities = ["critical", "high", "medium", "low", "info"]
        
        # Test valid severities
        for sev in severities:
            assert sev.lower() in severities
        
        # Test case insensitivity
        assert "CRITICAL".lower() in severities
        assert "Critical".lower() in severities

    def test_parse_time_duration(self):
        """Test parsing time duration strings."""
        from datetime import timedelta
        
        def parse_duration(s: str) -> timedelta:
            """Parse duration string like '1h', '30m', '15s'."""
            unit = s[-1]
            value = int(s[:-1])
            
            if unit == 'h':
                return timedelta(hours=value)
            elif unit == 'm':
                return timedelta(minutes=value)
            elif unit == 's':
                return timedelta(seconds=value)
            elif unit == 'd':
                return timedelta(days=value)
            else:
                raise ValueError(f"Unknown duration unit: {unit}")
        
        assert parse_duration("1h") == timedelta(hours=1)
        assert parse_duration("30m") == timedelta(minutes=30)
        assert parse_duration("15s") == timedelta(seconds=15)
        assert parse_duration("7d") == timedelta(days=7)
        
        with pytest.raises(ValueError):
            parse_duration("1x")

    def test_parse_labels(self):
        """Test parsing label key=value pairs."""
        def parse_labels(labels_str: str) -> dict:
            """Parse comma-separated key=value pairs."""
            if not labels_str:
                return {}
            
            result = {}
            for pair in labels_str.split(","):
                key, value = pair.strip().split("=", 1)
                result[key.strip()] = value.strip()
            return result
        
        assert parse_labels("") == {}
        assert parse_labels("app=nginx") == {"app": "nginx"}
        assert parse_labels("app=nginx,env=prod") == {"app": "nginx", "env": "prod"}
        assert parse_labels("app=nginx, env=prod") == {"app": "nginx", "env": "prod"}


# ============================================================================
# CLI Config Validation Tests
# ============================================================================


class TestConfigValidation:
    """Tests for CLI config validation."""

    def test_validate_config_structure(self):
        """Test validating config structure."""
        valid_config = {
            "version": "2.0",
            "llm": {
                "provider": "openai",
                "model": "gpt-4o",
            },
            "alerts": {
                "sources": [],
            },
        }
        
        # Check required keys
        assert "version" in valid_config
        assert "llm" in valid_config
        
        # Check nested structure
        assert "provider" in valid_config["llm"]

    def test_validate_config_invalid_version(self):
        """Test validating config with invalid version."""
        invalid_config = {
            "version": "0.1",  # Old version
            "llm": {},
        }
        
        # Version check
        supported_versions = ["1.0", "2.0"]
        is_valid = invalid_config.get("version") in supported_versions
        assert not is_valid

    def test_validate_llm_provider(self):
        """Test validating LLM provider."""
        valid_providers = ["openai", "anthropic", "azure", "ollama"]
        
        assert "openai" in valid_providers
        assert "invalid_provider" not in valid_providers

    def test_validate_url_format(self):
        """Test validating URL format."""
        from urllib.parse import urlparse
        
        def is_valid_url(url: str) -> bool:
            try:
                result = urlparse(url)
                return all([result.scheme, result.netloc])
            except Exception:
                return False
        
        assert is_valid_url("http://localhost:9090")
        assert is_valid_url("https://prometheus.example.com")
        assert not is_valid_url("not-a-url")
        assert not is_valid_url("")


# ============================================================================
# CLI Error Handling Tests
# ============================================================================


class TestErrorHandling:
    """Tests for CLI error handling."""

    def test_handle_connection_error(self):
        """Test handling connection errors."""
        import httpx
        
        error = httpx.ConnectError("Connection refused")
        
        # Error message formatting
        message = f"Connection error: {error}"
        assert "Connection refused" in message

    def test_handle_timeout_error(self):
        """Test handling timeout errors."""
        import httpx
        
        error = httpx.TimeoutException("Request timed out")
        
        message = f"Timeout: {error}"
        assert "timed out" in message

    def test_handle_api_error(self):
        """Test handling API errors."""
        error_response = {
            "error": "Unauthorized",
            "message": "Invalid API key",
            "status_code": 401,
        }
        
        def format_api_error(error: dict) -> str:
            return f"API Error ({error['status_code']}): {error['error']} - {error['message']}"
        
        message = format_api_error(error_response)
        assert "401" in message
        assert "Unauthorized" in message
        assert "Invalid API key" in message

    def test_handle_validation_error(self):
        """Test handling validation errors."""
        from pydantic import ValidationError, BaseModel
        
        class TestModel(BaseModel):
            name: str
            value: int
        
        with pytest.raises(ValidationError) as exc_info:
            TestModel(name="test", value="not-an-int")
        
        error = exc_info.value
        assert len(error.errors()) > 0


# ============================================================================
# CLI Progress Display Tests
# ============================================================================


class TestProgressDisplay:
    """Tests for CLI progress display."""

    def test_spinner_states(self):
        """Test spinner state handling."""
        states = ["pending", "running", "completed", "failed"]
        
        state_symbols = {
            "pending": "○",
            "running": "◐",
            "completed": "●",
            "failed": "✗",
        }
        
        for state in states:
            assert state in state_symbols
            assert len(state_symbols[state]) > 0

    def test_progress_bar_calculation(self):
        """Test progress bar calculation."""
        def calculate_progress(current: int, total: int) -> float:
            if total == 0:
                return 0.0
            return min(current / total, 1.0)
        
        assert calculate_progress(0, 10) == 0.0
        assert calculate_progress(5, 10) == 0.5
        assert calculate_progress(10, 10) == 1.0
        assert calculate_progress(15, 10) == 1.0  # Capped at 100%
        assert calculate_progress(0, 0) == 0.0  # Handle division by zero


# ============================================================================
# CLI Color Theme Tests
# ============================================================================


class TestColorTheme:
    """Tests for CLI color theming."""

    def test_severity_colors(self):
        """Test severity to color mapping."""
        severity_colors = {
            "critical": "red",
            "high": "orange",
            "medium": "yellow",
            "low": "blue",
            "info": "green",
        }
        
        assert severity_colors["critical"] == "red"
        assert severity_colors["info"] == "green"

    def test_status_colors(self):
        """Test status to color mapping."""
        status_colors = {
            "firing": "red",
            "resolved": "green",
            "acknowledged": "yellow",
            "pending": "blue",
            "running": "cyan",
            "completed": "green",
            "failed": "red",
        }
        
        assert status_colors["firing"] == "red"
        assert status_colors["completed"] == "green"


# ============================================================================
# CLI Help Text Tests
# ============================================================================


class TestHelpText:
    """Tests for CLI help text."""

    def test_command_descriptions(self):
        """Test command descriptions are meaningful."""
        commands = {
            "init": "Initialize AutoSRE configuration",
            "alerts": "Manage alerts",
            "investigate": "Start investigation",
            "serve": "Run API server",
            "chat": "Interactive chat mode",
        }
        
        for cmd, desc in commands.items():
            assert len(desc) > 10  # Meaningful description
            assert cmd.lower() not in desc.lower() or len(desc) > len(cmd) + 5

    def test_option_descriptions(self):
        """Test option descriptions format."""
        options = [
            {"name": "--verbose", "short": "-v", "help": "Enable verbose output"},
            {"name": "--json", "short": "-j", "help": "Output in JSON format"},
            {"name": "--config", "short": "-c", "help": "Path to config file"},
        ]
        
        for opt in options:
            assert opt["name"].startswith("--")
            assert opt["short"].startswith("-")
            assert len(opt["help"]) > 5


# ============================================================================
# Environment Variable Tests
# ============================================================================


class TestEnvironmentVariables:
    """Tests for environment variable handling."""

    def test_env_var_override(self, monkeypatch):
        """Test environment variable override."""
        monkeypatch.setenv("AUTOSRE_DEBUG", "true")
        
        value = os.getenv("AUTOSRE_DEBUG")
        assert value == "true"
        
        # Boolean parsing
        is_debug = value.lower() in ("true", "1", "yes")
        assert is_debug is True

    def test_env_var_default(self, monkeypatch):
        """Test environment variable default."""
        monkeypatch.delenv("AUTOSRE_NONEXISTENT", raising=False)
        
        value = os.getenv("AUTOSRE_NONEXISTENT", "default")
        assert value == "default"

    def test_config_path_env(self, monkeypatch, tmp_path):
        """Test config path from environment."""
        config_path = tmp_path / "custom.yaml"
        config_path.write_text("version: 2.0")
        
        monkeypatch.setenv("AUTOSRE_CONFIG_PATH", str(config_path))
        
        path = os.getenv("AUTOSRE_CONFIG_PATH")
        assert Path(path).exists()


# ============================================================================
# File Path Handling Tests
# ============================================================================


class TestFilePathHandling:
    """Tests for file path handling in CLI."""

    def test_expand_home_path(self):
        """Test expanding home directory in paths."""
        path = "~/.autosre.yaml"
        expanded = os.path.expanduser(path)
        
        assert "~" not in expanded
        assert expanded.endswith(".autosre.yaml")

    def test_resolve_relative_path(self, tmp_path):
        """Test resolving relative paths."""
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            
            relative = Path("./config/test.yaml")
            absolute = relative.resolve()
            
            assert absolute.is_absolute()
            assert str(tmp_path) in str(absolute)
        finally:
            os.chdir(original_cwd)

    def test_validate_file_exists(self, tmp_path):
        """Test file existence validation."""
        existing = tmp_path / "exists.txt"
        existing.write_text("content")
        
        nonexistent = tmp_path / "nonexistent.txt"
        
        assert existing.exists()
        assert not nonexistent.exists()


# ============================================================================
# Interactive Mode Tests
# ============================================================================


class TestInteractiveMode:
    """Tests for interactive mode handling."""

    def test_detect_tty(self):
        """Test TTY detection."""
        import sys
        
        # In tests, usually not a TTY
        is_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
        # Just verify we can check
        assert isinstance(is_tty, bool)

    def test_prompt_confirmation(self):
        """Test confirmation prompt logic."""
        def parse_confirmation(response: str) -> bool:
            """Parse yes/no confirmation."""
            return response.lower().strip() in ("y", "yes", "true", "1")
        
        assert parse_confirmation("y") is True
        assert parse_confirmation("yes") is True
        assert parse_confirmation("Y") is True
        assert parse_confirmation("YES") is True
        assert parse_confirmation("n") is False
        assert parse_confirmation("no") is False
        assert parse_confirmation("") is False
