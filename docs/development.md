# Development Guide

This guide covers setting up a development environment, running tests, contributing, and code style guidelines.

---

## Development Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- Git

### Clone Repository

```bash
git clone https://github.com/autosre/autosre-v2.git
cd autosre-v2
```

### Install Dependencies

```bash
# Setup creates config files and directories
make setup

# Install all dependencies
make install
```

This installs:
- Python packages via `uv` (fast package manager)
- Node.js packages via `npm`

### Configure Environment

```bash
# Copy example config
cp .env.example .env

# Edit with your settings
vi .env
```

Minimum required:
```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key
AUTOSRE_SECRET_KEY=dev-secret-change-in-prod
```

### Start Development Servers

```bash
# Start everything (API + UI + infrastructure)
make dev

# Or start components individually
make dev-api    # API only (port 8000)
make dev-ui     # UI only (port 3000)
```

### Verify Setup

```bash
# Check environment
make env-check

# Run tests
make test
```

---

## Project Structure

```
autosre-v2/
├── src/autosre/           # Python backend
│   ├── agents/            # AI agents (triage, investigation, remediation)
│   │   ├── base_agent.py  # Base agent class
│   │   ├── coordinator.py # Agent orchestration
│   │   ├── triage_agent.py
│   │   ├── investigation_agent.py
│   │   └── remediation_agent.py
│   ├── api/               # FastAPI endpoints
│   │   ├── app.py         # Application factory
│   │   └── routes/        # Route handlers
│   ├── cli/               # Command-line interface
│   │   ├── main.py        # CLI entry point
│   │   ├── investigate.py
│   │   └── chat.py
│   ├── core/              # Core types and utilities
│   │   ├── alert.py       # Alert models
│   │   ├── investigation.py
│   │   ├── llm_client.py  # LLM abstraction
│   │   └── prompts.py     # Prompt templates
│   ├── integrations/      # External integrations
│   │   ├── prometheus.py
│   │   ├── loki.py
│   │   ├── kubernetes.py
│   │   └── slack.py
│   └── utils/             # Helpers
│       ├── config.py      # Configuration loading
│       ├── logging.py     # Structured logging
│       └── cache.py       # Caching utilities
├── web-ui/                # React frontend
│   └── src/
│       ├── components/    # UI components
│       ├── hooks/         # React hooks
│       ├── pages/         # Page components
│       └── api/           # API client
├── tests/                 # Test suite
│   ├── unit/              # Unit tests
│   ├── integration/       # Integration tests
│   └── e2e/               # End-to-end tests
├── deploy/                # Deployment configs
│   ├── kubernetes/        # K8s manifests
│   └── helm/              # Helm chart
├── docker/                # Dockerfiles
└── docs/                  # Documentation
```

---

## Running Tests

### All Tests

```bash
make test
```

### With Coverage

```bash
make test-cov
```

Coverage report is generated at `htmlcov/index.html`.

### Specific Tests

```bash
# Unit tests only
make test-unit

# Integration tests (requires running services)
make docker-up  # Start dependencies
make test-integration

# End-to-end tests
make test-e2e

# Specific file
uv run pytest tests/unit/test_triage_agent.py -v

# Specific test
uv run pytest tests/unit/test_triage_agent.py::test_classify_alert -v

# Pattern matching
uv run pytest -k "triage" -v
```

### Watch Mode

```bash
make test-watch
```

### Test Fixtures

Common fixtures are in `tests/conftest.py`:

```python
import pytest
from autosre.core.alert import Alert

@pytest.fixture
def sample_alert():
    return Alert(
        name="HighErrorRate",
        description="Error rate above threshold",
        severity="critical",
        service="payment-service",
        namespace="production"
    )

@pytest.fixture
def mock_prometheus(mocker):
    """Mock Prometheus client."""
    mock = mocker.patch("autosre.integrations.prometheus.PrometheusClient")
    mock.return_value.query.return_value = {"status": "success", "data": {...}}
    return mock
```

