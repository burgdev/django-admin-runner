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
    import logging

    from .context import _clear_execution_context, _set_execution_context
    from .hooks import HookContext, get_hooks
    from .models import CommandExecution

    logger = logging.getLogger(__name__)

    execution = CommandExecution.objects.get(pk=execution_pk)
    execution.status = CommandExecution.Status.RUNNING
    execution.started_at = now()
    execution.save(update_fields=["status", "started_at"])

    ctx = HookContext()
    hooks = get_hooks()

    # Activate execution context (contextvars)
    exec_ctx = _set_execution_context()

    command_exc: Exception | None = None

    try:
        # Setup hooks (forward order)
        for hook in hooks:
            try:
                hook.setup(command_name, kwargs, execution, ctx)
            except Exception:
                logger.exception(
                    "Error in hook %s.setup() for command %s",
                    type(hook).__qualname__,
                    command_name,
                )

        stdout_buf = _TtyStringIO()
        stderr_buf = _TtyStringIO()
        try:
            # _hidden_aware_argparse strips custom kwargs (widget=, hidden=)
            # that commands may pass to add_argument but argparse doesn't understand.
            from .forms import _hidden_aware_argparse

            with _hidden_aware_argparse():
                call_command(
                    command_name,
                    stdout=stdout_buf,
                    stderr=stderr_buf,
                    force_color=True,
                    **kwargs,
                )
            execution.status = CommandExecution.Status.SUCCESS
        except Exception as exc:
            execution.status = CommandExecution.Status.FAILED
            execution.stderr = _rich_traceback() or traceback.format_exc()
            command_exc = exc
        finally:
            execution.stdout = stdout_buf.getvalue()
            if not execution.stderr:
                execution.stderr = stderr_buf.getvalue()
            execution.finished_at = now()

        # Pre-save hooks (forward order)
        for hook in hooks:
            try:
                hook.pre_save(command_name, kwargs, execution, ctx)
            except Exception:
                logger.exception(
                    "Error in hook %s.pre_save() for command %s",
                    type(hook).__qualname__,
                    command_name,
                )

        # Collect result_html from execution context
        result_html = exec_ctx.get("result_html")
        if result_html is not None:
            execution.result_html = str(result_html)

        # Save execution record
        execution.save(update_fields=["status", "stdout", "stderr", "result_html", "finished_at"])

        # Post-save hooks (reversed order, non-fatal)
        for hook in reversed(hooks):
            try:
                hook.post_save(command_name, kwargs, execution, ctx)
            except Exception:
                logger.exception(
                    "Error in hook %s.post_save() for command %s",
                    type(hook).__qualname__,
                    command_name,
                )

        # Re-raise so the task backend (Celery, django-q2, …) also marks the
        # task as failed.  We do this *after* saving the execution record so
        # the admin always has the failure details even if the backend doesn't
        # store them.
        if command_exc is not None:
            raise command_exc
    finally:
        _clear_execution_context()
