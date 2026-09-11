from __future__ import annotations

import copy
import re
import threading
from typing import TYPE_CHECKING, cast

from django import forms
from django.contrib import admin
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    JsonResponse,
)
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils.safestring import SafeString, mark_safe

from .admin_compat import get_model_admin_base, get_template, is_unfold_installed
from .forms import form_from_command
from .models import CommandExecution, CommandOutputPart, RegisteredCommand, ScheduledCommand
from .registry import _registry, has_permission
from .runners import get_runner
from .schedules import materialize_schedule, remove_native_schedule
from .tasks import _terminal_size

if TYPE_CHECKING:
    from django.db import models as _models

_OUTPUT_FIELDS = ("stdout", "stderr")


def _staff_view(view):
    """Staff-gate a view *without* ``never_cache``.

    ``admin_view`` always disables caching, which would defeat the immutable
    caching of sealed output parts.  The view itself enforces object-level
    permissions via the admin queryset.
    """
    from django.contrib.auth.decorators import user_passes_test

    return user_passes_test(
        lambda u: u.is_active and u.is_staff,
        login_url="/admin/login/",
    )(view)


def _terminal_placeholder(field: str) -> SafeString:
    """Render the container div that ``terminal-output.js`` turns into a widget."""
    return cast(
        SafeString,
        mark_safe(f'<div class="dar-terminal" data-dar-field="{field}"></div>'),
    )


# Status badge colors: (foreground, background-tint). Fixed hex values so
# the badges read well in light and dark themes alike.
_STATUS_COLORS = {
    "PENDING": ("#6b7280", "rgba(107, 114, 128, 0.14)"),
    "RUNNING": ("#2563eb", "rgba(37, 99, 235, 0.14)"),
    "SUCCESS": ("#16a34a", "rgba(22, 163, 74, 0.14)"),
    "FAILED": ("#dc2626", "rgba(220, 38, 38, 0.14)"),
    "CANCELLED": ("#d97706", "rgba(217, 119, 6, 0.14)"),
    "TIMEOUT": ("#dc2626", "rgba(220, 38, 38, 0.12)"),
}

# Inline SVG icons (theme-independent — no icon-font dependency).
_STATUS_ICONS = {
    "PENDING": (
        '<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">'
        '<path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm0 18a8 8 0 1 1 8-8'
        ' 8 8 0 0 1-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67z"/></svg>'
    ),
    "RUNNING": (
        '<svg class="dar-spin" width="12" height="12" viewBox="0 0 24 24" '
        'fill="none" stroke="currentColor" stroke-width="3" '
        'stroke-linecap="round"><path d="M12 3a9 9 0 1 0 9 9"/></svg>'
    ),
    "SUCCESS": (
        '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="3" stroke-linecap="round" '
        'stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>'
    ),
    "FAILED": (
        '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="3" stroke-linecap="round">'
        '<path d="M18 6 6 18M6 6l12 12"/></svg>'
    ),
    "CANCELLED": (
        '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="3" stroke-linecap="round">'
        '<circle cx="12" cy="12" r="9"/><path d="M9 9l6 6M15 9l-6 6"/></svg>'
    ),
    "TIMEOUT": (
        '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="3" stroke-linecap="round">'
        '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/></svg>'
    ),
}


def _status_badge(obj: CommandExecution) -> SafeString:
    """Pill badge with an icon: spinner while running, check/cross when done.

    Carries ``data-status`` so ``terminal-output.js`` can update it live
    from the output poll (the page polls anyway; the badge follows along).
    """
    status = str(obj.status)
    color, tint = _STATUS_COLORS.get(status, ("#6b7280", "rgba(107,114,128,0.14)"))
    icon = _STATUS_ICONS.get(status, _STATUS_ICONS["PENDING"])
    label = obj.get_status_display()
    html = (
        f'<span id="dar-status-badge" data-status="{status}"'
        f' style="display:inline-flex;align-items:center;gap:6px;'
        f"padding:2px 10px;border-radius:999px;white-space:nowrap;"
        f'color:{color};background:{tint};font-size:12px;font-weight:600;">'
        f"{icon}{label}</span>"
    )
    return cast(SafeString, mark_safe(html))


def _parse_cursor(cursor: str) -> tuple[int, int] | None:
    """Parse an opaque ``"<seq>:<offset>"`` cursor; ``""`` means "from start"."""
    if cursor == "":
        return None
    try:
        seq_s, off_s = cursor.split(":", 1)
        seq, off = int(seq_s), int(off_s)
    except ValueError as err:
        raise ValueError("invalid cursor") from err
    if seq < 0 or off < 0:
        raise ValueError("invalid cursor")
    return seq, off


def _supported_schedule_kinds() -> frozenset[str]:
    """Schedule kinds the active runner supports (empty on any failure)."""
    try:
        return get_runner().supported_schedule_kinds
    except Exception:  # noqa: BLE001
        return frozenset()


# Stale-sweep rate limiting (process-local): the output poll fires every
# flush interval; the actual sweep may run at most once per
# ADMIN_RUNNER_SWEEP_INTERVAL seconds.
_sweep_state = {"last": 0.0}


def _maybe_sweep_stale() -> None:
    """Run the stale-run sweep, rate-limited; never raises into the request."""
    import logging
    import time

    from django.conf import settings

    from .tasks import sweep_stale_executions

    interval = float(getattr(settings, "ADMIN_RUNNER_SWEEP_INTERVAL", 30))
    now_mono = time.monotonic()
    if now_mono - _sweep_state["last"] < interval:
        return
    _sweep_state["last"] = now_mono
    try:
        sweep_stale_executions()
    except Exception:  # noqa: BLE001
        logging.getLogger(__name__).exception("Stale-run sweep raised")


# ---------------------------------------------------------------------------
# Mixin for model admins that want attached command run links
# ---------------------------------------------------------------------------


class CommandRunnerModelAdminMixin:
    """Mix into any ``ModelAdmin`` to show "Run" links for commands registered with
    ``models=[ThisModel]``.

    Example:

    ```python
    from django.contrib import admin
    from django_admin_runner.admin import CommandRunnerModelAdminMixin

    @admin.register(Book)
    class BookAdmin(CommandRunnerModelAdminMixin, admin.ModelAdmin):
        ...
    ```
    """

    model: type[_models.Model]  # provided by the ModelAdmin subclass

    def changelist_view(self, request, extra_context=None):
        attached = [
            entry
            for entry in _registry.values()
            if self.model in entry["models"] and has_permission(request.user, entry)
        ]
        extra_context = extra_context or {}
        extra_context["admin_runner_commands"] = attached
        return super().changelist_view(request, extra_context=extra_context)  # type: ignore[misc]


# ---------------------------------------------------------------------------
# CommandExecution admin (also hosts the command list/run views)
# ---------------------------------------------------------------------------

_ModelAdminBase = get_model_admin_base()


class ActiveListFilter(admin.SimpleListFilter):
    title = "active"
    parameter_name = "active"

    def lookups(self, request, model_admin):
        return [("1", "Yes"), ("0", "No")]

    def queryset(self, request, queryset):
        if self.value() == "0":
            return queryset.filter(active=False)
        return queryset.filter(active=True)


# Action-button icons for the commands changelist (12px, currentColor).
_RUN_ICON = (
    '<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">'
    '<path d="M8 5.14v13.72L19 12z"/></svg>'
)
_RESULTS_ICON = (
    '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" '
    'stroke="currentColor" stroke-width="2.5" stroke-linecap="round" '
    'stroke-linejoin="round"><path d="M8 6h13M8 12h13M8 18h13M3 6h.01'
    'M3 12h.01M3 18h.01"/></svg>'
)
_SCHEDULES_ICON = (
    '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" '
    'stroke="currentColor" stroke-width="2.5" stroke-linecap="round">'
    '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/></svg>'
)
# "never ran" marker for the Results button.
_NONE_ICON = (
    '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" '
    'stroke="currentColor" stroke-width="3" stroke-linecap="round">'
    '<path d="M6 12h12"/></svg>'
)

