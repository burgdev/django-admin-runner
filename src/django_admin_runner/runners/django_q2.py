from __future__ import annotations

from django.urls import reverse

from . import BaseCommandRunner, RunResult


class DjangoQ2CommandRunner(BaseCommandRunner):
    """Enqueues commands as django-q2 tasks.

    django-q2 does not support per-task retry control — ``max_retries``
    is ignored. Configure retries globally via ``Q_CLUSTER["max_attempts"]``.
    """

    backend = "django-q2"
    supports_max_retries = False

    def run(self, command_name, kwargs, triggered_by, execution) -> RunResult:
        from django_admin_runner.registry import _registry
        from django_admin_runner.tasks import execute_command

        execution.backend = self.backend
        execution.save(update_fields=["backend"])

        # Read per-command settings from the registry
        entry = _registry.get(command_name, {})
        timeout = entry.get("timeout")
        max_retries = entry.get("max_retries", 0)

        # Warn if max_retries is set but unsupported
        if max_retries > 0 and not self.supports_max_retries:
            import logging

            logging.getLogger(__name__).warning(
                "Command %r has max_retries=%d but the django-q2 runner "
                "does not support per-task retry control. "
                'Configure retries via Q_CLUSTER["max_attempts"] instead.',
                command_name,
                max_retries,
            )

        # Build q_options for async_task
        q_options = {}
        if timeout is not None:
            q_options["timeout"] = timeout

        try:
            from django_q.tasks import async_task

            task_kwargs = {"q_options": q_options} if q_options else {}
            task_id = async_task(
                execute_command,
                command_name,
                kwargs,
                execution.pk,
                **task_kwargs,
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
