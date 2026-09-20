## ADDED Requirements

### Requirement: TIMEOUT status
`CommandExecution` SHALL support a TIMEOUT status ("Timed out"),
displayed with its own badge/filter/footer like the other statuses,
treated as a terminal (`finished`) state, and included in the status
check constraint.

#### Scenario: Timed-out execution display
- **WHEN** an execution was finalized as TIMEOUT
- **THEN** the admin shows a "Timed out" badge, the result footer reads
      "Timed out", and the output poll reports it as finished

#### Scenario: Terminal state semantics
- **WHEN** an execution is TIMEOUT
- **THEN** no stop control is rendered and rerun is allowed

### Requirement: In-process timeout mapping
The system SHALL finalize an execution as TIMEOUT when a soft time limit
raises inside the worker (Celery `SoftTimeLimitExceeded`), with its
output and traceback preserved, instead of FAILED. A stop requested for
the same execution keeps precedence over timeout classification.

#### Scenario: Soft time limit
- **WHEN** the command is interrupted by a soft-time-limit exception
- **THEN** the execution's status is TIMEOUT and stderr contains the
      traceback

#### Scenario: Stop wins over timeout
- **WHEN** a stop was requested and the unwinding raises a
      soft-time-limit exception
- **THEN** the execution's status is CANCELLED

### Requirement: Stale-run sweeping
The system SHALL lazily finalize executions stuck in RUNNING because
their worker process died without finalizing (hard timeout kill, crash,
dead cluster): on admin views/polls, executions whose recorded
`worker_pid` no longer exists (after a grace period) — or legacy rows
without a `worker_pid` older than a configurable age — SHALL be
finalized. The sweep SHALL use conditional updates on `status=RUNNING`
and SHALL never raise into the request path.

#### Scenario: Hard-kill by backend timeout is swept
- **WHEN** a worker was SIGKILLed by the backend's time limit and an
      admin page/poll is served after the grace period
- **THEN** the execution is finalized (TIMEOUT when the backend's
      records attribute the kill to a timeout, else FAILED) with a note
      naming the cause, and `finished_at` is set

#### Scenario: Live worker is never swept
- **WHEN** a RUNNING execution's worker process is alive
- **THEN** the sweep leaves the execution untouched, regardless of age

#### Scenario: Legacy rows without PID
- **WHEN** a RUNNING execution has no `worker_pid` and is older than
      the configured stale age
- **THEN** it is finalized as FAILED with a "worker lost" note

#### Scenario: No race with a finishing worker
- **WHEN** the worker finalizes the execution at the same moment the
      sweep runs
- **THEN** exactly one of the two writes wins (conditional on
      RUNNING) and the row never ends in an inconsistent state

### Requirement: Per-backend stale attribution
Runners SHALL provide a best-effort `finalize_stale()` hook that MAY
inspect the backend's own task records to attribute the cause (e.g.
django-q2's failure record for a timed-out task id). Attribution
failures SHALL fall back to FAILED with a generic note and SHALL never
break the sweep; the appended note SHALL name the attribution source.

#### Scenario: django-q2 timeout attribution
- **WHEN** a swept q2 execution has a backend failure record for its
      task id indicating a timeout
- **THEN** the execution is finalized as TIMEOUT with a note that the
      django-q2 timeout killed the worker

#### Scenario: Attribution unavailable
- **WHEN** the backend records are unreachable or inconclusive
- **THEN** the execution is finalized as FAILED with a "worker lost"
      note
