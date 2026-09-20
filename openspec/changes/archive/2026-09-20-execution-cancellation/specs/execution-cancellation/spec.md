## ADDED Requirements

### Requirement: Graceful stop via stop flag
The system SHALL provide a cooperative stop mechanism: when a running
execution's `stop_requested` flag is set, the executing command SHALL be
interrupted at the next output-flush heartbeat by raising a
`CommandCancelledError` that flows the existing cleanup path, finalizing
the execution as CANCELLED with its output preserved up to the stop point.

#### Scenario: Command that prints is stopped gracefully
- **WHEN** `stop_requested` is set while the command is running and the
  command writes output within one flush interval
- **THEN** the execution's status becomes CANCELLED, `finished_at` is set,
  and the stored output ends at (or near) the stop point with a
  "Cancelled by <user>" line appended

#### Scenario: Stop flag on idle command
- **WHEN** `stop_requested` is set but the command produces no output
- **THEN** the flag is also honored by the graceful backend signal
  (SIGTERM / revoke) and the execution finalizes as CANCELLED

#### Scenario: Stop requested after completion
- **WHEN** a stop is requested for an execution whose status is no longer
  RUNNING
- **THEN** the request is a no-op and the final status is unchanged

### Requirement: Manual force kill on second request
The system SHALL provide an explicit, user-triggered force kill — there
SHALL be no automatic escalation. A force-kill request for an execution
that is still RUNNING after a graceful stop was requested SHALL hard-kill
the worker process on backends that run commands in their own process:
Celery SHALL use `revoke(task_id, terminate=True, signal=SIGKILL)`;
django-q2 SHALL signal the recorded `worker_pid` with SIGKILL after
verifying the PID still belongs to the task's process. Sync and
django-tasks SHALL NOT send process signals (graceful stop only).

#### Scenario: Second click force-kills
- **WHEN** a graceful stop was requested, the execution is still RUNNING,
  and the user requests a force kill
- **THEN** the worker process running the command is killed with SIGKILL
  (or Celery revoke-terminated) and the execution is finalized as
  CANCELLED with output up to the last flush

#### Scenario: No automatic escalation
- **WHEN** a graceful stop was requested and the execution is still
  RUNNING with no further user action
- **THEN** no kill is performed; escalation happens only on an explicit
  force-kill request (the user decides how long to wait)

#### Scenario: No retry after force kill (django-q2)
- **WHEN** a django-q2 execution is force-killed
- **THEN** the task is not retried by the broker and no second execution
  attempt runs (retry disabled at enqueue + idempotency guard in
  `execute_command`)

#### Scenario: Force kill impossible (no worker / unsupported backend)
- **WHEN** the active backend is sync or django-tasks, or the worker
  process no longer exists (stale row)
- **THEN** no process signal is sent and the execution is finalized as
  CANCELLED (nothing is running that could do it)

### Requirement: Stop button visibility and states
The admin SHALL render at most one stop control for an execution, **only
while its status is RUNNING**. The control SHALL be shown on the
execution change page and in the live run/result view, gated by a stop
permission (default: model change permission). Its state SHALL be:
"Stop" (graceful request) while RUNNING without a pending stop request,
and "Force Stop" (hard kill) while RUNNING with a stop already requested
— hidden on backends without forced support. For every other status
(PENDING, SUCCESS, FAILED, CANCELLED) no stop control SHALL be rendered.

#### Scenario: Stop button while running
- **WHEN** a user with stop permission views an execution whose status is
      RUNNING and no stop has been requested
- **THEN** a "Stop" button is rendered and submits a graceful stop request

#### Scenario: Force Stop after stop requested
- **WHEN** the execution is still RUNNING and a graceful stop was already
      requested
- **THEN** the control shows "Force Stop" (on backends with forced
      support), which submits a force-kill request

#### Scenario: No button after stop
- **WHEN** an execution has left the RUNNING status (including CANCELLED)
- **THEN** no stop control of any kind is rendered on any view

#### Scenario: Permission denied
- **WHEN** a user without stop permission views a RUNNING execution
- **THEN** no stop button is rendered and the stop endpoint rejects the
      request

### Requirement: CANCELLED status
`CommandExecution` SHALL support a CANCELLED status, displayed in status
badges/filters like the other statuses, set only via the cancellation
path, and included in the status check constraint.

#### Scenario: Cancelled execution display
- **WHEN** an execution was cancelled
- **THEN** the admin shows it with a CANCELLED badge and its output and
      metadata remain viewable

### Requirement: worker_pid recording and race safety
The worker SHALL record its OS PID on the execution when transitioning to
RUNNING. Stop and escalation requests SHALL use conditional updates on
`status=RUNNING` so that a stop racing command completion resolves
deterministically, and duplicate stop requests SHALL be idempotent.

#### Scenario: PID recorded
- **WHEN** an execution starts running
- **THEN** `worker_pid` contains the executing process's PID

#### Scenario: Completion race
- **WHEN** a stop is requested at the same moment the command finishes
- **THEN** the execution ends in SUCCESS/FAILED (worker wins the
      conditional update) or CANCELLED (stop wins), never an inconsistent
      state
