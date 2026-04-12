## ADDED Requirements

### Requirement: Sync runs automatically on app startup
The system SHALL sync `_registry` entries to `RegisteredCommand` rows during `AppConfig.ready()`, after `autodiscover_commands()` has populated the registry.

#### Scenario: Fresh startup with no existing rows
- **WHEN** the app starts and `_registry` contains commands `cleanup_books` and `import_books`, and no `RegisteredCommand` rows exist
- **THEN** two `RegisteredCommand` rows are created with `active=True` and metadata matching their registry entries

#### Scenario: Startup with existing rows
- **WHEN** the app starts and `_registry` contains `cleanup_books` (unchanged), `import_books` (description changed in code), and a new command `export_report`
- **THEN** `cleanup_books` row is unchanged, `import_books` row has its `description` and `updated_at` updated, `export_report` row is created with `active=True`

### Requirement: New commands are created, existing commands are updated
For each entry in `_registry`, the sync SHALL create a `RegisteredCommand` if one does not exist for that `name`, or update the existing row's `group`, `display_name`, `description`, and `app_label` fields if they differ from the registry entry.

#### Scenario: Command group changes
- **WHEN** a command's `group` is changed in the `@register_command` decorator from `"Maintenance"` to `"Book Operations"`
- **THEN** the `RegisteredCommand` row's `group` field is updated to `"Book Operations"` on next startup

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
The system SHALL handle the case where the `RegisteredCommand` table does not exist yet (e.g., before `migrate` is run) without raising errors.

#### Scenario: Migrations not yet applied
- **WHEN** `AppConfig.ready()` runs but the `RegisteredCommand` table does not exist in the database
- **THEN** the sync is skipped silently (no exception raised)
