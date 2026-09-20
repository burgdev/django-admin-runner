from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django_admin_runner.models import CommandExecution, ScheduledCommand


class ScheduleNotSupportedError(NotImplementedError):
    """Raised when a schedule operation is requested for an unsupported kind."""


#: All schedule kinds a runner may declare support for.
ALL_SCHEDULE_KINDS = frozenset({"cron", "interval", "clocked"})


@dataclass
class RunResult:
    """Returned by every ``BaseCommandRunner.run()`` implementation."""

    execution: CommandExecution
    redirect_url: str
    is_async: bool
    backend: str
    task_id: str = field(default="")


class BaseCommandRunner:
    """Base class for command runners. Subclass and implement ``run()``.

    Set ``supports_max_retries`` to ``True`` if the runner's task backend
    supports per-task retry control (e.g. Celery's ``max_retries``).
    When ``False``, a warning is logged if a command has ``max_retries > 0``.
    """

    backend: str = ""
    supports_max_retries: bool = False

    #: Whether the backend can hard-kill a running task (separate worker
    #: process + a way to target it). When ``False`` the admin hides the
    #: "Force Stop" control once a graceful stop was requested.
    supports_force_stop: bool = False

    #: Schedule kinds this runner's backend can materialize natively.
    #: Runners whose backend has no periodic-task support (sync,
    #: django-tasks, rq) keep this empty — the admin hides the feature.
    supported_schedule_kinds: frozenset[str] = frozenset()

    def run(
        self,
        command_name: str,
        kwargs: dict,
        triggered_by,
        execution: CommandExecution,
    ) -> RunResult:
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Cancellation API
    # ------------------------------------------------------------------

    def stop(self, execution: CommandExecution) -> None:
        """Request a graceful stop of a RUNNING *execution*.

        The base implementation sets the cooperative ``stop_requested``
        flag (checked on the worker's output-flush heartbeat); backends
        with a way to signal the worker process override this to also
        send a SIGTERM-equivalent.
        """
        from django_admin_runner.models import CommandExecution

        CommandExecution.objects.filter(
            pk=execution.pk, status=CommandExecution.Status.RUNNING
        ).update(stop_requested=True)

    def force_stop(self, execution: CommandExecution) -> bool:
        """Hard-kill the process running *execution*.

        Returns ``True`` when a kill was performed. The base
        implementation is a no-op (unsupported backend); runners whose
        backend runs each task in its own process override this.
        """
        return False

    def finalize_stale(self, execution: CommandExecution) -> tuple[str, str] | None:
        """Attribute why a dead worker's execution ended (best effort).

        Called by the stale-run sweeper for RUNNING executions whose
        ``worker_pid`` no longer exists. Returns ``(status, note)`` —
        e.g. ``(TIMEOUT, "Killed by django-q2 timeout")`` — or ``None``
        when the backend has nothing to say (the sweeper then marks the
        execution FAILED with a generic "worker lost" note). Must never
        raise; wrap backend lookups defensively.
        """
        return None

    # ------------------------------------------------------------------
    # Schedule materialization API
    # ------------------------------------------------------------------

    def _check_schedule_kind(self, schedule: ScheduledCommand) -> None:
        if schedule.kind not in self.supported_schedule_kinds:
            raise ScheduleNotSupportedError(
                f"Backend {self.backend or type(self).__name__!r} does not support "
                f"{schedule.kind!r} schedules."
            )

    def create_schedule(self, schedule: ScheduledCommand) -> str:
        """Materialize *schedule* into a native backend object.

        Returns the backend reference to store in
        ``ScheduledCommand.backend_schedule_key``.
        """
        self._check_schedule_kind(schedule)
        raise ScheduleNotSupportedError(
            f"Backend {self.backend or type(self).__name__!r} does not support schedules."
        )

    def update_schedule(self, schedule: ScheduledCommand) -> str:
        """Update the native object referenced by ``backend_schedule_key`` in place.

        Returns the (possibly new) backend reference.
        """
        self._check_schedule_kind(schedule)
        raise ScheduleNotSupportedError(
            f"Backend {self.backend or type(self).__name__!r} does not support schedules."
        )

    def delete_schedule(self, schedule: ScheduledCommand) -> None:
        """Remove the native object referenced by ``backend_schedule_key``."""
        self._check_schedule_kind(schedule)
        raise ScheduleNotSupportedError(
            f"Backend {self.backend or type(self).__name__!r} does not support schedules."
        )

    def schedule_next_run(self, schedule: ScheduledCommand):
        """Next run datetime of the native object, or ``None`` when unknown."""
        return None


def get_runner() -> BaseCommandRunner:
    """Instantiate and return the runner configured by ``ADMIN_RUNNER_BACKEND``.

    Possible values:
    - ``"django"`` (default) — :class:`~django_admin_runner.runners.django_tasks.DjangoTaskRunner`
    - ``"sync"`` — :class:`~django_admin_runner.runners.sync.SyncCommandRunner`
    - ``"celery"`` — :class:`~django_admin_runner.runners.celery.CeleryCommandRunner`
    - ``"django-q2"`` — :class:`~django_admin_runner.runners.django_q2.DjangoQ2CommandRunner`
    - dotted path — any :class:`BaseCommandRunner` subclass
    """
    from django.conf import settings

    backend = getattr(settings, "ADMIN_RUNNER_BACKEND", "django")

    if backend == "sync":
        from .sync import SyncCommandRunner

        return SyncCommandRunner()
    if backend == "celery":
        from .celery import CeleryCommandRunner

        return CeleryCommandRunner()
    if backend == "django-q2":
        from .django_q2 import DjangoQ2CommandRunner

        return DjangoQ2CommandRunner()
    if backend == "django":
        from .django_tasks import DjangoTaskRunner

        return DjangoTaskRunner()

    # Dotted import path to a custom runner class
    import importlib

    module_path, class_name = backend.rsplit(".", 1)
    module = importlib.import_module(module_path)
    runner_class = getattr(module, class_name)
    return runner_class()
