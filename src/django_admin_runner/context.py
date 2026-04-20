"""Execution context for admin runner commands.

Provides :func:`is_admin_runner` and :func:`set_result_html` so that
management commands can detect when they are running inside the admin runner
and optionally store rich HTML as the execution result.
"""

from __future__ import annotations

from contextvars import ContextVar

# Holds a mutable dict while an admin-runner execution is in flight,
# or ``None`` otherwise.
_execution_ctx: ContextVar[dict[str, object] | None] = ContextVar(
    "django_admin_runner_execution_ctx",
    default=None,
)


def is_admin_runner() -> bool:
    """Return ``True`` when called during an admin-runner command execution."""
    return _execution_ctx.get() is not None


def set_result_html(html: str) -> None:
    """Store *html* as the rich result for the current execution.

    No-op when called outside an admin-runner execution.  Last writer wins.
    """
    ctx = _execution_ctx.get()
    if ctx is not None:
        ctx["result_html"] = html


def _set_execution_context() -> dict[str, object]:
    """Create and activate a new execution context dict.  Returns the dict."""
    ctx: dict[str, object] = {}
    _execution_ctx.set(ctx)
    return ctx


def _clear_execution_context() -> None:
    """Deactivate the execution context."""
    _execution_ctx.set(None)
