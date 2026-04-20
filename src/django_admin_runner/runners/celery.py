from __future__ import annotations

from django.urls import reverse

from . import BaseCommandRunner, RunResult


class CeleryCommandRunner(BaseCommandRunner):
    """Enqueues commands as Celery tasks."""

    backend = "celery"

    def run(self, command_name, kwargs, triggered_by, execution) -> RunResult:
        from django_admin_runner.celery_tasks import get_celery_task

        execution.backend = self.backend
        execution.save(update_fields=["backend"])

        try:
            task = get_celery_task(command_name)
            result = task.apply_async(
                kwargs={"kwargs": kwargs, "execution_pk": execution.pk},
                headers={"periodic_task_name": "Admin Runner"},
            )
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
