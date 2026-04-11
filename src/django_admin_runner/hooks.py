from __future__ import annotations

import importlib
import logging
import shutil
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import CommandExecution

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Hook context — mutable state bag scoped to a single execution
# ---------------------------------------------------------------------------


class HookContext:
    """Dict-like state bag scoped to a single command execution.

    Lets hooks share data between ``setup()`` and ``teardown()`` without
    coupling hooks to each other.  A fresh instance is created per execution.
    """

    def __init__(self) -> None:
        self._data: dict[str, object] = {}

    def __setitem__(self, key: str, value: object) -> None:
        self._data[key] = value

    def __getitem__(self, key: str) -> object:
        return self._data[key]

    def get(self, key: str, default: object = None) -> object:
        return self._data.get(key, default)


# ---------------------------------------------------------------------------
# Hook protocol
# ---------------------------------------------------------------------------


class CommandHook:
    """Base class for command execution hooks.

    Subclass and implement ``setup()``, ``pre_save()``, and/or ``post_save()``.
    """

    def setup(
        self,
        command_name: str,
        kwargs: dict,
        execution: CommandExecution,
        ctx: HookContext,
    ) -> None: ...

    def pre_save(
        self,
        command_name: str,
        kwargs: dict,
        execution: CommandExecution,
        ctx: HookContext,
    ) -> None:
        """Called after command execution but before the DB save."""
        ...

    def post_save(
        self,
        command_name: str,
        kwargs: dict,
        execution: CommandExecution,
        ctx: HookContext,
    ) -> None:
        """Called after the DB save completes.  Replaces the old ``teardown()``."""
        ...

    # Backwards-compat alias — old ``teardown`` maps to ``post_save``.
    def teardown(
        self,
        command_name: str,
        kwargs: dict,
        execution: CommandExecution,
        ctx: HookContext,
    ) -> None:
        """Deprecated: override :meth:`post_save` instead."""
        self.post_save(command_name, kwargs, execution, ctx)


# ---------------------------------------------------------------------------
# Built-in: temp file management
# ---------------------------------------------------------------------------


class TempFileHook(CommandHook):
    """Creates a unique upload directory under ``ADMIN_RUNNER_UPLOAD_PATH``
    in ``setup()`` and removes it in ``post_save()``.

    Only active when ``ADMIN_RUNNER_UPLOAD_PATH`` is configured.
    """

    def setup(self, command_name, kwargs, execution, ctx):
        from django.conf import settings

        upload_path = getattr(settings, "ADMIN_RUNNER_UPLOAD_PATH", "")
        if not upload_path:
            return

        dir_name = f"{command_name}_{uuid.uuid4().hex[:12]}"
        temp_dir = f"{upload_path.rstrip('/')}/{dir_name}"
        # Ensure base path exists
        import os

        os.makedirs(upload_path, exist_ok=True)
        os.makedirs(temp_dir, exist_ok=True)
        ctx["upload_dir"] = temp_dir

    def post_save(self, command_name, kwargs, execution, ctx):
        temp_dir = ctx.get("upload_dir")
        if temp_dir is None:
            return
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            logger.exception("Failed to clean up temp directory: %s", temp_dir)


# ---------------------------------------------------------------------------
# Hook loader
# ---------------------------------------------------------------------------

_hooks_cache: list[CommandHook] | None = None


def get_hooks() -> list[CommandHook]:
    """Return the list of instantiated hook singletons.

    Reads ``ADMIN_RUNNER_HOOKS`` setting and auto-registers
    ``TempFileHook`` when ``ADMIN_RUNNER_UPLOAD_PATH`` is set.
    """
    global _hooks_cache
    if _hooks_cache is not None:
        return _hooks_cache

    from django.conf import settings

    hooks: list[CommandHook] = []

    # Auto-register TempFileHook when upload path is configured
    upload_path = getattr(settings, "ADMIN_RUNNER_UPLOAD_PATH", "")
    if upload_path:
        hooks.append(TempFileHook())

    # Load user-configured hooks
    hook_paths: list[str] = getattr(settings, "ADMIN_RUNNER_HOOKS", [])
    for dotted_path in hook_paths:
        hooks.append(_import_hook(dotted_path))

    _hooks_cache = hooks
    return hooks


def _import_hook(dotted_path: str) -> CommandHook:
    """Import a hook class by dotted path and instantiate it."""
    module_path, class_name = dotted_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    if not issubclass(cls, CommandHook):
        msg = f"{dotted_path} is not a CommandHook subclass"
        raise TypeError(msg)
    return cls()


def reset_hooks_cache() -> None:
    """Clear the cached hooks list. Used in tests."""
    global _hooks_cache
    _hooks_cache = None
