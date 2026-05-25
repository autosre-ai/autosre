# Releasing

AutoSRE release process and versioning.

## Versioning

We follow [Semantic Versioning](https://semver.org/):

- **MAJOR** - Breaking changes
- **MINOR** - New features (backward compatible)
- **PATCH** - Bug fixes (backward compatible)

## Release Process

### 1. Prepare Release

```bash
# Ensure main is up to date
git checkout main
git pull origin main

# Run all tests
uv run pytest

# Check lint
uv run ruff check .
```

### 2. Update Version

Update version in `pyproject.toml`:

```toml
version = "X.Y.Z"
```

### 3. Update Changelog

Add entry to `CHANGELOG.md`:

```markdown
## [X.Y.Z] - YYYY-MM-DD

### Added
- New feature description

### Fixed
- Bug fix description

### Changed
- Change description
```

### 4. Create Release

```bash
# Commit changes
git add pyproject.toml CHANGELOG.md
git commit -m "chore: release vX.Y.Z"

# Tag release
git tag -a vX.Y.Z -m "Release vX.Y.Z"

# Push
git push origin main --tags
```

### 5. GitHub Release

1. Go to GitHub Releases
2. Create release from tag
3. Copy changelog entry to description
4. Publish release

### 6. Automated Publish

The GitHub Actions `release.yml` workflow automatically:

- Builds the package
- Publishes to PyPI
- Builds and pushes Docker images

## Hotfix Process

For urgent fixes:

```bash
git checkout -b hotfix/fix-description main
# Make fix
git commit -m "fix: description"
# PR to main, then release
```
