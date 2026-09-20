# Scheduled Command Model

## ADDED Requirements

### Requirement: ScheduledCommand stores schedule definitions
The system SHALL provide a `ScheduledCommand` model that stores, per row: `command_name` (referencing an active registered command), an optional label, an `enabled` flag, a schedule `kind` (`cron`, `interval`, or `clocked`), the kind-specific schedule fields (cron expression, interval in minutes, run-at datetime in UTC), the command `kwargs` as JSON, and a `backend_schedule_key` referencing the materialized native backend object.

#### Scenario: Creating a cron schedule
- **WHEN** a schedule row is created with kind `cron`, a valid cron expression, a command name, and kwargs
- **THEN** the row is persisted with all fields and is uniquely referenced by its primary key

#### Scenario: Multiple schedules per command
- **WHEN** two or more schedule rows reference the same `command_name` with different schedule definitions
- **THEN** the system stores and manages them independently

### Requirement: Schedule field validation
The system SHALL validate that: the cron expression parses, `interval_minutes` is a positive integer, `run_at` for clocked schedules is in the future, and `command_name` references an active `RegisteredCommand`.

#### Scenario: Invalid cron expression rejected
- **WHEN** a schedule is saved with an unparseable cron expression
- **THEN** validation fails with a field error and nothing is persisted

#### Scenario: Unknown command rejected
- **WHEN** a schedule is saved with a `command_name` that is not an active registered command
- **THEN** validation fails with a field error

### Requirement: kwargs validated against the live command form
The system SHALL validate stored `kwargs` against the command's current argparse definition whenever a schedule is created or edited, so schedules referencing removed or renamed options fail with actionable errors.

#### Scenario: Stale kwargs detected on edit
- **WHEN** a schedule is edited and its stored kwargs contain an option the command no longer defines
- **THEN** the edit form shows a validation error and the schedule is not saved
