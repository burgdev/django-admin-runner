from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django_admin_runner.models import CommandExecution


@dataclass
class RunResult:
    """Returned by every ``BaseCommandRunner.run()`` implementation."""

    execution: CommandExecution
    redirect_url: str
    is_async: bool
    backend: str
    task_id: str = field(default="")


class BaseCommandRunner:
    """Base class for command runners. Subclass and implement ``run()``."""

    backend: str = ""

    def run(
        self,
        command_name: str,
        kwargs: dict,
        triggered_by,
        execution: CommandExecution,
    ) -> RunResult:
        raise NotImplementedError


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
