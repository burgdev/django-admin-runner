# Example: Unfold + Celery

Unfold-themed admin with asynchronous command execution via Celery and Valkey
(Redis-compatible broker). Demonstrates `ADMIN_RUNNER_BACKEND = "celery"`,
Celery Beat scheduling, and the `FileOrPathField` widget.

## Prerequisites

- Docker (for Valkey)

## Setup & run

```bash
cd examples/unfold_celery
docker compose up -d   # start Valkey on port 6379
make init              # install deps, migrate, create superuser (root/root)
make run               # start Django dev server on port 8765
```

Open a second terminal for the Celery worker:

```bash
make worker            # start Celery worker
```

Optionally start Celery Beat for periodic task scheduling:

```bash
make beat              # start Beat scheduler (uses Django DB backend)
```

Visit <http://localhost:8765/admin/> (login: `root` / `root`) and navigate to
**Run Commands** in the sidebar.

## Available `make` targets

```
make          # show this help
make init     # install deps, migrate, create superuser
make run      # start Django dev server on port 8765
make worker   # start Celery worker
make beat     # start Celery Beat scheduler
```

## What's included

### Commands (`books` app)

| Command | Group | Description |
|---|---|---|
| `import_books` | Import | CSV import with `--source` (file upload **or** path), `--dry-run`, `--limit` |
| `export_report` | Export | Report export with `--format` choice (csv / json / xlsx) |
| `cleanup_books` | Maintenance | Removes stale records; `--older-than` threshold |

### `FileOrPathField` example

`import_books` demonstrates the combined file-upload + server-path widget.
The `--source` argument is registered with `widget=FileOrPathField()` directly
in `add_arguments`:

```python
from django_admin_runner import FileOrPathField, register_command

@register_command(group="Import", params=["source", "dry_run", "limit"])
class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            widget=FileOrPathField(),
            default="books.csv",
            help="Upload a file or enter a server-side path",
        )
        ...
```

A sample `books.csv` is included in this directory.

### Celery Beat periodic tasks

Per-command Celery tasks (`books.import_books`, `books.export_report`,
`books.cleanup_books`) are registered in `books/tasks.py` and appear
individually in the Celery Beat task selector under
**Periodic Tasks → Add periodic task**.

### Notes

- `CELERY_BROKER_URL` defaults to `redis://localhost:6379/0` and can be
  overridden via the environment variable of the same name.
- `django-celery-results` stores task results in Django's database
  (`CELERY_RESULT_BACKEND = "django-db"`).
- `django-celery-beat` provides database-backed periodic scheduling.
- If the broker is unreachable when submitting a command, the execution record
  is immediately marked `FAILED` with the error stored in stderr.
