from __future__ import annotations

import concurrent.futures
import io
import threading
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


class WorkerStoppedError(Exception):
    """Raised inside a command when the worker receives SIGTERM."""


class CommandCancelledError(Exception):
    """Raised inside a command when a stop was requested from the admin.

    Flows the normal cleanup path so the execution finalizes as CANCELLED
    with its output preserved up to the stop point.
    """


def _stop_requested(execution) -> bool:
    """Whether a stop was requested for *execution* (fresh DB read)."""
    from .models import CommandExecution

    return bool(
        CommandExecution.objects.filter(pk=execution.pk, stop_requested=True).values_list(
            "pk", flat=True
        )
    )


def _is_timeout_exception(exc: BaseException) -> bool:
    """Whether *exc* is a soft time limit (e.g. Celery SoftTimeLimitExceeded).

    The class name is matched first so behaviour is identical whether or
    not Celery is installed (the name is specific to the Celery ecosystem);
    ``isinstance`` adds subclasses of Celery's own exception.
    """
    if type(exc).__name__ == "SoftTimeLimitExceeded":
        return True
    try:
        from celery.exceptions import SoftTimeLimitExceeded
    except ImportError:
        return False
    return isinstance(exc, SoftTimeLimitExceeded)


def sweep_stale_executions() -> int:
    """Finalize RUNNING executions whose worker died without finalizing.

    A hard kill (django-q2 ``timeout``, Celery ``time_limit``, crash, OOM,
    dead cluster) leaves the row RUNNING: the only writer — the worker —
    is gone. This sweeper runs lazily from admin request handlers and
    finalizes such rows:

    - ``worker_pid`` recorded and the process no longer exists (grace
      period past), or
    - legacy rows without ``worker_pid`` older than
      ``ADMIN_RUNNER_STALE_AFTER`` seconds (default 1 h).

    The runner's ``finalize_stale()`` may attribute the cause (backend
    records → TIMEOUT); otherwise the row becomes FAILED with a
    "worker lost" note. All updates are conditional on ``status=RUNNING``
    so a concurrently finishing worker always wins. Never raises.
    """
    import errno
    import logging
    import os
    from datetime import timedelta

    from django.utils.timezone import now

    from .models import CommandExecution
    from .runners import get_runner

    logger = logging.getLogger(__name__)
    grace = timedelta(seconds=max(10, int(2 * _default_flush_interval())))
    stale_after = timedelta(
        seconds=int(getattr(settings, "ADMIN_RUNNER_STALE_AFTER", 3600)),
    )
    sweep_from = now()

    runner = None
    swept = 0
    try:
        candidates = CommandExecution.objects.filter(
            status=CommandExecution.Status.RUNNING,
            started_at__lt=sweep_from - grace,
        )
        for execution in candidates:
            if execution.worker_pid:
                try:
                    os.kill(execution.worker_pid, 0)
                except OSError as exc:
                    if exc.errno != errno.ESRCH:
                        continue  # e.g. EPERM: treat as alive
                except (ValueError, OverflowError, TypeError):
                    pass  # bogus pid: treat as dead
                else:
                    continue  # alive: never sweep, regardless of age
            elif execution.started_at and execution.started_at > sweep_from - stale_after:
                continue  # legacy row (no pid): not old enough yet

            status = CommandExecution.Status.FAILED
            note = "Worker process no longer exists (worker lost)."
            try:
                if runner is None:
                    runner = get_runner()
                attributed = runner.finalize_stale(execution)
                if attributed:
                    status, note = attributed
            except Exception:  # noqa: BLE001
                logger.exception("Stale-sweep attribution failed for execution %s", execution.pk)

            updated = CommandExecution.objects.filter(
                pk=execution.pk, status=CommandExecution.Status.RUNNING
            ).update(status=status, finished_at=now())
            if updated:
                swept += 1
                try:
                    _append_output(execution, "stderr", f"\n{note}\n")
                except Exception:  # noqa: BLE001
                    logger.exception(
                        "Stale-sweep note append failed for execution %s", execution.pk
                    )
    except Exception:  # noqa: BLE001
        logger.exception("Stale-run sweep failed")
    return swept


