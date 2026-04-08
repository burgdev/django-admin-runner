"""Custom RQ runner — demonstrates the full BaseCommandRunner interface."""

import django_rq
from django.urls import reverse

from django_admin_runner.models import CommandExecution
from django_admin_runner.runners import BaseCommandRunner, RunResult
from django_admin_runner.tasks import execute_command


class RqCommandRunner(BaseCommandRunner):
    """Enqueues commands as Django-RQ jobs.

    Shows how to integrate any third-party queue backend (Huey, Dramatiq, etc.)
    by implementing :class:`~django_admin_runner.runners.BaseCommandRunner`.
    """

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
