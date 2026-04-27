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


class TestCLIStatus:
    """Test status command."""
    
    def test_status_runs(self, runner):
        """Test status command runs."""
        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0
        assert "Status" in result.output
    
    def test_status_shows_config(self, runner):
        """Test status shows configuration."""
        result = runner.invoke(cli, ["status"])
        assert "Configuration" in result.output
    
    def test_status_shows_context(self, runner):
        """Test status shows context store."""
        result = runner.invoke(cli, ["status"])
        assert "Context Store" in result.output
    
    def test_status_shows_llm(self, runner):
        """Test status shows LLM provider."""
        result = runner.invoke(cli, ["status"])
        assert "LLM Provider" in result.output


class TestCLIInit:
    """Test init command."""
    
    def test_init_help(self, runner):
        """Test init --help."""
        result = runner.invoke(cli, ["init", "--help"])
        assert result.exit_code == 0
        assert "Initialize AutoSRE" in result.output
    
    def test_init_creates_directories(self, runner):
        """Test init creates required directories."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(cli, ["init", "--dir", tmpdir])
            assert result.exit_code == 0
            assert "initialized" in result.output.lower()
            
            from pathlib import Path
            assert (Path(tmpdir) / ".autosre").exists()
            assert (Path(tmpdir) / "runbooks").exists()
            assert (Path(tmpdir) / ".env.example").exists()


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
        # Rich tables may split the title, check for key words
        assert "Context" in result.output
        assert "Resource" in result.output
    
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
        # May show "Evaluation Results" table or "No evaluation results"
        assert "result" in result.output.lower() or "Results" in result.output


class TestSandboxCommands:
    """Test sandbox subcommands."""
    
    def test_sandbox_start_help(self, runner):
        """Test sandbox start --help."""
        result = runner.invoke(cli, ["sandbox", "start", "--help"])
        assert result.exit_code == 0
        assert "--name" in result.output
    
    def test_sandbox_stop_help(self, runner):
        """Test sandbox stop --help."""
        result = runner.invoke(cli, ["sandbox", "stop", "--help"])
        assert result.exit_code == 0
        assert "--name" in result.output


class TestAgentCommands:
    """Test agent subcommands."""
    
    def test_agent_analyze_help(self, runner):
        """Test agent analyze --help."""
        result = runner.invoke(cli, ["agent", "analyze", "--help"])
        assert result.exit_code == 0
        assert "--alert" in result.output
    
    def test_agent_run_help(self, runner):
        """Test agent run --help."""
        result = runner.invoke(cli, ["agent", "run", "--help"])
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
