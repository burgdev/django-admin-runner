from __future__ import annotations

import io
import traceback

from django.core.management import call_command
from django.utils.timezone import now


def execute_command(command_name: str, kwargs: dict, execution_pk: int) -> None:
    """Run *command_name* and update the ``CommandExecution`` record.

    This is a plain Python function intentionally free of any task-backend
    decorator so that every runner (sync, Django Tasks, Celery, RQ, …) can
    wrap or call it as needed.
    """
    from .models import CommandExecution

    execution = CommandExecution.objects.get(pk=execution_pk)
    execution.status = CommandExecution.Status.RUNNING
    execution.started_at = now()
    execution.save(update_fields=["status", "started_at"])

    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    try:
        call_command(command_name, stdout=stdout_buf, stderr=stderr_buf, **kwargs)
        execution.status = CommandExecution.Status.SUCCESS
    except Exception:
        execution.status = CommandExecution.Status.FAILED
        execution.stderr = traceback.format_exc()
    finally:
        execution.stdout = stdout_buf.getvalue()
        if not execution.stderr:
            execution.stderr = stderr_buf.getvalue()
        execution.finished_at = now()
        execution.save(update_fields=["status", "stdout", "stderr", "finished_at"])
