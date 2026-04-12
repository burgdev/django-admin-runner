## 1. Model

- [ ] 1.1 Add `RegisteredCommand` model to `models.py` with fields: `name` (unique CharField), `group`, `display_name`, `description` (TextField, blank), `app_label`, `active` (BooleanField, default True), `created_at`, `updated_at`. Meta: `ordering = ["group", "name"]`.
- [ ] 1.2 Create and run the migration for `RegisteredCommand`.

## 2. Sync Logic

- [ ] 2.1 Create `sync.py` with a `sync_registered_commands()` function that: iterates `_registry`, creates/updates `RegisteredCommand` rows, deactivates rows not in `_registry`. Handles `OperationalError` gracefully (table not exist yet).
- [ ] 2.2 Update `apps.py` `ready()` to call `sync_registered_commands()` after `autodiscover_commands()`.
- [ ] 2.3 Add tests for sync: fresh DB, update existing, deactivate removed, reactivate re-added, idempotent, missing table.

## 3. Admin

- [ ] 3.1 Register `RegisteredCommandAdmin` in `admin.py`: `has_add_permission` and `has_change_permission` return False; `has_delete_permission` returns True only for superusers. `list_display` with `name`, `display_name`, `group`, `active`, `updated_at`, and custom `run_button` + `history_button` columns.
- [ ] 3.2 Implement `run_button`: returns an HTML link to `django_admin_runner_command_run` for active commands, dash for inactive.
- [ ] 3.3 Implement `history_button`: returns an HTML link to `CommandExecution` changelist filtered by `command_name`.
- [ ] 3.4 Add `search_fields = ["name", "display_name"]`, `list_filter = ["active", "group"]`. Default queryset filtered to `active=True` (overridable via query params).
- [ ] 3.5 Add tests for `RegisteredCommandAdmin`: read-only permissions, Run link visible for active, hidden for inactive, History link, default filter, search.

## 4. Cleanup

- [ ] 4.1 Delete `src/django_admin_runner/templates/admin/index.html`.
- [ ] 4.2 Fix button gap in `src/django_admin_runner/templates/django_admin_runner/base/list.html` (add `display: flex; gap: 6px` to the Run/History button cell).
- [ ] 4.3 Run `just check` and `just tests` to verify everything passes.
