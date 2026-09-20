# Scheduling

Registered commands can be scheduled — periodically (cron expression or
fixed interval) or once at a specific time. Schedules are
backend-abstracted: the library owns the schedule rows
(`ScheduledCommand`) and materializes them into the active runner's
native periodic-task system.

| Runner | Schedule kinds |
|---|---|
| `django-q2` | cron, interval, one-off |
| `celery`, `django` (tasks), `sync`, `rq` | not supported (action hidden) |

## Interactive (admin UI)

When the active runner supports scheduling, an **Add schedule** action
appears next to **Run** on the command pages. The creation form combines
the command's argparse-generated parameter form with a schedule section
(kind picker with dynamic fields, label, enabled toggle).

Existing schedules are edited in a change view with **Parameters** and
**Schedule** tabs; saving re-validates the kwargs against the command's
current definition (stale options surface an error, never run with wrong
args) and re-materializes the native backend schedule:

- **Disabling** keeps the row but stops runs (the native backend object
  is removed).
- **Enabling** re-creates it.
- **Deleting** removes both the row and the native object.

A global **Schedules** overview (`/admin/django_admin_runner/scheduledcommand/`)
lists every schedule with its kind, parameters, next run, and last run.

!!! note
    Interval schedules accept an optional *repeats* count (empty = run
    forever). Cron expressions are validated with
    [croniter](https://pypi.org/project/croniter/) when available.

## Declarative (in code)

Declare schedules directly on the decorator — they are materialized on
startup (in `AppConfig.ready()`) and kept in sync on every deploy:

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

A single declaration (not a list) may omit `name` — it defaults to the
command name. Lists must declare explicit, unique names.

### Sync semantics

- Identity is `(command_name, source=code, name)` — reordering a list
  never rewires schedules. Renaming an entry creates a new schedule;
  the removed declaration's row and native object are deleted.
- **The registry wins for the schedule spec** (kind, expression, kwargs):
  edits in code are picked up on the next startup.
- **The database wins for `enabled`** — admins can pause a declarative
  schedule without a deploy; the sync never flips it back on.
- Admin-created schedules (`source=admin`) are never touched by the sync.
- Schedules whose declaration (or command) is no longer registered are
  deleted along with their native backend object.

## Value objects

```python
from django_admin_runner import Schedule, CronSchedule, IntervalSchedule, ClockedSchedule
```

| Class | Arguments | Description |
|---|---|---|
| `CronSchedule` | `cron`, `name=`, `kwargs=`, `enabled=` | Run on a cron expression (five fields) |
| `IntervalSchedule` | `minutes`, `repeats=`, `name=`, `kwargs=`, `enabled=` | Run every *minutes* minutes, optionally limited to *repeats* runs |
| `ClockedSchedule` | `at`, `name=`, `kwargs=`, `enabled=` | Run once at a specific (aware) datetime — must be in the future |

All are frozen value objects; `kwargs` pre-fills the command's parameter
form and is validated against the command's current arguments. See the
[API reference](../api/schedules.md) for details.

## Scheduled runs

Scheduled executions appear in the regular results list with a schedule
filter, linked to their schedule row (and labelled from the schedule's
label). Overlapping runs are skipped — one execution per schedule at a
time: if the schedule's previous execution is still pending or running,
the new occurrence is not enqueued. Only recent executions (within
`ADMIN_RUNNER_STALE_AFTER`, default 1 h) block, so a stuck row cannot
starve the schedule forever.

Fired one-off (clocked) schedules are disabled afterwards — the row is
kept for the audit trail but will not run again.
