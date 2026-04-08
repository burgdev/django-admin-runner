# django-admin-runner

Run Django management commands from the admin — with auto-generated forms,
pluggable task runners, and a unified execution log.

## Features

- **`@register_command` decorator** — register any management command with metadata
- **Auto-generated forms** — argparse arguments become Django form fields automatically
- **Pluggable runners** — Django Tasks (default), Celery, sync, or your own custom runner
- **Execution log** — every run is stored as a `CommandExecution` record with full audit trail
- **Permission control** — per-command permission requirements (`"superuser"`, Django perm strings, or a list)
- **Model attachment** — show a "Run" button on any model's admin change-list via `models=[...]`
- **Unfold support** — auto-detected; uses Unfold templates when installed

## Quick navigation

- [Installation](installation.md)
- [Quickstart](quickstart.md)
- [Decorator reference](decorator.md)
- [Runners](runners.md)
- [Custom runners](custom-runner.md)
- [Admin themes](admin-themes.md)
