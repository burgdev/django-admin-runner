## ADDED Requirements

### Requirement: RegisteredCommand model stores command metadata
The system SHALL provide a `RegisteredCommand` model with the following fields:
- `name` — CharField, unique, max_length=200 (the command name, e.g. `"cleanup_books"`)
- `group` — CharField, max_length=200 (group label, derived from the app label or decorator)
- `display_name` — CharField, max_length=200 (human-readable name, e.g. `"Cleanup Books"`)
- `description` — TextField, blank=True (the command's `help` text)
- `app_label` — CharField, max_length=200, blank=True (the Django app the command belongs to)
- `active` — BooleanField, default=True (True if the command is currently in the registry)
- `created_at` — DateTimeField, auto_now_add=True
- `updated_at` — DateTimeField, auto_now=True

The model SHALL use `Meta.ordering = ["group", "name"]` and `Meta.verbose_name = "Registered Command"`.

#### Scenario: Model fields match registry entry
- **WHEN** a `RegisteredCommand` is created from a registry entry for `cleanup_books`
- **THEN** `name` is `"cleanup_books"`, `group` is the app label, `display_name` is `"Cleanup Books"`, `description` is the command's help text, `app_label` is the originating app label, and `active` is `True`

### Requirement: RegisteredCommand is uniquely identified by name
The system SHALL enforce uniqueness on the `name` field. No two `RegisteredCommand` rows SHALL share the same `name`.

#### Scenario: Duplicate command name rejected
- **WHEN** a sync attempts to create a `RegisteredCommand` with a `name` that already exists
- **THEN** the existing row is updated instead of creating a duplicate

### Requirement: Deactivated commands are preserved
The system SHALL set `active=False` on `RegisteredCommand` rows whose `name` is no longer present in the in-memory `_registry`. The system SHALL NOT delete `RegisteredCommand` rows.

#### Scenario: Command removed from code
- **WHEN** a command was registered on the previous startup but is no longer in `_registry` on the current startup
- **THEN** the corresponding `RegisteredCommand` row has `active` set to `False` and all other fields remain unchanged

#### Scenario: Deactivated command re-registered
- **WHEN** a command that was previously deactivated (`active=False`) appears in `_registry` again
- **THEN** the `RegisteredCommand` row has `active` set to `True` and its metadata fields are updated
