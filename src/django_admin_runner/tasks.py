from __future__ import annotations

import io
import traceback

from django.core.management import call_command
from django.utils.timezone import now


class _TtyStringIO(io.StringIO):
    """StringIO that reports itself as a TTY.

    Django's management framework (and ``rich``) check ``isatty()`` to decide
    whether to emit ANSI escape codes.  Returning ``True`` here — combined with
    ``force_color=True`` passed to ``call_command`` — ensures that commands
    using ``self.style.SUCCESS(…)`` etc. produce coloured output that is later
    converted to HTML by ``ansi2html`` in the admin.
    """

    def isatty(self) -> bool:
        return True


def _rich_traceback() -> str | None:
    """Return a rich-formatted traceback string with ANSI codes.

    Returns ``None`` if ``rich`` is not installed, so the caller can fall back
    to ``traceback.format_exc()``.
    """
    try:
        from rich.console import Console

        buf = _TtyStringIO()
        console = Console(file=buf, force_terminal=True, width=120, highlight=True)
        console.print_exception(show_locals=False)
        return buf.getvalue()
    except ImportError:
        return None


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

    stdout_buf = _TtyStringIO()
    stderr_buf = _TtyStringIO()
    try:
        call_command(
            command_name,
            stdout=stdout_buf,
            stderr=stderr_buf,
            force_color=True,
            **kwargs,
        )
        execution.status = CommandExecution.Status.SUCCESS
    except Exception:
        execution.status = CommandExecution.Status.FAILED
        execution.stderr = _rich_traceback() or traceback.format_exc()
    finally:
        execution.stdout = stdout_buf.getvalue()
        if not execution.stderr:
            execution.stderr = stderr_buf.getvalue()
        execution.finished_at = now()
        execution.save(update_fields=["status", "stdout", "stderr", "finished_at"])
