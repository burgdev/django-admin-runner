# command-sync-on-startup Specification

## Purpose

Keep `RegisteredCommand` rows (and declarative `ScheduledCommand` rows) in
sync with the in-memory `_registry` without touching the database during app
initialization, so `django.setup()` works without a reachable database
(image builds running `collectstatic`) and never opens pooled connections
pre-fork (gunicorn `--preload`).

## Requirements

### Requirement: AppConfig.ready() performs no database access
The system SHALL NOT execute queries, open database connections, or run the sync during `AppConfig.ready()`. `ready()` SHALL only populate the in-memory registry (`autodiscover_commands()`) and connect the `post_migrate` receiver.

#### Scenario: Preloaded worker with a pooled connection
- **WHEN** `django.setup()` runs in a gunicorn `--preload` master process using a pooled database connection
- **THEN** no database connection is opened and no queries are executed by `ready()`

#### Scenario: Image build without a database
- **WHEN** `collectstatic` (or any other `django.setup()` boot) runs with no reachable database
- **THEN** app initialization completes successfully without database access

### Requirement: Sync runs automatically after migrations
The system SHALL sync `_registry` entries to `RegisteredCommand` rows on Django's `post_migrate` signal, exactly once per `migrate` run, after `autodiscover_commands()` has populated the registry.

#### Scenario: Fresh migrate with no existing rows
- **WHEN** `migrate` finishes and `_registry` contains commands `cleanup_books` and `import_books`, and no `RegisteredCommand` rows exist
- **THEN** two `RegisteredCommand` rows are created with `active=True` and metadata matching their registry entries

#### Scenario: Migrate with existing rows
- **WHEN** `migrate` finishes and `_registry` contains `cleanup_books` (unchanged), `import_books` (description changed in code), and a new command `export_report`
- **THEN** `cleanup_books` row is unchanged, `import_books` row has its `description` and `updated_at` updated, `export_report` row is created with `active=True`

### Requirement: Sync can be run on demand
The system SHALL provide a management command (`admin_runner_sync`) that runs the full sync — registered commands and declarative schedules — for manual runs, worker boot, or re-sync after code changes.

#### Scenario: Manual re-sync after code changes
- **WHEN** a new command is registered in code and `admin_runner_sync` runs without migrations
- **THEN** a `RegisteredCommand` row is created for the new command and declarative schedules are materialized

### Requirement: Legacy ready-time sync is opt-in
The system SHALL support an `ADMIN_RUNNER_SYNC_ON_READY` setting (default `False`) that restores sync during `AppConfig.ready()` for consumers that cannot run migrations or the sync command during deploy.

#### Scenario: Opt-in enabled
- **WHEN** `ADMIN_RUNNER_SYNC_ON_READY = True` and the app starts
- **THEN** the sync runs during `AppConfig.ready()` as before the setting existed

### Requirement: New commands are created, existing commands are updated
For each entry in `_registry`, the sync SHALL create a `RegisteredCommand` if one does not exist for that `name`, or update the existing row's `group`, `display_name`, `description`, and `app_label` fields if they differ from the registry entry.

#### Scenario: Command group changes
- **WHEN** a command's `group` is changed in the `@register_command` decorator from `"Maintenance"` to `"Book Operations"`
- **THEN** the `RegisteredCommand` row's `group` field is updated to `"Book Operations"` on the next sync

### Requirement: Removed commands are deactivated
After processing all `_registry` entries, the sync SHALL set `active=False` on any `RegisteredCommand` whose `name` is not in the current `_registry`.

#### Scenario: Multiple commands removed
- **WHEN** `_registry` has commands A and B, and the DB has rows for A, B, and C
- **THEN** A and B remain `active=True`, C is set to `active=False`

### Requirement: Sync is idempotent
Running the sync multiple times within the same process SHALL produce the same result as running it once.

#### Scenario: Sync called twice
- **WHEN** sync is executed twice with the same `_registry` state
- **THEN** no additional rows are created, no rows are modified on the second run (timestamps aside)

### Requirement: Sync is silent on fresh DB
The system SHALL handle the case where the `RegisteredCommand` table does not exist yet (e.g. before `migrate` is run) without raising errors.

#### Scenario: Migrations not yet applied
- **WHEN** the sync runs but the `RegisteredCommand` table does not exist in the database
- **THEN** the sync is skipped silently (no exception raised)
