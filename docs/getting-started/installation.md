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

That's it. The package auto-discovers registered commands on startup via
`AppConfig.ready()` — without touching the database — and syncs them into
the database automatically after migrations.

## Keeping commands in sync

Discovered commands and declarative schedules materialize as database rows
when the registry is synced:

- automatically after migrations (`post_migrate` signal), and
- on demand via `python manage.py admin_runner_sync` — manual runs, worker
  boot, or re-sync after code changes.

`AppConfig.ready()` performs no database access, so `django.setup()` works
without a reachable database (image builds running `collectstatic`) and is
safe with gunicorn `--preload` and pooled connections.

To restore the legacy behavior of syncing during app startup, set:

```python
ADMIN_RUNNER_SYNC_ON_READY = True
```

Not recommended with preloaded workers or pooled connections.

## Optional extras

For Celery support:

```bash
pip install "django-admin-runner[celery]"
```

For Django-Q2 support:

```bash
pip install "django-admin-runner[django-q2]"
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

# settings.py — use Django-Q2 (no external broker needed)
ADMIN_RUNNER_BACKEND = "django-q2"

# settings.py — custom dotted path
ADMIN_RUNNER_BACKEND = "myapp.runners.MyCustomRunner"
```
