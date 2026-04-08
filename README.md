# django-admin-runner

Run Django management commands from the admin — with auto-generated forms,
pluggable task runners, and a unified execution log. Supports plain Django
admin and Unfold out of the box.

## Features

- **`@register_command` decorator** — register any management command with metadata
- **Auto-generated forms** — argparse arguments become Django form fields automatically
- **Pluggable runners** — Django Tasks (default), Celery, sync, or custom
- **Execution log** — every run is stored as a `CommandExecution` record
- **Permission control** — per-command permission requirements (superuser, Django perms, or a list)
- **Model attachment** — show a "Run" button on any model's admin change-list via `models=[...]`
- **Unfold support** — auto-detected, uses Unfold templates when available

## Quick start

```bash
pip install django-admin-runner
```

```python
# settings.py
INSTALLED_APPS = [
    ...
    "django_admin_runner",
]
```

```python
# myapp/management/commands/my_command.py
from django.core.management.base import BaseCommand
from django_admin_runner import register_command

@register_command(group="Maintenance", permission="myapp.change_mymodel")
class Command(BaseCommand):
    help = "Does something useful"

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=10)

    def handle(self, *args, **options):
        self.stdout.write(f"Running {options['count']} times")
```

Visit `/admin/django_admin_runner/commandexecution/commands/` to run your commands.

## Documentation

https://burgdev.github.io/django-admin-runner

## License

MIT
