"""Custom admin for django-q2 models using the Unfold theme.

Unregisters django-q2's default ``ModelAdmin`` subclasses and replaces them
with Unfold-styled versions. The Schedule admin is further customized to show
a dropdown of registered management commands instead of a plain text input
for the ``func`` field.

References:
- https://unfoldadmin.com/docs/installation/auth/
"""

from django.contrib import admin
from django_q.admin import FailAdmin as QFailAdmin
from django_q.admin import QueueAdmin as QQueueAdmin
from django_q.admin import ScheduleAdmin as QScheduleAdmin
from django_q.admin import TaskAdmin as QTaskAdmin
from django_q.models import Failure, OrmQ, Schedule, Success
from unfold.admin import ModelAdmin
from unfold.widgets import UnfoldAdminSelectWidget, UnfoldAdminTextInputWidget

# ---------------------------------------------------------------------------
# Unregister django-q2's default admins
# ---------------------------------------------------------------------------

for _model in [Schedule, Success, Failure, OrmQ]:
    admin.site.unregister(_model)


# ---------------------------------------------------------------------------
# Schedule admin with command dropdown
# ---------------------------------------------------------------------------


@admin.register(Schedule)
class CustomScheduleAdmin(QScheduleAdmin, ModelAdmin):
    """Schedule admin with a ``func`` dropdown listing registered commands."""

    fieldsets = (
        (
            None,
            {
                "fields": ("name", "func", "hook", "args", "kwargs"),
            },
        ),
        (
            "Schedule",
            {
                "fields": (
                    "schedule_type",
                    "minutes",
                    "cron",
                    "repeats",
                    "next_run",
                    "intended_date_kwarg",
                ),
            },
        ),
        (
            "Advanced",
            {
                "classes": ("collapse",),
                "fields": ("cluster",),
            },
        ),
    )

    conditional_fields = {
        "minutes": "schedule_type == 'I'",
        "cron": "schedule_type == 'C'",
    }

    def get_form(self, request, obj=None, **kwargs):
        from django_admin_runner.registry import _registry

        form_class = super().get_form(request, obj, **kwargs)

        # Build choices from the registry — blank option allows free-text entry
        choices = [("", "---------")]
        for cmd_name, entry in sorted(_registry.items()):
            choices.append(("django_admin_runner.tasks.execute_command", entry["display_name"]))

        # Replace func widget with Unfold-styled Select
        form_class.base_fields["func"].widget = UnfoldAdminSelectWidget(choices=choices)

        # Use Unfold-styled text input for args and kwargs
        form_class.base_fields["args"].widget = UnfoldAdminTextInputWidget()
        form_class.base_fields["kwargs"].widget = UnfoldAdminTextInputWidget()

        # Adjust field labels and help text for clarity
        form_class.base_fields["minutes"].label = "Interval (minutes)"
        form_class.base_fields[
            "minutes"
        ].help_text = "Only used when Schedule Type is set to Minutes"
        return form_class


# ---------------------------------------------------------------------------
# Remaining django-q2 models — Unfold-styled versions
# ---------------------------------------------------------------------------


@admin.register(Success)
class UnfoldSuccessAdmin(QTaskAdmin, ModelAdmin):
    pass


@admin.register(Failure)
class UnfoldFailureAdmin(QFailAdmin, ModelAdmin):
    pass


@admin.register(OrmQ)
class UnfoldQueueAdmin(QQueueAdmin, ModelAdmin):
    pass
