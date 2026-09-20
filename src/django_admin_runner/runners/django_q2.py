from __future__ import annotations

from django.urls import reverse

from . import ALL_SCHEDULE_KINDS, BaseCommandRunner, RunResult

#: django-q2 ``Schedule.schedule_type`` values per schedule kind.
_KIND_TO_SCHEDULE_TYPE = {
    "cron": "C",
    "interval": "I",
    "clocked": "O",
}


class DjangoQ2CommandRunner(BaseCommandRunner):
    """Enqueues commands as django-q2 tasks.

    django-q2 does not support per-task retry control — ``max_retries``
    is ignored. Configure retries globally via ``Q_CLUSTER["max_attempts"]``.
    """

    backend = "django-q2"
    supports_max_retries = False
    supports_force_stop = True
    supported_schedule_kinds = ALL_SCHEDULE_KINDS

    def _signal_worker(self, execution, sig: int) -> bool:
        """Send *sig* to the worker process running *execution*.

        Guards against PID reuse: the signal is only sent when the target
        process started at or after the execution's ``started_at`` (its
        ``/proc/<pid>/stat`` starttime, converted via the boot time from
        ``/proc/stat``). Best effort — on any read failure the check is
        skipped and the signal is sent if the PID exists.
        """
        import os

        pid = execution.worker_pid
        if not pid:
            return False

        if execution.started_at is not None:
            started = self._proc_starttime(pid)
            if started is not None and started < execution.started_at:
                return False  # PID predates the execution → reused

        try:
            os.kill(pid, sig)
        except (ProcessLookupError, PermissionError, OSError):
            return False
        return True

    @staticmethod
    def _proc_starttime(pid: int):
        """Start time of *pid* as a timezone-aware datetime, or ``None``."""
        try:
            with open(f"/proc/{pid}/stat", "rb") as fh:
                # Field 22 (starttime, 1-based) — after the comm field,
                # which may contain spaces, so split after its ')'.
                fields = fh.read().rsplit(b")", 1)[1].split()
            starttime_ticks = int(fields[19])  # (22) minus the two consumed
            with open("/proc/stat", "rb") as fh:
                btime = next(int(line.split()[1]) for line in fh if line.startswith(b"btime"))
        except (OSError, ValueError, IndexError, StopIteration):
            return None
        from django.utils import timezone

        return timezone.datetime.fromtimestamp(
            btime + starttime_ticks // 100, tz=timezone.get_current_timezone()
        )

    def stop(self, execution) -> None:
        """Graceful stop: stop flag (heartbeat) + SIGTERM to the worker PID."""
        super().stop(execution)
        import signal

        self._signal_worker(execution, signal.SIGTERM)

    def force_stop(self, execution) -> bool:
        """Hard kill: SIGKILL to the (verified) worker PID."""
        import signal

        return self._signal_worker(execution, signal.SIGKILL)

    def finalize_stale(self, execution):
        """Attribute a swept execution via django-q2's Task records.

        The q2 sentinel writes a failure record for tasks it killed
        (e.g. for exceeding ``Q_CLUSTER["timeout"]``). Best effort — a
        missing/unreachable record yields ``None`` (generic FAILED).
        """
        if not execution.task_id:
            return None
        from django_admin_runner.models import CommandExecution

        try:
            from django_q.models import Task

            task = Task.objects.filter(name=execution.task_id).first()
        except Exception:  # noqa: BLE001 - attribution must never break the sweep
            return None
        if task is None or task.success or not task.stopped:
            return None
        result = str(task.result or "")
        if "time" in result.lower():
            return (
                CommandExecution.Status.TIMEOUT,
                f"Killed by django-q2 timeout: {result}",
            )
        return (
            CommandExecution.Status.FAILED,
            f"Worker killed; django-q2 recorded failure: {result}",
        )

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
        # Never retry admin-runner tasks: a force-killed worker leaves the
        # task unacknowledged, and a retry would run the command twice
        # (the PENDING→RUNNING idempotency guard in execute_command also
        # backs this up). -1 = disable retries in django-q2.
        q_options["retry"] = -1

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

    # ------------------------------------------------------------------
    # Schedule materialization (django-q2 ``Schedule`` rows)
    # ------------------------------------------------------------------

    def _native_kwargs(self, schedule) -> dict:
        kwargs: dict = {
            "name": str(schedule.label or schedule.command_name)[:100],
            "func": "django_admin_runner.tasks.run_scheduled_command",
            # django-q2 parses Schedule.args with ast.literal_eval and
            # wraps non-tuples as a single argument — so store a *tuple*
            # repr (a list repr would arrive as one positional arg and
            # crash run_scheduled_command). ast.literal_eval can't parse
            # JSON (true/false/null), hence repr, not json.
            "args": repr((schedule.command_name, dict(schedule.kwargs or {}), schedule.pk)),
            "schedule_type": _KIND_TO_SCHEDULE_TYPE[schedule.kind],
        }
        if schedule.kind == "cron":
            kwargs["cron"] = schedule.cron
        elif schedule.kind == "interval":
            kwargs["minutes"] = schedule.interval_minutes
            # django-q2: -1 = repeat forever; None (unset) maps to -1.
            kwargs["repeats"] = schedule.repeats if schedule.repeats is not None else -1
        elif schedule.kind == "clocked":
            kwargs["next_run"] = schedule.run_at
            kwargs["repeats"] = 1
        return kwargs

    def create_schedule(self, schedule) -> str:
        from django_q.models import Schedule

        self._check_schedule_kind(schedule)
        native = Schedule.objects.create(**self._native_kwargs(schedule))
        return str(native.pk)

    def update_schedule(self, schedule) -> str:
        self._check_schedule_kind(schedule)
        native = self._get_native(schedule)
        if native is None:
            return self.create_schedule(schedule)
        for key, value in self._native_kwargs(schedule).items():
            setattr(native, key, value)
        native.save()
        return str(native.pk)

    def delete_schedule(self, schedule) -> None:
        self._check_schedule_kind(schedule)
        native = self._get_native(schedule)
        if native is not None:
            native.delete()

    def schedule_next_run(self, schedule):
        native = self._get_native(schedule)
        return native.next_run if native is not None else None

    def _get_native(self, schedule):
        from django_q.models import Schedule

        if not schedule.backend_schedule_key:
            return None
        return Schedule.objects.filter(pk=schedule.backend_schedule_key).first()
