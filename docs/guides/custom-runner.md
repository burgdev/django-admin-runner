# Custom Runner

Any third-party queue (Django-RQ, Huey, Dramatiq, …) can be used by
implementing `BaseCommandRunner`.

## Example: Django-RQ

```python
# myproject/runners.py
import django_rq
from django.urls import reverse

from django_admin_runner.models import CommandExecution
from django_admin_runner.runners import BaseCommandRunner, RunResult
from django_admin_runner.tasks import execute_command


class RqCommandRunner(BaseCommandRunner):
    backend = "rq"

    def run(self, command_name, kwargs, triggered_by, execution) -> RunResult:
        execution.backend = self.backend
        execution.save(update_fields=["backend"])

        job = django_rq.enqueue(execute_command, command_name, kwargs, execution.pk)

        execution.task_id = job.id
        execution.save(update_fields=["task_id"])

        return RunResult(
            execution=execution,
            redirect_url=reverse(
                "admin:django_admin_runner_commandexecution_change",
                args=[execution.pk],
            ),
            is_async=True,
            backend=self.backend,
            task_id=job.id,
        )
```

```python
# settings.py
ADMIN_RUNNER_BACKEND = "myproject.runners.RqCommandRunner"
RQ_QUEUES = {"default": {"HOST": "localhost", "PORT": 6379}}
```

## Key points

- Set `execution.backend` before saving so the record reflects the runner used.
- Use `execute_command` from `django_admin_runner.tasks` — it handles status
  updates, stdout/stderr capture, and timestamps.
- Return a `RunResult` with a valid `redirect_url` (usually the execution detail page).
- Set `is_async=True` if the command runs in a worker process.

## Optional capabilities

`BaseCommandRunner` declares several opt-in capabilities. Override them if
your backend supports them — the admin adapts automatically:

| Attribute / method | Effect |
|---|---|
| `supports_max_retries = True` | Enables per-command `max_retries=` instead of warning |
| `supports_force_stop = True` | Shows the **Force Stop** control once a stop was requested |
| `stop(execution)` | Request a graceful stop (base: sets the `stop_requested` flag; add a SIGTERM-equivalent if you can target the worker) |
| `force_stop(execution) -> bool` | Hard-kill the worker process; return `True` when performed |
| `finalize_stale(execution)` | Attribute why a dead worker's execution ended — return `(status, note)` (e.g. `("TIMEOUT", …)`) or `None` |
| `supported_schedule_kinds` | Schedule kinds your backend can materialize natively (e.g. `frozenset({"cron", "interval", "clocked"})`) — unhides the scheduling UI |
| `create_schedule` / `update_schedule` / `delete_schedule` / `schedule_next_run` | Materialize `ScheduledCommand` rows into your backend's native periodic tasks |

See [django_q2.py](https://github.com/burgdev/django-admin-runner/blob/main/src/django_admin_runner/runners/django_q2.py)
for a complete implementation of all of the above, and the
[Scheduling guide](scheduling.md) for the row/native-object lifecycle.
