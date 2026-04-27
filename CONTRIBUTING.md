# Contributing to AutoSRE

Thank you for your interest in contributing to AutoSRE! This document provides guidelines and instructions for contributing.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Pull Request Process](#pull-request-process)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Documentation](#documentation)

## Code of Conduct

This project follows our [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## Getting Started

### Prerequisites

- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- Git
- Docker (for sandbox features)
- Kind (for local Kubernetes testing)

### First Contribution

Looking for something to work on? Check out:

- [Good first issues](https://github.com/opensre/autosre/labels/good%20first%20issue)
- [Help wanted](https://github.com/opensre/autosre/labels/help%20wanted)
- [Documentation improvements](https://github.com/opensre/autosre/labels/documentation)

## Development Setup

1. **Fork and clone the repository**

```bash
git clone https://github.com/YOUR_USERNAME/autosre.git
cd autosre
```

2. **Install dependencies**

```bash
# Using uv (recommended)
uv sync --all-extras

# Or using pip
pip install -e ".[dev,llm,sandbox]"
```

3. **Set up pre-commit hooks** (optional but recommended)

```bash
uv run pre-commit install
```

4. **Verify your setup**

```bash
# Run tests
uv run pytest

# Check linting
uv run ruff check .

# Run type checking
uv run mypy autosre/
```

## Making Changes

### Branch Naming

Use descriptive branch names:

- `feat/add-slack-connector` - New feature
- `fix/memory-leak-detection` - Bug fix
- `docs/improve-readme` - Documentation
- `refactor/cleanup-context-store` - Refactoring
- `test/add-topology-tests` - Testing

### Commit Messages

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types:**
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `test:` Adding or updating tests
- `refactor:` Code refactoring
- `chore:` Maintenance tasks
- `perf:` Performance improvements

**Examples:**

```
feat(agent): add Slack notification support

Adds ability to send notifications to Slack channels
when incidents are detected.

Closes #123
```

```
fix(connectors): handle Prometheus connection timeout

Previously, the Prometheus connector would hang indefinitely
when the server was unreachable. Now it properly times out
after 30 seconds.
```

## Pull Request Process

1. **Create a branch** from `main`

2. **Make your changes** with clear, focused commits

3. **Update tests** and documentation as needed

4. **Run the test suite** locally

```bash
uv run pytest
uv run ruff check .
uv run mypy autosre/
```

5. **Push your branch** and create a PR

6. **Fill out the PR template** completely

7. **Address review feedback** promptly

### PR Requirements

- [ ] Tests pass (`pytest`)
- [ ] Linting passes (`ruff check .`)
- [ ] Type checking passes (`mypy`)
- [ ] Documentation updated (if applicable)
- [ ] Changelog updated (for significant changes)
- [ ] PR description explains the change

## Coding Standards

### Python Style

We follow [PEP 8](https://peps.python.org/pep-0008/) with these specifics:

- Line length: 88 characters (Black default)
- Use type hints for all public functions
- Docstrings in Google style

```python
def analyze_alert(
    alert: Alert,
    context: dict[str, Any],
    verbose: bool = False,
) -> AnalysisResult:
    """
    Analyze an alert and determine root cause.
    
    Args:
        alert: The alert to analyze
        context: Additional context data
        verbose: If True, include detailed reasoning
        
    Returns:
        AnalysisResult with root cause and recommendations
        
    Raises:
        ValueError: If alert is invalid
    """
    ...
```

### Project Structure

```
autosre/
├── foundation/      # Core data layer
│   ├── models.py    # Pydantic models
│   ├── context_store.py
│   └── connectors/
├── evals/           # Evaluation framework
│   ├── framework.py
│   ├── scenarios/   # YAML scenario definitions
│   └── metrics.py
├── sandbox/         # Testing environment
├── agent/           # AI agent components
│   ├── observer.py
│   ├── reasoner.py
│   ├── actor.py
│   └── guardrails.py
├── feedback/        # Learning pipeline
└── cli/             # Command-line interface
```

### Import Order

1. Standard library
2. Third-party packages
3. Local imports

Use `ruff` for automatic sorting.

## Testing

### Running Tests

```bash
# All tests
uv run pytest

# With coverage
uv run pytest --cov=autosre --cov-report=html

# Specific test file
uv run pytest tests/test_context_store.py

# Specific test
uv run pytest tests/test_models.py::TestService::test_service_creation

# Verbose output
uv run pytest -v
```

### Writing Tests

- Place tests in `tests/` mirroring the source structure
- Use descriptive test names
- Test both success and failure cases
- Use fixtures for common setup

```python
import pytest
from autosre.foundation.models import Service, ServiceStatus

class TestService:
    def test_service_creation(self):
        """Test basic service creation."""
        service = Service(
            name="api-gateway",
            namespace="production",
        )
        assert service.name == "api-gateway"
    
    def test_service_health_check(self):
        """Test is_healthy property."""
        service = Service(
            name="test",
            status=ServiceStatus.HEALTHY,
            replicas=3,
            ready_replicas=3,
        )
        assert service.is_healthy is True
```

### Integration Tests

Mark integration tests that require external services:

```python
@pytest.mark.integration
def test_kubernetes_sync():
    """Test syncing from actual Kubernetes cluster."""
    ...
```

Run with: `pytest -m integration`

## Documentation

### Where to Document

- **Code**: Docstrings for all public APIs
- **README.md**: Quick start and overview
- **docs/**: Detailed guides and references
- **CHANGELOG.md**: User-facing changes

### Documentation Style

- Use clear, concise language
- Include code examples
- Keep examples up to date with the code
- Use Mermaid for diagrams

## Questions?

- Open a [Discussion](https://github.com/opensre/autosre/discussions)
- Join our community (link coming soon)
- Check existing [Issues](https://github.com/opensre/autosre/issues)

Thank you for contributing! 🙏
