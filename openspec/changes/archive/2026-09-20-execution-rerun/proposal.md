## Why

The CommandExecution change page is fully read-only, yet it still shows the
default "Save" button — which does nothing useful. Re-running a command with
the same selection currently means re-opening the run form and re-entering
every argument by hand, even though the execution already stores the exact
`command_name` and `kwargs` that were used.

## What Changes

- Add a "Rerun" button to the CommandExecution change page (object tools /
  submit row) that links to the existing command run view with the form
  prepopulated from that execution's stored `kwargs`.
- Hide the default "Save" (and "Save and continue") buttons on the
  CommandExecution change page since every field is read-only; keep "Delete"
  for superusers.
- The run view accepts a reference to a previous execution (e.g.
  `?rerun=<pk>`) and uses its validated `kwargs` as the form's `initial`
  data when the command is still registered and the user has permission.
- Degrade gracefully: if the command is no longer registered, the kwargs no
  longer validate against the current form, or the user lacks permission,
  the run view opens with an empty form (and a notice) instead of failing.

## Capabilities

### New Capabilities
- `execution-rerun`: Re-running a command from a past execution with its
  stored arguments, and removing the dead "Save" control from the read-only
  execution page.

### Modified Capabilities

(none — the run view itself keeps its existing requirements; prepopulation
is additive behavior covered by the new capability)

## Impact

- `django_admin_runner/admin.py` (`CommandExecutionAdmin.change_view`,
  submit-row/object-tools context, `_command_run_view` GET branch).
- `django_admin_runner/forms.py` (optional: passing `initial` through
  `form_from_command`).
- Templates for the change page submit row (Unfold + base theme).
- Tests for prepopulation, permission handling and the disabled Save button.
