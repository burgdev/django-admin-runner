"""Celery Beat-compatible task for django-admin-runner.

This module exposes a :func:`schedule_command` shared task that Celery Beat
can invoke to create and run a :class:`~django_admin_runner.models.CommandExecution`
on a recurring schedule.

Unlike :class:`~django_admin_runner.runners.celery.CeleryCommandRunner` (which
enqueues commands from the admin and passes an existing ``execution_pk``), this
task creates the ``CommandExecution`` record at run-time — the correct behaviour
for periodic tasks where no prior record exists.

**Registering with Celery autodiscovery**

Celery's default ``autodiscover_tasks()`` only finds modules named ``tasks``.
To make the ``schedule_command`` task visible, add an explicit import in your
``celery_app.py`` after the Django setup::

    import django_admin_runner.celery_tasks  # noqa: F401

**Using with Celery Beat**

In the Celery Beat periodic-task admin, select::

    Task: django_admin_runner.schedule_command

and provide keyword arguments as JSON, e.g.::

    {"command_name": "import_books", "kwargs": {"source": "books.csv", "dry_run": true}}
"""

from __future__ import annotations

from celery import shared_task  # type: ignore[import-untyped]


@shared_task(name="django_admin_runner.schedule_command")
def schedule_command(command_name: str, kwargs: dict | None = None) -> None:
    """Create a :class:`~django_admin_runner.models.CommandExecution` and run *command_name*.

    Designed for use with Celery Beat periodic tasks.  Each invocation creates
    a fresh execution record so that every run is tracked individually.

    Args:
        command_name: The registered management command to run.
        kwargs: Optional dict of keyword arguments forwarded to the command.
    """
    from .models import CommandExecution
    from .tasks import execute_command

    execution = CommandExecution.objects.create(
        command_name=command_name,
        kwargs=kwargs or {},
        backend="celery",
    )
    execute_command(command_name, kwargs or {}, execution.pk)
