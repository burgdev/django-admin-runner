from __future__ import annotations

from django.urls import reverse

from django_admin_runner.tasks import execute_command

from . import BaseCommandRunner, RunResult


class SyncCommandRunner(BaseCommandRunner):
    """Runs management commands inline in the current thread (no async)."""

    backend = "sync"

    def run(self, command_name, kwargs, triggered_by, execution) -> RunResult:
        execution.backend = self.backend
        execution.save(update_fields=["backend"])

        execute_command(command_name, kwargs, execution.pk)
        execution.refresh_from_db()

        return RunResult(
            execution=execution,
            redirect_url=reverse(
                "admin:django_admin_runner_commandexecution_change",
                args=[execution.pk],
            ),
            is_async=False,
            backend=self.backend,
        )
