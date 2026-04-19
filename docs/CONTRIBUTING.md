# Contributing to OpenSRE

Thank you for your interest in contributing to OpenSRE! This guide will help you get started.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How to Contribute](#how-to-contribute)
- [Development Setup](#development-setup)
- [Code Style](#code-style)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Architecture Guidelines](#architecture-guidelines)

---

## Code of Conduct

Be respectful, inclusive, and constructive. We're building something useful together.

**Do:**
- Welcome newcomers
- Give constructive feedback
- Focus on the issue, not the person
- Assume good intentions

**Don't:**
- Harass or discriminate
- Be dismissive
- Use offensive language

---

## How to Contribute

### Reporting Bugs

1. **Search existing issues** to avoid duplicates
2. **Create a new issue** with:
   - Clear, descriptive title
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details:
     ```
     OS: macOS 14.0
     Python: 3.11.4
     OpenSRE: 0.1.0
     Kubernetes: 1.28
     ```
   - Relevant logs (redact secrets!)

### Feature Requests

1. **Check the roadmap** in README.md
2. **Open a discussion** for major features
3. **Create an issue** with:
   - Use case description
   - Proposed solution
   - Alternatives considered

### Contributing Code

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Write tests
5. Submit a pull request

---

## Development Setup

### Prerequisites

- Python 3.11+
- Git
- Docker (optional)
- kubectl configured

### Clone and Install

```bash
# Fork on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/opensre.git
cd opensre

# Add upstream remote
git remote add upstream https://github.com/srisainath/opensre.git

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install with dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pip install pre-commit
pre-commit install
```

### Dev Dependencies

```bash
# Testing
pip install pytest pytest-cov pytest-asyncio

# Linting
pip install ruff mypy

# Documentation
pip install mkdocs mkdocs-material
```

### Configuration for Development

```bash
# Copy example env
cp .env.example .env

# Use mock mode for testing without infrastructure
# Edit config.yaml:
#   sources:
#     prometheus:
#       mode: mock
#     kubernetes:
#       mode: mock
```

### Running Locally

```bash
# Start the server with hot reload
uvicorn opensre_core.api:create_app --factory --reload --port 8080

# Or use the CLI
python -m opensre.cli investigate "test issue"
```

---

## Code Style

### Python Style Guide

We follow [PEP 8](https://pep8.org/) with some modifications, enforced by Ruff.

```bash
# Check style
ruff check .

# Auto-fix issues
ruff check . --fix

# Format code
ruff format .
```

### Key Style Rules

```python
# ✅ Good
from typing import Any

def calculate_confidence(
    observations: list[Observation],
    threshold: float = 0.7,
) -> float:
    """
    Calculate confidence score from observations.
    
    Args:
        observations: List of observation objects
        threshold: Minimum confidence threshold
    
    Returns:
        Confidence score between 0.0 and 1.0
    """
    if not observations:
        return 0.0
    
    scores = [obs.severity_score for obs in observations]
    return sum(scores) / len(scores)


# ❌ Bad
def calc_conf(obs, t=0.7):
    # no docstring, unclear names
    if not obs: return 0
    return sum([o.severity_score for o in obs])/len(obs)
```

### Type Hints

Required for all public functions:

```python
# ✅ Good
async def investigate(
    issue: str,
    namespace: str = "default",
) -> InvestigationResult:
    ...

# ❌ Bad
async def investigate(issue, namespace="default"):
    ...
```

### Docstrings

Use Google style:

```python
def analyze_metrics(
    metrics: list[Metric],
    time_range: timedelta,
) -> AnalysisResult:
    """
    Analyze metrics for anomalies.
    
    Args:
        metrics: List of metric objects to analyze
        time_range: Time range to consider
    
    Returns:
        AnalysisResult containing findings
    
    Raises:
        ValueError: If metrics list is empty
        AnalysisError: If analysis fails
    
    Example:
        >>> result = analyze_metrics(metrics, timedelta(hours=1))
        >>> print(result.anomalies)
    """
```

### Imports

Organized by:
1. Standard library
2. Third-party packages
3. Local imports

```python
# Standard library
import asyncio
from dataclasses import dataclass
from datetime import datetime

# Third-party
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Local
from opensre_core.agents import ObserverAgent
from opensre_core.config import settings
```

---

## Testing

### Running Tests

```bash
# Run all tests
pytest

# With coverage
pytest --cov=opensre_core --cov-report=html

# Specific test file
pytest tests/agents/test_observer.py

# Specific test
pytest tests/agents/test_observer.py::test_observe_metrics

# Verbose output
pytest -v

# Run only fast tests (no integration)
pytest -m "not integration"
```

### Test Structure

```
tests/
├── conftest.py            # Shared fixtures
├── test_api.py            # API endpoint tests
├── agents/
│   ├── test_observe.py    # Observer agent tests
│   ├── test_reason.py     # Reasoner agent tests
│   └── test_act.py        # Actor agent tests
├── adapters/
│   ├── test_prometheus.py
│   └── test_kubernetes.py
├── integration/           # Integration tests
│   └── test_investigations.py
└── security/             # Security tests
    ├── test_auth.py
    └── test_rbac.py
```

### Writing Tests

```python
# tests/agents/test_observer.py
import pytest
from opensre_core.agents import ObserverAgent


@pytest.fixture
def observer():
    """Create observer with mock adapters."""
    return ObserverAgent(use_mocks=True)


@pytest.mark.asyncio
async def test_observe_returns_observations(observer):
    """Observer should return observations for an issue."""
    result = await observer.observe(
        issue="High memory usage",
        namespace="production",
    )
    
    assert result.observations is not None
    assert len(result.observations) > 0


@pytest.mark.asyncio
async def test_observe_handles_empty_namespace(observer):
    """Observer should handle missing namespace gracefully."""
    result = await observer.observe(
        issue="Test issue",
        namespace="nonexistent",
    )
    
    # Should return empty but not fail
    assert result is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_observe_real_prometheus():
    """Integration test with real Prometheus."""
    # Requires OPENSRE_PROMETHEUS_URL to be set
    observer = ObserverAgent(use_mocks=False)
    result = await observer.observe("test", "default")
    assert result is not None
```

### Test Coverage

Aim for 80%+ coverage on core modules:

```bash
pytest --cov=opensre_core --cov-fail-under=80
```

---

## Pull Request Process

### Before Submitting

1. **Update from upstream:**
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Run checks locally:**
   ```bash
   # Lint
   ruff check .
   
   # Type check
   mypy opensre_core
   
   # Tests
   pytest
   ```

3. **Update documentation** if needed

4. **Write meaningful commit messages:**
   ```
   feat: add PagerDuty integration
   
   - Add PagerDuty adapter with incident creation
   - Configure via OPENSRE_PAGERDUTY_API_KEY
   - Add tests for PagerDuty webhook handling
   
   Closes #123
   ```

### Commit Convention

We use [Conventional Commits](https://www.conventionalcommits.org/):

| Type | Description |
|------|-------------|
| `feat:` | New feature |
| `fix:` | Bug fix |
| `docs:` | Documentation only |
| `style:` | Formatting, no code change |
| `refactor:` | Code change, no new feature or fix |
| `test:` | Adding tests |
| `chore:` | Maintenance tasks |

### PR Description Template

```markdown
## Summary
Brief description of changes.

## Changes
- Added X
- Fixed Y
- Updated Z

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests pass
- [ ] Manual testing done

## Documentation
- [ ] README updated (if applicable)
- [ ] Docstrings added
- [ ] CHANGELOG updated

## Related Issues
Closes #123
```

### Review Process

1. **Automated checks** must pass (CI/CD)
2. **Code review** by maintainer
3. **Address feedback** via additional commits
4. **Squash and merge** when approved

---

## Architecture Guidelines

### Adding a New Agent

1. Create `opensre_core/agents/your_agent.py`:

```python
from dataclasses import dataclass


@dataclass
class YourResult:
    """Result from YourAgent analysis."""
    data: dict
    confidence: float


class YourAgent:
    """Agent for doing X."""
    
    async def process(self, input_data: dict) -> YourResult:
        """Process input and return result."""
        # Implementation
        pass
```

2. Add to `opensre_core/agents/__init__.py`
3. Write tests in `tests/agents/test_your_agent.py`
4. Document in `docs/ARCHITECTURE.md`

### Adding a New Adapter

1. Create `opensre_core/adapters/your_adapter.py`:

```python
class YourAdapter:
    """Adapter for Your Service."""
    
    def __init__(self, url: str, token: str | None = None):
        self.url = url
        self.token = token
    
    async def health_check(self) -> dict:
        """Check connection health."""
        # Implementation
        return {"status": "connected"}
    
    async def query(self, query: str) -> list[dict]:
        """Query the service."""
        # Implementation
        pass
```

2. Add configuration to `opensre_core/config.py`
3. Add to `opensre_core/adapters/__init__.py`
4. Write tests in `tests/adapters/test_your_adapter.py`

### Adding a New Integration

1. Update `.env.example` with new variables
2. Add config options in `config.py`
3. Add health check to `/api/status`
4. Document in `docs/INTEGRATIONS.md`
5. Add to `docs/CONFIGURATION.md`

---

## Areas We Need Help

### High Priority
- **Additional integrations:** Datadog, New Relic, Splunk
- **More runbook templates:** Common scenarios
- **Testing and feedback:** Real-world usage

### Medium Priority
- **Documentation improvements**
- **Performance optimization**
- **UI enhancements**

### Nice to Have
- **Multi-language support**
- **Additional LLM providers**
- **Custom action plugins**

---

## Questions?

- Open a [GitHub Discussion](https://github.com/srisainath/opensre/discussions)
- Check existing [Issues](https://github.com/srisainath/opensre/issues)

Thank you for contributing! 🙏
