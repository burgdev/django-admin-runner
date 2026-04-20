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


def _get_description(entry: dict) -> str:
    """Extract help text from a registry entry's command class."""
    command_class = entry.get("command_class")
    if command_class and hasattr(command_class, "help"):
        return getattr(command_class, "help", "") or ""
    return ""
