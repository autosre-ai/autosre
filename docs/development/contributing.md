# Contributing

Thank you for your interest in contributing to AutoSRE!

## Ways to Contribute

- 🐛 **Bug Reports** - Found a bug? Open an issue
- 💡 **Feature Requests** - Have an idea? Start a discussion
- 📖 **Documentation** - Help improve our docs
- 🔧 **Code** - Submit pull requests

## Development Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Write or update tests
5. Run the test suite
6. Submit a pull request

## Code Style

We use:

- **Ruff** for linting and formatting
- **MyPy** for type checking
- **Black** code style (via Ruff)

Run all checks:

```bash
uv run ruff check .
uv run ruff format .
uv run mypy src/
```

## Commit Messages

Follow conventional commits:

- `feat:` New features
- `fix:` Bug fixes
- `docs:` Documentation changes
- `test:` Test changes
- `refactor:` Code refactoring
- `chore:` Maintenance tasks

## Pull Request Guidelines

- Keep PRs focused and small
- Include tests for new functionality
- Update documentation as needed
- Ensure CI passes
- Request review from maintainers

## Code of Conduct

Be respectful and inclusive. We follow the [Contributor Covenant](https://www.contributor-covenant.org/).
