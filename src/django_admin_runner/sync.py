from __future__ import annotations

import logging

from django.db import OperationalError

logger = logging.getLogger(__name__)


def sync_registered_commands() -> None:
    """Sync in-memory ``_registry`` entries to ``RegisteredCommand`` rows.

    - Creates rows for new commands.
    - Updates metadata (group, display_name, description, app_label) for existing commands.
    - Deactivates rows whose ``name`` is no longer in the registry.
    - Handles ``OperationalError`` gracefully (table not yet migrated).
    """
    from .models import RegisteredCommand
    from .registry import _registry

    try:
        existing = {rc.name: rc for rc in RegisteredCommand.objects.all()}
    except OperationalError:
        logger.debug("RegisteredCommand table does not exist yet — skipping sync.")
        return

    registry_names = set(_registry.keys())

    for name, entry in _registry.items():
        defaults = {
            "group": entry["group"],
            "display_name": entry["display_name"],
            "description": _get_description(entry),
            "app_label": entry["app_label"],
            "active": True,
        }
        if name in existing:
            rc = existing[name]
            changed = False
            for field, value in defaults.items():
                if getattr(rc, field) != value:
                    setattr(rc, field, value)
                    changed = True
            if changed:
                rc.save(update_fields=list(defaults.keys()) + ["updated_at"])
        else:
            RegisteredCommand.objects.create(name=name, **defaults)

    # Deactivate commands no longer in registry
    stale_names = set(existing.keys()) - registry_names
    if stale_names:
        RegisteredCommand.objects.filter(name__in=stale_names, active=True).update(active=False)


def sync_declarative_schedules() -> None:
    """Materialize ``@register_command(schedule=…)`` declarations into DB rows.

    Identity is ``(command_name, source=code, label)``:

    - Registry wins for the schedule spec (kind, expression, kwargs) —
      sync updates rows to match the code.
    - DB wins for ``enabled`` — admins may pause a declarative schedule
      without a deploy; sync never re-enables.
    - ``source=admin`` rows are never touched.
    - Declarations removed from code (or commands no longer registered/
      active) have their rows and native objects deleted.
    """
    from .models import RegisteredCommand, ScheduledCommand
    from .registry import _registry
    from .schedules import materialize_schedule, remove_native_schedule

    try:
        active_names = set(
            RegisteredCommand.objects.filter(active=True).values_list("name", flat=True)
        )
        rows = list(ScheduledCommand.objects.filter(source=ScheduledCommand.Source.CODE))
    except OperationalError:
        logger.debug("ScheduledCommand table does not exist yet — skipping schedule sync.")
        return

    by_command: dict[str, dict[str, ScheduledCommand]] = {}
    for row in rows:
        by_command.setdefault(row.command_name, {})[row.label] = row

    runner_kinds = _supported_kinds()

    for name, entry in _registry.items():
        if name not in active_names:
            continue
        declared = {sched.name: sched for sched in entry.get("schedules") or []}
        existing = by_command.pop(name, {})
        for label, sched in declared.items():
            spec = sched.model_kwargs()
            row = existing.pop(label, None)
            if row is None:
                row = ScheduledCommand(
                    command_name=name,
                    label=label,
                    source=ScheduledCommand.Source.CODE,
                    enabled=sched.enabled,
                    **spec,
                )
                row.save()
            else:
                changed = False
                for field, value in spec.items():
                    if getattr(row, field) != value:
                        setattr(row, field, value)
                        changed = True
                if changed:
                    row.save()
            if runner_kinds:
                materialize_schedule(row)

        # Code rows for this command whose declaration was removed.
        for row in existing.values():
            remove_native_schedule(row)
            row.delete()

    # Leftover code rows: declarations removed from code, or their command
    # no longer registered/active.
    for command_rows in by_command.values():
        for row in command_rows.values():
            remove_native_schedule(row)
            row.delete()


def _supported_kinds() -> frozenset[str]:
    """Supported schedule kinds of the active runner (empty set on failure)."""
    try:
        from .runners import get_runner

        return get_runner().supported_schedule_kinds
    except Exception:  # noqa: BLE001
        return frozenset()


def _get_description(entry: dict) -> str:
    """Extract help text from a registry entry's command class."""
    command_class = entry.get("command_class")
    if command_class and hasattr(command_class, "help"):
        return getattr(command_class, "help", "") or ""
    return ""
