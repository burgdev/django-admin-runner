## Why

The classic Django admin has no mechanism for adding custom sidebar/index links — Unfold solves this with `SIDEBAR.navigation`, but classic users have no equivalent. The current `admin/index.html` template override approach is broken because Django's `APP_DIRS` loader always finds `django.contrib.admin`'s template first. A `RegisteredCommand` model gives classic admin users a proper changelist for commands (with search, filter, ordering) and unlocks per-command metadata that the in-memory registry alone cannot provide.

## What Changes

- Add a `RegisteredCommand` model that mirrors the in-memory `_registry` in the database: `name`, `group`, `display_name`, `description` (help text), `active` flag, and timestamps.
- Sync `_registry` → `RegisteredCommand` rows on app startup (`AppConfig.ready()`). New commands are created; existing commands have their metadata updated (group, display_name, description); commands no longer in the registry are set to `active=False` but **never deleted**.
- Remove the broken `src/django_admin_runner/templates/admin/index.html` template override.
- Register `RegisteredCommand` as a read-only admin with a custom "Run" action link per row, giving classic admin a native changelist for commands.
- `CommandExecution` stays unchanged — no FK to `RegisteredCommand`. Command name is stored directly on the execution, preserving historical accuracy even if the command is later renamed or deactivated.
- Add a `registered_command` field (optional FK) to `CommandExecution` so the admin can link executions to their command — but this is purely for convenience/filtering, not for display of command name on the execution.

## Capabilities

### New Capabilities
- `registered-command-model`: Persistent model synced from the in-memory command registry, providing a database-backed representation of registered commands with active/inactive tracking.
- `command-sync-on-startup`: Startup sync logic in `AppConfig.ready()` that reconciles `_registry` entries with `RegisteredCommand` rows.
- `command-admin-changelist`: Admin registration for `RegisteredCommand` providing a read-only changelist with "Run" action links, search, and filters — replacing the need for template-based index hacks.

### Modified Capabilities

## Impact

- **Models**: New `RegisteredCommand` model; optional FK from `CommandExecution` to `RegisteredCommand`
- **Migrations**: New migration for `RegisteredCommand` model; migration adding FK to `CommandExecution`
- **Admin**: New `RegisteredCommandAdmin`; minor update to `CommandExecutionAdmin` for FK filtering
- **Apps**: `AppConfig.ready()` extended with sync call after `autodiscover_commands()`
- **Templates**: Remove `src/django_admin_runner/templates/admin/index.html`
- **Registry**: No changes to `registry.py` — it remains the source of truth
- **Backward compatibility**: Fully backward-compatible. Existing `CommandExecution` rows are unaffected. The FK on `CommandExecution` is optional (nullable).