#: Primary color that works in every theme: Unfold defines ``--primary-600``
#: in its stylesheet, the classic admin uses ``--button-bg``; the literal
#: fallback covers themes that define neither.
_PRIMARY = "var(--primary-600, var(--button-bg, #5b6ee1))"

#: Theme-agnostic border/hover colors (no reliance on theme CSS variables
#: that may not exist, and no Tailwind arbitrary-value classes — those are
#: JIT-generated and absent from Unfold's shipped stylesheet).
_BTN_BORDER = "2px solid rgba(128, 128, 128, 0.45)"


def _status_icon(status: str) -> SafeString:
    """Status icon tinted with its badge color (spinner while RUNNING)."""
    color = _STATUS_COLORS.get(status, ("#6b7280",))[0]
    icon = _STATUS_ICONS.get(status, _RESULTS_ICON)
    return cast(SafeString, mark_safe(f'<span style="color:{color};">{icon}</span>'))


def _action_button(
    *,
    icon: str,
    label: str = "",
    url: str | None = None,
    title: str,
    style: str = "ghost",
    disabled: bool = False,
) -> str:
    """One changelist action button (theme-agnostic inline styles).

    Styles:
    - ``tinted``: 2px-bordered icon button with the icon in the primary
      color and a faint primary background wash (Run).
    - ``ghost``: 2px-bordered icon button (Schedules).
    - ``soft``: borderless quiet text button (Results) whose leading glyph
      carries the status color.

    ``label=""`` renders an icon-only button. Disabled buttons keep their
    label but render as a faded, non-clickable ``<span>``.
    """
    icon_html = f'<span style="color:{_PRIMARY};">{icon}</span>' if style == "tinted" else icon
    border_css = "" if style == "soft" else f"border:{_BTN_BORDER};"
    # Icon-only buttons (Run, Schedules) stay compact; the soft text
    # button (Results) is framed by its text and needs less padding.
    padding = "4px 7px" if not label else "4px 6px"
    base_css = (
        "display:inline-flex;align-items:center;gap:5px;"
        f"padding:{padding};border-radius:6px;font-size:12px;font-weight:600;"
        f"color:var(--body-quiet-color,#888);text-decoration:none;{border_css}"
    )
    if style == "tinted":
        base_css += f"background:color-mix(in srgb, {_PRIMARY} 10%, transparent);"

    if disabled:
        css = base_css + "opacity:.4;cursor:not-allowed;"
        inner = f"{icon_html}{label}"
        return (
            f'<span class="dar-cmdbtn" style="{css}" title="{title}" '
            f'aria-disabled="true">{inner}</span>'
        )
    inner = f"{icon_html}{label}"
    return f'<a class="dar-cmdbtn" href="{url}" title="{title}" style="{base_css}">{inner}</a>'


class CommandGroupListFilter(admin.SimpleListFilter):
    """Filter commands by their registry group (e.g. ?group=Maintenance)."""

    title = "group"
    parameter_name = "group"

    def lookups(self, request, model_admin):
        values = (
            RegisteredCommand.objects.order_by("group").values_list("group", flat=True).distinct()
        )
        return [(name, name) for name in values]

    def queryset(self, request, queryset):
        value = self.value()
        return queryset.filter(group=value) if value else queryset


class ExecutionScheduleListFilter(admin.SimpleListFilter):
    """Filter executions by their originating schedule (or manual runs)."""

    title = "schedule"
    parameter_name = "schedule"

    def lookups(self, request, model_admin):
        rows = ScheduledCommand.objects.order_by("command_name", "label").values_list(
            "pk", "label", "command_name"
        )
        return [(pk, str(label or command_name)) for pk, label, command_name in rows] + [
            ("none", "— manual run —")
        ]

    def queryset(self, request, queryset):
        value = self.value()
        if value == "none":
            return queryset.filter(schedule__isnull=True)
        if value:
            return queryset.filter(schedule__pk=value)
        return queryset


@admin.register(RegisteredCommand)
class RegisteredCommandAdmin(_ModelAdminBase):  # type: ignore[misc]
    list_display = [
        "name_link",
        "group",
        "buttons",
    ]
    list_display_links = None
    search_fields = ["name", "display_name"]
    list_filter = [ActiveListFilter, CommandGroupListFilter]
    ordering = ["group", "name"]

    class Media:
        # Spinner animation for the RUNNING status icon in the Results button.
        css = {"all": ("django_admin_runner/status-badges.css",)}

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def get_queryset(self, request):
        from django.db.models import Exists, OuterRef, Subquery

        from .models import CommandExecution, ScheduledCommand

        last_execution = CommandExecution.objects.filter(command_name=OuterRef("name")).order_by(
            "-created_at"
        )
        qs = (
            super()
            .get_queryset(request)
            .annotate(
                has_schedules=Exists(
                    ScheduledCommand.objects.filter(command_name=OuterRef("name"))
                ),
                last_status=Subquery(last_execution.values("status")[:1]),
                last_created_at=Subquery(last_execution.values("created_at")[:1]),
            )
        )
        # Pinned group view(s): filter here (not via list filters — a
        # filter with no lookups is skipped by the changelist, lookups
        # and all).
        pinned = getattr(request, "_dar_pin_groups", None)
        if pinned:
            qs = qs.filter(group__in=pinned)
        return qs

    def get_list_filter(self, request):
        if getattr(request, "_dar_pin_groups", None):
            # Group(s) fixed on the pinned view — hide every filter.
            return []
        return super().get_list_filter(request)

    def changelist_view(self, request, extra_context=None):
        pinned = getattr(request, "_dar_pin_groups", None)
        # Pinned group view: the group(s) are fixed — no filters at all
        # (and no active-default redirect, which would append an unclaimed
        # "active" param now that the active filter is gone here).
        if pinned:
            extra_context = extra_context or {}
            extra_context["title"] = "Commands: " + " + ".join(pinned)
            return super().changelist_view(request, extra_context=extra_context)
        # Default the active filter to "Yes" when no active param is present
        if "active" not in request.GET:
            qp = request.GET.copy()
            qp["active"] = "1"
            return redirect(f"{request.path}?{qp.urlencode()}")
        return super().changelist_view(request, extra_context=extra_context)

    # ------------------------------------------------------------------
    # Pinned group view (e.g. sidebar "Maintenance" entry)
    # ------------------------------------------------------------------

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "group/<str:group_name>/",
                self.admin_site.admin_view(self._group_view),
                name="django_admin_runner_registeredcommand_group",
            ),
        ]
        return custom + urls

    def _group_view(self, request, group_name: str):
        """Changelist pinned to one or more groups, on its own URL.

        A dedicated URL (instead of ``?group=…``) means admin/Unfold menu
        highlighting can distinguish it from the plain commands list. Groups
        are "+"-separated for multi-group views, e.g. ``group/A+B/``.
        """
        groups = [g.strip() for g in group_name.split("+") if g.strip()]
        if not groups or not RegisteredCommand.objects.filter(group__in=groups).exists():
            raise Http404(f"No commands in group(s) {group_name!r}.")
        # The flag rides on the request object; filtering happens in
        # get_queryset (any GET filter param would be rejected as unknown
        # here, because all filters are removed on this view).
        request._dar_pin_groups = groups
        return self.changelist_view(request)

    @admin.display(description="Name", ordering="name")
    def name_link(self, obj: RegisteredCommand) -> SafeString:
        name_html = f"<strong>{obj.display_name}</strong>"
        desc_html = ""
        if obj.description:
            desc_html = (
                f'<br><span style="color:var(--body-quiet-color,#666);'
                f"max-width:100%;display:block;overflow:hidden;"
                f"text-overflow:ellipsis;white-space:nowrap;"
                f'font-size:12px;">{obj.description}</span>'
            )
        if obj.active:
            run_url = reverse("admin:django_admin_runner_command_run", args=[obj.name])
            return cast(SafeString, mark_safe(f'<a href="{run_url}">{name_html}</a>{desc_html}'))
        return cast(SafeString, mark_safe(f"{name_html}{desc_html}"))

    @admin.display(description="Actions")
    def buttons(self, obj: RegisteredCommand) -> SafeString:
        from django.utils.timesince import timesince

        run_btn = ""
        results_btn = ""
        if obj.active:
            run_url = reverse("admin:django_admin_runner_command_run", args=[obj.name])
            run_btn = _action_button(
                icon=_RUN_ICON,
                url=run_url,
                title="Run command",
                style="tinted",
            )
        else:
            # Inactive (no longer registered in code): keep the button
            # visible but disabled, with an explaining tooltip.
            run_btn = _action_button(
                icon=_RUN_ICON,
                disabled=True,
                title="Command is no longer registered (inactive)",
                style="tinted",
            )
        if obj.active:
            # Results: soft text button whose leading glyph is the last
            # execution's status (spinner while one is running); faded
            # and non-clickable when the command has never run.
            results_url = (
                reverse("admin:django_admin_runner_commandexecution_changelist")
                + f"?command_name={obj.name}"
            )
            last_status = getattr(obj, "last_status", None)
            if last_status:
                label = CommandExecution.Status(str(last_status)).label
                title = f"Results - last run {label}"
                last_created = getattr(obj, "last_created_at", None)
                if last_created:
                    title = f"Results - {label}, {timesince(last_created)} ago"
                results_btn = _action_button(
                    icon=_status_icon(str(last_status)),
                    label="Results",
                    url=results_url,
                    title=title,
                    style="soft",
                )
            else:
                results_btn = _action_button(
                    icon=_NONE_ICON,
                    label="Results",
                    disabled=True,
                    title="No results yet",
                    style="soft",
                )
        # Schedules: clock icon next to Run, faded and non-clickable when
        # none exist (also shown for inactive commands with schedules).
        schedules_url = (
            reverse("admin:django_admin_runner_scheduledcommand_changelist")
            + f"?command_name={obj.name}"
        )
        has_schedules = getattr(obj, "has_schedules", False)
        schedules_btn = _action_button(
            icon=_SCHEDULES_ICON,
            url=schedules_url if has_schedules else None,
            disabled=not has_schedules,
            title="Schedules" if has_schedules else "No schedules",
        )
        html = (
            f'<span style="display:inline-flex;align-items:center;gap:9px;">'
            f"{run_btn}{schedules_btn}{results_btn}</span>"
        )
        return cast(SafeString, mark_safe(html))


