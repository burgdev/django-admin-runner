# Design: execution-cancellation

## Context

Executions run via `execute_command` in `tasks.py` on one of four backends.
Output is streamed through `_LiveTtyStringIO`, which flushes on a fixed
heartbeat (default 0.5 s) — a natural place for a cooperative stop check.
A SIGTERM handler (`_install_sigterm_handler`) already converts worker
shutdown into an exception that flows the normal failure path.

django-q2 has **no per-task revoke**; tasks run in individual pool worker
processes, so a PID-targeted signal kills exactly one task process and the
sentinel recycles the pool worker. Celery has native `revoke(terminate=…)`.
The sync backend runs inside the HTTP request thread — it cannot be
signalled at all.

## Goals / Non-Goals

Goals:
- Stop a running execution from the admin.
- Graceful first: command gets a chance to unwind, output preserved.
- User-controlled force kill as an explicit second step — the user decides
  how long to wait before escalating.
- Minimal UI surface: at most one stop button, only while RUNNING.

Non-goals:
- Interactive stdin / real Ctrl+C semantics in the terminal view.
- Stopping PENDING (queued, not yet started) executions — follow-up.
- Cancellation of scheduled commands (they can be disabled already).

## Decisions

### D1: Stop ladder — graceful on first click, force kill on second

No automatic escalation — the user decides how long to wait.

**First click ("Stop"):**

1. `CommandExecution.objects.filter(pk=…, status=RUNNING).update(
   stop_requested=True)` (idempotent, race-safe).
2. Runner-specific graceful signal:
   - celery: `revoke(task_id, terminate=True, signal=SIGTERM)`
   - django-q2: `os.kill(worker_pid, SIGTERM)` using the recorded PID
   - sync / django-tasks: flag only (cooperative)

**Second click ("Force Stop", shown only if still RUNNING after the
first request):** runner-specific hard kill:
- celery: `revoke(task_id, terminate=True, signal=SIGKILL)`
- django-q2: `os.kill(worker_pid, SIGKILL)`
- sync / django-tasks: no process (no separate process to signal)

The stop endpoint finalizes the execution as CANCELLED **in both cases**
(still conditional on `status=RUNNING`): a performed kill leaves no worker
to write the row, and a failed kill (unsupported backend, worker already
dead / stale row) equally means nothing running could finalize it. This
also gives Force Stop a defined meaning for stale rows with no worker.

SIGTERM lands in the existing handler; instead of `WorkerStoppedError` the
stop path raises `CommandCancelledError` so the final status is CANCELLED,
not FAILED. The stop flag distinguishes the two cases in the handler.

### D2: Cooperative check on the flush heartbeat

`_LiveTtyStringIO._maybe_flush` (which runs on every `write()` at flush
cadence) checks the `stop_requested` flag — but only once per flush
interval and only when the execution is running, so the added DB load is
one cheap indexed query per ~0.5 s per running execution. On detection it
raises `CommandCancelledError` from the `write()` call, which propagates
out of `call_command` into the existing exception path. This makes
graceful stops work even without signals (any backend).

A command blocked in C code / network I/O without output never hits the
heartbeat — that is what the manual force kill (D1 second click) is for.

### D3: `worker_pid` recording

`execute_command` saves `execution.worker_pid = os.getpid()` when it
transitions to RUNNING. This is what makes a per-task q2 kill possible.
On process exit the field stays as an audit artifact.

### D4: django-q2 retry guard

A SIGKILLed q2 task is an unacknowledged task and q2 would retry it. All
executions must therefore be enqueued with retry disabled (`retry=-1`),
and `execute_command` gains an idempotency guard: if the execution is
already in a terminal state (or another attempt set it RUNNING with a
different PID), the duplicate attempt exits immediately.

### D5: Status & finalization

- New `Status.CANCELLED` ("Cancelled"), included in the status check
  constraint, badges and filters.
- `CommandCancelledError` finalization: status CANCELLED, `finished_at`
  set, output preserved (no traceback overlay — a short "Cancelled by
  <user> at <time>" line is appended to stderr).
- `stop_requested_by` FK? — No: the requesting user is recorded in the
  appended stderr line only (keeps the model surface small; executions
  are already auditable via the admin log).

### D6: UI — one button, RUNNING-only, Stop → Force Stop

At most one stop control, rendered **only while status is RUNNING**
(object tools on the change page and in the live run/result view header).
Button state derives from the execution:

- status == RUNNING and not `stop_requested` → **"Stop"** (graceful
  request, D1 first click)
- status == RUNNING and `stop_requested` → **"Force Stop"** (hard kill,
  D1 second click); on backends without forced support (sync,
  django-tasks) the button is hidden instead, with a notice that a
  graceful stop was already requested
- any other status (PENDING, SUCCESS, FAILED, CANCELLED) → no stop button
  at all

The button performs a POST to a stop endpoint; the response refreshes the
view. The live poller re-renders the button from the current status/flag,
so it flips to Force Stop after the first click and disappears entirely
once the execution leaves RUNNING. The user decides how long to wait
between the two clicks — there is no timer.

Permission: modeled as `has_stop_permission`, defaulting to the model's
change permission, overridable via `ModelAdmin` method. Force Stop
requires the same permission (no separate gate — requesting a graceful
stop is the more dangerous "polite" action anyway, and both are
destructive).

### D7: No background escalation

Automatic escalation after a grace period was rejected: it needs a
background sweeper or per-stop timer (extra infra, leaks on
multi-process deployments) and takes the escalation decision away from
the user. The two-click model (D1/D6) makes escalation explicit and
unhurried; a stuck execution keeps running only until the user clicks
Force Stop.

### D8: Races

- Stop vs. completion: worker's final save is conditional on
  `status=RUNNING`; stop escalation is conditional on `status=RUNNING`.
  Whoever wins, the other no-ops.
- Stop vs. start (PENDING→RUNNING): stop requests only apply to RUNNING
  (per D6); a request arriving mid-transition is a no-op.
- Duplicate stop clicks: `stop_requested` update is idempotent.

## Risks / Trade-offs

- **q2 PID reuse:** between recording `worker_pid` and the kill, the pool
  worker could die and the PID be reused by another process. Mitigation:
  verify the target process command line / start time via
  `/proc/<pid>/stat` before signalling (best effort, POSIX only).
- **Cooperative gap:** commands doing long blocking I/O without prints
  rely entirely on the manual force kill; on sync/django-tasks they cannot
  be stopped at all — documented limitation, Force Stop is hidden there
  once a graceful stop was requested.
- **User forgets to click Force Stop:** a stuck execution keeps running
  indefinitely until someone looks at it again. Accepted trade-off for
  keeping the user in control of escalation.

## Migration Plan

1. Model migration adds `stop_requested` and `worker_pid`, and the new
   status choice (char field — no DB change needed for the choice itself,
   only the check constraint).
2. Deploy code; running executions from the old version simply never show
   the button (no `worker_pid` recorded → force kill no-ops gracefully).

## Open Questions

- Should the live terminal view show a transient "Stopping…" indicator
  between the stop request and the CANCELLED transition? (Nice-to-have;
  the status badge already flips via poll.)
