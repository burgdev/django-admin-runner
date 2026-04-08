# Quickstart

## 1. Register a command

```python
# myapp/management/commands/send_reminders.py
from django.core.management.base import BaseCommand
from django_admin_runner import register_command


@register_command(group="Notifications", permission="myapp.change_reminder")
class Command(BaseCommand):
    help = "Send pending reminder emails"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Preview without sending")
        parser.add_argument("--limit", type=int, default=100, help="Max emails to send")

    def handle(self, *args, **options):
        self.stdout.write(f"Sending up to {options['limit']} reminders")
```

## 2. Run it from the admin

Navigate to `/admin/django_admin_runner/commandexecution/commands/` and click **send_reminders**.

A form is generated automatically from the `--dry-run` and `--limit` arguments.
Fill in the values and click **Run command**.

## 3. View execution history

All runs appear in `/admin/django_admin_runner/commandexecution/` with status,
stdout, stderr, backend used, timestamps, and the user who triggered the run.

## 4. Attach to a model's admin page

```python
from django.contrib import admin
from django_admin_runner.admin import CommandRunnerModelAdminMixin
from myapp.models import Reminder


@register_command(group="Notifications", models=[Reminder])
class Command(BaseCommand):
    ...


@admin.register(Reminder)
class ReminderAdmin(CommandRunnerModelAdminMixin, admin.ModelAdmin):
    ...
```

A **Run** link for `send_reminders` now appears on the Reminder change-list page.
