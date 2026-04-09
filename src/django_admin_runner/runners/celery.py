from __future__ import annotations

from django.urls import reverse

from . import BaseCommandRunner, RunResult

_celery_task = None


def _get_celery_task():
    """Return a cached Celery ``shared_task`` wrapping ``execute_command``."""
    global _celery_task
    if _celery_task is None:
        from celery import shared_task

        from django_admin_runner.tasks import execute_command

        _celery_task = shared_task(
            execute_command,
            name="django_admin_runner.execute_command",
        )
    return _celery_task


class CeleryCommandRunner(BaseCommandRunner):
    """Enqueues commands as Celery tasks."""

    backend = "celery"

    def run(self, command_name, kwargs, triggered_by, execution) -> RunResult:
        celery_task = _get_celery_task()

        execution.backend = self.backend
        execution.save(update_fields=["backend"])

        try:
            result = celery_task.delay(command_name, kwargs, execution.pk)
        except Exception as exc:
            execution.status = "FAILED"
            execution.stderr = f"Failed to enqueue task: {exc}"
            execution.save(update_fields=["status", "stderr"])
            return RunResult(
                execution=execution,
                redirect_url=reverse(
                    "admin:django_admin_runner_commandexecution_change",
                    args=[execution.pk],
                ),
                is_async=False,
                backend=self.backend,
                task_id="",
            )

        execution.task_id = result.id
        execution.save(update_fields=["task_id"])

        return RunResult(
            execution=execution,
            redirect_url=reverse(
                "admin:django_admin_runner_commandexecution_change",
                args=[execution.pk],
            ),
            is_async=True,
            backend=self.backend,
            task_id=result.id,
        )
