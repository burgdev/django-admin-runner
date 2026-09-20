# Tasks: Interactive command scheduling

## 1. Entry point and model

- [x] 1.1 Add `run_scheduled_command(command_name, kwargs)` to `tasks.py`: create `CommandExecution` (PENDING), delegate to `execute_command`, re-raise on failure
- [x] 1.2 Make `CommandExecution.triggered_by` nullable (if not already) and add nullable FK `schedule` to `ScheduledCommand` for traceability; migration
- [x] 1.3 Add `ScheduledCommand` model (command_name, label, enabled, source, kind, cron, interval_minutes, run_at, kwargs JSON, backend_schedule_key, timestamps) with kind-conditional validation (cron parses, interval > 0, run_at future, command active)
- [x] 1.4 Add kwargs validation helper reusing the argparse form machinery to reject stale options on save

## 2. Runner abstraction

- [x] 2.1 Add `supported_schedule_kinds: frozenset[str]` to `BaseCommandRunner` (default empty; sync/django-tasks/rq empty)
- [x] 2.2 Add `create_schedule` / `update_schedule` / `delete_schedule` to `BaseCommandRunner`, raising `NotSupportedError` when the kind is unsupported
- [x] 2.3 Implement django-q2 materializer: map kind → `Schedule.schedule_type` (C/I/O), `func=run_scheduled_command`, `args=[command_name, kwargs]`, store native pk in `backend_schedule_key`; update in place via key; delete by key
- [x] 2.4 Mark fired clocked schedules complete/disabled (django-q2 deletes native one-offs)
- [x] 2.5 Implement enabled=False semantics: remove native schedule, keep row; re-enable recreates it

## 3. Admin UI

- [x] 3.1 Add "Add schedule" action next to "Run" on the command page, gated on `supported_schedule_kinds`
- [x] 3.2 Schedule creation view/page: argparse parameter form + schedule section (kind picker limited to supported kinds, conditional fields, label, enabled); dynamic show/hide of kind-conditional fields on type change (htmx or JS)
- [x] 3.3 `ScheduledCommand` change view with Parameters/Schedule tabs, Save (re-validate kwargs, re-materialize) and Delete (native first, row second)
- [x] 3.4 Global Schedules changelist: label, command, kind, schedule summary, enabled, next run where available; filterable by command and enabled
- [x] 3.5 "Schedules" action per command in the command overview (shown when the command has schedules), linking to the filtered changelist
- [x] 3.6 Register admin in both classic and unfold theme variants (templates + Media, no query strings inside static paths)

## 4. Declarative schedules

- [x] 4.1 Add `Schedule` value objects (`CronSchedule`, `IntervalSchedule`, `ClockedSchedule`; frozen, validating `name`/`kwargs`/initial `enabled`) and accept `schedule: Schedule | Sequence[Schedule] | None` on `@register_command`
- [x] 4.2 Extend startup sync: create/update `source=code` schedules keyed by `(command_name, name)` (registry wins for spec, DB wins for enabled), never touch `source=admin`, delete `source=code` rows whose declaration was removed
- [x] 4.3 Tests: value-object validation, sync create/update/multi-declaration/reorder-stability/pause-survives/admin-untouched/cleanup

## 5. Tests

- [x] 5.1 Tests for `ScheduledCommand` validation (cron/interval/clocked/command-active/stale kwargs)
- [x] 5.2 Tests for django-q2 materializer (create/update/delete, correct func/args mapping, key round-trip, disable/re-enable)
- [x] 5.3 Tests for `run_scheduled_command` (execution created, status transitions, traceability FK, failure path)
- [x] 5.4 Admin view tests (action visibility per capability, create/edit/delete flows, tab rendering, dynamic form behavior, both themes)

## 6. Examples and docs

- [x] 6.1 Update `unfold_django_q2` example: interactive schedules (cron + interval + clocked) plus a declarative `cron=` command; document in its README
- [x] 6.2 Note the feature in `unfold_celery` / `classic` examples as backend-dependent (capability hidden where unsupported)
- [x] 6.3 Update library README with the scheduling section (capability matrix, declarative vs interactive, screenshots optional)
