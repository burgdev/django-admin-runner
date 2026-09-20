## 1. Run view prefill

- [x] 1.1 Extend `_command_run_view` GET branch: parse `rerun=<pk>`, look
      the execution up via `self.get_queryset(request)`, and build
      `initial` from its `kwargs` (drop unknown keys; split strings for
      multiple-choice fields on `[,\s]+`)
- [x] 1.2 Construct the unbound form with `FormClass(initial=...)`

## 2. Change page buttons

- [x] 2.1 In `change_view`, add `show_save=False` and
      `show_save_and_continue=False` to the context
- [x] 2.2 Compute `dar_rerun_url` (run view URL + `?rerun=<pk>`) when the
      command is registered and `has_permission` passes; else `None`
- [x] 2.3 Render the "Rerun" object-tools button in the change_form
      template (base + Unfold variants) when `dar_rerun_url` is set

## 3. Tests

- [x] 3.1 Run view prefill: stored kwargs appear as initial values
- [x] 3.2 String kwarg for a multiple-choice field is split into a list
- [x] 3.3 Stale kwargs keys and missing/inaccessible `rerun` pk degrade to
      an empty form
- [x] 3.4 Change page: no Save button, Rerun button present for permitted
      users, absent for unregistered commands

## 4. Verification

- [x] 4.1 Run full test suite and ruff
- [x] 4.2 Manual check under Unfold in cartoload-server (rerun a
      generate_maps execution, adjust selection, run)
