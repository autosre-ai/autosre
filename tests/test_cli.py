"""
Tests for the CLI commands.
"""

import pytest
from typer.testing import CliRunner

from autosre.cli.main import app


@pytest.fixture
def runner():
    """CLI test runner."""
    return CliRunner()


class TestCLIBasics:
    """Test basic CLI functionality."""
    
    def test_cli_help(self, runner):
        """Test --help flag."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "AutoSRE" in result.output or "autosre" in result.output
        assert "investigate" in result.output
    
    def test_cli_version(self, runner):
        """Test --version flag."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        # Version could be 0.1.0 or 0.2.0
        assert "0." in result.output


class TestCLIStatus:
    """Test status command."""
    
    def test_status_runs(self, runner):
        """Test status command runs."""
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        # Should show some status info
        assert "AutoSRE" in result.output or "Status" in result.output


class TestInvestigateCommands:
    """Test investigate subcommands."""
    
    def test_investigate_help(self, runner):
        """Test investigate --help."""
        result = runner.invoke(app, ["investigate", "--help"])
        assert result.exit_code == 0
        assert "run" in result.output
    
    def test_investigate_run_help(self, runner):
        """Test investigate run --help."""
        result = runner.invoke(app, ["investigate", "run", "--help"])
        assert result.exit_code == 0
        assert "--service" in result.output or "ALERT" in result.output
        assert "--demo" in result.output
    
    def test_investigate_run_demo_mode(self, runner):
        """Test investigate run --demo produces output."""
        result = runner.invoke(app, ["investigate", "run", "API latency spike", "--demo", "--no-stream"])
        assert result.exit_code == 0
        # Check for expected demo output
        assert "Investigation" in result.output
        assert "Demo" in result.output or "demo" in result.output.lower()
        assert "Evidence" in result.output or "evidence" in result.output.lower()
    
    def test_investigate_history_help(self, runner):
        """Test investigate history --help."""
        result = runner.invoke(app, ["investigate", "history", "--help"])
        assert result.exit_code == 0


class TestQuickRun:
    """Test the quick 'run' command."""
    
    def test_run_help(self, runner):
        """Test run --help."""
        result = runner.invoke(app, ["run", "--help"])
        assert result.exit_code == 0
        assert "ALERT" in result.output or "alert" in result.output.lower()


class TestCompletion:
    """Test shell completion command."""
    
    def test_completion_help(self, runner):
        """Test completion --help."""
        result = runner.invoke(app, ["completion", "--help"])
        assert result.exit_code == 0
        assert "bash" in result.output.lower()
        assert "zsh" in result.output.lower()
        assert "fish" in result.output.lower()
    
    def test_completion_bash(self, runner):
        """Test bash completion script generation."""
        result = runner.invoke(app, ["completion", "bash"])
        assert result.exit_code == 0
        assert "_autosre_completion" in result.output
        assert "COMPREPLY" in result.output
        assert "_AUTOSRE_COMPLETE" in result.output
    
    def test_completion_zsh(self, runner):
        """Test zsh completion script generation."""
        result = runner.invoke(app, ["completion", "zsh"])
        assert result.exit_code == 0
        assert "#compdef autosre" in result.output
        assert "_autosre_completion" in result.output
        assert "_AUTOSRE_COMPLETE" in result.output
    
    def test_completion_fish(self, runner):
        """Test fish completion script generation."""
        result = runner.invoke(app, ["completion", "fish"])
        assert result.exit_code == 0
        assert "complete --command autosre" in result.output
        assert "_AUTOSRE_COMPLETE" in result.output
    
    def test_completion_without_shell_arg(self, runner):
        """Test completion without shell argument (should prompt or auto-detect)."""
        result = runner.invoke(app, ["completion"])
        # Should either auto-detect or ask for shell
        # In test environment, it typically can't detect, so should exit with message
        assert "shell" in result.output.lower() or result.exit_code == 0