### Writing Tests

```python
# tests/unit/test_triage_agent.py

import pytest
from autosre.agents.triage_agent import TriageAgent

class TestTriageAgent:
    """Tests for TriageAgent."""
    
    @pytest.fixture
    def agent(self):
        return TriageAgent()
    
    async def test_classify_alert_latency(self, agent, sample_alert):
        """Test alert classification for latency issues."""
        sample_alert.name = "HighLatency"
        result = await agent.quick_classify(sample_alert)
        
        assert result["category"] == "latency"
        assert "metrics" in result["recommended_agents"]
    
    async def test_classify_alert_errors(self, agent, sample_alert):
        """Test alert classification for error issues."""
        sample_alert.name = "HighErrorRate"
        result = await agent.quick_classify(sample_alert)
        
        assert result["category"] == "errors"
        assert result["priority"] == "high"
    
    @pytest.mark.parametrize("alert_name,expected_category", [
        ("HighCPUUsage", "resources"),
        ("PodCrashLooping", "availability"),
        ("ConnectionTimeout", "connectivity"),
    ])
    async def test_classify_various_alerts(
        self, agent, sample_alert, alert_name, expected_category
    ):
        """Test classification of various alert types."""
        sample_alert.name = alert_name
        result = await agent.quick_classify(sample_alert)
        assert result["category"] == expected_category
```

---

## Code Quality

### Linting

```bash
# Run all linters
make lint

# Python linting (Ruff)
uv run ruff check src/ tests/

# Type checking (Mypy)
uv run mypy src/

# Frontend linting (ESLint)
cd web-ui && npm run lint
```

### Auto-fix

```bash
# Fix linting issues
make lint-fix

# Format code
make format
```

### Pre-commit Hooks

```bash
# Install hooks
uv run pre-commit install

# Run manually
make pre-commit
```

### Run All Checks

```bash
make check  # lint + test
```

---

## Code Style

### Python

