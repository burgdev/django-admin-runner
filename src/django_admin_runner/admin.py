from __future__ import annotations

from typing import TYPE_CHECKING, cast

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
from .models import CommandExecution, CommandOutputPart, RegisteredCommand
from .registry import _registry, has_permission
from .runners import get_runner
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


@admin.register(RegisteredCommand)
class RegisteredCommandAdmin(_ModelAdminBase):  # type: ignore[misc]
    list_display = [
        "name_link",
        "group",
        "active",
        "updated_at",
        "buttons",
    ]
    list_display_links = None
    search_fields = ["name", "display_name"]
    list_filter = [ActiveListFilter, "group"]
    ordering = ["group", "name"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def changelist_view(self, request, extra_context=None):
        # Default the active filter to "Yes" when no active param is present
        if "active" not in request.GET:
            qp = request.GET.copy()
            qp["active"] = "1"
            return redirect(f"{request.path}?{qp.urlencode()}")
        return super().changelist_view(request, extra_context=extra_context)

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

    @admin.display(description="")
    def buttons(self, obj: RegisteredCommand) -> SafeString:
        parts: list[str] = []
        if obj.active:
            run_url = reverse("admin:django_admin_runner_command_run", args=[obj.name])
            parts.append(
                f'<a href="{run_url}" '
                f'style="display:inline-block;padding:4px 10px;border-radius:4px;'
                f"font-size:11px;font-weight:600;color:#fff;"
                f'background:#28a745;text-decoration:none;">Run</a>'
            )
        history_url = (
            reverse("admin:django_admin_runner_commandexecution_changelist")
            + f"?command_name={obj.name}"
        )
        parts.append(
            f'<a href="{history_url}" '
            f'style="display:inline-block;padding:4px 10px;border-radius:4px;'
            f"font-size:11px;font-weight:600;color:#fff;"
            f'background:#0d6efd;text-decoration:none;">History</a>'
        )
        return cast(SafeString, mark_safe(" ".join(parts)))


@admin.register(CommandExecution)
class CommandExecutionAdmin(_ModelAdminBase):  # type: ignore[misc]
    change_form_template = "admin/django_admin_runner/commandexecution/change_form.html"

    class Media:
        css = {
            "all": (
                "django_admin_runner/vendor/xterm/xterm.css",
                "django_admin_runner/ansi-output.css",
            )
        }
        js = (
            "django_admin_runner/vendor/xterm/xterm.js",
            "django_admin_runner/vendor/xterm/addon-webgl.js",
            "django_admin_runner/terminal-output.js",
        )

    list_display = [
        "command_name",
        "status",
        "triggered_by",
        "backend",
        "created_at",
        "result_button",
    ]
    # Avoid N+1 queries on the triggered_by foreign key in the change list.
    list_select_related = ("triggered_by",)
    list_filter = ["status", "backend"]
    search_fields = ["command_name", "triggered_by__username"]
    readonly_fields = [
        "command_name",
        "status",
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
            "Result",
            {
                "fields": ["result_html_display"],
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
        if not obj.has_output("stdout"):
            return cast(SafeString, mark_safe("<em>—</em>"))
        url = reverse(
            "admin:django_admin_runner_commandexecution_stdout",
            args=[obj.pk],
        )
        html = f'{_terminal_placeholder("stdout")}<p><a href="{url}">Full View</a></p>'
        return cast(SafeString, mark_safe(html))

    @admin.display(description="Standard error / traceback")
    def stderr_display(self, obj: CommandExecution) -> SafeString:
        if not obj.has_output("stderr"):
            return cast(SafeString, mark_safe("<em>—</em>"))
        url = reverse(
            "admin:django_admin_runner_commandexecution_stderr",
            args=[obj.pk],
        )
        html = f'{_terminal_placeholder("stderr")}<p><a href="{url}">Full View</a></p>'
        return cast(SafeString, mark_safe(html))

    @admin.display(description="Result")
    def result_html_display(self, obj: CommandExecution) -> SafeString:
        if not obj.result_html:
            return cast(SafeString, mark_safe("<em>—</em>"))
        result_url = reverse(
            "admin:django_admin_runner_commandexecution_result",
            args=[obj.pk],
        )
        html = (
            f'<div style="max-height:300px;overflow:auto;border:1px solid #ddd;'
            f'padding:8px;border-radius:4px;margin-bottom:8px;">'
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
            url = reverse(
                "admin:django_admin_runner_commandexecution_stdout",
                args=[obj.pk],
            )
            buttons.append(
                f'<a href="{url}" '
                f'style="display:inline-block;padding:4px 10px;border-radius:4px;'
                f"font-size:11px;font-weight:600;color:#fff;"
                f'background:#0d6efd;text-decoration:none;margin-right:4px;"'
                f">Stdout</a>"
            )
        if getattr(obj, "has_stderr", False) or obj.has_output("stderr"):
            url = reverse(
                "admin:django_admin_runner_commandexecution_stderr",
                args=[obj.pk],
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
        extra_context = extra_context or {}
        extra_context.update(
            self._terminal_context("admin:django_admin_runner_commandexecution_output", object_id)
        )
        return super().change_view(request, object_id, form_url, extra_context)

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

    def _terminal_context(self, url_name: str, object_id) -> dict:
        """Context needed by the terminal widget (config JSON in templates)."""
        from .models import CommandExecution

        execution = CommandExecution.objects.filter(pk=object_id).first()
        cols, rows = _terminal_size()
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
            }
        )

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

        etag = f'"{execution.pk}:{field}:{seq}"'
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

    def _render_output_context(self, request, execution, title):
        """Build context shared by stdout/stderr/result views."""
        change_url = reverse(
            "admin:django_admin_runner_commandexecution_change",
            args=[execution.pk],
        )
        ctx = self._terminal_context(
            "admin:django_admin_runner_commandexecution_output", execution.pk
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
            **ctx,
        }

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
