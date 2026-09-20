# Design: timeout-status

## Context

Hard time limits (django-q2 `timeout`, Celery `time_limit`) SIGKILL the
worker: nothing in the killed process can run, so no in-process hook can
set a status. Soft limits (Celery `soft_time_limit`) raise an exception
inside the worker and can be mapped in-process. The sentinel/parent
processes that performed the kill keep records (q2 writes a failure
entry for timed-out tasks), enabling out-of-process attribution.

`worker_pid` (from execution-cancellation) makes "is the worker still
alive?" answerable; Force Stop already finalizes rows manually. The
sweeper is the automatic complement.

## Goals / Non-Goals

Goals:
- Timed-out executions end in a distinguishable TIMEOUT status.
- Rows whose worker died without finalizing are finalized automatically.
- No background infrastructure (sweeper piggybacks on admin traffic).

Non-goals:
- Preventing timeouts (configuration concern; docs only).
- Immediate detection — sweeping is lazy (next page view / poll).
- Changing Force Stop semantics.

## Decisions

### D1: New `Status.TIMEOUT`

Char-field choice `"TIMEOUT"`, label "Timed out", amber-red clock badge,
added to the check constraint, list filter choices, `finished`
computation, and result footer ("Timed out"). Rerun stays allowed
(terminal state). Distinct from CANCELLED (user intent) and FAILED
(command error).

### D2: In-process timeout mapping

In `execute_command`'s exception path, classify the exception before
choosing the final status:

- `celery.exceptions.SoftTimeLimitExceeded` (imported defensively) →
  TIMEOUT with the traceback preserved in stderr.
- Worker-lost/cancellation classification from execution-cancellation
  keeps precedence (a stop wins over a timeout).

Only exceptions raised *inside* the worker can be mapped here; hard
kills are handled by D3.

### D3: Lazy stale-run sweeper

`sweep_stale_executions()` in tasks.py (or a new module), invoked from:

- `CommandExecutionAdmin.change_view` (single execution view), and
- the `_output_view` poll endpoint — but rate-limited to at most one
  sweep per `ADMIN_RUNNER_SWEEP_INTERVAL` seconds (default 30, process
  local) so the poll does not run a liveness check on every tick.

Sweep criteria (single queryset, conditional update):

- `status=RUNNING`, `worker_pid` is not NULL,
- `started_at < now() - grace` (grace default 2× flush interval, floor
  10 s — a live worker that merely hasn't flushed yet must not be
  swept), and
- the PID is dead (POSIX `os.kill(pid, 0)` → ESRCH) — checked per
  candidate row (bounded: only RUNNING rows).

Rows with `worker_pid IS NULL` and `started_at` older than
`ADMIN_RUNNER_STALE_AFTER` seconds (default 1 h) are swept by age alone
(legacy rows from before worker_pid existed).

Finalization for each swept row:

1. Ask the runner's `finalize_stale(execution)` for a status + note:
   - **django-q2**: query q2's Task/Failure records for `task_id`;
     a timeout/failure record → TIMEOUT (or FAILED with the backend's
     stored result as note), no record → FAILED "worker lost".
   - **Celery**: inspect the AsyncResult state (FAILURE/REVOKED →
     attribute; else FAILED "worker lost"). Best effort — a broker
     that is down must not break the sweep (exceptions → default).
   - **base/default**: FAILED, note "worker process no longer exists".
2. Conditional `update(status=…, finished_at=now())` guarded on
   `status=RUNNING`; append the note to stderr output parts.

### D4: Attribution hook on the runner

`BaseCommandRunner.finalize_stale(execution) -> tuple[Status, str] |
None` — `None` means "no backend knowledge", the caller falls back to
FAILED/"worker lost". Runners override with best-effort backend lookups
wrapped in try/except: attribution must never break sweeping.

### D5: Sweeper safety

- Conditional updates only (`status=RUNNING`): a worker finalizing
  concurrently wins or loses atomically; the sweeper never overwrites a
  terminal state.
- PID-liveness uses the same best-effort guard as q2 force-kill
  (`_proc_starttime` not needed here — a reused PID would need the row
  to be RUNNING and the grace to have elapsed; accepted residual risk,
  mitigated by requiring the PID to be dead *and* no output growth is
  impractical, so documented instead).
- The sweep never raises into the request path; all failures logged.

## Risks / Trade-offs

- **Lazy detection lag**: a timed-out execution nobody watches stays
  RUNNING until the next admin hit. Accepted (same trade-off as D7 in
  execution-cancellation); docs state it.
- **PID reuse**: a dead worker's PID reused by another process keeps
  the row RUNNING until that process exits. Rare; document.
- **Wrong attribution**: a backend record may be ambiguous; the note
  always names the source ("killed by django-q2 timeout" vs "worker
  lost") so operators can judge.

## Migration Plan

1. Model migration: status choice + check constraint extension
   (char field — constraint only), nothing else.
2. Deploy: sweeper is inert until admin traffic arrives; legacy RUNNING
   rows with NULL `worker_pid` finalize after `ADMIN_RUNNER_STALE_AFTER`.

## Open Questions

- Should the sweeper also run from `run_scheduled_command` (worker-side
  piggyback) so unwatched queues self-heal? Deferred — admin-side first.
