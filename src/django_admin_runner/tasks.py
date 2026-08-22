from __future__ import annotations

import concurrent.futures
import io
import time
import traceback

from django.conf import settings
from django.core.management import call_command
from django.utils.timezone import now


def _max_output_chars() -> int:
    """Total retention cap per output field (ADMIN_RUNNER_MAX_OUTPUT, default 500 MB).

    When the retained output for a field exceeds this cap, the oldest
    **sealed** output parts are deleted (the active part is never pruned).
    """
    return int(getattr(settings, "ADMIN_RUNNER_MAX_OUTPUT", 500_000_000))


def _terminal_size() -> tuple[int, int]:
    """Configured terminal dimensions (cols, rows) for command execution.

    ``ADMIN_RUNNER_TERM_COLS`` (default 120) and ``ADMIN_RUNNER_TERM_ROWS``
    (default 40), clamped to sane bounds so commands (rich et al.) lay out
    output deterministically regardless of the caller's environment.
    """
    cols = int(getattr(settings, "ADMIN_RUNNER_TERM_COLS", 120))
    rows = int(getattr(settings, "ADMIN_RUNNER_TERM_ROWS", 40))
    return max(20, min(cols, 500)), max(5, min(rows, 200))


def _append_output(execution, field: str, chunk: str) -> None:
    """Append *chunk* to the active output part, sealing at ``PART_SIZE``.

    The append happens at the database level (``F("text") + Value(...)``) so
    only the active part row is rewritten — per-flush cost is proportional to
    new output, not total output.  Afterwards, retention pruning deletes the
    oldest sealed parts if the field exceeds ``ADMIN_RUNNER_MAX_OUTPUT``.
    """
    from django.db.models import TextField, Value
    from django.db.models.functions import Concat

    from .models import CommandOutputPart

    part_size = CommandOutputPart.PART_SIZE
    active = (
        CommandOutputPart.objects.filter(execution=execution, field=field).order_by("-seq").first()
    )
    if active is None:
        active = CommandOutputPart.objects.create(execution=execution, field=field, seq=0, text="")

    pos = 0
    while pos < len(chunk):
        space = part_size - len(active.text)  # type: ignore[arg-type]
        if space <= 0:
            # Part is full: seal it and start a new part for the remainder.
            active = CommandOutputPart.objects.create(
                execution=execution,
                field=field,
                seq=active.seq + 1,  # type: ignore[operator]
                text="",
            )
            continue
        take = min(space, len(chunk) - pos)
        piece = chunk[pos : pos + take]
        # Concat (not ``F() + Value()``): on SQLite the latter renders as
        # arithmetic ``+`` and string operands coerce to numbers.
        CommandOutputPart.objects.filter(pk=active.pk).update(
            text=Concat("text", Value(piece), output_field=TextField())
        )
        active.text += piece  # type: ignore[operator]
        pos += take

    _prune_output(execution, field)


def _prune_output(execution, field: str) -> None:
    """Delete the oldest sealed parts until the field is within the cap."""
    from django.db.models.functions import Length

    from .models import CommandOutputPart

    cap = _max_output_chars()
    parts = list(
        CommandOutputPart.objects.filter(execution=execution, field=field)
        .order_by("seq")
        .values_list("pk", Length("text"))
    )
    if len(parts) <= 1:
        return
    total = sum(length for _, length in parts)
    to_delete: list[int] = []
    for pk, length in parts[:-1]:  # never delete the active (last) part
        if total <= cap:
            break
        to_delete.append(pk)
        total -= length
    if to_delete:
        CommandOutputPart.objects.filter(pk__in=to_delete).delete()


def _clear_output(execution, field: str) -> None:
    """Remove all output parts for *field*."""
    from .models import CommandOutputPart

    CommandOutputPart.objects.filter(execution=execution, field=field).delete()


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


# Fixed flush cadence for _LiveTtyStringIO: appends only rewrite the active
# part row (≤512 KB), so the interval never needs to grow with output size.
# Global default — override per command via ``flush_interval`` in
# ``@register_command`` (e.g. 0.1 for progress-bar heavy commands).
DEFAULT_FLUSH_INTERVAL = 0.5


def _default_flush_interval() -> float:
    """Flush interval from settings, default 0.5 s."""
    return float(
        getattr(settings, "ADMIN_RUNNER_FLUSH_INTERVAL", DEFAULT_FLUSH_INTERVAL),
    )


