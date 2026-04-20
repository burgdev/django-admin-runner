"""Dynamic per-command Celery tasks for django-admin-runner.

This module automatically registers one :class:`celery.shared_task` per
management command found in the registry.  Each task is named
``<app_label>.<command_name>`` (e.g. ``books.import_books``) so that commands
are individually visible in Celery results, Flower, and monitoring tools.

**Task signature**

Every generated task accepts ``(kwargs=None, execution_pk=None)``:

- **Admin-triggered** — ``execution_pk`` is provided; the task uses the
  existing :class:`~django_admin_runner.models.CommandExecution` record.
- **Beat-triggered** — ``execution_pk`` is ``None``; the task creates a fresh
  ``CommandExecution`` record before running the command.

**Celery Beat usage**

In the Celery Beat periodic-task admin, select the task by name (e.g.
``books.import_books``) and provide keyword arguments as JSON::

    {"source": "books.csv", "dry_run": true}

**Registration**

Tasks are registered automatically during
:func:`~django_admin_runner.registry.autodiscover_commands`.  No manual
import is required beyond ensuring ``django_admin_runner`` is in
``INSTALLED_APPS``.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from celery import Task  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

# Maps command_name → Celery task instance
_celery_tasks: dict[str, Task] = {}


def _register_celery_tasks() -> None:
    """Create one Celery task per registered management command."""
    try:
        from celery import shared_task  # type: ignore[import-untyped]
    except ImportError:  # pragma: no cover – Celery not installed
        return

    from .registry import _registry

    for cmd_name, entry in _registry.items():
        app_label = entry["app_label"]
        task_name = f"{app_label}.{cmd_name}"
        command_class = entry["command_class"]

        # Derive description from the command's help text.
        help_text: str = getattr(command_class, "help", "") or ""

        def _make_task(cn: str, tn: str, desc: str):
            """Factory to capture variables in the closure."""

            @shared_task(name=tn, description=desc)
            def _task(kwargs: dict | None = None, execution_pk: int | None = None) -> None:
                from .tasks import execute_command

                if execution_pk is None:
                    from .models import CommandExecution

                    execution = CommandExecution.objects.create(
                        command_name=cn,
                        kwargs=kwargs or {},
                        backend="celery",
                    )
                    execution_pk = execution.pk

                assert execution_pk is not None
                execute_command(cn, kwargs or {}, execution_pk)

            return _task

        _celery_tasks[cmd_name] = _make_task(cmd_name, task_name, help_text)
        logger.debug("Registered Celery task %s for command %s", task_name, cmd_name)


def get_celery_task(command_name: str) -> Task:
    """Return the Celery task for *command_name*.

    Raises ``KeyError`` if the command is not registered.
    """
    return _celery_tasks[command_name]
