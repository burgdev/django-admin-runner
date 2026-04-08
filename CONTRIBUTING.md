# Contributing

## Setup

```bash
git clone https://github.com/burgdev/django-admin-runner
cd django-admin-runner
uv sync --all-extras
```

## Running tests

```bash
uv run pytest
```

## Linting

```bash
uv run ruff check src tests
uv run ruff format src tests
```

## Submitting changes

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Open a pull request

Please follow [Conventional Commits](https://www.conventionalcommits.org/) for commit messages.
