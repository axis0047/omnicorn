# Contributing to Omnicorn

Thank you for considering contributing to Omnicorn! This document outlines how to contribute to the project.

## Development Setup

### Prerequisites

- **Python**: 3.9+
- **Erlang/OTP**: 25+
- **rebar3**: 3.20+

### Local Development

```bash
# Clone the repository
git clone https://github.com/axis0047/omnicorn.git
cd omnicorn

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac

# Install in development mode
pip install -e ".[dev]"

# Build Erlang backend
cd omnicorn/erl_src
rebar3 release
cd ../..

# Run tests
./scripts/test.sh
```

## Branch Strategy

We use a structured branching model:

```
release/stable          ← Production releases (protected)
  └─ dev/stable         ← Integration branch for current release
        └─ dev/stable-phase-X  ← Feature branches
```

### Workflow

1. **Create feature branch** from `dev/stable`

   ```bash
   git checkout -b dev/stable-phase-0 dev/stable
   ```

2. **Make changes** with tests

3. **Run CI checks** locally

   ```bash
   ./scripts/test.sh
   ```

4. **Create PR** to `dev/stable`

5. **Code review** by maintainers

6. **Merge** after approval

## Code Style

### Python

- **Formatter**: Black (line length: 100)
- **Linter**: Ruff
- **Type checking**: mypy
- **Docstrings**: Google style

```bash
# Format code
black omnicorn/ tests/

# Lint
ruff check omnicorn/ tests/

# Type check
mypy omnicorn/
```

### Erlang

- **Formatter**: rebar3 fmt
- **Linter**: rebar3 lint
- **Documentation**: Edoc

```bash
cd omnicorn/erl_src

# Format
rebar3 fmt

# Lint
rebar3 lint
```

## Testing Requirements

- **Python**: pytest with >70% coverage
- **Erlang**: EUnit tests for all public APIs
- **Integration**: End-to-end tests for critical paths

### Running Tests

```bash
# All tests
./scripts/test.sh

# Python only
pytest tests/ -v --cov=omnicorn

# Erlang only
cd omnicorn/erl_src && rebar3 eunit
```

## Pull Request Guidelines

### PR Title Format

```
<type>(scope): <description>

Examples:
- feat(cache): add TTL support
- fix(router): prevent worker pool deadlock
- docs(readme): update installation instructions
```

### Types

- `feat` - New feature
- `fix` - Bug fix
- `docs` - Documentation changes
- `style` - Code style changes (formatting)
- `refactor` - Code refactoring
- `test` - Test additions/changes
- `chore` - Build/config changes

### PR Checklist

- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] CHANGELOG.md entry added
- [ ] No new warnings/errors
- [ ] Branch rebased on latest `dev/stable`

### Review Process

1. **Automated checks** must pass (CI)
2. **One maintainer** approval required
3. **No unresolved** comments
4. **Squash merge** to keep history clean

## Reporting Issues

### Bug Reports

Include:

- Omnicorn version
- Python/Erlang versions
- OS and architecture
- Steps to reproduce
- Expected vs actual behavior
- Logs (with sensitive data removed)

### Feature Requests

Include:

- Use case description
- Proposed solution
- Alternatives considered
- Impact on existing features

## Release Process

Releases follow [Semantic Versioning](https://semver.org/):

- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

### Release Checklist

- [ ] All tests passing
- [ ] Documentation complete
- [ ] CHANGELOG updated
- [ ] Version bumped in `__init__.py` and `.app.src`
- [ ] Git tag created

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help newcomers
- Stay on topic

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