def _flush_interval_for_command(command_name: str) -> float:
    """Effective flush interval: per-command override or the global default."""
    from .registry import _registry

    entry = _registry.get(command_name, {})
    override = entry.get("flush_interval")
    if override:
        return float(override)
    return _default_flush_interval()


# Single-worker executor for deferred (async-context) output appends:
# guarantees FIFO ordering — a multi-worker pool could persist concurrent
# flushes out of order and garble the stored output.
_APPEND_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=1,
    thread_name_prefix="dar-append",
)


class _LiveTtyStringIO(_TtyStringIO):
    """``_TtyStringIO`` that periodically appends new output to the database.

    Every ``FLUSH_INTERVAL`` seconds (or ``flush_bytes`` bytes written,
    whichever comes first), the characters written since the last flush are
    appended to the active ``CommandOutputPart`` for this field.  This
    enables live output in the admin at a fixed ~250 ms cadence while keeping
    per-flush cost proportional to new output only.

    A watermark tracks how much of the in-memory buffer has already been
    persisted; ``final_flush()`` persists whatever remains at completion.
    """

    def __init__(
        self,
        execution,
        field_name="stdout",
        *,
        flush_interval=None,
        flush_bytes=4096,
    ):
        super().__init__()
        self._execution = execution
        self._field_name = field_name
        self._flush_interval = (
            flush_interval if flush_interval is not None else _default_flush_interval()
        )
        self._flush_bytes = flush_bytes
        self._last_flush = time.monotonic()
        self._bytes_since_flush = 0
        self._watermark = 0  # chars of the buffer already persisted to parts

    def _maybe_flush(self) -> None:
        now_mono = time.monotonic()
        if (
            now_mono - self._last_flush >= self._flush_interval
            or self._bytes_since_flush >= self._flush_bytes
        ):
            self._flush()
            self._last_flush = now_mono
            self._bytes_since_flush = 0

    def _flush(self) -> None:
        """Append the not-yet-persisted tail of the buffer to output parts.

        Commands may write output from inside a running asyncio event loop
        (e.g. async pipelines logging progress). Django's ORM refuses sync
        calls from async context, so the append is deferred to a thread there.
        """
        import asyncio

        execution = self._execution
        field_name = self._field_name
        chunk = self.getvalue()[self._watermark :]
        if not chunk:
            return
        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            _append_output(execution, field_name, chunk)
        else:
            # Async context — a direct ORM call would raise
            # SynchronousOnlyOperation. Hand it to the single-worker append
            # executor: FIFO order is guaranteed (a multi-worker pool could
            # append concurrent flushes out of order and garble the output).
            running_loop.run_in_executor(
                _APPEND_EXECUTOR, _append_output, execution, field_name, chunk
            )
        self._watermark += len(chunk)

    def final_flush(self) -> None:
        """Persist all remaining output (used at command completion)."""
        self._flush()

    def write(self, s: str, /) -> int:
        n = super().write(s)
        self._bytes_since_flush += n
        self._maybe_flush()
        return n


def _split_positional_args(command_name: str, kwargs: dict) -> tuple[list, dict]:
    """Separate positional arguments from keyword arguments.

    Django's ``call_command`` crashes on positional arguments passed via
    ``**options`` because it tries ``min(opt.option_strings)`` and positional
    args have an empty ``option_strings`` list (Django >= 5.2 / 6.x).

    This function inspects the command's argparse definition, identifies which
    ``kwargs`` keys correspond to positional arguments, and returns them as a
    list of positional values (in declaration order) plus the remaining kwargs.
    """
    import argparse

    from django.core.management import get_commands, load_command_class

    from .forms import _hidden_aware_argparse

    app_name = get_commands().get(command_name, "django.core")
    with _hidden_aware_argparse():
        cmd = load_command_class(app_name, command_name)
        parser = cmd.create_parser("manage.py", command_name)

    positional_dests: list[str] = []
    for action in parser._actions:
        if not action.option_strings and not isinstance(
            action,
            argparse._HelpAction | argparse._SubParsersAction,
        ):
            positional_dests.append(action.dest)

    positional_values: list = []
    remaining_kwargs: dict = {}
    for key, value in kwargs.items():
        if key in positional_dests:
            continue  # handled below in declaration order
        remaining_kwargs[key] = value

    # Extract positional values in declaration order
    for dest in positional_dests:
        if dest in kwargs:
            positional_values.append(kwargs[dest])

    return positional_values, remaining_kwargs


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


