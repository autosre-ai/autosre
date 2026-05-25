# Testing

Running and writing tests for AutoSRE.

## Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=autosre

# Run specific test file
uv run pytest tests/test_skills.py

# Run specific test
uv run pytest tests/test_skills.py::test_kubernetes_skill -v
```

## Test Categories

### Unit Tests

Fast tests for individual components:

```bash
uv run pytest tests/ -m "not integration"
```

### Integration Tests

Tests that require external services:

```bash
uv run pytest tests/ -m integration
```

### Evaluation Scenarios

Run the evaluation framework:

```bash
uv run autosre eval run --scenario high-cpu
```

## Writing Tests

### Test Structure

```python
import pytest
from autosre.skills import KubernetesSkill

class TestKubernetesSkill:
    """Tests for Kubernetes skill."""

    @pytest.fixture
    def skill(self):
        return KubernetesSkill()

    def test_get_pods(self, skill):
        """Test getting pod list."""
        result = skill.get_pods(namespace="default")
        assert result is not None

    @pytest.mark.integration
    def test_live_cluster(self, skill):
        """Test against live cluster."""
        # Requires KUBECONFIG
        pass
```

### Fixtures

Common fixtures in `conftest.py`:

- `mock_llm` - Mocked LLM responses
- `test_config` - Test configuration
- `sample_alert` - Sample alert data

## Coverage

Generate coverage report:

```bash
uv run pytest --cov=autosre --cov-report=html
open htmlcov/index.html
```

Minimum coverage target: **80%**
