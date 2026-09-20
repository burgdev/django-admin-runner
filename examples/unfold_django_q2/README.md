# Example: Unfold + Django-Q2

Unfold-themed admin with asynchronous command execution via Django-Q2 and the
Django ORM broker. No Docker, no Redis — just the database.

## Setup & run

```bash
cd examples/unfold_django_q2
make init    # install deps, migrate, create superuser (root/root)
make run     # start Django dev server on port 8766
```

Open a second terminal for the Q2 worker:

```bash
make worker  # start qcluster
```

Visit <http://localhost:8766/admin/> (login: `root` / `root`) and navigate to
**Run Commands** in the sidebar.

## Available `make` targets

```
make          # show this help
make init     # install deps, migrate, create superuser
make run      # start Django dev server on port 8766
make worker   # start django-q2 worker (qcluster)
```

## What's included

### Commands (`books` app)

| Command | Group | Description |
|---|---|---|
| `import_books` | Import | CSV import with `--source`, `--dry-run`, `--limit` |
| `export_report` | Export | Report export with `--format` choice (csv / json / xlsx) |
| `cleanup_books` | Maintenance | Removes stale records; `--older-than` threshold |
| `simulate_workload` | Maintenance | Long-running simulation with live rich progress bars; `--minutes`, `--bars` |

### Scheduling commands

Two ways to schedule commands (django-q2 supports all three kinds — cron,
interval, and one-off):

- **Interactive**: click **Add schedule** next to a command in the overview
  (or on the run page). The form combines the command's parameter form with
  a schedule section — pick a kind, fill the kind-specific fields, and save.
  Existing schedules can be edited (Parameters / Schedule tabs), disabled
  (the native q2 schedule is removed, the row is kept) or deleted. The
  global **Schedules** overview lists all schedules with their next run.
- **Declarative**: `cleanup_books` declares a nightly cron schedule in code:

  ```python
  @register_command(
      group="Maintenance",
      schedule=CronSchedule("0 3 * * *", kwargs={"older-than": 90}),
  )
  class Command(BaseCommand): ...
  ```

  The startup sync materializes it as a `source=code` schedule — the code
  wins for the schedule spec, the database wins for the enabled flag, so
  admins can pause it without a deploy.

### Notes

- The ORM broker (`Q_CLUSTER = {'name': 'DJANGORM', 'orm': 'default'}`) uses
  database polling — no external services required. For higher throughput,
  switch to the Redis broker by changing `Q_CLUSTER` config.
- `ADMIN_RUNNER_BACKEND = "django-q2"` enqueues commands via `async_task`.
- If the task cluster is down when submitting a command, the execution record
  is immediately marked `FAILED` with the error stored in stderr.
