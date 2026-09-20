# declarative-schedules Specification

## Purpose
TBD - created by archiving change add-interactive-scheduling. Update Purpose after archive.
## Requirements
### Requirement: Schedule value objects
The library SHALL provide frozen `Schedule` value objects with one subclass per kind — `CronSchedule(cron)`, `IntervalSchedule(minutes)`, `ClockedSchedule(at)` — each carrying an optional `name`, command `kwargs`, and an initial `enabled` flag. Constructors SHALL validate their parameters (parseable cron expression, positive interval, future run-at).

#### Scenario: Invalid declaration fails at import
- **WHEN** a command is registered with `CronSchedule("not-a-cron")`
- **THEN** construction raises immediately at import time

### Requirement: Schedule declaration on register_command
`@register_command` SHALL accept `schedule: Schedule | Sequence[Schedule] | None`. A sequence declares multiple schedules for one command (e.g. different kwargs for full and incremental runs).

#### Scenario: Declaring a single cron schedule
- **WHEN** a command is registered with `schedule=CronSchedule("15 4 * * *")`
- **THEN** the registry entry records one declarative schedule, named after the command by default

#### Scenario: Declaring multiple schedules
- **WHEN** a command is registered with a list of two schedules with distinct names and different kwargs
- **THEN** the registry records both declarations

### Requirement: Sync materializes declared schedules
The startup command sync SHALL create or update `ScheduledCommand` rows (marked `source=code`) for each declared schedule, materializing native backend schedules via the runner. The registry SHALL win for the schedule spec (kind, expression/interval, kwargs); the database SHALL win for `enabled` so admins can pause a declarative schedule without a deploy.

#### Scenario: Sync creates declared schedules
- **WHEN** a command with two declarations is registered and sync runs
- **THEN** a `source=code` schedule exists per declaration and native backend schedules fire per their specs

#### Scenario: Code change updates the declared schedule
- **WHEN** a cron expression is changed in code and sync runs
- **THEN** the matching `source=code` schedule and its native object are updated to match

#### Scenario: Admin pause survives sync
- **WHEN** an admin disables a declarative schedule and sync runs again
- **THEN** the schedule remains disabled

### Requirement: Declarative schedule identity
Declarative schedules SHALL be identified by `(command_name, source=code, name)`; a single declaration defaults its name to the command name, and sequences SHALL declare explicit names so reordering the list never rewires schedules.

#### Scenario: Reordering a declaration list
- **WHEN** the order of declared schedules in code changes and sync runs
- **THEN** each schedule keeps its identity and spec

### Requirement: Admin-created schedules are never touched by sync
Schedules with `source=admin` SHALL NOT be created, modified, or deleted by the sync.

#### Scenario: Sync ignores admin schedules
- **WHEN** sync runs and admin-created schedules exist
- **THEN** those schedules are unchanged

### Requirement: Removed declarations are cleaned up
When a declaration is removed from code (or the command is deactivated), sync SHALL delete the corresponding `source=code` schedule and its native object.

#### Scenario: Declaration removed
- **WHEN** a command no longer declares a schedule and sync runs
- **THEN** its `source=code` schedule row and native object are removed
