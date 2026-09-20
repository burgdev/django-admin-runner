# Schedule Admin UI

## ADDED Requirements

### Requirement: Both themes supported
The schedule admin UI SHALL work with both the native Django admin and the Unfold theme, sharing form and view logic with per-theme templates.

#### Scenario: Unfold theme rendering
- **WHEN** Unfold is installed and the schedule pages are opened
- **THEN** they render with Unfold widgets and styling

#### Scenario: Native admin rendering
- **WHEN** only the native Django admin is active
- **THEN** the schedule pages render with native admin templates and widgets

### Requirement: Add schedule action
The command page SHALL offer an "Add schedule" action alongside "Run", available only when the active runner supports at least one schedule kind.

#### Scenario: Action visibility
- **WHEN** the active runner supports scheduling
- **THEN** the "Add schedule" action is shown next to "Run" on the command page

### Requirement: Schedule creation page
The schedule creation page SHALL combine the command's argparse-generated parameter form with a schedule section offering only the kinds in `supported_schedule_kinds`, kind-conditional fields (cron expression, interval minutes, run-at datetime), an optional label, and an enabled toggle. The form SHALL update dynamically when the schedule type is selected, showing only the fields relevant to the chosen kind.

#### Scenario: Dynamic type-dependent form
- **WHEN** the user selects schedule kind `interval` on the creation page
- **THEN** the interval-minutes field becomes visible and the cron and run-at fields are hidden

#### Scenario: Creating a schedule with typed parameters
- **WHEN** the user fills the parameter form, selects kind `cron`, enters a valid expression, and saves
- **THEN** a `ScheduledCommand` row is created with the typed kwargs and the native backend schedule is materialized

### Requirement: Schedule change view with tabs
The `ScheduledCommand` change view SHALL present two tabs — Parameters and Schedule — with Save and Delete actions; Save re-validates kwargs and re-materializes the native object; Delete removes the native object and the row.

#### Scenario: Editing a schedule
- **WHEN** the user changes the interval of an existing schedule and saves
- **THEN** the library row is updated and the native backend schedule reflects the new interval

#### Scenario: Deleting a schedule
- **WHEN** the user deletes a schedule
- **THEN** both the native backend object and the library row are removed

### Requirement: Disabled schedules are kept but not run
Setting `enabled=False` on a schedule SHALL stop it from running while keeping the row in the database; the native backend schedule SHALL be removed or paused accordingly. Re-enabling SHALL resume the schedule.

#### Scenario: Disabling a schedule
- **WHEN** the user unchecks enabled and saves
- **THEN** the schedule row remains in the DB and the backend no longer fires it

#### Scenario: Re-enabling a schedule
- **WHEN** the user re-enables a disabled schedule and saves
- **THEN** the native backend schedule is re-created and the schedule runs again

### Requirement: Schedules button in the command overview
The command overview SHALL show a "Schedules" action for each command that has at least one schedule, linking to that command's schedules.

#### Scenario: Button shown only when schedules exist
- **WHEN** a command has one or more schedules
- **THEN** the command overview shows a "Schedules" action linking to them

### Requirement: Global schedules overview
The admin SHALL provide a global Schedules overview listing all schedules with label, command, kind, schedule summary, enabled state, and — where the backend exposes it — next run information.

#### Scenario: Overview of schedules
- **WHEN** an admin opens the global schedules overview
- **THEN** all schedules (admin-created and declarative) are listed with their command, kind, summary, and enabled state

### Requirement: Clocked schedules after firing
Fired clocked (one-off) schedules SHALL be marked complete or disabled in the library rather than silently deleted, preserving an audit trail.

#### Scenario: One-off schedule fires
- **WHEN** a clocked schedule's run time passes and the task executes
- **THEN** the schedule row remains visible, marked as completed or disabled

### Requirement: Examples updated
The example projects SHALL demonstrate the scheduling UI for backends that support it (at minimum `unfold_django_q2`), including creating, editing, and deleting a schedule.

#### Scenario: Django-Q2 example demonstrates scheduling
- **WHEN** the `unfold_django_q2` example is run
- **THEN** a command can be scheduled, edited, and deleted through the admin
