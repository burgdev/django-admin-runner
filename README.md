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
- **Widget & form customisation** — override widgets per-argument (`widget=` on `add_argument`), supply a custom `Form` class, or use per-parameter field overrides in the decorator
- **Built-in file fields** — `FileOrPathField` (upload or server path), `FileField`, `ImageField`
- **Pluggable runners** — Django Tasks (default), Celery, sync, or custom
- **Execution log** — every run is stored as a `CommandExecution` record
- **Permission control** — per-command permission requirements (superuser, Django perms, or a list)
- **Model attachment** — show a "Run" button on any model's admin change-list via `models=[...]`
- **Unfold support** — auto-detected, uses Unfold templates and widgets when available

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

### Custom widgets

Override how individual parameters render — right inside `add_arguments`:

```python
from django_admin_runner import FileOrPathField, register_command

@register_command(group="Import")
class Command(BaseCommand):
    def add_arguments(self, parser):
        # File upload OR server-side path text field
        parser.add_argument("--source", widget=FileOrPathField(), default="data.csv")
        # Swap to a textarea
        parser.add_argument("--notes", widget=forms.Textarea(attrs={"rows": 3}))
        # Image upload (requires Pillow)
        parser.add_argument("--photo", widget=forms.ImageField(required=False))
```

Or provide a fully custom form class:

```python
@register_command(form_class=MyImportForm)
class Command(BaseCommand):
    ...
```

See the [Widget & form customisation](https://burgdev.github.io/django-admin-runner/widgets/) docs for the full reference.

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