We use [Ruff](https://docs.astral.sh/ruff/) for linting and formatting.

**Key Rules:**
- Line length: 88 characters (Black-style)
- Imports: sorted, grouped (standard, third-party, local)
- Docstrings: Google style
- Type hints: Required for public APIs

**Example:**

```python
"""
Module docstring describing purpose.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from autosre.core.alert import Alert
from autosre.utils.logging import get_logger

logger = get_logger(__name__)


class TriageResult(BaseModel):
    """Result of triage analysis.
    
    Attributes:
        category: Alert category (latency, errors, etc.)
        severity: Assessed severity level.
        hypotheses: List of potential causes.
    """
    
    category: str = Field(description="Alert category")
    severity: str = Field(description="Severity level")
    hypotheses: list[dict[str, Any]] = Field(default_factory=list)


async def classify_alert(alert: Alert) -> TriageResult:
    """Classify an alert and generate hypotheses.
    
    Args:
        alert: The alert to classify.
        
    Returns:
        Triage result with category and hypotheses.
        
    Raises:
        ValueError: If alert is invalid.
    """
    logger.info("Classifying alert", alert_name=alert.name)
    
    # Implementation
    return TriageResult(
        category="errors",
        severity="high",
        hypotheses=[],
    )
```

### TypeScript

We use ESLint + Prettier.

**Example:**

```typescript
import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';

import { Investigation } from '@/types';
import { fetchInvestigation } from '@/api/investigations';

interface UseInvestigationProps {
  id: string;
  pollInterval?: number;
}

/**
 * Hook for fetching and polling investigation status.
 */
export function useInvestigation({ id, pollInterval = 5000 }: UseInvestigationProps) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['investigation', id],
    queryFn: () => fetchInvestigation(id),
    refetchInterval: (data) => {
      // Stop polling when completed
      if (data?.status === 'completed' || data?.status === 'failed') {
        return false;
      }
      return pollInterval;
    },
  });

  return { investigation: data, isLoading, error };
}
```

---

## Contributing

### Getting Started

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

### Branch Naming

- `feature/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation
- `refactor/description` - Code refactoring

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): description

[optional body]

[optional footer]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Formatting (no code change)
- `refactor`: Code refactoring
- `test`: Adding tests
- `chore`: Maintenance

**Examples:**
```
feat(agents): add custom investigation agent support

fix(prometheus): handle connection timeout gracefully

docs(api): add WebSocket documentation

refactor(coordinator): simplify agent dispatch logic
```

### Pull Request Process

1. **Description**: Clearly describe your changes
2. **Tests**: Add tests for new functionality
3. **Documentation**: Update docs if needed
4. **Changelog**: Add entry to CHANGELOG.md
5. **Review**: Address review comments

### PR Template

```markdown
## Description
Brief description of changes.

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing performed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-reviewed
- [ ] Documentation updated
- [ ] No new warnings
```

---

## Database Migrations

We use Alembic for database migrations.

### Create Migration

```bash
# Auto-generate from model changes
make db-revision
# Enter: "Add investigation status index"

# Or manually
uv run alembic revision -m "add_investigation_index"
```

### Run Migrations

```bash
make db-migrate    # Apply all pending
make db-upgrade    # Same as migrate
make db-downgrade  # Roll back one
```

### Migration File

```python
# alembic/versions/xxxx_add_investigation_index.py

"""Add investigation status index

Revision ID: abc123
Revises: def456
Create Date: 2024-01-15 10:00:00
"""

from alembic import op
import sqlalchemy as sa

revision = 'abc123'
down_revision = 'def456'

def upgrade():
    op.create_index(
        'ix_investigations_status',
        'investigations',
        ['status'],
    )

def downgrade():
    op.drop_index('ix_investigations_status', 'investigations')
```

---

## Building

### Python Package

```bash
uv build
# Creates dist/autosre-2.0.0.tar.gz
```

### Docker Images

```bash
# Build all
make build

# Build specific
make build-api
make build-ui

# Push to registry
make build-push
```

---

## Debugging

### API Debugging

```bash
# Enable debug mode
AUTOSRE_DEBUG=true AUTOSRE_LOG_LEVEL=DEBUG make dev-api
```

### Agent Debugging

```python
# Enable verbose agent logging
import logging
logging.getLogger("autosre.agents").setLevel(logging.DEBUG)
```

### Database Debugging

```bash
# Connect to database
docker compose exec postgres psql -U autosre -d autosre

# SQL queries
SELECT * FROM investigations ORDER BY created_at DESC LIMIT 5;
```

### VS Code Launch Config

```json
// .vscode/launch.json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Debug API",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": [
        "autosre.api.app:app",
        "--reload",
        "--host", "0.0.0.0",
        "--port", "8000"
      ],
      "cwd": "${workspaceFolder}/src",
      "env": {
        "AUTOSRE_DEBUG": "true"
      }
    },
    {
      "name": "Debug Tests",
      "type": "python",
      "request": "launch",
      "module": "pytest",
      "args": ["-v", "${file}"],
      "cwd": "${workspaceFolder}"
    }
  ]
}
```

---

## Release Process

### Versioning

We follow [Semantic Versioning](https://semver.org/):
- MAJOR: Breaking changes
- MINOR: New features (backward compatible)
- PATCH: Bug fixes

### Release Steps

1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md`
3. Create PR titled "Release vX.Y.Z"
4. After merge, create Git tag
5. CI builds and publishes automatically

```bash
# Tag release
git tag -a v2.1.0 -m "Release v2.1.0"
git push origin v2.1.0
```

---

## Getting Help

- **Documentation**: Read the docs first
- **GitHub Issues**: Search existing issues
- **Discussions**: Ask questions in GitHub Discussions
- **Discord**: Join our community (link in README)

### Reporting Bugs

Include:
1. AutoSRE version (`autosre --version`)
2. Python version (`python --version`)
3. OS and version
4. Steps to reproduce
5. Expected vs actual behavior
6. Logs and error messages
