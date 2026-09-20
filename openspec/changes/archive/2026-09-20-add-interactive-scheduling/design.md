# Design: Interactive command scheduling

## Context

`django-admin-runner` registers management commands and runs them on demand from the admin via backend runners (`sync`, `django-q2`, `celery`, `django-tasks`, `rq`). The run-now flow always creates a `CommandExecution` row *before* enqueueing `execute_command(command_name, kwargs, execution_pk)`. There is no scheduling capability; the `execute_command` signature is fundamentally incompatible with future runs because the execution row (and its pk) cannot exist ahead of time. Downstream projects have attempted to bridge this with django-q2 `Schedule` rows pointing at `execute_command`, which cannot work.

The command run form is generated from each command's argparse definition (`forms.py`), giving typed parameter widgets — schedules should reuse this rather than exposing raw args/kwargs JSON.

## Goals / Non-Goals

**Goals:**
- Backend-abstracted, interactive scheduling of registered commands from the admin.
- Multiple schedules per command; create, edit (parameters and schedule), enable/disable, delete.
- Native parameter forms on schedule pages (reuse the argparse-driven run form).
- Library-owned source of truth so schedules survive backend switches and can be re-materialized.
- Kind capability reporting per runner so the UI only offers what the backend supports.

**Non-Goals:**
- Two-way sync of backend-native schedule edits back into the library model (backend objects are an implementation detail).
- Solar calendars, watch files, or schedule dependencies/chains.
- django-tasks support (no native periodic tasks) — it simply reports no supported kinds.

## Decisions

### 1. Library-owned `ScheduledCommand` model as source of truth
Fields: `command_name`, `name` (optional label), `enabled`, `kind` (`cron` | `interval` | `clocked`), `cron`, `interval_minutes`, `run_at` (UTC), `kwargs` (JSON), `backend_schedule_key` (char, backend-specific reference), `created_at`/`modified_at`.
*Alternative*: write directly to the backend-native model (django-q `Schedule`). Rejected: edits/deletes and backend portability become fragile, and the admin UI would need per-backend forms.

### 2. Materializer pattern on the runner
Runner API: `supported_schedule_kinds: frozenset[str]` plus `create_schedule(sched)`, `update_schedule(sched)`, `delete_schedule(sched)`. The model layer calls these on save/update/delete (from the admin and any programmatic API); runners materialize into native objects:
- django-q2: `Schedule(func="django_admin_runner.tasks.run_scheduled_command", args=[command_name, kwargs], schedule_type=C/I/O, ...)`; `backend_schedule_key` stores the native pk.
- Celery: `PeriodicTask` with `CrontabSchedule` / `IntervalSchedule` / `ClockedSchedule`.
- Others / sync / django-tasks: `supported_schedule_kinds = frozenset()`; admin hides the feature.
*Alternative*: separate methods per kind (`create_cron_schedule`, ...). Rejected: quadruples the API surface and the capability set already conveys support.

### 3. Schedule-safe entry point `run_scheduled_command(command_name, kwargs)`
Creates the `CommandExecution` (status PENDING) then calls `execute_command`. `triggered_by` is nullable; store the schedule label in the execution kwargs/trigger metadata so admins can trace runs back to a schedule. Runs are recorded exactly like run-now executions (live output, timeouts, failures).

### 4. Admin UX integrated into the existing command pages
- Works with **both themes** (native Django admin and Unfold); shared form/view logic with per-theme templates.
- "Add schedule" action next to "Run" on the command page; navigates to a creation page.
- Creation page: the existing argparse-generated parameter form plus a schedule section (kind picker limited to `supported_schedule_kinds`, kind-conditional fields, label, enabled). The form **updates dynamically** when the schedule type is selected (htmx or vanilla JS toggle of kind-conditional fields — same pattern as django-q's own schedule admin).
- Command changelist/overview: a **"Schedules" button per command** shown when the command has at least one schedule, linking to that command's schedules.
- A **global Schedules overview** (`ScheduledCommand` changelist) listing all schedules (label, command, kind, summary, enabled, next run where available).
- Change view: two tabs — Parameters, Schedule — with Save and Delete buttons. Save validates kwargs against the command's current argparse definition (stale schedules referencing removed options surface a validation error) and re-materializes the native object; Delete removes the native object first, then the row.

### 5. Enabled flag semantics
`enabled=False` SHALL NOT run the schedule but MUST keep the row in the DB. Materializer maps this to the backend's pause mechanism (django-q2: delete the native `Schedule` row, keep the library row and its key empty; re-enabling re-creates it — alternative `Schedule.enabled` toggling is not available in django-q2).

### 6. Declarative schedules on the command
`@register_command(schedule=...)` accepts a single `Schedule` value object or a sequence of them (usually one; multiple are useful for different kwargs, e.g. a nightly full run plus an hourly incremental). `Schedule` is a frozen value object with subclasses per kind — `CronSchedule(cron)`, `IntervalSchedule(minutes)`, `ClockedSchedule(at)` — plus `name`, `kwargs`, `enabled` (initial value only; the DB owns it after first sync). Constructor validates the cron expression / positive interval / future run_at at import time.
- **Identity for sync**: declarative schedules are identified by `(command_name, source=code, name)`; a single schedule defaults its name to the command name, lists require explicit names (no positional matching — reordering must not rewire schedules).
- **Registry wins** for the schedule spec — sync creates or updates each declared schedule to match the code.
- **DB wins for `enabled`** — admins may pause a declarative schedule without a deploy; sync never re-enables.
- Declarative schedules carry `source=code` so admin-created schedules (`source=admin`) are never touched by sync; removing a declaration from code deletes its `source=code` row and native object.

### 7. Validation
- Cron syntax validated with the backend's parser (django-q2 ships `croniter`); `interval_minutes > 0`; `run_at` in the future for clocked; `command_name` must reference an active `RegisteredCommand`.
- Clocked schedules that have fired: django-q2 deletes its native one-off schedule; the library row is marked complete/disabled rather than deleted (audit trail), with optional cleanup action.

## Risks / Trade-offs

- [Library and native objects drift (e.g. manual edits in django-q admin)] → native side is read as display-only; `backend_schedule_key` ties edits to the exact row created; a `materialize_all` management command can re-sync.
- [Command signature changes make stored kwargs invalid] → kwargs validated against the live argparse form on every edit; broken schedules flagged in the changelist, never silently run with wrong args.
- [Orphaned native schedules on backend switch or crashed delete] → delete is best-effort with logging; sweep for orphans is a follow-up.
- [Two storage layers add latency on save] → negligible; single-row writes.
- [Timezone mistakes on clocked schedules] → `run_at` stored in UTC (`USE_TZ`), widgets render in the admin's current timezone.

## Migration Plan

1. Ship `run_scheduled_command` + `ScheduledCommand` model + migration (ensure `CommandExecution.triggered_by` is nullable) — additive, safe.
2. Ship django-q2 materializer + admin UI behind the capability set; backends without support are unaffected.
3. Downstream (wodore-backend) deletes its custom Schedule admin glue.
Rollback: remove the admin views/materializer; the model is additive and can be dropped in a later migration.

## Open Questions

- Should `ScheduledCommand.kwargs` reuse the JSON `CommandExecution.kwargs` field class or add a shared base? (Implementation detail; lean shared.)
- Celery materializer in the first iteration or django-q2 only? (Lean: django-q2 only, Celery behind the same API next.)
- Store schedule label on the execution as `triggered_by` string vs. a nullable FK to `ScheduledCommand`? (Lean: nullable FK — cheap, precise traceability.)
