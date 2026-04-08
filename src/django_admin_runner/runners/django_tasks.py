from __future__ import annotations

from django.urls import reverse

from . import BaseCommandRunner, RunResult

_wrapped_task = None


def _get_django_task():
    """Return a cached django.tasks-wrapped version of ``execute_command``."""
    global _wrapped_task
    if _wrapped_task is None:
        from django.tasks import task

        from django_admin_runner.tasks import execute_command

        _wrapped_task = task(execute_command)
    return _wrapped_task


def _is_immediate_backend() -> bool:
    """Return ``True`` when the default task backend is ``ImmediateBackend``."""
    from django.conf import settings

    tasks_config = getattr(settings, "TASKS", {})
    default = tasks_config.get("default", {})
    backend_path = default.get("BACKEND", "")
    return "ImmediateBackend" in backend_path


class DjangoTaskRunner(BaseCommandRunner):
    """Enqueues commands using Django 6.0's built-in task system (``django.tasks``)."""

    backend = "django"

    def run(self, command_name, kwargs, triggered_by, execution) -> RunResult:
        execution.backend = self.backend
        execution.save(update_fields=["backend"])

        wrapped = _get_django_task()
        result = wrapped.enqueue(command_name, kwargs, execution.pk)

        task_id = str(result.id) if getattr(result, "id", None) is not None else ""
        execution.task_id = task_id
        execution.save(update_fields=["task_id"])
        execution.refresh_from_db()

        return RunResult(
            execution=execution,
            redirect_url=reverse(
                "admin:django_admin_runner_commandexecution_change",
                args=[execution.pk],
            ),
            is_async=not _is_immediate_backend(),
            backend=self.backend,
            task_id=task_id,
        )
