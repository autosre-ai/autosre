# Development Setup

Set up your local development environment for AutoSRE.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- Git
- Docker (optional, for integration tests)

## Quick Start

```bash
# Clone the repository
git clone https://github.com/autosre/autosre.git
cd autosre

# Install with uv (recommended)
uv sync --extra dev

# Or with pip
pip install -e ".[dev]"
```

## IDE Setup

### VS Code

Recommended extensions:

- Python
- Ruff
- Pylance

Settings (`.vscode/settings.json`):

```json
{
  "python.defaultInterpreterPath": ".venv/bin/python",
  "python.analysis.typeCheckingMode": "basic",
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff",
    "editor.formatOnSave": true
  }
}
```

### PyCharm

1. Set interpreter to `.venv/bin/python`
2. Enable Ruff plugin
3. Configure Ruff as the formatter

## Running Locally

```bash
# Start the development server
uv run autosre server --reload

# Run an investigation
uv run autosre investigate "Test alert"
```

## Environment Variables

Create a `.env` file:

```bash
ANTHROPIC_API_KEY=your-key-here
AUTOSRE_LOG_LEVEL=debug
```

## Pre-commit Hooks

Install pre-commit hooks:

```bash
pip install pre-commit
pre-commit install
```