def _revert_debugsqlshell_monkeypatch() -> None:
    """Undo ``debug_toolbar``'s ``debugsqlshell`` monkeypatch if active.

    The ``debugsqlshell`` management command replaces
    ``CursorDebugWrapper`` with a ``PrintQueryWrapper`` that runs
    ``sqlparse.format()`` on every query.  In a task worker (django-q2,
    Celery, …) this causes two problems:

    1. Enormous log spam — every SQL statement is printed.
    2. ``SQLParseError`` on large queries (e.g. ``bulk_update`` with many
       rows) because the token limit is exceeded.

    If we detect the patched class we restore the original on both the
    generic ``django.db.backends.utils`` module and the PostgreSQL backend
    module (``debugsqlshell`` patches whichever ``base_module`` matches
    the active connection vendor).
    """
    import sys

    if "debug_toolbar.management.commands.debugsqlshell" not in sys.modules:
        return  # module never imported, nothing to undo

    def _restore_on(module) -> bool:
        """Restore ``CursorDebugWrapper`` on *module* if patched. Return True if restored."""
        wrapper = getattr(module, "CursorDebugWrapper", None)
        if wrapper is None or wrapper.__name__ != "PrintQueryWrapper":
            return False
        for cls in wrapper.__mro__[1:]:
            if cls.__name__ == "CursorDebugWrapper":
                module.CursorDebugWrapper = cls
                return True
        return False

    from django.db.backends import utils as db_utils

    _restore_on(db_utils)

    # The PostgreSQL backend imports CursorDebugWrapper into its own namespace
    # and debugsqlshell patches that copy too.
    try:
        from django.db.backends.postgresql import base as pg_base

        _restore_on(pg_base)
    except ImportError:
        pass


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

    # Undo debug_toolbar's debugsqlshell monkeypatch if it has been applied
    # (e.g. by another import path or a process that was started before the
    # autodiscovery skip list was in effect).
    _revert_debugsqlshell_monkeypatch()

    execution = CommandExecution.objects.get(pk=execution_pk)
    execution.status = CommandExecution.Status.RUNNING
    execution.started_at = now()
    execution.save(update_fields=["status", "started_at"])

    ctx = HookContext()
    hooks = get_hooks()

    # Activate execution context (contextvars)
    exec_ctx = _set_execution_context()

    command_exc: Exception | None = None
    traceback_text = ""

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

        stdout_buf = _LiveTtyStringIO(
            execution,
            "stdout",
            flush_interval=_flush_interval_for_command(command_name),
        )
        stderr_buf = _LiveTtyStringIO(
            execution,
            "stderr",
            flush_interval=_flush_interval_for_command(command_name),
        )
        try:
            # _hidden_aware_argparse strips custom kwargs (widget=, hidden=)
            # that commands may pass to add_argument but argparse doesn't understand.
            from .forms import _hidden_aware_argparse

            # Separate positional args from keyword args so that
            # call_command() doesn't try to resolve them as option flags.
            positional, keyword_kwargs = _split_positional_args(command_name, kwargs)

            # Redirect sys.stdout/sys.stderr so that libraries which write
            # directly to the process streams (e.g. click.echo, print) are
            # captured alongside Django's self.stdout/self.stderr.
            import os
            import sys

            old_stdout, old_stderr = sys.stdout, sys.stderr
            sys.stdout, sys.stderr = stdout_buf, stderr_buf
            # Export the configured terminal size so commands (rich et al.)
            # lay out progress bars deterministically; restore afterwards.
            term_cols, term_rows = _terminal_size()
            old_env = {}
            for key, value in (("COLUMNS", str(term_cols)), ("LINES", str(term_rows))):
                old_env[key] = os.environ.get(key)
                os.environ[key] = value
            try:
                with _hidden_aware_argparse():
                    call_command(
                        command_name,
                        *positional,
                        stdout=stdout_buf,
                        stderr=stderr_buf,
                        force_color=True,
                        **keyword_kwargs,
                    )
            finally:
                for key, old_value in old_env.items():
                    if old_value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = old_value
                sys.stdout, sys.stderr = old_stdout, old_stderr
            execution.status = CommandExecution.Status.SUCCESS
        except Exception as exc:
            execution.status = CommandExecution.Status.FAILED
            traceback_text = _rich_traceback() or traceback.format_exc()
            command_exc = exc
        finally:
            stdout_buf.final_flush()
            if command_exc is not None:
                # On failure the traceback replaces any captured stderr
                # (matches the legacy field behaviour).
                _clear_output(execution, "stderr")
                _append_output(execution, "stderr", traceback_text)
            else:
                stderr_buf.final_flush()
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
        execution.save(update_fields=["status", "result_html", "finished_at"])

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
