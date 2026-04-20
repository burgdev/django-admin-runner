## Why

Django-Q2 is a popular task queue for Django that uses Django's ORM as its backend, making it a lightweight alternative to Celery that doesn't require a separate broker for many deployments. Users of django-admin-runner who use django-q2 currently must implement a custom runner via dotted-path import. Adding native django-q2 support gives these users a first-class, zero-config integration just like Celery and Django Tasks users already enjoy.

## What Changes

- Add a new `DjangoQ2CommandRunner` class in `src/django_admin_runner/runners/django_q2.py` that enqueues management commands via `django_q.tasks`
- Register `"django-q2"` as a built-in backend option in `get_runner()`
- Add `django-q2` optional dependency extra in `pyproject.toml`
- Add tests for the django-q2 runner (mirroring the existing runner test patterns)
- Add an `unfold_django_q2` example project using the Django ORM broker (no external services like Redis), with Unfold theme, and a custom `Schedule` admin that offers a dropdown of all registered management commands
- Update documentation: runners guide, installation page, examples page, and API reference

## Capabilities

### New Capabilities
- `django-q2-runner`: Native django-q2 task queue runner that enqueues management commands and tracks task IDs, following the same patterns as the Celery and Django Tasks runners
- `django-q2-schedule-admin`: Custom admin for django-q2's `Schedule` model that provides a choice field listing all registered management commands, so users can schedule recurring commands without knowing dotted function paths

### Modified Capabilities

## Impact

- **New file**: `src/django_admin_runner/runners/django_q2.py` — runner implementation
- **Modified file**: `src/django_admin_runner/runners/__init__.py` — add `"django-q2"` to `get_runner()`
- **Modified file**: `pyproject.toml` — add `django-q2` optional dependency
- **New tests**: test coverage for the django-q2 runner
- **New example**: `examples/unfold_django_q2/` — complete example project with Unfold theme, ORM-only broker (no external services), and custom Schedule admin
- **Modified docs**: `docs/guides/runners.md`, `docs/getting-started/installation.md`, `docs/examples.md`, `docs/api/runners.md` — add django-q2 runner documentation
