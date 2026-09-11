# Stopping Commands

Commands started from the admin can be stopped while they are running. The
stop control appears on the execution page and in the live output view —
**only while the execution's status is Running**. Once the execution leaves
that state (finished, failed, or cancelled), no stop control is rendered.
No refresh needed: the live output poll inserts the button on the
Pending → Running transition, flips its label to "Force Stop" once a stop
was requested, and removes it when the execution ends.

## Two steps: Stop, then Force Stop

There is no automatic escalation — you decide how long to wait.

1. **Stop** — requests a graceful stop:
    - a stop flag is set, which the worker checks on its output-flush
      heartbeat (roughly every flush interval) — a printing command stops
      here within a fraction of a second,
    - backends that can target the worker process additionally send a
      SIGTERM-equivalent.
   The command unwinds through the normal cleanup path: output written so
   far is preserved and the execution is finalized as **Cancelled**.

2. **Force Stop** — appears after a stop was requested and the execution is
   still running. Clicking it hard-kills the worker process (SIGKILL /
   Celery `revoke(terminate=True)`). Output is preserved up to the last
   flush; the execution is finalized as **Cancelled**.

On backends without forced support (see below), the Force Stop control is
hidden once a graceful stop has been requested.

## Backend support

| Backend | Graceful stop | Force stop | Mechanism |
|---|---|---|---|
| `celery` | ✅ | ✅ | stop flag + `revoke(terminate=True, SIGTERM/SIGKILL)` |
| `django-q2` | ✅ | ✅ | stop flag + PID-targeted SIGTERM/SIGKILL (PID reuse guarded via `/proc`) |
| `django` (django.tasks) | ✅ | ❌ | stop flag only |
| `sync` | ✅ (limited) | ❌ | runs in the request thread — stop flag only |

Notes:

- A command blocked in a long C call or network I/O without producing
  output only responds to **Force Stop** — and on `sync` / `django` it
  cannot be interrupted at all.
- django-q2 tasks are enqueued with retries disabled, and `execute_command`
  refuses duplicate attempts: a force-killed task is never re-run.

## Permissions

Stopping requires the `django_admin_runner.change_commandexecution`
permission by default. Override `has_stop_permission()` on the
`CommandExecutionAdmin` to change this.

## Timeouts and dead workers

Task backends can enforce time limits by **hard-killing** the worker
(django-q2 `Q_CLUSTER["timeout"]`, Celery `time_limit`). A SIGKILLed
worker cannot write a status, so the execution would stay Running
forever. Two mechanisms handle this:

- **Soft limits in-process** (Celery `soft_time_limit` raises
  `SoftTimeLimitExceeded` inside the worker) finalize the execution as
  **Timed out** with the traceback preserved. A stop requested before
  the limit counts as **Cancelled** instead.
- **Stale-run sweeper** (lazy, no background infra): when an admin page
  or output poll is served, executions that are still Running while
  their recorded worker process no longer exists are finalized —
  **Timed out** when the backend's records attribute the kill to a
  timeout (django-q2 Task record, Celery result state), otherwise
  **Failed** with a "worker lost" note. Legacy rows without a recorded
  PID are swept after `ADMIN_RUNNER_STALE_AFTER` seconds (default 1 h).
  The sweep runs at most once per `ADMIN_RUNNER_SWEEP_INTERVAL` seconds
  (default 30) per web process and never races a finishing worker
  (conditional updates).

Keep backend timeouts well above your longest command, and prefer soft
limits where available — they produce the cleanest result.

Settings:

| Setting | Default | Meaning |
|---|---|---|
| `ADMIN_RUNNER_SWEEP_INTERVAL` | `30` | Min. seconds between sweeps per web process |
| `ADMIN_RUNNER_STALE_AFTER` | `3600` | Age before PID-less Running rows are swept |

## Command contract

Cancellation is cooperative for the graceful step: your `handle()` should
print or loop (almost all management commands do) so the heartbeat gets a
chance to run. There is no signal or callback inside the command — it is
stopped by an exception raised from the next `write()`.
