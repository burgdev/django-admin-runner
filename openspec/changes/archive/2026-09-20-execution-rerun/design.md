## Context

`CommandExecution` stores `command_name` and `kwargs` (the cleaned form
values captured at run time). The change page for an execution is entirely
read-only (`readonly_fields`), but Django still renders "Save" /
"Save and continue" buttons that submit the form and change nothing of
consequence. The command run view (`_command_run_view`) already builds its
form via `form_from_command(command_name)` from the argparse definition, so
prefilling is a matter of supplying `initial` data on the GET branch.

## Goals / Non-Goals

**Goals:**
- One click from an execution back to a run form pre-filled with that
  execution's arguments.
- Remove the dead "Save" controls from the read-only execution page.
- Work under both Unfold and the base admin theme.
- Degrade to a normal (empty) run form when the command is gone, args no
  longer map, or permission is missing.

**Non-Goals:**
- One-click rerun without seeing the form (the user should be able to
  adjust arguments before launching).
- Scheduling or repeating executions automatically.
- Editing stored kwargs of a past execution.

## Decisions

1. **Link shape: query param on the existing run view.**
   `<run-url>?rerun=<execution.pk>` — no new URL patterns, no schema
   change. The change-page button renders as an object-tools link.

2. **Prefill via form `initial`, not bound data.**
   The GET branch constructs `FormClass(initial=coerced_kwargs)` so the
   form renders unbound (no validation errors on open). Coercion per field:
   - `MultipleChoiceField` receiving a string (append args can be stored as
     a single comma/space-joined string) → split on `[,\s]+` into a list.
   - Boolean fields keep `False` (a stored `False` still checks nothing,
     matching the original submission).
   - Unknown keys (fields removed from the command since the execution)
     are dropped silently.
   The source execution is fetched through the admin queryset, so users
   only rerun from executions they are allowed to see.

3. **Save buttons: context flags, not template surgery.**
   `changeform_view` adds `show_save=False` and
   `show_save_and_continue=False` to the context; Django's `submit_row`
   (and Unfold's, which mirrors it) honors these flags. Superuser delete
   stays untouched. A `dar_rerun_url` (or `None`) is added to the context
   for the object-tools row; it is `None` when the command is no longer
   registered or the user lacks run permission.

4. **Rerun button visibility mirrors run permission.**
   The button reuses `has_permission(request.user, entry)` from the
   registry — the same gate as the changelist "Run" button. No separate
   permission is introduced.

## Risks / Trade-offs

- [Stored kwargs drift from the current argparse definition (renamed
  args, changed choices)] → unknown keys are dropped and `initial` is
  unbound, so the form still opens; the user sees current defaults for
  vanished fields.
- [Unfold renders its own submit row] → both themes documently honor
  `show_save*` context flags; verified in tests for the base theme and
  manually under Unfold.
- [`?rerun=` pointing at another user's execution] → lookup goes through
  `get_queryset(request)`, which is already restricted per user.

## Migration Plan

Additive change only (templates, admin context, GET-branch prefill). No
models, migrations, or settings. Rollback is reverting the release.
