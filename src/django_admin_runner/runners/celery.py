from __future__ import annotations

from django.urls import reverse

from . import BaseCommandRunner, RunResult


class CeleryCommandRunner(BaseCommandRunner):
    """Enqueues commands as Celery tasks.

    Supports per-task retry control via Celery's ``autoretry_for`` and
    ``max_retries`` on the shared task.
    """

    backend = "celery"
    supports_max_retries = True

    def run(self, command_name, kwargs, triggered_by, execution) -> RunResult:
        from django_admin_runner.celery_tasks import get_celery_task
        from django_admin_runner.registry import _registry

        execution.backend = self.backend
        execution.save(update_fields=["backend"])

        # Read per-command settings
        entry = _registry.get(command_name, {})
        max_retries = entry.get("max_retries", 0)

        try:
            task = get_celery_task(command_name)
            task_kwargs = {"kwargs": kwargs, "execution_pk": execution.pk}
            celery_options = {}
            if max_retries > 0:
                celery_options["max_retries"] = max_retries
            result = task.apply_async(
                kwargs=task_kwargs,
                headers={"periodic_task_name": "Admin Runner"},
                **celery_options,
            )
        except Exception as exc:
            from django_admin_runner.tasks import _append_output

            execution.status = "FAILED"
            _append_output(execution, "stderr", f"Failed to enqueue task: {exc}")
            execution.save(update_fields=["status"])
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
