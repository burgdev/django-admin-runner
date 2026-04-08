from __future__ import annotations

from typing import TYPE_CHECKING, cast

from django.contrib import admin
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.urls import path
from django.utils.safestring import SafeString, mark_safe

from ._ansi import ansi_to_html as _convert_ansi
from .admin_compat import get_model_admin_base, get_template, is_unfold_installed
from .forms import form_from_command
from .models import CommandExecution
from .registry import _registry, has_permission
from .runners import get_runner

if TYPE_CHECKING:
    from django.db import models as _models


def _ansi_to_html(text: str) -> SafeString:
    """Wrap ANSI-coded *text* in a themed ``<pre>`` block."""
    return cast(SafeString, mark_safe(f'<pre class="ansi-output">{_convert_ansi(text)}</pre>'))


# ---------------------------------------------------------------------------
# Mixin for model admins that want attached command run links
# ---------------------------------------------------------------------------


class CommandRunnerModelAdminMixin:
    """Mix into any ``ModelAdmin`` to show "Run" links for commands registered with
    ``models=[ThisModel]``.

    Example::

        from django_admin_runner.admin import CommandRunnerModelAdminMixin

        @admin.register(Book)
        class BookAdmin(CommandRunnerModelAdminMixin, admin.ModelAdmin):
            ...
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


@admin.register(CommandExecution)
class CommandExecutionAdmin(_ModelAdminBase):  # type: ignore[misc]
    class Media:
        css = {"all": ("django_admin_runner/ansi-output.css",)}

    list_display = ["command_name", "status", "triggered_by", "backend", "created_at"]
    list_filter = ["status", "backend"]
    search_fields = ["command_name", "triggered_by__username"]
    readonly_fields = [
        "command_name",
        "status",
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
            None,
            {
                "fields": [
                    "command_name",
                    "status",
                    "kwargs",
                    "triggered_by",
                    "backend",
                    "task_id",
                ]
            },
        ),
        (
            "Output",
            {
                "fields": ["stdout_display", "stderr_display"],
            },
        ),
        (
            "Timing",
            {
                "fields": ["created_at", "started_at", "finished_at"],
                "classes": ["collapse"],
            },
        ),
    ]
    ordering = ["-created_at"]

    @admin.display(description="Standard output")
    def stdout_display(self, obj: CommandExecution) -> SafeString:
        stdout = str(obj.stdout)
        return _ansi_to_html(stdout) if stdout else cast(SafeString, mark_safe("<em>—</em>"))

    @admin.display(description="Standard error / traceback")
    def stderr_display(self, obj: CommandExecution) -> SafeString:
        stderr = str(obj.stderr)
        return _ansi_to_html(stderr) if stderr else cast(SafeString, mark_safe("<em>—</em>"))

    def has_add_permission(self, request):
        return False

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.has_perm("django_admin_runner.view_all_executions"):
            return qs
        return qs.filter(triggered_by=request.user)

    # ------------------------------------------------------------------
    # Extra URLs: command list + run form
    # ------------------------------------------------------------------

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "commands/",
                self.admin_site.admin_view(self._command_list_view),
                name="django_admin_runner_command_list",
            ),
            path(
                "commands/<str:command_name>/run/",
                self.admin_site.admin_view(self._command_run_view),
                name="django_admin_runner_command_run",
            ),
        ]
        return custom + urls

    def _command_list_view(self, request):
        visible = [entry for entry in _registry.values() if has_permission(request.user, entry)]
        grouped: dict[str, list] = {}
        for entry in sorted(visible, key=lambda e: (e["group"], e["name"])):
            grouped.setdefault(entry["group"], []).append(entry)

        context = {
            **self.admin_site.each_context(request),
            "title": "Run Management Commands",
            "grouped_commands": grouped,
            "opts": self.model._meta,
        }
        return render(request, get_template("list"), context)

    def _command_run_view(self, request, command_name: str):
        if command_name not in _registry:
            raise Http404(f"Command '{command_name}' is not registered.")

        entry = _registry[command_name]
        if not has_permission(request.user, entry):
            return HttpResponseForbidden(b"You do not have permission to run this command.")

        FormClass = form_from_command(command_name)

        if request.method == "POST":
            form = FormClass(request.POST)
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
                )
                runner = get_runner()
                result = runner.run(command_name, kwargs, request.user, execution)
                return redirect(result.redirect_url)
        else:
            form = FormClass()

        context = {
            **self.admin_site.each_context(request),
            "title": f"Run: {command_name}",
            "form": form,
            "command_name": command_name,
            "entry": entry,
            "opts": self.model._meta,
            "is_unfold": is_unfold_installed(),
        }
        return render(request, get_template("run"), context)
