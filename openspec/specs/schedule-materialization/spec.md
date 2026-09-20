# schedule-materialization Specification

## Purpose
TBD - created by archiving change add-interactive-scheduling. Update Purpose after archive.
## Requirements
### Requirement: Runners declare supported schedule kinds
Each runner SHALL expose `supported_schedule_kinds: frozenset[str]` drawn from `{"cron", "interval", "clocked"}`. The django-q2 runner SHALL support all three kinds; runners whose backend has no native periodic tasks SHALL report an empty set.

#### Scenario: Capability-driven UI
- **WHEN** the active runner reports an empty `supported_schedule_kinds`
- **THEN** the admin does not offer the "Add schedule" action

### Requirement: Runner schedule CRUD API
The runner abstraction SHALL provide `create_schedule(sched)`, `update_schedule(sched)`, and `delete_schedule(sched)`, translating a `ScheduledCommand` row into the backend's native schedule objects and recording the native reference in `backend_schedule_key`.

#### Scenario: Materializing a django-q2 schedule
- **WHEN** `create_schedule` is called for a cron schedule on the django-q2 runner
- **THEN** a django-q2 `Schedule` row is created pointing at the schedule-safe entry point with the command name and kwargs as args, and its primary key is stored in `backend_schedule_key`

#### Scenario: Updating a schedule re-materializes the native object
- **WHEN** a `ScheduledCommand` is saved with changed schedule fields
- **THEN** the native backend object referenced by `backend_schedule_key` is updated in place, not duplicated

#### Scenario: Deleting a schedule removes the native object
- **WHEN** a `ScheduledCommand` is deleted
- **THEN** the native backend object is removed first and the library row second

### Requirement: Disabled schedules are not materialized as active
When `enabled=False`, the materializer SHALL remove (or pause, where the backend supports it) the native schedule while preserving the `ScheduledCommand` row; re-enabling SHALL recreate/reactivate the native object.

#### Scenario: Disable and re-enable round-trip
- **WHEN** a schedule is disabled and later re-enabled
- **THEN** no native schedule fires while disabled, and a native schedule equivalent to the library row exists after re-enabling

### Requirement: Library row is the source of truth
Native backend schedule objects SHALL be treated as materialized implementation details; the `ScheduledCommand` row SHALL remain authoritative, and edits made directly to native objects SHALL NOT corrupt the library row.

#### Scenario: Re-materialization restores consistency
- **WHEN** native objects are missing or hand-edited and re-materialization is triggered
- **THEN** native objects are recreated or updated to match the library rows