@admin.register(CommandExecution)
class CommandExecutionAdmin(_ModelAdminBase):  # type: ignore[misc]
    change_form_template = "admin/django_admin_runner/commandexecution/change_form.html"

    def render_change_form(self, request, context, **kwargs):
        """Tell the template whether Unfold handles the tabs natively.

        The base-theme tab fallback (execution-tabs.js) must not run under
        Unfold — it would build a second, mislabeled tab bar and hide the
        Input fieldset behind inline styles.
        """
        context["dar_is_unfold"] = is_unfold_installed()
        return super().render_change_form(request, context, **kwargs)

    class Media:
        # NOTE: cache-busting query strings (?v=…) must NOT be part of the
        # path here — Django's static templatetag/storage URL-encodes the
        # whole string, turning "?" into %3F and 404-ing the asset.
        css = {
            "all": (
                "django_admin_runner/vendor/xterm/xterm.css",
                "django_admin_runner/ansi-output.css",
                # Full-width terminals in both themes:
                "django_admin_runner/terminals.css",
                # Status badge spinner animation (changelist + change page):
                "django_admin_runner/status-badges.css",
            )
        }
        js = (
            "django_admin_runner/vendor/xterm/xterm.js",
            "django_admin_runner/vendor/xterm/addon-webgl.js",
            "django_admin_runner/vendor/xterm/addon-fit.js",
            "django_admin_runner/terminal-output.js",
        )

    list_display = [
        "command_name",
        "label_display",
        "status_display",
        "triggered_by_display",
        "backend",
        "created_at",
        "result_button",
    ]
    # Avoid N+1 queries on the triggered_by foreign key in the change list.
    list_select_related = ("triggered_by", "schedule")
    list_filter = ["status", "backend", ExecutionScheduleListFilter]
    search_fields = ["command_name", "triggered_by__username"]
    readonly_fields = [
        "command_name",
        "label",
        "schedule_display",
        "status_display",
        "result_html_display",
        "stdout_display",
        "stderr_display",
        "kwargs",
        "triggered_by",
        "backend",
        "task_id",
        "created_at",
        "started_at",
        "finished_at",
    ]
    fieldsets = [
        (
            "Output",
            {
                "classes": ["tab"],
                "fields": [
                    "status_display",
                    "result_html_display",
                    "stdout_display",
                    "stderr_display",
                ],
            },
        ),
        (
            "Input",
            {
                "classes": ["tab"],
                "fields": [
                    "command_name",
                    "label",
                    "schedule_display",
                    "kwargs",
                    "triggered_by",
                    "backend",
                    "task_id",
                    "created_at",
                    "started_at",
                    "finished_at",
                ],
            },
        ),
    ]
    ordering = ["-created_at"]

    @admin.display(description="Label", ordering="label")
    def label_display(self, obj: CommandExecution) -> str:
        """Run label: manual label or the originating schedule's label."""
        label = str(obj.label or "")
        if not label and obj.schedule_id and obj.schedule:
            label = str(obj.schedule.label)
        return label or "—"

    @admin.display(description="Schedule")
    def schedule_display(self, obj: CommandExecution) -> SafeString | str:
        """Link to the originating schedule, or '—' for manual runs."""
        if not obj.schedule_id or not obj.schedule:
            return "—"
        url = reverse(
            "admin:django_admin_runner_scheduledcommand_change",
            args=[obj.schedule_id],
        )
        name = str(obj.schedule.label or obj.schedule.command_name)
        return cast(SafeString, mark_safe(f'<a href="{url}">{name}</a>'))

    # Small leading icon marking how the run was triggered: a clock for
    # scheduled runs, a person for manual ones.
    _PERSON_ICON = (
        '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="2.5" stroke-linecap="round" '
        'stroke-linejoin="round"><circle cx="12" cy="8" r="4"/>'
        '<path d="M4 21c0-4 3.6-6 8-6s8 2 8 6"/></svg>'
    )
    _CLOCK_ICON = (
        '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="2.5" stroke-linecap="round">'
        '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/></svg>'
    )

    @admin.display(description="Triggered by", ordering="triggered_by")
    def triggered_by_display(self, obj: CommandExecution) -> SafeString:
        if obj.schedule_id:
            label = str(obj.schedule.label or obj.schedule.command_name) if obj.schedule else ""
            who = "scheduled"
            icon = f'<span title="Scheduled run: {label}" style="color:var(--body-quiet-color,#888);">{self._CLOCK_ICON}</span>'  # noqa: E501
        else:
            who = str(obj.triggered_by) if obj.triggered_by_id else "—"
            icon = f'<span title="Manual run" style="color:var(--body-quiet-color,#888);">{self._PERSON_ICON}</span>'  # noqa: E501
        return cast(SafeString, mark_safe(f"{icon} {who}"))

    @admin.display(description="Status", ordering="status")
    def status_display(self, obj: CommandExecution) -> SafeString:
        """Status as a pill badge (spinner while running, check/cross when done)."""
        return _status_badge(obj)

    @admin.display(description="Output")
    def stdout_display(self, obj: CommandExecution) -> SafeString:
        # Always render the terminal placeholder: the page is often opened
        # before the first flush, and a missing placeholder means the widget
        # never attaches and live output never appears.
        url = reverse(
            "admin:django_admin_runner_commandexecution_output_full",
            args=[obj.pk],
        )
        html = f'{_terminal_placeholder("stdout")}<p><a href="{url}#stdout">Full View</a></p>'
        return cast(SafeString, mark_safe(html))

    @admin.display(description="Errors")
    def stderr_display(self, obj: CommandExecution) -> SafeString:
        # Always render the terminal placeholder (see stdout_display).
        url = reverse(
            "admin:django_admin_runner_commandexecution_output_full",
            args=[obj.pk],
        )
        html = f'{_terminal_placeholder("stderr")}<p><a href="{url}#stderr">Full View</a></p>'
        return cast(SafeString, mark_safe(html))

    def get_fieldsets(self, request, obj=None):
        """Show the Result field only when the command produced result HTML."""
        fieldsets = super().get_fieldsets(request, obj)
        if obj is not None and not obj.result_html:
            return [
                (
                    name,
                    {
                        **opts,
                        "fields": [f for f in opts.get("fields", []) if f != "result_html_display"],
                    },
                )
                for name, opts in fieldsets
            ]
        return fieldsets

    @admin.display(description="Result")
    def result_html_display(self, obj: CommandExecution) -> SafeString:
        if not obj.result_html:
            return cast(SafeString, mark_safe("<em>—</em>"))
        result_url = reverse(
            "admin:django_admin_runner_commandexecution_result",
            args=[obj.pk],
        )
        html = (
            # Theme-neutral translucent border (no white frame in dark themes)
            f'<div style="max-height:300px;overflow:auto;'
            f"border:1px solid rgba(128,128,128,0.35);"
            f'padding:8px;border-radius:6px;margin-bottom:8px;">'
            f"{obj.result_html}</div>"
            f'<a href="{result_url}">Full View</a>'
        )
        return cast(SafeString, mark_safe(html))

    @admin.display(description="", ordering="created_at")
    def result_button(self, obj: CommandExecution) -> SafeString:
        buttons: list[str] = []
        if obj.result_html:
            url = reverse(
                "admin:django_admin_runner_commandexecution_result",
                args=[obj.pk],
            )
            buttons.append(
                f'<a href="{url}" '
                f'style="display:inline-block;padding:4px 10px;border-radius:4px;'
                f"font-size:11px;font-weight:600;color:#fff;"
                f'background:#28a745;text-decoration:none;margin-right:4px;"'
                f">View</a>"
            )
        if getattr(obj, "has_stdout", False) or obj.has_output("stdout"):
            url = (
                reverse(
                    "admin:django_admin_runner_commandexecution_output_full",
                    args=[obj.pk],
                )
                + "#stdout"
            )
            buttons.append(
                f'<a href="{url}" '
                f'style="display:inline-block;padding:4px 10px;border-radius:4px;'
                f"font-size:11px;font-weight:600;color:#fff;"
                f'background:#0d6efd;text-decoration:none;margin-right:4px;"'
                f">Stdout</a>"
            )
        if getattr(obj, "has_stderr", False) or obj.has_output("stderr"):
            url = (
                reverse(
                    "admin:django_admin_runner_commandexecution_output_full",
                    args=[obj.pk],
                )
                + "#stderr"
            )
            buttons.append(
                f'<a href="{url}" '
                f'style="display:inline-block;padding:4px 10px;border-radius:4px;'
                f"font-size:11px;font-weight:600;color:#fff;"
                f'background:#dc3545;text-decoration:none;margin-right:4px;"'
                f">Stderr</a>"
            )
        if not buttons:
            return cast(SafeString, mark_safe("<span>—</span>"))
        return cast(SafeString, mark_safe("".join(buttons)))

    def has_add_permission(self, request):
        return False

    def get_queryset(self, request):
        from django.db.models import Exists, OuterRef

        qs = (
            super()
            .get_queryset(request)
            .annotate(
                has_stdout=Exists(
                    CommandOutputPart.objects.filter(execution=OuterRef("pk"), field="stdout")
                ),
                has_stderr=Exists(
                    CommandOutputPart.objects.filter(execution=OuterRef("pk"), field="stderr")
                ),
            )
        )
        if request.user.has_perm("django_admin_runner.view_all_executions"):
            return qs
        return qs.filter(triggered_by=request.user)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        # Lazily finalize executions whose worker died (hard timeout kill,
        # crash) before rendering — the page then shows the true status.
        _maybe_sweep_stale()
        extra_context = extra_context or {}
        extra_context.update(
            self._terminal_context("admin:django_admin_runner_commandexecution_output", object_id)
        )
        execution = self.get_queryset(request).filter(pk=object_id).first()
        if execution is not None:
            extra_context.update(self._stop_context(request, execution))
        # Every field is read-only: the default Save buttons are dead
        # controls — hide them and offer a Rerun link instead.
        extra_context["show_save"] = False
        extra_context["show_save_and_continue"] = False
        extra_context["dar_rerun_url"] = self._rerun_url(request, object_id)
        extra_context["dar_rerun_running"] = self._is_rerun_running(request, object_id)
        return super().change_view(request, object_id, form_url, extra_context)

    # ------------------------------------------------------------------
    # Stop / Force Stop
    # ------------------------------------------------------------------

    def has_stop_permission(self, request) -> bool:
        """Who may stop running executions (defaults to change permission)."""
        return request.user.has_perm("django_admin_runner.change_commandexecution")

    def _stop_context(self, request, execution: CommandExecution) -> dict:
        """Stop-control context: rendered only while the execution runs.

        - RUNNING, no stop requested → "Stop" (graceful request).
        - RUNNING, stop requested → "Force Stop" (hard kill) — only on
          backends that support it.
        - anything else → nothing at all.
        """
        if execution.status != CommandExecution.Status.RUNNING:
            return {}
        if not self.has_stop_permission(request):
            return {}
        if execution.stop_requested:
            if not get_runner().supports_force_stop:
                return {}
            return {"dar_stop_url": self._stop_url(execution), "dar_stop_force": True}
        return {"dar_stop_url": self._stop_url(execution), "dar_stop_force": False}

    @staticmethod
    def _stop_url(execution: CommandExecution) -> str:
        return reverse(
            "admin:django_admin_runner_commandexecution_stop",
            args=[execution.pk],
        )

    def _stop_view(self, request, object_id):
        """POST endpoint behind the Stop / Force Stop button.

        Without ``force=1``: graceful stop (stop flag + backend signal).
        With ``force=1``: hard kill; when the kill was performed the
        worker cannot finalize the row anymore, so the row is finalized
        here — conditionally on still being RUNNING.
        """
        from django.contrib import messages
        from django.utils.timezone import now

        if request.method != "POST":
            return HttpResponseBadRequest(b"POST required")
        execution = self._get_execution(request, object_id)
        if not self.has_stop_permission(request):
            return HttpResponseForbidden(b"You do not have permission to stop executions.")
        change_url = reverse(
            "admin:django_admin_runner_commandexecution_change",
            args=[execution.pk],
        )
        if execution.status != CommandExecution.Status.RUNNING:
            # Finished (or already stopped) between render and click —
            # the graceful-stop update is conditional and races safely.
            return redirect(change_url)

        runner = get_runner()
        if request.POST.get("force") == "1":
            killed = runner.force_stop(execution)
            # Finalize unconditionally (still conditional on RUNNING): a
            # performed kill leaves no worker to write the row, and a
            # failed kill (unsupported backend, worker already gone /
            # stale row) means nothing is running that could finalize it
            # either way — the user's intent is to be done with it.
            CommandExecution.objects.filter(
                pk=execution.pk, status=CommandExecution.Status.RUNNING
            ).update(status=CommandExecution.Status.CANCELLED, finished_at=now())
            if killed:
                self.message_user(
                    request,
                    "Force stop: the worker process was killed.",
                    messages.SUCCESS,
                )
            else:
                self.message_user(
                    request,
                    "Force stop: no running worker was found — the "
                    "execution was marked as cancelled.",
                    messages.WARNING,
                )
        else:
            runner.stop(execution)
            self.message_user(
                request,
                "Stop requested — the command stops at its next output "
                "heartbeat or on the stop signal.",
                messages.SUCCESS,
            )
        return redirect(change_url)

    def _rerun_url(self, request, object_id) -> str | None:
        """Run-view URL prefilled from this execution, or None.

        Only when the command is still registered and the user has run
        permission for it (same gate as the changelist "Run" button).
        """
        execution = self.get_queryset(request).filter(pk=object_id).first()
        if execution is None:
            return None
        entry = _registry.get(execution.command_name)
        if entry is None or not has_permission(request.user, entry):
            return None
        url = reverse(
            "admin:django_admin_runner_command_run",
            args=[execution.command_name],
        )
        return f"{url}?rerun={execution.pk}"

    def _is_rerun_running(self, request, object_id) -> bool:
        """Whether the execution is still pending/running (Rerun disabled)."""
        execution = self.get_queryset(request).filter(pk=object_id).first()
        return execution is not None and execution.status in (
            CommandExecution.Status.PENDING,
            CommandExecution.Status.RUNNING,
        )

    @staticmethod
    def _initial_from_kwargs(
        form_class: type[forms.Form],
        kwargs: dict,
    ) -> dict:
        """Form initial data from a past execution's stored kwargs.

        Unknown keys (args the command no longer has) are dropped; a
        single string for a multiple-choice field (append args can be
        stored comma/space-joined) is split into a list.
        """
        initial: dict = {}
        for name, value in kwargs.items():
            field = form_class.base_fields.get(name)
            if field is None or value in (None, ""):
                continue
            if isinstance(field, forms.MultipleChoiceField) and isinstance(value, str):
                value = [item for item in re.split(r"[,\s]+", value) if item]
            initial[name] = value
        return initial

    # ------------------------------------------------------------------
    # Extra URLs: command list + run form
    # ------------------------------------------------------------------

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "commands/<str:command_name>/run/",
                self.admin_site.admin_view(self._command_run_view),
                name="django_admin_runner_command_run",
            ),
            path(
                "<path:object_id>/result/",
                self.admin_site.admin_view(self._result_view),
                name="django_admin_runner_commandexecution_result",
            ),
            path(
                "<path:object_id>/output/full/",
                self.admin_site.admin_view(self._full_output_view),
                name="django_admin_runner_commandexecution_output_full",
            ),
            path(
                "<path:object_id>/stdout/",
                self.admin_site.admin_view(self._stdout_view),
                name="django_admin_runner_commandexecution_stdout",
            ),
            path(
                "<path:object_id>/stderr/",
                self.admin_site.admin_view(self._stderr_view),
                name="django_admin_runner_commandexecution_stderr",
            ),
            path(
                "<path:object_id>/stop/",
                self.admin_site.admin_view(self._stop_view),
                name="django_admin_runner_commandexecution_stop",
            ),
            path(
                "<path:object_id>/output/",
                self.admin_site.admin_view(self._output_view),
                name="django_admin_runner_commandexecution_output",
            ),
            path(
                "<path:object_id>/output/part/<int:seq>/",
                _staff_view(self._output_part_view),
                name="django_admin_runner_commandexecution_output_part",
            ),
        ]
        return custom + urls

    def _get_execution(self, request, object_id):
        """Fetch execution or 404, respecting queryset permissions."""
        execution = self.get_queryset(request).filter(pk=object_id).first()
        if execution is None:
            raise Http404
        return execution

    def _result_view(self, request, object_id):
        """Standalone result page: result_html if set, otherwise stdout."""
        execution = self._get_execution(request, object_id)

        if execution.result_html:
            content = cast(SafeString, mark_safe(execution.result_html))
        else:
            content = _terminal_placeholder("stdout")

        context = {
            **self._render_output_context(request, execution, f"Result: {execution.command_name}"),
            "content": content,
        }
        return render(request, get_template("result"), context)

    def _stdout_view(self, request, object_id):
        """Standalone stdout page."""
        execution = self._get_execution(request, object_id)
        content = _terminal_placeholder("stdout")
        context = {
            **self._render_output_context(request, execution, f"Output: {execution.command_name}"),
            "content": content,
        }
        return render(request, get_template("result"), context)

    def _full_output_view(self, request, object_id):
        """Combined full-output page: Output and Errors as tabs, full height."""
        execution = self._get_execution(request, object_id)
        content = cast(
            SafeString,
            mark_safe(
                '<div class="dar-full">'
                '<div class="dar-full-tabs">'
                '<button type="button" class="dar-full-tab active" '
                'data-pane="stdout">Output</button>'
                '<button type="button" class="dar-full-tab" '
                'data-pane="stderr">Errors</button>'
                "</div>"
                f'<div class="dar-full-pane" data-pane="stdout">'
                f"{_terminal_placeholder('stdout')}</div>"
                f'<div class="dar-full-pane dar-hidden" data-pane="stderr">'
                f"{_terminal_placeholder('stderr')}</div>"
                "<script>(function(){"
                "var tabs=document.querySelectorAll('.dar-full-tab');"
                "var panes=document.querySelectorAll('.dar-full-pane');"
                "function activate(pane){"
                "tabs.forEach(function(t){t.classList.toggle('active',t.dataset.pane===pane)});"
                "panes.forEach(function(p){p.classList.toggle('dar-hidden',p.dataset.pane!==pane)});"
                "setTimeout(function(){window.dispatchEvent(new Event('resize'));},50);"
                "}"
                "tabs.forEach(function(t){t.addEventListener('click',function(){"
                "if(location.hash!=='#'+t.dataset.pane){location.hash=t.dataset.pane;}"
                "activate(t.dataset.pane);"
                "});});"
                "var fromHash=function(){"
                "var h=location.hash.replace('#','');"
                "if(h==='stdout'||h==='stderr'){activate(h);}"
                "};"
                "window.addEventListener('hashchange',fromHash);"
                "fromHash();"
                "})();</script>"
                "</div>",
            ),
        )
        context = {
            **self._render_output_context(
                request,
                execution,
                f"Output: {execution.command_name}",
                fit=True,
            ),
            "content": content,
        }
        return render(request, get_template("result"), context)

    def _stderr_view(self, request, object_id):
        """Standalone stderr/traceback page."""
        execution = self._get_execution(request, object_id)
        content = _terminal_placeholder("stderr")
        context = {
            **self._render_output_context(
                request, execution, f"Traceback: {execution.command_name}"
            ),
            "content": content,
        }
        return render(request, get_template("result"), context)

    def _terminal_context(self, url_name: str, object_id, *, fit: bool = False) -> dict:
        """Context needed by the terminal widget (config JSON in templates)."""
        from django.conf import settings

        from .models import CommandExecution

        execution = CommandExecution.objects.filter(pk=object_id).first()
        cols, _rows = _terminal_size()
        # Widget height is decoupled from the LINES export: commands lay
        # out for ADMIN_RUNNER_TERM_ROWS (default 40, e.g. rich panels),
        # but the embedded terminal stays compact (default 20) and relies
        # on its scrollback for taller output.
        rows = int(getattr(settings, "ADMIN_RUNNER_TERM_VIEW_ROWS", 20))
        rows = max(5, min(rows, 200))
        from .tasks import _flush_interval_for_command

        poll_interval_ms = (
            int(
                _flush_interval_for_command(execution.command_name) * 1000,
            )
            if execution
            else 500
        )
        part_url = reverse(
            "admin:django_admin_runner_commandexecution_output_part",
            args=[object_id, 0],
        )
        return {
            "dar_output_url": reverse(url_name, args=[object_id]),
            "dar_output_part_url": part_url,
            "dar_term_cols": cols,
            "dar_term_rows": rows,
            "dar_poll_interval": poll_interval_ms,
            "dar_fit": "true" if fit else "false",
            "stdout_url": reverse(
                "admin:django_admin_runner_commandexecution_stdout",
                args=[object_id],
            ),
            "stderr_url": reverse(
                "admin:django_admin_runner_commandexecution_stderr",
                args=[object_id],
            ),
            "dar_started_at": (
                execution.started_at.isoformat(timespec="milliseconds")
                if execution and execution.started_at
                else ""
            ),
        }

    def _output_view(self, request, object_id):
        """JSON delta endpoint: output written after an opaque cursor.

        ``?field=stdout|stderr&cursor=<seq>:<offset>`` →
        ``{status, chunk, cursor, finished, reset}``.  An empty/missing
        cursor replays from the start.  When the client cursor points at a
        pruned part, ``reset: true`` is returned together with the full
        retained output so the widget can reset and replay.
        """
        # Lazy stale-run sweep (rate-limited): a watched execution whose
        # worker was killed reports its true status on the next tick.
        _maybe_sweep_stale()
        execution = self._get_execution(request, object_id)

        field = request.GET.get("field", "")
        if field not in _OUTPUT_FIELDS:
            return HttpResponseBadRequest(f"Invalid field: {field!r}".encode())

        try:
            cursor = _parse_cursor(request.GET.get("cursor", ""))
        except ValueError:
            return HttpResponseBadRequest(b"Invalid cursor")

        parts = list(execution.output_parts_for(field).values_list("seq", "text"))
        finished = execution.status in (
            CommandExecution.Status.SUCCESS,
            CommandExecution.Status.FAILED,
            CommandExecution.Status.CANCELLED,
            CommandExecution.Status.TIMEOUT,
        )
        if not parts:
            return JsonResponse(
                {
                    "status": execution.status,
                    "chunk": "",
                    "cursor": "",
                    "finished": finished,
                    "reset": False,
                }
            )

        last_seq, last_text = parts[-1]
        end_cursor = f"{last_seq}:{len(last_text)}"

        reset = False
        if cursor is None:
            chunk = "".join(text for _, text in parts)
        else:
            c_seq, c_off = cursor
            index = next((i for i, (seq, _) in enumerate(parts) if seq == c_seq), None)
            if index is None:
                # Cursor predates pruned parts: send everything retained.
                reset = True
                chunk = "".join(text for _, text in parts)
            else:
                _, text = parts[index]
                chunk = text[c_off:] + "".join(t for _, t in parts[index + 1 :])

        return JsonResponse(
            {
                "status": execution.status,
                "chunk": chunk,
                "cursor": end_cursor,
                "finished": finished,
                "reset": reset,
                # Live stop control: present only while RUNNING and the
                # user may stop — lets the terminal widget render/update
                # (or remove) the Stop/Force Stop button as the execution
                # transitions PENDING → RUNNING → terminal.
                "stop": self._stop_info(request, execution),
            }
        )

    def _stop_info(self, request, execution) -> dict | None:
        """Stop-control descriptor for the JSON poll endpoint."""
        ctx = self._stop_context(request, execution)
        if not ctx:
            return None
        return {"url": ctx["dar_stop_url"], "force": bool(ctx["dar_stop_force"])}

    def _output_part_view(self, request, object_id, seq: int):
        """Serve one output part whole, with immutable caching when sealed.

        Sealed parts (every part except the active/last one) never change,
        so they are served with an ETag and ``Cache-Control: immutable`` —
        repeat opens hit the browser cache instead of the server.
        """
        execution = self._get_execution(request, object_id)

        field = request.GET.get("field", "")
        if field not in _OUTPUT_FIELDS:
            return HttpResponseBadRequest(f"Invalid field: {field!r}".encode())

        part = (
            execution.output_parts_for(field).filter(seq=seq).values_list("text", flat=True).first()
        )
        if part is None:
            raise Http404

        # The ETag includes the part length: the active part keeps growing,
        # and a constant ETag would let revalidation return 304 for a stale
        # truncated copy after the part expanded (e.g. on page reload after
        # the command finished). Sealed parts are stable, so their ETag —
        # and therefore the immutable caching — is unaffected.
        etag = f'"{execution.pk}:{field}:{seq}:{len(part)}"'
        if request.headers.get("If-None-Match") == etag:
            response = HttpResponse(status=304)
        else:
            response = HttpResponse(part, content_type="text/plain; charset=utf-8")
        response.headers["ETag"] = etag
        last_seq = (
            execution.output_parts_for(field).order_by("-seq").values_list("seq", flat=True).first()
        )
        # Lets the widget render a replay progress bar (loaded / total parts).
        response.headers["X-Dar-Total-Parts"] = str(last_seq + 1 if last_seq is not None else 0)
        if last_seq is not None and seq < last_seq:
            # Sealed part: immutable, cacheable for a year.
            response.headers["Cache-Control"] = "private, max-age=31536000, immutable"
        else:
            # Active part: content may still grow.
            response.headers["Cache-Control"] = "no-cache"
        return response

    def _render_output_context(self, request, execution, title, *, fit: bool = False):
        """Build context shared by stdout/stderr/result views."""
        change_url = reverse(
            "admin:django_admin_runner_commandexecution_change",
            args=[execution.pk],
        )
        ctx = self._terminal_context(
            "admin:django_admin_runner_commandexecution_output",
            execution.pk,
            fit=fit,
        )
        return {
            **self.admin_site.each_context(request),
            "title": title,
            "execution": execution,
            "change_url": change_url,
            "dar_status": execution.status,
            "has_stderr": execution.has_output("stderr"),
            "has_stdout": execution.has_output("stdout"),
            "opts": self.model._meta,
            "is_unfold": is_unfold_installed(),
            **self._stop_context(request, execution),
            **ctx,
        }

    def _rerun_initial(
        self,
        request,
        command_name: str,
        form_class: type[forms.Form],
    ) -> dict:
        """Initial form data from ``?rerun=<pk>`` (empty when unavailable).

        The referenced execution is looked up through the permission-
        restricted queryset and must belong to the same command.
        """
        rerun_pk = request.GET.get("rerun", "")
        if not rerun_pk:
            return {}
        execution = self.get_queryset(request).filter(pk=rerun_pk).first()
        if execution is None or execution.command_name != command_name:
            return {}
        return self._initial_from_kwargs(form_class, execution.kwargs or {})

    def _command_run_view(self, request, command_name: str):
        if command_name not in _registry:
            raise Http404(f"Command '{command_name}' is not registered.")

        entry = _registry[command_name]
        if not has_permission(request.user, entry):
            return HttpResponseForbidden(b"You do not have permission to run this command.")

        FormClass = form_from_command(command_name)

        if request.method == "POST":
            form = FormClass(request.POST, request.FILES)
            if form.is_valid():
                kwargs = {}
                for k, v in form.cleaned_data.items():
                    if isinstance(v, bool):
                        kwargs[k] = v  # always include booleans (True and False)
                    elif v not in ("", None):
                        kwargs[k] = v  # exclude empty strings and None
                execution = CommandExecution.objects.create(
                    command_name=command_name,
                    kwargs=kwargs,
                    triggered_by=request.user,
                    label=request.POST.get("dar_label", "").strip()[:200],
                )
                runner = get_runner()
                result = runner.run(command_name, kwargs, request.user, execution)
                return redirect(result.redirect_url)
        else:
            form = FormClass(initial=self._rerun_initial(request, command_name, FormClass))

        context = {
            **self.admin_site.each_context(request),
            "title": f"Run: {command_name}",
            "form": form,
            "command_name": command_name,
            "entry": entry,
            "opts": self.model._meta,
            "is_unfold": is_unfold_installed(),
            "add_schedule_url": (
                reverse(
                    "admin:django_admin_runner_scheduledcommand_add_for_command",
                    args=[command_name],
                )
                if _supported_schedule_kinds()
                else ""
            ),
        }
        return render(request, get_template("run"), context)


