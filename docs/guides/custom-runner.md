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
