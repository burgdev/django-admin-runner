# scheduled-task-entrypoint Specification

## Purpose
TBD - created by archiving change add-interactive-scheduling. Update Purpose after archive.
## Requirements
### Requirement: Schedule-safe entry point
The system SHALL provide `run_scheduled_command(command_name, kwargs)` which creates a `CommandExecution` row at run time and then delegates to `execute_command(command_name, kwargs, execution_pk)`, producing the same output capture, status transitions, and failure handling as run-now executions.

#### Scenario: Scheduled run executes with full capture
- **WHEN** a backend fires a materialized schedule and invokes `run_scheduled_command`
- **THEN** a `CommandExecution` is created and transitions through RUNNING to SUCCESS or FAILED with live output captured

#### Scenario: Command raises
- **WHEN** the scheduled command fails
- **THEN** the execution is marked FAILED with the traceback stored, and the backend marks the task as failed

### Requirement: No triggering user required
`CommandExecution.triggered_by` SHALL be nullable for scheduled runs, and executions SHALL be traceable to the schedule that produced them (via nullable FK to `ScheduledCommand` or schedule label metadata).

#### Scenario: Traceability of a scheduled execution
- **WHEN** an execution created by `run_scheduled_command` is viewed in the admin
- **THEN** it is attributable to the originating schedule