def _append_output_logged(execution, field: str, chunk: str) -> None:
    """``_append_output`` wrapper that never raises.

    Runs on the append executor: a failed append must be logged, not kill
    the command (the exception would surface inside a random ``print()``).
    """
    import logging

    try:
        _append_output(execution, field, chunk)
    except Exception:  # noqa: BLE001
        logging.getLogger(__name__).exception(
            "Failed to append output chunk for execution %s (%s, %d chars)",
            execution.pk,
            field,
            len(chunk),
        )


def _install_sigterm_handler():
    """Install a SIGTERM handler that raises :class:`WorkerStoppedError`.

    Cluster shutdown (e.g. ``qcluster`` stopping) sends SIGTERM to worker
    processes; turning it into an exception lets the normal failure path
    mark the execution FAILED and app-level run guards unblock immediately.
    Returns ``(signal, previous_handler)`` for restoration, or ``None`` when
    signal handlers cannot be installed (non-main thread / non-POSIX).
    """
    import signal

    def _handler(signum, frame):  # pragma: no cover - exercised via raise
        raise WorkerStoppedError(
            "Worker received SIGTERM — the task cluster was stopped while this command was running."
        )

    try:
        previous = signal.getsignal(signal.SIGTERM)
        signal.signal(signal.SIGTERM, _handler)
        return (signal.SIGTERM, previous)
    except (ValueError, OSError, AttributeError):
        return None


def _restore_sigterm_handler(installed) -> None:
    """Restore the previous SIGTERM handler installed by *_install*."""
    if installed is None:
        return
    import signal

    signum, previous = installed
    try:
        signal.signal(signum, previous)
    except (ValueError, OSError):  # pragma: no cover
        pass


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
        stop_check=None,
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
        # Optional cooperative-stop probe (returns True when a stop was
        # requested for this execution); checked at most once per flush
        # interval — raising from write() unwinds call_command().
        self._stop_check = stop_check
        # Cooperative stop is thread-aware: rich's Live/progress display
        # writes from a background refresh thread. Raising there cannot
        # unwind the command (it only kills that thread and spams the
        # threading excepthook), so the exception is raised in the main
        # thread only — other threads just latch ``_stop_seen`` so the
        # main thread raises on its next write without another DB probe.
        self._main_thread = threading.main_thread()
        self._stop_seen = False
        # Serialises read-slice/advance-watermark: output is written from
        # multiple threads (event loop + executor workers), and two
        # concurrent flushes would read overlapping slices and append
        # duplicated chunks.
        self._flush_lock = threading.Lock()
        # Futures of appends submitted to _APPEND_EXECUTOR, drained by
        # final_flush so completion implies persisted output.
        self._pending_appends: list = []

    def _maybe_stop(self) -> None:
        """Raise :class:`CommandCancelledError` when a stop was requested.

        Probes the DB at most once per flush interval; the result is
        latched so subsequent writes (from any thread) skip the probe.
        Raises only in the main thread (see ``_stop_seen`` init note).
        """
        if self._stop_check is None:
            return
        if threading.current_thread() is not self._main_thread:
            # Background writer (e.g. rich's refresh thread): probe and
            # latch, but never raise here.
            if not self._stop_seen:
                self._stop_seen = bool(self._stop_check())
            return
        if not self._stop_seen:
            self._stop_seen = bool(self._stop_check())
        if self._stop_seen:
            raise CommandCancelledError("Stop requested.")

    def _maybe_flush(self) -> None:
        now_mono = time.monotonic()
        with self._flush_lock:
            due = (
                now_mono - self._last_flush >= self._flush_interval
                or self._bytes_since_flush >= self._flush_bytes
            )
            if due:
                self._last_flush = now_mono
                self._bytes_since_flush = 0
        if due:
            # Cooperative stop: probed at most once per flush interval.
            # Raised from write() so it unwinds call_command() through the
            # normal exception path in execute_command().
            self._maybe_stop()
            self._flush()

    def _flush(self) -> None:
        """Append the not-yet-persisted tail of the buffer to output parts.

        ALL appends go through the single-worker ``_APPEND_EXECUTOR``:

        - FIFO ordering is guaranteed for every chunk of this buffer,
          regardless of which thread (event loop, executor worker, main)
          triggered the flush — mixing direct sync appends with deferred
          ones would persist chunks out of order.
        - In async context a direct ORM call would additionally raise
          ``SynchronousOnlyOperation``.
        - Errors are logged in the worker instead of killing the command
          (a failed append must not turn a ``print()`` into a crash).
        """
        with self._flush_lock:
            chunk = self.getvalue()[self._watermark :]
            if not chunk:
                return
            # Advance under the lock so a concurrent flush cannot read the
            # same slice (and duplicate it).
            self._watermark += len(chunk)
        future = _APPEND_EXECUTOR.submit(
            _append_output_logged, self._execution, self._field_name, chunk
        )
        with self._flush_lock:
            self._pending_appends.append(future)
            # Drop completed futures so the list cannot grow unboundedly.
            self._pending_appends = [f for f in self._pending_appends if not f.done()]

    def final_flush(self) -> None:
        """Persist all remaining output (used at command completion).

        Submits any unflushed tail and blocks until every pending append has
        been written, so a subsequent read (or the failure path's
        ``_clear_output``) can never race a stale chunk.
        """
        self._flush()
        with self._flush_lock:
            pending = list(self._pending_appends)
            self._pending_appends = []
        if pending:
            concurrent.futures.wait(pending)

    def write(self, s: str, /) -> int:
        n = super().write(s)
        with self._flush_lock:
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


