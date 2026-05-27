# AutoSRE Development Guide

This guide covers setting up a development environment, running tests, and contributing to AutoSRE.

## Prerequisites

- **Python 3.11+** (3.12 recommended)
- **uv** (recommended) or pip
- **Git**
- **Docker** (optional, for integration tests)

---

## Development Setup

### 1. Clone the Repository

```bash
git clone https://github.com/opensre/autosre.git
cd autosre
```

### 2. Create Virtual Environment

**Using uv (recommended):**
```bash
uv venv
source .venv/bin/activate
```

**Using venv:**
```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

**Development install with all extras:**
```bash
# Using uv
uv pip install -e ".[dev]"

# Using pip
pip install -e ".[dev]"
```

**Available extras:**
- `dev` - Development tools (pytest, ruff, mypy)
- `docs` - Documentation tools (mkdocs)
- `sandbox` - Docker sandbox support
- `operator` - Kubernetes operator support
- `training` - Fine-tuning dependencies

### 4. Verify Installation

```bash
autosre --version
autosre doctor
```

---

## Project Structure

```
autosre/
├── src/
│   └── autosre/
│       ├── __init__.py
│       ├── cli/                 # CLI commands
│       │   ├── main.py          # Main CLI app
│       │   └── commands/        # Subcommands
│       ├── agents/              # AI agents and subagents
│       ├── skills/              # Investigation skills
│       ├── memory/              # Episodic memory
│       ├── foundation/          # Infrastructure connectors
│       │   └── connectors/      # Prometheus, Loki, etc.
│       ├── guardrails/          # Safety and approval
│       ├── slo/                 # SLO management
│       ├── workflows/           # Automation workflows
│       └── config.py            # Configuration
├── tests/                       # Test suite
├── docs/                        # Documentation
├── examples/                    # Example scripts
├── scenarios/                   # Demo scenarios
└── pyproject.toml               # Project configuration
```

---

## Running Tests

### Run All Tests

```bash
# Using pytest directly
pytest

# With coverage
pytest --cov=src/autosre --cov-report=term-missing

# Verbose output
pytest -v
```

### Run Specific Tests

```bash
# Single test file
pytest tests/test_memory.py

# Single test function
pytest tests/test_memory.py::test_store_episode

# By marker
pytest -m "not slow"        # Skip slow tests
pytest -m "integration"     # Only integration tests
```

### Test Markers

- `@pytest.mark.slow` - Slow tests
- `@pytest.mark.integration` - Integration tests requiring external services

---

## Code Quality

### Linting with Ruff

```bash
# Check for issues
ruff check .

# Auto-fix issues
ruff check --fix .
```

### Formatting with Ruff

```bash
# Check formatting
ruff format --check .

# Apply formatting
ruff format .
```

### Type Checking with MyPy

```bash
mypy src/autosre/
```

### Run All Checks

```bash
# Lint, format, and type check
ruff check .
ruff format .
mypy src/autosre/
```

---

## Making Changes

### 1. Create a Feature Branch

```bash
git checkout -b feature/my-feature
```

### 2. Make Your Changes

- Write code
- Add tests
- Update documentation

### 3. Run Tests and Checks

```bash
pytest
ruff check .
ruff format .
mypy src/autosre/
```

### 4. Commit with Conventional Commits

```bash
git commit -m "feat: add new investigation skill"
git commit -m "fix: handle empty metrics response"
git commit -m "docs: update CLI reference"
```

**Commit types:**
- `feat:` - New features
- `fix:` - Bug fixes
- `docs:` - Documentation changes
- `test:` - Test changes
- `refactor:` - Code refactoring
- `chore:` - Maintenance tasks

### 5. Push and Create PR

```bash
git push origin feature/my-feature
```

Then create a Pull Request on GitHub.

---

## Adding a New CLI Command

### 1. Create Command File

```python
# src/autosre/cli/commands/mycommand.py
import typer
from rich.console import Console

app = typer.Typer(
    name="mycommand",
    help="My new command group",
)
console = Console()

@app.command()
def run(
    name: str = typer.Argument(..., help="Resource name"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Run my command."""
    console.print(f"Running for {name}")
```

### 2. Register in Main CLI

```python
# src/autosre/cli/main.py
from autosre.cli.commands import mycommand

app.add_typer(mycommand.app, name="mycommand", help="My new command")
```

### 3. Add Tests

```python
# tests/test_mycommand.py
from typer.testing import CliRunner
from autosre.cli.main import app

runner = CliRunner()

def test_mycommand_run():
    result = runner.invoke(app, ["mycommand", "run", "test"])
    assert result.exit_code == 0
    assert "Running for test" in result.output
```

---

## Adding an Investigation Skill

### 1. Create Skill Module

```python
# src/autosre/skills/myskill.py
from typing import Any

async def analyze(context: dict[str, Any]) -> dict[str, Any]:
    """Analyze something."""
    # Implementation
    return {
        "status": "success",
        "findings": [],
        "confidence": 0.8,
    }
```

### 2. Register Skill

Add to the skills registry or import where needed.

---

## Documentation

### Local Preview

```bash
# Install docs dependencies
pip install -e ".[docs]"

# Serve documentation locally
mkdocs serve

# Build documentation
mkdocs build
```

### Writing Documentation

- **Markdown files** in `docs/`
- Use **admonitions** for notes/warnings
- Include **code examples**
- Keep **navigation** updated in `mkdocs.yml`

---

## Release Process

### Version Bump

Update version in:
1. `pyproject.toml`
2. `src/autosre/__init__.py`

### Create Release

```bash
# Tag release
git tag -a v0.3.0 -m "Release v0.3.0"
git push origin v0.3.0

# CI will publish to PyPI
```

---

## Debugging

### Enable Debug Logging

```bash
export OPENSRE_LOG_LEVEL=DEBUG
autosre investigate run "test alert" --demo
```

### Run with Debugger

```python
# Add breakpoint in code
import pdb; pdb.set_trace()

# Or use VS Code / PyCharm debugger
```

### Test Single Investigation

```bash
# Demo mode (no infrastructure)
autosre investigate run "test alert" --demo

# With verbose output
autosre doctor -v
```

---

## Getting Help

- **Issues:** [GitHub Issues](https://github.com/opensre/autosre/issues)
- **Discussions:** [GitHub Discussions](https://github.com/opensre/autosre/discussions)
- **Discord:** [Join our Discord](https://discord.gg/autosre)

---

## Code of Conduct

We follow the [Contributor Covenant](https://www.contributor-covenant.org/). Be respectful and inclusive.

---

## See Also

- [CLI Commands Reference](COMMANDS.md)
- [Configuration Reference](CONFIGURATION.md)
- [Main README](../README.md)
