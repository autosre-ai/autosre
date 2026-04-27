"""
Tests for the CLI commands.
"""

import pytest
from click.testing import CliRunner

from autosre.cli.main import cli


@pytest.fixture
def runner():
    """CLI test runner."""
    return CliRunner()


class TestCLIBasics:
    """Test basic CLI functionality."""
    
    def test_cli_help(self, runner):
        """Test --help flag."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "AutoSRE" in result.output
        assert "context" in result.output
        assert "eval" in result.output
        assert "agent" in result.output
    
    def test_cli_version(self, runner):
        """Test --version flag."""
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output


class TestContextCommands:
    """Test context subcommands."""
    
    def test_context_show_help(self, runner):
        """Test context show --help."""
        result = runner.invoke(cli, ["context", "show", "--help"])
        assert result.exit_code == 0
        assert "--services" in result.output
        assert "--changes" in result.output
        assert "--alerts" in result.output
    
    def test_context_show_summary(self, runner):
        """Test context show without flags shows summary."""
        result = runner.invoke(cli, ["context", "show"])
        assert result.exit_code == 0
        assert "Context Store Summary" in result.output
    
    def test_context_sync_help(self, runner):
        """Test context sync --help."""
        result = runner.invoke(cli, ["context", "sync", "--help"])
        assert result.exit_code == 0
        assert "--kubernetes" in result.output
        assert "--prometheus" in result.output


class TestEvalCommands:
    """Test eval subcommands."""
    
    def test_eval_list(self, runner):
        """Test eval list command."""
        result = runner.invoke(cli, ["eval", "list"])
        assert result.exit_code == 0
        assert "Available Scenarios" in result.output
    
    def test_eval_run_help(self, runner):
        """Test eval run --help."""
        result = runner.invoke(cli, ["eval", "run", "--help"])
        assert result.exit_code == 0
        assert "--scenario" in result.output
    
    def test_eval_report(self, runner):
        """Test eval report command."""
        result = runner.invoke(cli, ["eval", "report"])
        assert result.exit_code == 0
        assert "Evaluation Results" in result.output


class TestSandboxCommands:
    """Test sandbox subcommands."""
    
    def test_sandbox_create_help(self, runner):
        """Test sandbox create --help."""
        result = runner.invoke(cli, ["sandbox", "create", "--help"])
        assert result.exit_code == 0
        assert "--name" in result.output
    
    def test_sandbox_destroy_help(self, runner):
        """Test sandbox destroy --help."""
        result = runner.invoke(cli, ["sandbox", "destroy", "--help"])
        assert result.exit_code == 0
        assert "--name" in result.output


class TestAgentCommands:
    """Test agent subcommands."""
    
    def test_agent_analyze_help(self, runner):
        """Test agent analyze --help."""
        result = runner.invoke(cli, ["agent", "analyze", "--help"])
        assert result.exit_code == 0
        assert "--alert" in result.output
    
    def test_agent_watch_help(self, runner):
        """Test agent watch --help."""
        result = runner.invoke(cli, ["agent", "watch", "--help"])
        assert result.exit_code == 0
        assert "--interval" in result.output
    
    def test_agent_history_help(self, runner):
        """Test agent history --help."""
        result = runner.invoke(cli, ["agent", "history", "--help"])
        assert result.exit_code == 0
        assert "--limit" in result.output


class TestFeedbackCommands:
    """Test feedback subcommands."""
    
    def test_feedback_submit_help(self, runner):
        """Test feedback submit --help."""
        result = runner.invoke(cli, ["feedback", "submit", "--help"])
        assert result.exit_code == 0
        assert "--incident" in result.output
        assert "--correct" in result.output
    
    def test_feedback_report(self, runner):
        """Test feedback report command."""
        result = runner.invoke(cli, ["feedback", "report"])
        assert result.exit_code == 0
