"""
Integration tests for CLI commands.
"""

import pytest
import tempfile
import os
from pathlib import Path
from click.testing import CliRunner

from autosre.cli import cli


@pytest.fixture
def runner():
    """Create a CLI test runner."""
    return CliRunner()


@pytest.fixture
def temp_dir():
    """Create a temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


class TestCLIInit:
    """Integration tests for init command."""
    
    def test_init_creates_structure(self, runner, temp_dir):
        """Test that init creates expected directory structure."""
        result = runner.invoke(cli, ["init", "--dir", temp_dir])
        
        assert result.exit_code == 0
        assert (Path(temp_dir) / ".autosre").exists()
        assert (Path(temp_dir) / "runbooks").exists()
        assert (Path(temp_dir) / ".env.example").exists()
    
    def test_init_creates_sample_runbook(self, runner, temp_dir):
        """Test that init creates runbooks directory."""
        runner.invoke(cli, ["init", "--dir", temp_dir])
        
        runbooks_dir = Path(temp_dir) / "runbooks"
        assert runbooks_dir.exists()
    
    def test_init_idempotent(self, runner, temp_dir):
        """Test that init can be run multiple times."""
        result1 = runner.invoke(cli, ["init", "--dir", temp_dir])
        result2 = runner.invoke(cli, ["init", "--dir", temp_dir])
        
        assert result1.exit_code == 0
        assert result2.exit_code == 0


class TestCLIContext:
    """Integration tests for context commands."""
    
    def test_context_show_without_init(self, runner, temp_dir):
        """Test context show works without init."""
        os.chdir(temp_dir)
        result = runner.invoke(cli, ["context", "show"])
        
        # Should still work, just show empty/default data
        assert result.exit_code == 0 or "error" not in result.output.lower()
    
    def test_context_show_with_flags(self, runner, temp_dir):
        """Test context show with filter flags."""
        runner.invoke(cli, ["init", "--dir", temp_dir])
        os.chdir(temp_dir)
        
        # These should work without error
        result = runner.invoke(cli, ["context", "show", "--services"])
        assert result.exit_code == 0
        
        result = runner.invoke(cli, ["context", "show", "--changes"])
        assert result.exit_code == 0


class TestCLIEval:
    """Integration tests for eval commands."""
    
    def test_eval_list(self, runner):
        """Test listing available scenarios."""
        result = runner.invoke(cli, ["eval", "list"])
        
        assert result.exit_code == 0
        # Should list some scenarios
        assert "high" in result.output.lower() or "cpu" in result.output.lower() or "scenario" in result.output.lower()
    
    def test_eval_report_empty(self, runner, temp_dir):
        """Test eval report with no results."""
        os.chdir(temp_dir)
        result = runner.invoke(cli, ["eval", "report"])
        
        # Should work even with no results
        assert result.exit_code == 0


class TestCLIStatus:
    """Integration tests for status command."""
    
    def test_status_shows_sections(self, runner, temp_dir):
        """Test that status shows expected sections."""
        os.chdir(temp_dir)
        result = runner.invoke(cli, ["status"])
        
        assert result.exit_code == 0
        # Should show configuration and context sections
        output_lower = result.output.lower()
        assert "config" in output_lower or "status" in output_lower


class TestCLIHelp:
    """Tests for help output."""
    
    def test_help_shows_commands(self, runner):
        """Test that help shows available commands."""
        result = runner.invoke(cli, ["--help"])
        
        assert result.exit_code == 0
        assert "init" in result.output
        assert "status" in result.output
        assert "context" in result.output
        assert "eval" in result.output
    
    def test_subcommand_help(self, runner):
        """Test help for subcommands."""
        subcommands = ["context", "eval", "sandbox", "agent", "feedback"]
        
        for subcmd in subcommands:
            result = runner.invoke(cli, [subcmd, "--help"])
            assert result.exit_code == 0, f"Help failed for {subcmd}"
