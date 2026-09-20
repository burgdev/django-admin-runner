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
    supports_force_stop = True

    def _revoke(self, execution, signal: str) -> None:
        """Revoke the execution's task, terminating a running worker."""
        if not execution.task_id:
            return
        from celery import current_app

        current_app.control.revoke(
            execution.task_id,
            terminate=True,
            signal=signal,
        )

    def stop(self, execution) -> None:
        """Graceful stop: stop flag (heartbeat) + revoke with SIGTERM."""
        super().stop(execution)
        self._revoke(execution, "SIGTERM")

    def force_stop(self, execution) -> bool:
        """Hard kill: revoke with SIGKILL."""
        if not execution.task_id:
            return False
        self._revoke(execution, "SIGKILL")
        return True

    def finalize_stale(self, execution):
        """Attribute a swept execution via the Celery result backend.

        REVOKED tasks (e.g. killed by a hard ``time_limit`` revoke) are
        reported as TIMEOUT; FAILURE as FAILED. Best effort — an
        unreachable broker yields ``None`` (generic FAILED).
        """
        if not execution.task_id:
            return None
        try:
            from celery.result import AsyncResult

            state = AsyncResult(execution.task_id).state
        except Exception:  # noqa: BLE001 - attribution must never break the sweep
            return None
        from django_admin_runner.models import CommandExecution

        if state == "REVOKED":
            return (
                CommandExecution.Status.TIMEOUT,
                "Revoked/killed by Celery (hard time limit or revoke).",
            )
        if state == "FAILURE":
            return (
                CommandExecution.Status.FAILED,
                "Worker died; Celery recorded a task failure.",
            )
        return None

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
