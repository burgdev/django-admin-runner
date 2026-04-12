# Installation

## Requirements

- Python 3.12+
- Django 6.0+

## Install

```bash
pip install django-admin-runner
```

Or with uv:

```bash
uv add django-admin-runner
```

## Add to INSTALLED_APPS

```python
# settings.py
INSTALLED_APPS = [
    ...
    "django_admin_runner",
]
```

That's it. The package auto-discovers registered commands on startup via `AppConfig.ready()`.

## Optional extras

For Celery support:

```bash
pip install "django-admin-runner[celery]"
```

For Unfold admin:

```bash
pip install "django-admin-runner[unfold]"
```

## Task backend (optional)

By default the package uses Django 6.0's built-in task system (`django.tasks`).
With `ImmediateBackend` (the default when no `TASKS` setting is configured)
commands run synchronously in the request cycle.

To configure a different backend:

```python
# settings.py — use sync runner (no task backend at all)
ADMIN_RUNNER_BACKEND = "sync"

# settings.py — use Celery
ADMIN_RUNNER_BACKEND = "celery"

# settings.py — custom dotted path
ADMIN_RUNNER_BACKEND = "myapp.runners.MyCustomRunner"
```
