# Runners

A runner decides *how* a management command is executed. Configure it with:

```python
# settings.py
ADMIN_RUNNER_BACKEND = "django"  # default
```

## Built-in runners

### `"django"` — DjangoTaskRunner (default)

Uses Django 6.0's built-in `django.tasks` system. When `ImmediateBackend` is
configured, commands run synchronously in the request cycle. With other backends
(e.g. `DatabaseBackend`) they run asynchronously in a worker.

```python
TASKS = {
    "default": {
        "BACKEND": "django.tasks.backends.immediate.ImmediateBackend",
    }
}
# ADMIN_RUNNER_BACKEND not required — "django" is the default
```

### `"sync"` — SyncCommandRunner

Runs commands inline with no task backend at all. Simple and reliable for
development or low-traffic deployments.

```python
ADMIN_RUNNER_BACKEND = "sync"
```

### `"celery"` — CeleryCommandRunner

Enqueues commands as Celery tasks. Requires `celery` installed.

```python
ADMIN_RUNNER_BACKEND = "celery"
CELERY_BROKER_URL = "redis://localhost:6379/0"
```

### `"django-q2"` — DjangoQ2CommandRunner

Enqueues commands as django-q2 tasks. Uses Django's ORM as its message broker,
so no external services (Redis, Docker) are needed. Requires `django-q2` installed.

```python
ADMIN_RUNNER_BACKEND = "django-q2"

Q_CLUSTER = {
    "name": "DJANGORM",
    "orm": "default",  # uses Django's database as the broker
}
```

## RunResult

Every `runner.run()` returns a `RunResult`:

```python
@dataclass
class RunResult:
    execution: CommandExecution
    redirect_url: str
    is_async: bool
    backend: str
    task_id: str = ""
```
