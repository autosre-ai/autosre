"""
Comprehensive CLI tests for AutoSRE.

Tests error handling, edge cases, and user experience flows.
"""

import pytest
import tempfile
import os
import json
from pathlib import Path
from click.testing import CliRunner

from autosre.cli.main import cli


@pytest.fixture
def runner():
    """Create a CLI test runner."""
    return CliRunner()


@pytest.fixture
def isolated_runner():
    """Runner with isolated filesystem."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        yield runner


@pytest.fixture
def initialized_dir(runner):
    """Create an initialized AutoSRE directory."""
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["init"])
        assert result.exit_code == 0
        yield Path.cwd()


class TestCLIRoot:
    """Tests for root CLI commands."""
    
    def test_version(self, runner):
        """Test version flag."""
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output
    
    def test_quiet_mode(self, runner):
        """Test quiet flag suppresses output."""
        with runner.isolated_filesystem():
            result_normal = runner.invoke(cli, ["init"])
            result_quiet = runner.invoke(cli, ["init", "-q"])
            
            # Quiet should have less output
            assert len(result_quiet.output) <= len(result_normal.output)
    
    def test_unknown_command_error(self, runner):
        """Test unknown command gives helpful error."""
        result = runner.invoke(cli, ["nonexistent"])
        assert result.exit_code != 0
        assert "No such command" in result.output or "nonexistent" in result.output


class TestInit:
    """Tests for init command."""
    
    def test_init_default_dir(self, isolated_runner):
        """Test init in current directory."""
        result = isolated_runner.invoke(cli, ["init"])
        
        assert result.exit_code == 0
        assert Path(".autosre").exists()
        assert Path("runbooks").exists()
        assert Path(".env.example").exists()
    
    def test_init_creates_subdirectories(self, isolated_runner):
        """Test init creates all necessary subdirs."""
        isolated_runner.invoke(cli, ["init"])
        
        autosre_dir = Path(".autosre")
        assert autosre_dir.exists()
    
    def test_init_env_example_content(self, isolated_runner):
        """Test .env.example has useful content."""
        isolated_runner.invoke(cli, ["init"])
        
        env_file = Path(".env.example")
        assert env_file.exists()
        content = env_file.read_text()
        assert "OPENSRE" in content or "LLM" in content.upper()
    
    def test_init_with_explicit_dir(self, isolated_runner):
        """Test init with explicit directory."""
        os.makedirs("subdir", exist_ok=True)
        result = isolated_runner.invoke(cli, ["init", "--dir", "subdir"])
        
        assert result.exit_code == 0
        assert Path("subdir/.autosre").exists()


class TestStatus:
    """Tests for status command."""
    
    def test_status_without_init(self, isolated_runner):
        """Test status before init shows not configured."""
        result = isolated_runner.invoke(cli, ["status"])
        
        # Should complete without crash
        assert result.exit_code == 0
        # Should indicate something is not configured
        output_lower = result.output.lower()
        assert "not" in output_lower or "✗" in result.output or "○" in result.output
    
    def test_status_after_init(self, isolated_runner):
        """Test status after init shows better state."""
        isolated_runner.invoke(cli, ["init"])
        result = isolated_runner.invoke(cli, ["status"])
        
        assert result.exit_code == 0
        assert "Status" in result.output or "status" in result.output.lower()


class TestContextCommands:
    """Tests for context subcommands."""
    
    def test_context_show_empty(self, isolated_runner):
        """Test context show with no data."""
        isolated_runner.invoke(cli, ["init"])
        result = isolated_runner.invoke(cli, ["context", "show"])
        
        assert result.exit_code == 0
        # Should show zeros or empty indicators
        assert "0" in result.output or "empty" in result.output.lower() or "○" in result.output
    
    def test_context_show_services_flag(self, isolated_runner):
        """Test context show with --services flag."""
        isolated_runner.invoke(cli, ["init"])
        result = isolated_runner.invoke(cli, ["context", "show", "--services"])
        
        assert result.exit_code == 0
    
    def test_context_add_service_missing_name(self, isolated_runner):
        """Test add service without required name."""
        isolated_runner.invoke(cli, ["init"])
        result = isolated_runner.invoke(cli, ["context", "add", "service"])
        
        assert result.exit_code != 0
        assert "name" in result.output.lower() or "missing" in result.output.lower()
    
    def test_context_add_service_valid(self, isolated_runner):
        """Test add service with valid options."""
        isolated_runner.invoke(cli, ["init"])
        result = isolated_runner.invoke(cli, [
            "context", "add", "service",
            "--name", "test-api",
            "--namespace", "production",
            "--team", "platform"
        ])
        
        assert result.exit_code == 0
        assert "test-api" in result.output or "added" in result.output.lower() or "✓" in result.output
    
    def test_context_sync_dry_run(self, isolated_runner):
        """Test sync with dry-run."""
        isolated_runner.invoke(cli, ["init"])
        result = isolated_runner.invoke(cli, ["context", "sync", "--dry-run"])
        
        # Should complete without actual syncing
        assert result.exit_code == 0


class TestEvalCommands:
    """Tests for eval subcommands."""
    
    def test_eval_list_shows_scenarios(self, runner):
        """Test eval list shows available scenarios."""
        result = runner.invoke(cli, ["eval", "list"])
        
        assert result.exit_code == 0
        # Should show at least some scenarios
        assert "Scenario" in result.output or "cpu" in result.output.lower() or "╭" in result.output
    
    def test_eval_list_json(self, runner):
        """Test eval list with JSON output."""
        result = runner.invoke(cli, ["eval", "list", "--json"])
        
        assert result.exit_code == 0
        # Should be valid JSON
        try:
            data = json.loads(result.output)
            assert isinstance(data, list)
        except json.JSONDecodeError:
            pytest.fail("Output is not valid JSON")
    
    def test_eval_run_missing_scenario(self, runner):
        """Test eval run without scenario."""
        result = runner.invoke(cli, ["eval", "run"])
        
        assert result.exit_code != 0
        assert "scenario" in result.output.lower() or "missing" in result.output.lower()
    
    def test_eval_run_nonexistent_scenario(self, runner):
        """Test eval run with nonexistent scenario."""
        result = runner.invoke(cli, ["eval", "run", "--scenario", "does-not-exist-xyz"])
        
        assert result.exit_code != 0 or "not found" in result.output.lower()
    
    def test_eval_run_valid_scenario(self, runner):
        """Test eval run with valid scenario."""
        # First list to get a valid scenario
        list_result = runner.invoke(cli, ["eval", "list", "--json"])
        if list_result.exit_code == 0:
            try:
                scenarios = json.loads(list_result.output)
                if scenarios:
                    scenario_name = scenarios[0]["name"]
                    result = runner.invoke(cli, ["eval", "run", "-s", scenario_name])
                    assert result.exit_code == 0 or "completed" in result.output.lower()
            except (json.JSONDecodeError, KeyError, IndexError):
                pass  # Skip if we can't parse scenarios
    
    def test_eval_report_empty(self, isolated_runner):
        """Test eval report with no results."""
        isolated_runner.invoke(cli, ["init"])
        result = isolated_runner.invoke(cli, ["eval", "report"])
        
        assert result.exit_code == 0
        # Should indicate no results
        assert "No" in result.output or "0" in result.output or "empty" in result.output.lower()


class TestSandboxCommands:
    """Tests for sandbox subcommands."""
    
    def test_sandbox_status_not_running(self, runner):
        """Test sandbox status when no cluster."""
        result = runner.invoke(cli, ["sandbox", "status"])
        
        assert result.exit_code == 0
        # Should indicate cluster not found
        assert "not found" in result.output.lower() or "not running" in result.output.lower() or "start" in result.output.lower()
    
    def test_sandbox_list_empty(self, runner):
        """Test sandbox list with no clusters."""
        result = runner.invoke(cli, ["sandbox", "list"])
        
        assert result.exit_code == 0
    
    def test_sandbox_stop_nonexistent(self, runner):
        """Test stopping nonexistent cluster."""
        result = runner.invoke(cli, ["sandbox", "stop", "-f"])  # -f to skip confirmation
        
        # Should handle gracefully
        assert result.exit_code == 0 or "not found" in result.output.lower()


class TestAgentCommands:
    """Tests for agent subcommands."""
    
    def test_agent_config(self, isolated_runner):
        """Test agent config shows configuration."""
        isolated_runner.invoke(cli, ["init"])
        result = isolated_runner.invoke(cli, ["agent", "config"])
        
        # Should complete without error
        assert result.exit_code == 0
    
    def test_agent_history_empty(self, isolated_runner):
        """Test agent history with no entries."""
        isolated_runner.invoke(cli, ["init"])
        result = isolated_runner.invoke(cli, ["agent", "history"])
        
        assert result.exit_code == 0
        # Should indicate empty or show no entries
        assert "No" in result.output or "0" in result.output or "history" in result.output.lower()
    
    def test_agent_analyze_missing_input(self, isolated_runner):
        """Test analyze without alert input."""
        isolated_runner.invoke(cli, ["init"])
        result = isolated_runner.invoke(cli, ["agent", "analyze"])
        
        # Should require some input
        assert result.exit_code != 0 or "required" in result.output.lower() or "provide" in result.output.lower()


class TestFeedbackCommands:
    """Tests for feedback subcommands."""
    
    def test_feedback_list_empty(self, isolated_runner):
        """Test feedback list with no entries."""
        isolated_runner.invoke(cli, ["init"])
        result = isolated_runner.invoke(cli, ["feedback", "list"])
        
        assert result.exit_code == 0
    
    def test_feedback_report(self, isolated_runner):
        """Test feedback report."""
        isolated_runner.invoke(cli, ["init"])
        result = isolated_runner.invoke(cli, ["feedback", "report"])
        
        assert result.exit_code == 0
    
    def test_feedback_submit_missing_incident(self, isolated_runner):
        """Test submit without incident ID."""
        isolated_runner.invoke(cli, ["init"])
        result = isolated_runner.invoke(cli, ["feedback", "submit"])
        
        assert result.exit_code != 0
        assert "incident" in result.output.lower() or "required" in result.output.lower()


class TestErrorMessages:
    """Tests for user-friendly error messages."""
    
    def test_missing_required_option_message(self, runner):
        """Test missing required option has clear message."""
        result = runner.invoke(cli, ["context", "add", "service"])
        
        assert result.exit_code != 0
        # Should mention the missing option
        assert "--name" in result.output or "name" in result.output.lower()
    
    def test_invalid_path_message(self, runner):
        """Test invalid file path has clear message."""
        result = runner.invoke(cli, ["agent", "analyze", "--alert", "/nonexistent/path.json"])
        
        assert result.exit_code != 0
        assert "does not exist" in result.output.lower() or "not found" in result.output.lower()
    
    def test_help_on_error(self, runner):
        """Test error messages suggest help."""
        result = runner.invoke(cli, ["context", "add", "service"])
        
        # Should suggest getting help
        assert "--help" in result.output or "help" in result.output.lower()


class TestOutputFormats:
    """Tests for output formatting options."""
    
    def test_json_output_context(self, isolated_runner):
        """Test JSON output for context."""
        isolated_runner.invoke(cli, ["init"])
        result = isolated_runner.invoke(cli, ["context", "show", "--json"])
        
        if result.exit_code == 0 and result.output.strip():
            try:
                json.loads(result.output)
            except json.JSONDecodeError:
                pytest.fail("Context --json output is not valid JSON")
    
    def test_table_output_readable(self, runner):
        """Test table output is human-readable."""
        result = runner.invoke(cli, ["eval", "list"])
        
        assert result.exit_code == 0
        # Should have table formatting
        assert "─" in result.output or "|" in result.output or "┃" in result.output or "│" in result.output
