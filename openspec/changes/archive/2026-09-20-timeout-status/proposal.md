## Why

When a task backend enforces a time limit with a hard kill (django-q2
`timeout`, Celery `time_limit`), the worker process receives SIGKILL:
no exception, no cleanup, no status write. The `CommandExecution` row
stays RUNNING forever while the elapsed-time badge keeps ticking —
observed twice in development (a timed-out `simulate_workload --minutes 5`
against `Q_CLUSTER["timeout"] = 300`, and a stale row from a dead
cluster). Users cannot tell a timed-out, crashed, or still-running
command apart, and nothing but a manual Force Stop ever finalizes the row.

Soft limits that surface as in-process exceptions (Celery
`soft_time_limit`) at least flow the failure path, but are reported as
generic FAILED with no timeout attribution.

## What Changes

- New `CommandExecution.Status.TIMEOUT` ("Timed out") with badge, filter
  entry, `finished` flag, and result-page footer text.
- **In-process timeout mapping**: exceptions recognized as timeouts
  (Celery `SoftTimeLimitError`, plus an opt-in marker for user code)
  finalize the execution as TIMEOUT instead of FAILED, preserving
  output and the traceback.
- **Lazy stale-run sweeper** — no background infra: on admin page
  render/result poll, executions that are RUNNING with a `worker_pid`
  that no longer exists (and `started_at` older than a small grace
  period) are finalized:
  - per-runner attribution hook `finalize_stale(execution)` inspects
    the backend's own records: django-q2 checks its Task/Failure table
    for the task id (the sentinel records timeout kills) → TIMEOUT;
    Celery inspects the result state → TIMEOUT/FAILED;
  - no attribution possible (crash, OOM, cluster gone, pre-`worker_pid`
    rows swept by age) → FAILED with a "worker lost" note.
- Sweeps are conditional updates (`status=RUNNING`) so they never race
  a worker that finalizes at the same moment.

## Capabilities

### New Capabilities
- `timeout-status`: TIMEOUT finalization via in-process exception
  mapping and out-of-process sweeping of dead workers, with per-backend
  attribution.

### Modified Capabilities

(none — builds on execution-cancellation's runner/status foundations
without changing its requirements)

## Impact

- `django_admin_runner/models.py` — `Status.TIMEOUT`, check constraint,
  migration.
- `django_admin_runner/tasks.py` — timeout-exception mapping in the
  failure path.
- `django_admin_runner/runners/__init__.py` — `finalize_stale()`
  default; `django_q2.py` / `celery.py` attribution overrides.
- `django_admin_runner/admin.py` — badge/footer/filter entries; sweeper
  invocation on change view + output poll endpoint.
- Frontend (`terminal-output.js`, result templates) — TIMEOUT badge
  label/style, finished handling.
- Tests: exception mapping, PID-death sweep, attribution, races,
  pre-PID rows, status display.
