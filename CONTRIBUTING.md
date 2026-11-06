# Contributing to Merge-TIFF

Thank you for your interest in contributing! This document provides guidelines for contributing to Merge-TIFF.

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you agree to uphold this code.

## Getting Started

### Prerequisites

- Node.js ≥ 24
- Python 3.12+
- Git

### Development Setup

```bash
# Clone the repository
git clone https://github.com/Shreyansh2203/Merge-TIFF.git
cd Merge-TIFF

# Install frontend dependencies
npm install

# Install backend dependencies
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run the development server
npm run dev
python api/merge.py
```

### Running Tests

```bash
# Frontend unit tests
npm run test:ui

# Frontend E2E tests
npm run test:e2e

# Backend API tests
pytest tests/ -q

# Linting
npm run lint
ruff check api/
```

## How to Contribute

### Reporting Bugs

1. Check if the bug has already been reported in [Issues](https://github.com/Shreyansh2203/Merge-TIFF/issues)
2. If not, create a new issue using the [Bug Report template](.github/ISSUE_TEMPLATE/bug_report.yml)
3. Include reproduction steps, expected behavior, and actual behavior

### Suggesting Features

1. Check existing [Issues](https://github.com/Shreyansh2203/Merge-TIFF/issues) and [Discussions](https://github.com/Shreyansh2203/Merge-TIFF/discussions)
2. Create a new issue using the [Feature Request template](.github/ISSUE_TEMPLATE/feature_request.yml)

### Pull Requests

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/your-feature-name`
3. Make your changes
4. Run all tests and linting
5. Commit with a descriptive message (see below)
6. Push to your fork
7. Open a Pull Request

### Commit Conventions

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add new feature
fix: fix a bug
docs: update documentation
style: formatting changes
refactor: code restructuring
test: add or update tests
chore: maintenance tasks
perf: performance improvements
ci: CI/CD changes
```

### Code Style

- **Frontend**: ESLint + Prettier (run `npm run format:check`)
- **Backend**: Ruff (run `ruff check .` and `ruff format --check .`)
- **TypeScript**: Strict mode, no `any` without justification
- **Python**: Type hints required, snake_case naming

### Testing Requirements

- All new features must include tests
- All bug fixes must include a regression test
- Maintain or improve code coverage
- Run the full test suite before submitting

## Review Process

1. A maintainer will review your PR within 48 hours
2. Address any requested changes
3. Once approved, a maintainer will merge

## License

By contributing, you agree that your contributions will be licensed under the MIT License. See [LICENSE](LICENSE) for details.