@admin.register(CommandOutputPart)
class CommandOutputPartAdmin(_ModelAdminBase):  # type: ignore[misc]
    """Read-only admin for the raw output parts (debugging/inspection)."""

    list_display = ["execution", "field", "seq", "length"]
    list_filter = ["field"]
    search_fields = ["execution__command_name"]
    ordering = ["execution", "field", "seq"]

    @admin.display(description="Length")
    def length(self, obj: CommandOutputPart) -> int:
        return len(str(obj.text))

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


# ---------------------------------------------------------------------------
# ScheduledCommand admin (schedules overview + create/change/delete)
# ---------------------------------------------------------------------------


class ScheduleForm(forms.ModelForm):
    """Model form for ``ScheduledCommand`` with a dynamic kind picker.

    The admin injects the command's argparse-generated parameter fields as
    extra (non-model) declared fields; ``_post_clean`` folds them into
    ``instance.kwargs`` before model validation runs, so stale kwargs are
    rejected on every save.
    """

    _param_fields: dict[str, str] = {}  # form field name -> kwargs key
    _schedule_command_name: str = ""

    class Meta:
        model = ScheduledCommand
        fields = ["label", "kind", "cron", "interval_minutes", "repeats", "run_at", "enabled"]

    def __init__(self, *args, supported_kinds=None, **kwargs):
        super().__init__(*args, **kwargs)
        kinds = sorted(supported_kinds or _supported_schedule_kinds())
        if not kinds:
            kinds = [ScheduledCommand.Kind.CRON]
        self.fields["kind"].choices = [(kind, ScheduledCommand.Kind(kind).label) for kind in kinds]
        if len(kinds) == 1:
            self.fields["kind"].initial = kinds[0]
        self.fields["cron"].help_text = mark_safe(
            "Five-field cron expression (min hour day month weekday) — "
            'see <a href="https://crontab.guru" target="_blank" rel="noopener">'
            "crontab.guru</a> for examples."
        )
        self.fields["interval_minutes"].help_text = "Minutes between runs."
        self.fields["repeats"].help_text = "Number of runs (empty = run forever)."
        # Datetime chooser: Unfold's date/time pickers when available, the
        # browser-native datetime picker otherwise.
        if is_unfold_installed():
            try:
                from unfold.widgets import UnfoldAdminSplitDateTimeWidget

                self.fields["run_at"] = forms.SplitDateTimeField(
                    required=False,
                    widget=UnfoldAdminSplitDateTimeWidget(),
                )
            except ImportError:
                pass
        if "run_at" not in self.fields or not isinstance(
            self.fields["run_at"].widget, forms.MultiWidget
        ):
            self.fields["run_at"] = forms.DateTimeField(
                required=False,
                input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"],
                widget=forms.DateTimeInput(
                    attrs={"type": "datetime-local"},
                    format="%Y-%m-%dT%H:%M",
                ),
            )
        self._apply_theme_widgets()

    def _apply_theme_widgets(self) -> None:
        """Swap the plain model-form widgets for theme-styled ones (Unfold)."""
        if not is_unfold_installed():
            return
        try:
            from unfold.widgets import (
                UnfoldAdminIntegerFieldWidget,
                UnfoldAdminSelectWidget,
                UnfoldAdminTextInputWidget,
                UnfoldBooleanWidget,
            )
        except ImportError:
            return
        widgets = {
            "label": UnfoldAdminTextInputWidget(),
            "cron": UnfoldAdminTextInputWidget(),
            "interval_minutes": UnfoldAdminIntegerFieldWidget(),
            "repeats": UnfoldAdminIntegerFieldWidget(),
            "kind": UnfoldAdminSelectWidget(),
            "enabled": UnfoldBooleanWidget(),
        }
        for name, widget in widgets.items():
            if name in self.fields:
                self.fields[name].widget = widget
        if "kind" in self.fields:
            # Re-sync choices after the widget swap (fresh Select instance).
            self.fields["kind"].choices = self.fields["kind"].choices

    def _post_clean(self) -> None:
        # "Add schedule" flow: the command comes from the URL, not the form.
        if not self.instance.command_name and self._schedule_command_name:
            self.instance.command_name = self._schedule_command_name
        kwargs: dict = {}
        for form_name, key in self._param_fields.items():
            if form_name not in self.cleaned_data:
                continue
            value = self.cleaned_data[form_name]
            if isinstance(value, bool):
                kwargs[key] = value  # always include booleans (True and False)
            elif value not in ("", None):
                kwargs[key] = value
        self.instance.kwargs = kwargs
        super()._post_clean()
        # Default the label to the command's display name (e.g.
        # ``cleanup_books`` → "Cleanup Books").  Runs after super() because
        # construct_instance overwrites instance fields from cleaned_data.
        if not (self.instance.label or "").strip():
            entry = _registry.get(self.instance.command_name or "")
            if entry:
                self.instance.label = entry["display_name"]

    def _update_errors(self, errors):
        """Map model-validation errors for non-form fields to non-field errors.

        ``ScheduledCommand.clean()`` reports problems under ``command_name``
        and ``kwargs`` — neither is a (editable) form field here, and
        ``add_error`` would raise ``ValueError`` for unknown field names.
        """
        from django.core.exceptions import NON_FIELD_ERRORS, ValidationError

        if hasattr(errors, "error_dict"):
            remapped: dict = {}
            for field, messages in errors.error_dict.items():
                key = (
                    field if field in self.fields or field == NON_FIELD_ERRORS else NON_FIELD_ERRORS
                )
                remapped.setdefault(key, [])
                remapped[key].extend(messages)
            errors = ValidationError(remapped)
        super()._update_errors(errors)


