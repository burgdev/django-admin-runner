# AGENTS.md

## Project

Django package for running management commands from the Django admin interface. Auto-generates forms from argparse, supports pluggable runners (sync, Django Tasks, Celery), and logs all executions.

## Stack

- Python >=3.12, Django >=6.0
- Build: hatchling
- Package manager: uv
- Task runner: just (`just help` for commands)
- Linting: ruff + pre-commit
- Type checking: pyright
- Tests: pytest + pytest-django
- Docs: mkdocs

## Common Commands

```bash
just install          # Install deps + pre-commit hooks
just check            # Lint (ruff + pre-commit hooks)
just check fix        # Auto-fix with ruff
just check types      # Pyright type checking
just tests            # Run pytest
just tests cov=yes    # Run pytest with coverage
just docs             # Build docs
```

## Structure

```
src/django_admin_runner/     # Package source
  runners/                   # Runner implementations (sync, celery, django_tasks)
  registry.py                # @register_command decorator
  forms.py                   # Auto-generated form fields from argparse
  models.py                  # CommandExecution model
  admin.py                   # Admin integration
tests/                       # pytest suite (settings.py for Django config)
examples/                    # Example projects (classic, unfold_celery, unfold_rq)
docs/                        # MkDocs documentation
tasks/                       # Just task definitions
```

## Conventions

- Source code lives in `src/django_admin_runner/` (src layout).
- Run `just check` before committing — CI runs the same checks.
- Tests use SQLite in-memory DB and `ImmediateBackend` for Django tasks (no worker needed).
- Optional deps (celery, unfold, rich) are gated behind extras in pyproject.toml.
