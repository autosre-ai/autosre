# Contributing to AutoSRE

Thank you for your interest in contributing to AutoSRE! This document provides guidelines and instructions for contributing.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Pull Request Process](#pull-request-process)
- [Code Style](#code-style)
- [Testing](#testing)
- [Documentation](#documentation)

## Code of Conduct

This project adheres to a Code of Conduct. By participating, you are expected to uphold this code. Please be respectful and constructive in all interactions.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/autosre.git
   cd autosre
   ```
3. **Add the upstream remote**:
   ```bash
   git remote add upstream https://github.com/autosre-ai/autosre.git
   ```

## Development Setup

### Prerequisites

- Python 3.11+
- Node.js 18+ (for UI development)
- Docker & Docker Compose
- Git

### Installation

```bash
# Install Python dependencies with uv (recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync

# Or with pip
pip install -e ".[dev,all]"

# Install pre-commit hooks
pre-commit install

# Start development services
docker-compose up -d postgres redis

# Run migrations
uv run alembic upgrade head
```

### Running Locally

```bash
# Start the API server with hot reload
make dev-api

# In another terminal, start the UI
cd web-ui && npm install && npm run dev

# Or run everything with Docker
make docker-up
```

## Making Changes

### Branch Naming

Use descriptive branch names:

- `feature/add-prometheus-integration`
- `fix/kubernetes-agent-timeout`
- `docs/improve-api-documentation`
- `refactor/llm-client-abstraction`

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Formatting (no code change)
- `refactor`: Code refactoring
- `test`: Adding tests
- `chore`: Maintenance

Examples:
```
feat(agents): add Datadog metrics integration
fix(kubernetes): handle namespace not found error
docs(readme): add deployment instructions
```

## Pull Request Process

1. **Update your fork**:
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature
   ```

3. **Make your changes** and commit

4. **Ensure all checks pass**:
   ```bash
   make check  # Runs lint, type check, and tests
   ```

5. **Push to your fork**:
   ```bash
   git push origin feature/your-feature
   ```

6. **Open a Pull Request** against `main`

### PR Checklist

- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] CHANGELOG.md updated (for user-facing changes)
- [ ] All CI checks pass
- [ ] Self-reviewed the code

## Code Style

### Python

We use [Ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
# Check linting
ruff check .

# Auto-fix issues
ruff check --fix .

# Format code
ruff format .
```

Key style points:
- Line length: 100 characters
- Use type hints everywhere
- Use `async`/`await` for I/O operations
- Prefer `pydantic` models for data validation

### TypeScript

We use ESLint and Prettier:

```bash
cd web-ui
npm run lint
npm run format
```

## Testing

### Running Tests

```bash
# All tests
make test

# With coverage
make test-cov

# Specific test file
uv run pytest tests/unit/test_triage_agent.py -v

# Integration tests (requires services)
make docker-up
make test-integration
```

### Writing Tests

- Place unit tests in `tests/unit/`
- Place integration tests in `tests/integration/`
- Use fixtures from `tests/conftest.py`
- Mock external services (LLM, Prometheus, etc.)

Example:
```python
import pytest
from autosre.agents.triage import TriageAgent

@pytest.fixture
def triage_agent(mock_llm_client):
    return TriageAgent(llm_client=mock_llm_client)

async def test_triage_classifies_critical_alert(triage_agent, sample_alert):
    result = await triage_agent.classify(sample_alert)
    assert result.severity == "critical"
    assert result.confidence > 0.8
```

## Documentation

- Update README.md for user-facing features
- Add docstrings to all public functions/classes
- Update API documentation when endpoints change
- Add architecture docs for significant changes

### Building Docs

```bash
make docs  # Builds and serves documentation locally
```

## Need Help?

- Check existing [issues](https://github.com/autosre-ai/autosre/issues)
- Join our [Discord](https://discord.gg/autosre) (coming soon)
- Open a [discussion](https://github.com/autosre-ai/autosre/discussions)

---

Thank you for contributing! 🎉
