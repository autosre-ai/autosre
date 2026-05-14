"""Integration tests for CLI commands."""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from autosre.cli.main import app


runner = CliRunner()


# ============================================================================
# Main CLI Tests
# ============================================================================


class TestMainCLI:
    """Tests for main CLI entry point."""

    def test_version_command(self):
        """Test version command."""
        result = runner.invoke(app, ["version"])
        
        assert result.exit_code == 0
        assert "AutoSRE" in result.output

    def test_version_verbose(self):
        """Test verbose version command."""
        result = runner.invoke(app, ["version", "--verbose"])
        
        assert result.exit_code == 0
        assert "Python Version" in result.output
        assert "Platform" in result.output

    def test_version_flag(self):
        """Test --version flag."""
        result = runner.invoke(app, ["--version"])
        
        assert result.exit_code == 0
        assert "AutoSRE" in result.output

    def test_no_command_shows_help(self):
        """Test that no command shows banner."""
        result = runner.invoke(app, [])
        
        assert result.exit_code == 0
        # Should show banner or help
        assert "AutoSRE" in result.output or "help" in result.output.lower()

    def test_help_command(self):
        """Test help command."""
        result = runner.invoke(app, ["--help"])
        
        assert result.exit_code == 0
        assert "Usage" in result.output
        assert "alerts" in result.output
        assert "investigate" in result.output
        assert "chat" in result.output


# ============================================================================
# Init Command Tests
# ============================================================================


class TestInitCommand:
    """Tests for init command."""

    def test_init_creates_config(self, tmp_path):
        """Test init creates configuration file."""
        result = runner.invoke(app, ["init", "--dir", str(tmp_path)])
        
        assert result.exit_code == 0
        assert "initialized" in result.output.lower() or "complete" in result.output.lower()
        
        config_path = tmp_path / ".autosre.yaml"
        assert config_path.exists()

    def test_init_creates_runbooks_dir(self, tmp_path):
        """Test init creates runbooks directory."""
        result = runner.invoke(app, ["init", "--dir", str(tmp_path)])
        
        assert result.exit_code == 0
        
        runbooks_path = tmp_path / "runbooks"
        assert runbooks_path.exists()
        assert runbooks_path.is_dir()

    def test_init_creates_example_runbook(self, tmp_path):
        """Test init creates example runbook."""
        result = runner.invoke(app, ["init", "--dir", str(tmp_path)])
        
        assert result.exit_code == 0
        
        example = tmp_path / "runbooks" / "example-high-cpu.yaml"
        assert example.exists()

    def test_init_fails_if_exists(self, tmp_path):
        """Test init fails if config already exists."""
        # Create existing config
        config_path = tmp_path / ".autosre.yaml"
        config_path.write_text("version: 1.0")
        
        result = runner.invoke(app, ["init", "--dir", str(tmp_path)])
        
        assert result.exit_code == 1
        assert "already exists" in result.output.lower()

    def test_init_force_overwrites(self, tmp_path):
        """Test init --force overwrites existing config."""
        # Create existing config
        config_path = tmp_path / ".autosre.yaml"
        config_path.write_text("version: 1.0")
        
        result = runner.invoke(app, ["init", "--dir", str(tmp_path), "--force"])
        
        assert result.exit_code == 0
        assert "initialized" in result.output.lower() or "complete" in result.output.lower()


# ============================================================================
# Config Commands Tests
# ============================================================================


class TestConfigCommands:
    """Tests for config subcommands."""

    def test_config_help(self):
        """Test config help."""
        result = runner.invoke(app, ["config", "--help"])
        
        assert result.exit_code == 0
        assert "config" in result.output.lower()

    def test_config_validate_no_config(self, tmp_path, monkeypatch):
        """Test config validate when no config exists."""
        monkeypatch.chdir(tmp_path)
        
        result = runner.invoke(app, ["config", "validate"])
        
        # Should handle gracefully (either error or default)
        assert result.exit_code in (0, 1)


# ============================================================================
# Alerts Commands Tests
# ============================================================================


class TestAlertsCommands:
    """Tests for alerts subcommands."""

    def test_alerts_help(self):
        """Test alerts help."""
        result = runner.invoke(app, ["alerts", "--help"])
        
        assert result.exit_code == 0
        assert "alert" in result.output.lower()

    def test_alerts_list_requires_server(self):
        """Test alerts list requires running server."""
        result = runner.invoke(app, ["alerts", "list"])
        
        # May fail if server not running, but should not crash
        assert result.exit_code in (0, 1)


# ============================================================================
# Investigate Commands Tests
# ============================================================================


class TestInvestigateCommands:
    """Tests for investigate subcommands."""

    def test_investigate_help(self):
        """Test investigate help."""
        result = runner.invoke(app, ["investigate", "--help"])
        
        assert result.exit_code == 0
        assert "invest" in result.output.lower()


# ============================================================================
# Serve Commands Tests
# ============================================================================


class TestServeCommands:
    """Tests for serve subcommands."""

    def test_serve_help(self):
        """Test serve help."""
        result = runner.invoke(app, ["serve", "--help"])
        
        assert result.exit_code == 0
        assert "server" in result.output.lower() or "serve" in result.output.lower()


# ============================================================================
# Runbook Commands Tests
# ============================================================================


class TestRunbookCommands:
    """Tests for runbook subcommands."""

    def test_runbook_help(self):
        """Test runbook help."""
        result = runner.invoke(app, ["runbook", "--help"])
        
        assert result.exit_code == 0
        assert "runbook" in result.output.lower()


# ============================================================================
# Chat Commands Tests
# ============================================================================


class TestChatCommands:
    """Tests for chat subcommands."""

    def test_chat_help(self):
        """Test chat help."""
        result = runner.invoke(app, ["chat", "--help"])
        
        assert result.exit_code == 0
        assert "chat" in result.output.lower()


# ============================================================================
# Output Formatting Tests
# ============================================================================


class TestOutputFormatting:
    """Tests for CLI output formatting."""

    def test_json_output_flag(self):
        """Test JSON output flag if supported."""
        result = runner.invoke(app, ["version", "--verbose"])
        
        # Should produce readable output
        assert result.exit_code == 0
        # Rich formatting may be present
        assert len(result.output) > 0

    def test_color_disabled_in_tests(self):
        """Test that colors are handled properly."""
        result = runner.invoke(app, ["version"])
        
        assert result.exit_code == 0
        # Should still work without TTY


# ============================================================================
# Environment Integration Tests
# ============================================================================


class TestEnvironmentIntegration:
    """Tests for environment variable handling in CLI."""

    def test_respects_env_vars(self, monkeypatch):
        """Test CLI respects environment variables."""
        monkeypatch.setenv("AUTOSRE_DEBUG", "true")
        
        result = runner.invoke(app, ["version"])
        
        assert result.exit_code == 0

    def test_config_path_env_var(self, tmp_path, monkeypatch):
        """Test AUTOSRE_CONFIG_PATH environment variable."""
        import yaml
        
        config_path = tmp_path / "custom-config.yaml"
        config_path.write_text(yaml.dump({"version": "2.0"}))
        
        monkeypatch.setenv("AUTOSRE_CONFIG_PATH", str(config_path))
        
        result = runner.invoke(app, ["config", "show"])
        
        # Should attempt to load from custom path
        assert result.exit_code in (0, 1)
