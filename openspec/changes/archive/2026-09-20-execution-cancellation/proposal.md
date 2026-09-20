## Why

Once a command is running there is no way to stop it from the admin. A
mis-behaving long-running command (bad arguments, runaway loop, stuck I/O)
just has to be waited out, and with the sync backend that also blocks the
HTTP worker. Users expect an equivalent of Ctrl+C: ask the command to stop,
and if it does not comply within a grace period, kill it.

django-q2 — the primary async backend of this project — has no per-task
revoke API (unlike Celery's `revoke(terminate=True)`), so a per-runner
stop mechanism with a graceful-first / forced-after-grace ladder is needed.

## What Changes

- New `CommandExecution.Status.CANCELLED` status and a `stop_requested`
  flag (set when a stop is requested) plus a `worker_pid` field (recorded
  by the worker when the execution starts running).
- Cooperative stop: `execute_command` checks the stop flag on the existing
  output-flush heartbeat and exits via a `CommandCancelledError` that flows
  the normal cleanup path, preserving output up to that point.
- Manual force kill per runner, exposed as `BaseCommandRunner.stop()`
  (graceful) and `force_stop()`, **with no automatic escalation** — the
  user decides how long to wait:
  - graceful first (set flag + SIGTERM-equivalent, caught by the existing
    SIGTERM handler),
  - a second explicit force-kill request hard-kills: Celery
    `revoke(task_id, terminate=True, SIGKILL)`; django-q2 PID-targeted
    SIGKILL (tasks must be enqueued with `retry` disabled so a killed
    task is not re-run); sync/django-tasks: graceful only (forced
    unsupported — no separate process to signal).
- A stop control (admin action on the execution page and in the live
  run/result view) that is **only shown while the execution's status is
  RUNNING**: it renders as **"Stop"** (graceful) initially and becomes
  **"Force Stop"** (hard kill) once a stop has been requested and the
  execution is still running — hidden on backends without forced support.
  Once the execution leaves RUNNING (cancelled, finished, or failed), no
  stop control is rendered at all.
- Permission-gated: a new permission (or superuser/staff check) controls
  who may stop executions.
- Race handling: stop requests and the worker's final save use
  conditional updates (`status=RUNNING`) so "finished just as stop was
  requested" resolves deterministically.

## Capabilities

### New Capabilities
- `execution-cancellation`: Stopping a running command execution
  gracefully, escalating to a forced kill after a grace period, and the
  "Force Stop" button visibility rules.

### Modified Capabilities

(none)

## Impact

- `django_admin_runner/models.py` — new status, `stop_requested`,
  `worker_pid`, migration.
- `django_admin_runner/tasks.py` — `CommandCancelledError`, heartbeat stop
  check, CANCELLED finalization, PID recording.
- `django_admin_runner/runners/__init__.py` — `stop()` API on
  `BaseCommandRunner`.
- `django_admin_runner/runners/celery.py`, `runners/django_q2.py`,
  `runners/sync.py`, `runners/django_tasks.py` — per-backend stop
  implementations (graceful-only where forced is impossible).
- `django_admin_runner/admin.py` — Force Stop action/button, permission,
  escalation trigger.
- Templates/static for base + Unfold themes and the live result view.
- Tests: graceful cancellation, forced escalation (q2 PID kill, Celery
  revoke), button visibility, races, retry guard.
