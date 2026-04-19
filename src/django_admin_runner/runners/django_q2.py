from __future__ import annotations

from django.urls import reverse

from . import BaseCommandRunner, RunResult


class DjangoQ2CommandRunner(BaseCommandRunner):
    """Enqueues commands as django-q2 tasks."""

    backend = "django-q2"

    def run(self, command_name, kwargs, triggered_by, execution) -> RunResult:
        from django_admin_runner.tasks import execute_command

        execution.backend = self.backend
        execution.save(update_fields=["backend"])

        try:
            from django_q.tasks import async_task

            task_id = async_task(execute_command, command_name, kwargs, execution.pk)
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

        execution.task_id = str(task_id)
        execution.save(update_fields=["task_id"])

        return RunResult(
            execution=execution,
            redirect_url=reverse(
                "admin:django_admin_runner_commandexecution_change",
                args=[execution.pk],
            ),
            is_async=True,
            backend=self.backend,
            task_id=str(task_id),
        )