class ScheduleCommandListFilter(admin.SimpleListFilter):
    title = "command"
    parameter_name = "command_name"

    def lookups(self, request, model_admin):
        values = (
            ScheduledCommand.objects.order_by("command_name")
            .values_list("command_name", flat=True)
            .distinct()
        )
        return [(name, name) for name in values]

    def queryset(self, request, queryset):
        value = self.value()
        return queryset.filter(command_name=value) if value else queryset


@admin.register(ScheduledCommand)
class ScheduledCommandAdmin(_ModelAdminBase):  # type: ignore[misc]
    change_form_template = "admin/django_admin_runner/scheduledcommand/change_form.html"

    list_display = [
        "label",
        "command_name",
        "kind",
        "schedule_summary_display",
        "enabled_display",
        "next_run",
        "last_run_display",
    ]
    list_filter = [ScheduleCommandListFilter, "enabled", "source"]
    search_fields = ["label", "command_name"]
    ordering = ["command_name", "label"]
    readonly_fields = ["command_name", "source", "created_at", "updated_at"]

    class Media:
        js = ("django_admin_runner/schedule-form.js",)
        css = {"all": ("django_admin_runner/status-badges.css",)}

    def get_queryset(self, request):
        from django.db.models import OuterRef, Subquery

        from .models import CommandExecution

        last_execution = CommandExecution.objects.filter(schedule_id=OuterRef("pk")).order_by(
            "-created_at"
        )
        return (
            super()
            .get_queryset(request)
            .annotate(
                last_status=Subquery(last_execution.values("status")[:1]),
                last_run_at=Subquery(last_execution.values("created_at")[:1]),
            )
        )

    # ------------------------------------------------------------------
    # Combined parameter + schedule form
    # ------------------------------------------------------------------

    _MODEL_FORM_FIELDS = frozenset(ScheduleForm.Meta.fields)

    # Model form fields plus readonly fields: parameter dests clashing with
    # any of these are rendered as ``param_<name>`` to avoid being shadowed
    # (e.g. an ``--source`` parameter vs. the readonly ``source`` field).
    _RESERVED_FORM_NAMES = _MODEL_FORM_FIELDS | {
        "command_name",
        "source",
        "created_at",
        "updated_at",
    }

    # Per-request state for the "Add schedule" flow (no instance exists yet):
    # kept thread-local so concurrent requests cannot cross wires.
    _state = threading.local()

    @property
    def _current_command_name(self) -> str:
        return getattr(self._state, "command_name", "")

    @_current_command_name.setter
    def _current_command_name(self, value: str) -> None:
        self._state.command_name = value

    def get_form(self, request, obj=None, change=False, **kwargs):
        command_name = obj.command_name if obj is not None else self._current_command_name
        stored_kwargs = (obj.kwargs or {}) if obj is not None else {}
        # "Add schedule" opened from the run page carries the parameters the
        # user already filled in as query parameters — use them as initial.
        query_initial = request.GET if obj is None else {}
        param_fields: dict[str, forms.Field] = {}
        param_map: dict[str, str] = {}
        if command_name:
            ParamForm = form_from_command(command_name)
            for name, field in ParamForm.base_fields.items():
                if name in self._RESERVED_FORM_NAMES:
                    # Name clash with a model/readonly form field — render the
                    # parameter under a prefixed name and map it back on save.
                    form_name = f"param_{name}"
                else:
                    form_name = name
                field = copy.copy(field)
                value = stored_kwargs.get(name)
                if value is None and name in query_initial:
                    value = query_initial.get(name)
                if value is not None:
                    if isinstance(field, forms.MultipleChoiceField) and isinstance(value, str):
                        value = [item for item in re.split(r"[,\s]+", value) if item]
                    field.initial = value
                param_fields[form_name] = field
                param_map[form_name] = name
        attrs = {
            "_param_fields": param_map,
            "_schedule_command_name": command_name,
            "supported_kinds": sorted(_supported_schedule_kinds()),
            **param_fields,
        }
        return type("ScheduledCommandForm", (ScheduleForm,), attrs)

    def get_fieldsets(self, request, obj=None):
        command_name = obj.command_name if obj is not None else self._current_command_name
        param_fields = (
            [
                f"param_{name}" if name in self._RESERVED_FORM_NAMES else name
                for name in form_from_command(command_name).base_fields
            ]
            if command_name
            else []
        )
        fieldsets = []
        if param_fields:
            fieldsets.append(("Parameters", {"classes": ["tab"], "fields": param_fields}))
        fieldsets.append(
            (
                "Schedule",
                {
                    "classes": ["tab"],
                    "fields": [
                        "command_name",
                        "source",
                        "label",
                        "kind",
                        "cron",
                        "interval_minutes",
                        "repeats",
                        "run_at",
                        "enabled",
                        "created_at",
                        "updated_at",
                    ],
                },
            ),
        )
        return fieldsets

    def render_change_form(self, request, context, **kwargs):
        context["dar_is_unfold"] = is_unfold_installed()
        return super().render_change_form(request, context, **kwargs)

    # ------------------------------------------------------------------
    # Save / delete — keep the native backend object in sync
    # ------------------------------------------------------------------

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        materialize_schedule(obj)

    def delete_model(self, request, obj):
        remove_native_schedule(obj)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            remove_native_schedule(obj)
        super().delete_queryset(request, queryset)

    # ------------------------------------------------------------------
    # Changelist display
    # ------------------------------------------------------------------

    @admin.display(description="Schedule")
    def schedule_summary_display(self, obj: ScheduledCommand) -> str:
        return obj.schedule_summary()

    @admin.display(description="Enabled", ordering="enabled", boolean=True)
    def enabled_display(self, obj: ScheduledCommand) -> bool:
        return bool(obj.enabled)

    @admin.display(description="Next run")
    def next_run(self, obj: ScheduledCommand) -> str:
        if not obj.enabled:
            return "—"
        try:
            value = get_runner().schedule_next_run(obj)
        except Exception:  # noqa: BLE001
            return "—"
        if not value:
            return "—"
        # Locale-formatted (e.g. "Sept. 11, 2026, 9:26 p.m." for en-us,
        # "11.09.2026 21:26" for de) in the project timezone, instead of
        # the raw datetime repr.
        from django.utils.formats import localize
        from django.utils.timezone import localtime

        return localize(localtime(value))

    @admin.display(description="Last run")
    def last_run_display(self, obj: ScheduledCommand) -> SafeString:
        """Last *scheduled* execution: status icon + relative time, linking
        to the results filtered on this schedule."""
        status = getattr(obj, "last_status", None)
        last_run_at = getattr(obj, "last_run_at", None)
        if not status or not last_run_at:
            return cast(SafeString, mark_safe('<span style="opacity:.4;">—</span>'))
        from django.utils.timesince import timesince

        label = CommandExecution.Status(str(status)).label
        url = (
            reverse("admin:django_admin_runner_commandexecution_changelist") + f"?schedule={obj.pk}"
        )
        title = f"{label}, {timesince(last_run_at)} ago"
        return cast(
            SafeString,
            mark_safe(
                f'<a href="{url}" title="{title}" '
                f'style="text-decoration:none;">{_status_icon(str(status))}</a>'
            ),
        )

    def has_add_permission(self, request):
        # Schedules are added through the per-command "Add schedule" action
        # only — the plain admin "Add" button stays hidden.
        return bool(self._current_command_name)

    # ------------------------------------------------------------------
    # "Add schedule" creation view (argparse parameters + schedule section)
    # ------------------------------------------------------------------

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "add/<str:command_name>/",
                self.admin_site.admin_view(self._schedule_add_view),
                name="django_admin_runner_scheduledcommand_add_for_command",
            ),
        ]
        return custom + urls

    def _schedule_add_view(self, request, command_name: str):
        if command_name not in _registry:
            raise Http404(f"Command '{command_name}' is not registered.")
        entry = _registry[command_name]
        if not has_permission(request.user, entry):
            return HttpResponseForbidden(b"You do not have permission to schedule this command.")
        if not _supported_schedule_kinds():
            return HttpResponseForbidden(b"The active runner does not support schedules.")

        # Route through the standard ModelAdmin add machinery so the page
        # renders with native admin / Unfold styling and the same
        # Parameters / Schedule tabs as the change view.
        self._current_command_name = command_name
        try:
            return self.add_view(
                request,
                extra_context={"title": f"Add schedule: {entry['display_name']}"},
            )
        finally:
            self._current_command_name = ""
