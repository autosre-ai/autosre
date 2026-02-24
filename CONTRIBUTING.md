# Contributing to SRE-Agent

Thank you for your interest in contributing to SRE-Agent! 🛡️

## How to Contribute

### Reporting Bugs

1. Check if the issue already exists
2. Create a new issue with:
   - Clear title
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details (OS, Python version, K8s version)

### Feature Requests

1. Check existing issues/discussions
2. Open an issue with:
   - Use case description
   - Proposed solution
   - Alternatives considered

### Pull Requests

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Add tests if applicable
5. Run tests: `pytest`
6. Run linting: `ruff check .`
7. Commit with conventional commits: `feat: add new feature`
8. Push and create PR

## Development Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/sre-agent.git
cd sre-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install with dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

## Code Style

- Python: Follow PEP 8, enforced by Ruff
- Type hints: Required for all public functions
- Docstrings: Google style
- Tests: pytest, aim for 80%+ coverage

## Architecture Guidelines

### Adding a New Agent

1. Create `sre_agent/agents/your_agent.py`
2. Follow the existing agent pattern
3. Add to `sre_agent/agents/__init__.py`
4. Add tests in `tests/agents/test_your_agent.py`

### Adding a New Adapter

1. Create `sre_agent/adapters/your_adapter.py`
2. Implement `health_check()` method
3. Add to `sre_agent/adapters/__init__.py`
4. Add tests

### Adding a New Integration

1. Update `.env.example`
2. Add config options in `sre_agent/config.py`
3. Document in README.md
4. Add health check to `/api/status`

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=sre_agent

# Run specific test
pytest tests/agents/test_observer.py
```

## Documentation

- Update README.md for user-facing changes
- Add docstrings for new functions/classes
- Update examples/ for new features

## Release Process

1. Update version in `pyproject.toml` and `sre_agent/__init__.py`
2. Update CHANGELOG.md
3. Create release PR
4. Tag release after merge

## Code of Conduct

Be respectful, inclusive, and constructive. We're all here to build something useful.

## Questions?

Open a discussion or reach out to maintainers.

Thank you for contributing! 🙏
