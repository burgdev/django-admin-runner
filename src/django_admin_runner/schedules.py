"""Declarative schedule value objects and materialization helpers.

``Schedule`` value objects are declared on ``@register_command(schedule=…)``
and materialized into ``ScheduledCommand`` rows (``source=code``) by the
startup sync.  The materialization helpers below are shared by the sync,
the admin, and any programmatic API to keep library rows and native backend
schedule objects in sync.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import ScheduledCommand

logger = logging.getLogger(__name__)


def validate_cron_expression(expression: str) -> None:
    """Validate a cron expression; raises ``ValueError`` when unparseable.

    Prefers ``croniter`` (shipped with django-q2); falls back to a basic
    five-field check when it is not installed.
    """
    try:
        from croniter import croniter

        croniter(expression)
        return
    except ImportError:
        pass
    parts = expression.split()
    if len(parts) != 5 or not all(re.fullmatch(r"[\d*/,\-]+", p) for p in parts):
        raise ValueError(f"Invalid cron expression: {expression!r}")


@dataclass(frozen=True)
class Schedule:
    """Frozen value object describing one declarative schedule.

    ``name`` identifies the schedule for the startup sync (identity is
    ``(command_name, source=code, name)``); a single declaration defaults
    its name to the command name.  ``enabled`` is only the initial value —
    after the first sync the database owns it (admins may pause without
    a deploy).
    """

    kind: str
    name: str | None = None
    kwargs: dict = field(default_factory=dict)
    enabled: bool = True
    cron: str | None = None
    interval_minutes: int | None = None
    repeats: int | None = None
    run_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.kind not in ("cron", "interval", "clocked"):
            raise ValueError(f"Unknown schedule kind: {self.kind!r}")

    def model_kwargs(self) -> dict:
        """Field values for the ``ScheduledCommand`` row (spec only)."""
        return {
            "kind": self.kind,
            "cron": self.cron or "",
            "interval_minutes": self.interval_minutes,
            "repeats": self.repeats,
            "run_at": self.run_at,
            "kwargs": dict(self.kwargs),
        }


class CronSchedule(Schedule):
    """Run on a cron expression, e.g. ``"15 4 * * *"``."""

    def __init__(self, cron, *, name=None, kwargs=None, enabled=True):
        validate_cron_expression(cron)
        super().__init__(
            "cron",
            name=name,
            kwargs=dict(kwargs or {}),
            enabled=enabled,
            cron=cron,
        )


class IntervalSchedule(Schedule):
    """Run every *minutes* minutes, optionally limited to *repeats* runs."""

    def __init__(self, minutes, *, repeats=None, name=None, kwargs=None, enabled=True):
        minutes = int(minutes)
        if minutes <= 0:
            raise ValueError(f"Interval minutes must be positive, got {minutes}.")
        if repeats is not None:
            repeats = int(repeats)
            if repeats <= 0:
                raise ValueError(f"Repeats must be positive, got {repeats}.")
        super().__init__(
            "interval",
            name=name,
            kwargs=dict(kwargs or {}),
            enabled=enabled,
            interval_minutes=minutes,
            repeats=repeats,
        )


class ClockedSchedule(Schedule):
    """Run once at a specific (aware) datetime."""

    def __init__(self, at, *, name=None, kwargs=None, enabled=True):
        if not isinstance(at, datetime):
            raise TypeError("ClockedSchedule 'at' must be a datetime.")
        if at.tzinfo is None:
            at = at.replace(tzinfo=UTC)
        if at <= datetime.now(UTC):
            raise ValueError("ClockedSchedule 'at' must be in the future.")
        super().__init__(
            "clocked",
            name=name,
            kwargs=dict(kwargs or {}),
            enabled=enabled,
            run_at=at,
        )


# ---------------------------------------------------------------------------
# Materialization helpers
# ---------------------------------------------------------------------------


def materialize_schedule(schedule: ScheduledCommand) -> None:
    """Sync *schedule*'s native backend object with the library row.

    - ``enabled=False``: remove the native object (keep the row, clear the key).
    - ``enabled=True``: create or update the native object in place.
    """
    from .runners import get_runner

    runner = get_runner()
    if not schedule.enabled:
        if schedule.backend_schedule_key:
            try:
                runner.delete_schedule(schedule)
            except Exception:  # noqa: BLE001
                logger.exception(
                    "Failed to delete native schedule for %s (key=%s)",
                    schedule,
                    schedule.backend_schedule_key,
                )
        schedule.backend_schedule_key = ""
        _save_key(schedule)
        return
    if schedule.kind not in runner.supported_schedule_kinds:
        return
    key = (
        runner.update_schedule(schedule)
        if schedule.backend_schedule_key
        else runner.create_schedule(schedule)
    )
    if key != schedule.backend_schedule_key:
        schedule.backend_schedule_key = key
        _save_key(schedule)


def _save_key(schedule: ScheduledCommand) -> None:
    from .models import ScheduledCommand

    ScheduledCommand.objects.filter(pk=schedule.pk).update(
        backend_schedule_key=schedule.backend_schedule_key
    )


def remove_native_schedule(schedule: ScheduledCommand) -> None:
    """Best-effort removal of the native backend object (keeps the row)."""
    from .runners import get_runner

    if not schedule.backend_schedule_key:
        return
    try:
        get_runner().delete_schedule(schedule)
    except Exception:  # noqa: BLE001
        logger.exception(
            "Failed to delete native schedule for %s (key=%s)",
            schedule,
            schedule.backend_schedule_key,
        )
    schedule.backend_schedule_key = ""
    _save_key(schedule)
