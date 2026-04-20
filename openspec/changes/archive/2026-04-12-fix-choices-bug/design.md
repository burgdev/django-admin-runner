## Context

`form_from_command()` auto-generates Django form fields from argparse definitions. For `choices` arguments, it creates a `forms.ChoiceField(choices=...)` which internally syncs choices to `self.widget`. Then `_apply_unfold_widget()` replaces the widget with `UnfoldAdminSelectWidget()` — a fresh instance with `choices = []`. The field's `_choices` attribute still holds the correct data, but the widget's `choices` are empty, resulting in empty `<select>` dropdowns.

This only manifests when Unfold is installed; classic admin doesn't replace the ChoiceField widget.

## Goals / Non-Goals

**Goals:**
- Fix the empty select dropdown for choices fields when Unfold is active

**Non-Goals:**
- Changing the hook protocol, admin views, or model schema
- Supporting other widget replacement scenarios beyond Unfold

## Decisions

**Re-sync choices after widget swap**: After `field.widget = UnfoldAdminSelectWidget()`, call `field.choices = field.choices` to re-trigger the setter which pushes choices to `self.widget`. This is the idiomatic Django pattern — the `ChoiceField.choices` setter explicitly syncs to the widget.

**Why not copy widget.choices manually**: `field.widget.choices = field.choices` would also work but is less idiomatic. The setter approach is what Django itself uses internally.

## Risks / Trade-offs

- **[Future widget swaps]**: Any future code that replaces a ChoiceField's widget must re-sync choices. This is documented in the code comment on `_apply_unfold_widget`. → Mitigation: the fix is a one-liner pattern that's easy to replicate.
