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
- **Stop running commands** — a "Stop" button (graceful, via the output
  heartbeat) that becomes "Force Stop" (hard kill) while the command keeps
  running; Celery uses `revoke(terminate=True)`, django-q2 signals the
  task's worker PID. Shown only while the execution is running.
- **Terminal output** — stdout/stderr render in an embedded xterm.js terminal
  (vendored, no CDN): progress bars display as in a real terminal. Output is
  stored as append-only 512 KB parts, so live updates cost only the new
  characters and arrive every 250 ms regardless of output size; a cursor-based
  delta endpoint transfers just the delta, sealed parts are served
  browser-cacheable (immutable), and retention is capped per field at 500 MB
  (`ADMIN_RUNNER_MAX_OUTPUT`) by pruning the oldest parts. Terminal size is
  configurable (`ADMIN_RUNNER_TERM_COLS`/`ADMIN_RUNNER_TERM_ROWS`, default
  120×40) and exported as `COLUMNS`/`LINES` so output layout is deterministic.
- **Permission control** — per-command permission requirements (superuser, Django perms, or a list)
- **Model attachment** — show a "Run" button on any model's admin change-list via `models=[...]`
- **Scheduling** — interactive "Add schedule" admin UI (cron / interval / one-off)
  and declarative `@register_command(schedule=…)` schedules, materialized into
  the backend's native periodic tasks (django-q2; see the
  [scheduling guide](https://burgdev.github.io/django-admin-runner/guides/scheduling/))
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

See the [Widget & form customisation](https://burgdev.github.io/django-admin-runner/guides/widgets/) docs for the full reference.

## Scheduling

Registered commands can be scheduled — periodically (cron expression or
fixed interval) or once at a specific time. Schedules are backend-abstracted:

| Runner | Schedule kinds |
|---|---|
| `django-q2` | cron, interval, one-off |
| `celery`, `django` (tasks), `sync`, `rq` | not supported (action hidden) |

### Interactive (admin UI)

When the active runner supports scheduling, an **Add schedule** action
appears next to **Run** on the command pages. The creation form combines the
command's argparse-generated parameter form with a schedule section (kind
picker with dynamic fields, label, enabled toggle). Existing schedules are
edited in a change view with **Parameters** and **Schedule** tabs; saving
re-validates the kwargs against the command's current definition (stale
options surface an error, never run with wrong args) and re-materializes the
native backend schedule. Disabling keeps the row but stops runs; deleting
removes both. A global **Schedules** overview lists every schedule with its
next run.

### Declarative (in code)

```python
from django_admin_runner import CronSchedule, IntervalSchedule, register_command

@register_command(
    group="Maintenance",
    schedule=[
        CronSchedule("0 3 * * *", name="nightly-full"),
        IntervalSchedule(15, name="quick-incremental", kwargs={"limit": 10}),
    ],
)
class Command(BaseCommand):
    ...
```

The startup sync materializes declarations as `source=code` schedule rows
keyed by `(command_name, name)` (a single declaration defaults its name to
the command name; lists require explicit unique names so reordering never
rewires schedules). The registry wins for the schedule spec, the database
wins for `enabled` — admins can pause a declarative schedule without a
deploy. Admin-created schedules are never touched by the sync.

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
