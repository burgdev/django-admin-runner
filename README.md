<h3 align="center"><b>django-admin-runner</b></h3>
<p align="center">
  <em>Run Django management commands from the admin — with auto-generated forms,
  pluggable task runners, and a unified execution log.</em>
</p>
<p align="center">
    <b><a href="https://burgdev.github.io/django-admin-runner">Documentation</a></b>
    | <b><a href="https://pypi.org/project/django-admin-runner">PyPI</a></b>
    | <b><a href="https://github.com/burgdev/django-admin-runner/blob/main/CHANGELOG.md">Changelog</a></b>
</p>

---

## Features

- **`@register_command` decorator** — register any management command with metadata
- **Auto-generated forms** — argparse arguments become Django form fields automatically
- **Pluggable runners** — Django Tasks (default), Celery, sync, or custom
- **Execution log** — every run is stored as a `CommandExecution` record
- **Permission control** — per-command permission requirements (superuser, Django perms, or a list)
- **Model attachment** — show a "Run" button on any model's admin change-list via `models=[...]`
- **Unfold support** — auto-detected, uses Unfold templates when available

## Installation

```bash
pip install django-admin-runner
```

Add to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    ...
    "django_admin_runner",
]
```

Run migrations:

```bash
python manage.py migrate
```

## Quick start

```python
# myapp/management/commands/my_command.py
from django.core.management.base import BaseCommand
from django_admin_runner import register_command

@register_command(group="Maintenance", permission="myapp.change_mymodel")
class Command(BaseCommand):
    help = "Does something useful"

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=10)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        self.stdout.write(f"Running {options['count']} times")
```

Visit `/admin/django_admin_runner/commandexecution/commands/` to run your commands.

## Development

**Requirements:** [uv](https://docs.astral.sh/uv/) and [just](https://github.com/casey/just)

```bash
# Install dependencies and pre-commit hooks
just install

# Run tests
just tests

# Run linters
just check

# Serve docs locally
just docs
```

## Contributing

Contributions are welcome! Please open an issue or pull request on
[GitHub](https://github.com/burgdev/django-admin-runner).

## License

MIT