def _schedule_run_overlaps(schedule) -> bool:
    """Whether *schedule* still has a live (pending/running) execution.

    Guards against overlapping scheduled runs: one execution per schedule
    at a time. Only *recent* executions block — older ones are assumed
    dead (worker lost; the stale sweep will finalize them) so a stuck row
    cannot starve the schedule forever. Window:
    ``ADMIN_RUNNER_STALE_AFTER`` seconds (default 1 h).
    """
    from datetime import timedelta

    from django.utils.timezone import now

    from .models import CommandExecution

    cutoff = now() - timedelta(seconds=int(getattr(settings, "ADMIN_RUNNER_STALE_AFTER", 3600)))
    return CommandExecution.objects.filter(
        schedule_id=schedule.pk,
        status__in=[CommandExecution.Status.PENDING, CommandExecution.Status.RUNNING],
        created_at__gte=cutoff,
    ).exists()


def run_scheduled_command(command_name: str, kwargs: dict, schedule_pk: int | None = None) -> None:
    """Schedule-safe entry point: create the execution at run time, then run.

    Unlike the run-now flow (which creates the ``CommandExecution`` row in
    the admin before enqueueing), a future run cannot know the execution
    pk ahead of time — so this function creates the row when the backend
    fires the schedule, links it to the originating schedule for
    traceability, and delegates to :func:`execute_command`.

    Fired clocked (one-off) schedules are disabled afterwards: django-q2
    deletes its native one-off schedule after the run, so the library row
    is kept but marked disabled (audit trail).
    """
    from .models import CommandExecution, ScheduledCommand

    schedule = (
        ScheduledCommand.objects.filter(pk=schedule_pk).first() if schedule_pk is not None else None
    )
    if schedule is not None and _schedule_run_overlaps(schedule):
        # A previous run of this schedule is still pending/running (e.g.
        # the worker died and the row is awaiting the stale sweep, or the
        # command outgrew its interval). Skip this slot instead of piling
        # another run on top — one execution per schedule at a time.
        import logging

        logging.getLogger(__name__).warning(
            "Skipping scheduled run of %r (schedule %s): previous run still pending/running.",
            command_name,
            schedule.pk,
        )
        return
    from .runners import get_runner

    execution = CommandExecution.objects.create(
        command_name=command_name,
        kwargs=kwargs or {},
        schedule=schedule,
        # The execution row is created inside the backend's task, so its
        # backend is the active runner's; the label carries the schedule's
        # for traceability in the results list.
        backend=get_runner().backend,
        label=str(schedule.label or "") if schedule is not None else "",
    )
    try:
        execute_command(command_name, kwargs or {}, execution.pk)
    finally:
        if schedule is not None and schedule.kind == ScheduledCommand.Kind.CLOCKED:
            ScheduledCommand.objects.filter(pk=schedule.pk).update(
                enabled=False,
                backend_schedule_key="",
            )


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

    import os

    # Idempotency guard: claim the execution by transitioning PENDING →
    # RUNNING with this process's PID. A duplicate attempt (e.g. a backend
    # retry after a force-killed worker re-delivers the task) finds the row
    # in a non-PENDING state and exits without touching it.
    updated = CommandExecution.objects.filter(
        pk=execution_pk, status=CommandExecution.Status.PENDING
    ).update(
        status=CommandExecution.Status.RUNNING,
        started_at=now(),
        worker_pid=os.getpid(),
    )
    if not updated:
        return
    execution = CommandExecution.objects.get(pk=execution_pk)

    # Fail gracefully when the worker is asked to stop (qcluster shutdown
    # sends SIGTERM to its workers). Without this, a stopped cluster leaves
    # the execution (and any app-level run guards) stuck in a running state
    # until a stale-run sweep notices.
    _sigterm_handler = _install_sigterm_handler()

    ctx = HookContext()
    hooks = get_hooks()

    # Activate execution context (contextvars)
    exec_ctx = _set_execution_context()

    command_exc: Exception | None = None
    cancelled = False
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
            stop_check=lambda: _stop_requested(execution),
        )
        stderr_buf = _LiveTtyStringIO(
            execution,
            "stderr",
            flush_interval=_flush_interval_for_command(command_name),
            stop_check=lambda: _stop_requested(execution),
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
        except CommandCancelledError:
            # Cooperative stop (heartbeat) or stop-flagged SIGTERM: the
            # command unwound cleanly — finalize as CANCELLED with output
            # preserved (a cancellation note is appended below).
            execution.status = CommandExecution.Status.CANCELLED
            cancelled = True
        except Exception as exc:
            if isinstance(exc, WorkerStoppedError) and _stop_requested(execution):
                # A SIGTERM received because a stop was requested counts as
                # cancellation (the heartbeat probe missed it).
                execution.status = CommandExecution.Status.CANCELLED
                cancelled = True
            elif _is_timeout_exception(exc) and _stop_requested(execution):
                # A stop was requested before the limit hit: the user's
                # intent wins over the timeout classification.
                execution.status = CommandExecution.Status.CANCELLED
                cancelled = True
            elif _is_timeout_exception(exc):
                # Soft time limit (Celery): the limit is the cause, not a
                # command error — finalize as TIMEOUT with the traceback.
                execution.status = CommandExecution.Status.TIMEOUT
                traceback_text = _rich_traceback() or traceback.format_exc()
                command_exc = exc
            else:
                execution.status = CommandExecution.Status.FAILED
                traceback_text = _rich_traceback() or traceback.format_exc()
                command_exc = exc
        finally:
            stdout_buf.final_flush()
            if cancelled:
                # Append a cancellation note after the preserved output.
                stderr_buf.final_flush()
                cancel_note = (
                    f"\nCommand cancelled (stop requested from admin)"
                    f" at {now():%Y-%m-%d %H:%M:%S %Z}.\n"
                )
                _append_output(execution, "stderr", cancel_note)
            elif command_exc is not None:
                # Drain stderr appends BEFORE clearing: a deferred chunk
                # still in the executor queue would otherwise land after the
                # clear and resurrect pre-failure output after the traceback.
                stderr_buf.final_flush()
                # On failure the traceback replaces any captured stderr
                # (matches the legacy field behaviour).
                _clear_output(execution, "stderr")
                _append_output(
                    execution,
                    "stderr",
                    str(command_exc) + "\n" + traceback_text,
                )
            else:
                stderr_buf.final_flush()
            execution.finished_at = now()
            _restore_sigterm_handler(_sigterm_handler)

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

        # Save execution record — conditionally on still being RUNNING so a
        # stop/force-kill racing completion never overwrites the other
        # side's terminal state.
        CommandExecution.objects.filter(
            pk=execution.pk, status=CommandExecution.Status.RUNNING
        ).update(
            status=execution.status,
            result_html=execution.result_html,
            finished_at=execution.finished_at,
        )

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
        # store them.  Cancellations are not re-raised: the task backend
        # would flag the task failed (or retry it) for an intended stop.
        if command_exc is not None:
            raise command_exc
    finally:
        _clear_execution_context()
