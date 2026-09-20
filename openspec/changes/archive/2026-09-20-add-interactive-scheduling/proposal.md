# Proposal: Interactive command scheduling

## Why

The library supports on-demand "Run" from the admin, but there is no way to schedule a registered command to run periodically (cron), at an interval, or once at a specific time. Downstream projects (e.g. wodore-backend) have built broken glue for this: django-q2's `Schedule.func` was pointed directly at `execute_command`, which cannot work for future runs because `execute_command(command_name, kwargs, execution_pk)` requires an already-created `CommandExecution` row. Scheduling should be a first-class, backend-abstracted library capability.

## What Changes

- Add a schedule-safe task `run_scheduled_command(command_name, kwargs)` that creates the `CommandExecution` row at run time and delegates to `execute_command`. Scheduled runs have no triggering user; `triggered_by` stays nullable (or records a schedule label).
- Add a library-owned `ScheduledCommand` model as the source of truth: command name, optional label, enabled flag, schedule kind (`cron` | `interval` | `clocked`), kind-specific fields (cron expression, interval minutes, run-at datetime), validated `kwargs` (JSON), and a `backend_schedule_key` referencing the materialized native schedule object.
- Extend the runner abstraction with schedule capabilities:
  - `supported_schedule_kinds: frozenset[str]` (django-q2: all three kinds; Celery: all three; django-tasks: none).
  - `create_schedule(sched)`, `update_schedule(sched)`, `delete_schedule(sched)` materializing the library row into the backend's native objects (django-q2 `Schedule` first).
- Admin UX (works with both native Django admin and Unfold):
  - "Add schedule" action next to "Run" on the command page, offering only the schedule kinds supported by the active runner; the schedule form updates dynamically when the type is selected.
  - Schedule creation page combines the command's existing argparse-generated parameter form with a schedule section.
  - `ScheduledCommand` change view with two tabs — Parameters and Schedule — plus Save and Delete; saving re-materializes the native backend object, deleting removes it.
  - Disabling a schedule (`enabled=False`) stops it from running but keeps the row in the DB.
  - Command overview gains a "Schedules" button per command that has schedules, plus a global Schedules overview listing all schedules.
  - Multiple schedules per command are supported.
- Declarative schedules in code: `@register_command(schedule=Schedule | Sequence[Schedule])` with kind subclasses (`CronSchedule`, `IntervalSchedule`, `ClockedSchedule`) carrying `name`, `kwargs`, and initial `enabled` — the startup sync materializes declared defaults (registry wins for the spec, DB wins for `enabled`; multiple schedules per command allowed, identified by name), admin-created schedules are never touched.
- Update the examples (`classic`, `unfold_celery`, `unfold_django_q2`, `unfold_rq`) to exercise the new scheduling UI where the backend supports it.

## Capabilities

### New Capabilities
- `scheduled-command-model`: Library-owned `ScheduledCommand` model storing schedule definitions independent of the task backend, with enabled/label, kind-specific schedule fields, validated kwargs, and a backend schedule key.
- `schedule-materialization`: Runner-level capability set and CRUD API that translates `ScheduledCommand` rows into native backend schedule objects (django-q2 `Schedule`, Celery beat entries), kept in sync on save/update/delete.
- `scheduled-task-entrypoint`: Schedule-safe task entry point that creates the `CommandExecution` at run time and reuses `execute_command`, including handling for the missing triggering user.
- `schedule-admin-ui`: Interactive admin flow in both themes (native + Unfold) — "Add schedule" action with dynamic type-dependent form, combined parameter + schedule form, change view with Parameters/Schedule tabs, save/delete, enable/disable without deletion, per-command "Schedules" button, and a global schedules overview.
- `declarative-schedules`: `cron`/`interval_minutes`/`schedule_kwargs` on `@register_command`, materialized by the startup sync with registry-wins-for-spec, DB-wins-for-enabled semantics.

### Modified Capabilities
- `per-command-tasks`: The run-now flow is unchanged, but the command page gains an additional "Add schedule" action alongside "Run".

## Impact

- **Code**: new `schedules.py` (or models additions) + migration, `tasks.py` (new wrapper), runner base class and `runners/django_q2.py` (+ later Celery), `admin.py` and templates (schedule forms/views/tabs), registry unchanged.
- **Downstream**: wodore-backend can delete its broken `CustomScheduleAdmin` and django-q Schedule glue once this lands.
- **Dependencies**: none new; django-q2/Celery usage only where already optional extras.
- **Examples**: README/example projects updated with scheduling demos.
- **Migration**: one new app migration for `ScheduledCommand`; no changes to existing models except making `CommandExecution.triggered_by` nullable if it is not already.
