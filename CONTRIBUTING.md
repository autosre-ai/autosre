# Contributing to OpenSRE

Thank you for your interest in contributing to OpenSRE! 🎉

This document provides guidelines and information for contributors.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Testing](#testing)
- [Pull Requests](#pull-requests)
- [Coding Standards](#coding-standards)
- [Documentation](#documentation)
- [Community](#community)

## Code of Conduct

We are committed to providing a welcoming and inclusive environment. Please read our [Code of Conduct](CODE_OF_CONDUCT.md) before participating.

## Getting Started

### Ways to Contribute

- 🐛 **Bug Reports** — Found a bug? [Open an issue](https://github.com/srisainath/opensre/issues/new?template=bug_report.md)
- 💡 **Feature Requests** — Have an idea? [Start a discussion](https://github.com/srisainath/opensre/discussions/new?category=ideas)
- 📖 **Documentation** — Improve docs, fix typos, add examples
- 🔌 **New Skills** — Add integrations for new systems
- 🤖 **New Agents** — Create reusable agent templates
- 🧪 **Tests** — Improve test coverage
- 🔍 **Code Review** — Review open pull requests

### First-Time Contributors

Look for issues labeled [`good first issue`](https://github.com/srisainath/opensre/labels/good%20first%20issue) — these are great starting points!

## Development Setup

### Prerequisites

- Python 3.11+
- Git
- Docker (optional, for integration tests)

### Setup

1. **Fork and clone**

   ```bash
   git clone https://github.com/YOUR_USERNAME/opensre.git
   cd opensre
   ```

2. **Create virtual environment**

   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/macOS
   # or: venv\Scripts\activate  # Windows
   ```

3. **Install dependencies**

   ```bash
   pip install -e ".[dev]"
   ```

4. **Install pre-commit hooks**

   ```bash
   pre-commit install
   ```

5. **Verify setup**

   ```bash
   pytest
   ruff check .
   ```

### Project Structure

```
opensre/
├── opensre_core/         # Core library
│   ├── api.py            # REST API server
│   ├── cli.py            # CLI commands
│   ├── orchestrator.py   # Agent orchestration
│   ├── skills/           # Skill base classes
│   └── agents/           # Agent runtime
├── skills/               # Built-in skills
│   ├── prometheus/
│   ├── kubernetes/
│   └── slack/
├── agents/               # Pre-built agents
│   ├── incident-responder/
│   └── pod-crash-handler/
├── tests/                # Test suite
│   ├── unit/
│   └── integration/
├── docs/                 # Documentation
└── examples/             # Example configurations
```

## Making Changes

### Branch Naming

- `feature/description` — New features
- `fix/description` — Bug fixes
- `docs/description` — Documentation changes
- `refactor/description` — Code refactoring
- `test/description` — Test improvements

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types:**
- `feat` — New feature
- `fix` — Bug fix
- `docs` — Documentation
- `style` — Formatting (no code change)
- `refactor` — Code restructuring
- `test` — Adding tests
- `chore` — Maintenance

**Examples:**

```
feat(kubernetes): add rollback confirmation prompt
fix(prometheus): handle empty query results
docs(skills): add slack skill documentation
```

## Testing

### Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=opensre_core --cov-report=html

# Specific test file
pytest tests/unit/test_skills.py

# Specific test
pytest tests/unit/test_skills.py::test_prometheus_query
```

### Writing Tests

- Place unit tests in `tests/unit/`
- Place integration tests in `tests/integration/`
- Use descriptive test names
- Mock external services

```python
# tests/unit/test_prometheus_skill.py
import pytest
from unittest.mock import AsyncMock, patch

from opensre_core.skills.prometheus import PrometheusSkill

@pytest.mark.asyncio
async def test_query_returns_results():
    """Test that query returns expected results."""
    skill = PrometheusSkill(url="http://prometheus:9090")
    
    with patch.object(skill, '_execute_query') as mock:
        mock.return_value = {"status": "success", "data": {"result": []}}
        
        result = await skill.query("up")
        
        assert result["status"] == "success"
        mock.assert_called_once_with("up")
```

### Integration Tests

Integration tests require Docker:

```bash
# Start test services
docker-compose -f docker-compose.test.yml up -d

# Run integration tests
pytest tests/integration/

# Cleanup
docker-compose -f docker-compose.test.yml down
```

## Pull Requests

### Before Submitting

- [ ] Tests pass locally (`pytest`)
- [ ] Linting passes (`ruff check .`)
- [ ] Code is formatted (`ruff format .`)
- [ ] Documentation updated (if applicable)
- [ ] Changelog updated (if applicable)

### PR Template

```markdown
## Description
Brief description of changes.

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation
- [ ] Refactoring

## Testing
How was this tested?

## Checklist
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] Changelog updated
```

### Review Process

1. Create PR against `main` branch
2. Ensure CI passes
3. Request review from maintainers
4. Address feedback
5. Squash and merge

## Coding Standards

### Python Style

We use [Ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
# Check
ruff check .

# Fix auto-fixable issues
ruff check --fix .

# Format
ruff format .
```

### Type Hints

Use type hints for all public functions:

```python
async def query(
    self,
    query: str,
    time: datetime | None = None,
) -> dict[str, Any]:
    """Execute a PromQL query.
    
    Args:
        query: PromQL query string
        time: Evaluation timestamp (defaults to now)
    
    Returns:
        Query result with status and data
    
    Raises:
        PrometheusError: If query fails
    """
    ...
```

### Docstrings

Use Google-style docstrings:

```python
def create_silence(
    self,
    matchers: list[dict],
    duration: str,
    comment: str = "",
) -> str:
    """Create a Prometheus silence.
    
    Args:
        matchers: List of label matchers
        duration: Silence duration (e.g., "2h", "30m")
        comment: Optional comment
    
    Returns:
        Silence ID
    
    Raises:
        PrometheusError: If silence creation fails
    
    Example:
        >>> silence_id = skill.create_silence(
        ...     matchers=[{"name": "alertname", "value": "HighCPU"}],
        ...     duration="2h",
        ...     comment="Investigating"
        ... )
    """
```

### Error Handling

- Use specific exception classes
- Include helpful error messages
- Log appropriately

```python
class PrometheusError(Exception):
    """Prometheus skill error."""
    pass

class PrometheusConnectionError(PrometheusError):
    """Connection to Prometheus failed."""
    pass

# Usage
if response.status_code == 503:
    raise PrometheusConnectionError(
        f"Prometheus unavailable at {self.url}: {response.text}"
    )
```

## Creating Skills

### Skill Structure

```
skills/my_skill/
├── __init__.py
├── skill.yaml         # Metadata
├── SKILL.md           # Documentation
├── actions.py         # Action implementations
├── schemas.py         # Input/output schemas (optional)
└── tests/
    └── test_my_skill.py
```

### skill.yaml

```yaml
name: my_skill
version: 1.0.0
description: Description of what this skill does
author: Your Name

config:
  url:
    type: string
    required: true
    description: Service URL

actions:
  - name: action_name
    description: What this action does
    params:
      - name: param1
        type: string
        required: true
    returns: ResultType

dependencies:
  - some-package>=1.0.0
```

### actions.py

```python
from opensre_core.skills import Skill, action

class MySkill(Skill):
    """My custom skill."""
    
    name = "my_skill"
    version = "1.0.0"
    
    def setup(self, config: dict) -> None:
        self.url = config["url"]
    
    @action
    async def action_name(self, param1: str) -> dict:
        """Execute the action.
        
        Args:
            param1: Parameter description
        
        Returns:
            Action result
        """
        # Implementation
        return {"result": "success"}
```

## Creating Agents

### Agent Structure

```
agents/my-agent/
├── agent.yaml         # Agent definition
├── README.md          # Documentation
└── test_agent.py      # Tests
```

### agent.yaml

```yaml
name: my-agent
version: 1.0.0
description: What this agent does

triggers:
  - type: webhook
    source: alertmanager

skills:
  - prometheus
  - kubernetes
  - slack

config:
  some_setting: default_value

steps:
  - name: step-1
    action: prometheus.query
    params:
      query: "{{ trigger.labels.query }}"
    output: metrics
  
  - name: step-2
    action: slack.post_message
    params:
      channel: "#alerts"
      text: "Found {{ metrics.data.result | length }} results"
```

## Documentation

### Doc Structure

```
docs/
├── getting-started.md
├── installation.md
├── configuration.md
├── cli-reference.md
├── api-reference.md
├── skills/
│   ├── overview.md
│   └── [skill-name].md
├── agents/
│   ├── overview.md
│   └── [agent-name].md
├── deployment/
│   ├── docker.md
│   └── kubernetes.md
└── troubleshooting.md
```

### Writing Docs

- Use clear, concise language
- Include code examples
- Add links to related docs
- Keep examples up to date

## Community

### Getting Help

- [GitHub Discussions](https://github.com/srisainath/opensre/discussions) — Questions and ideas
- [Discord](https://discord.gg/opensre) — Real-time chat
- [Stack Overflow](https://stackoverflow.com/questions/tagged/opensre) — Q&A

### Maintainers

- [@srisainath](https://github.com/srisainath)

---

Thank you for contributing to OpenSRE! 🙏
