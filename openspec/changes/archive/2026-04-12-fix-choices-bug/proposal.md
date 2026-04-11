## Why

Argparse `choices` render as empty `<select>` dropdowns in admin forms when Unfold is installed. The `_apply_unfold_widget()` function replaces the `ChoiceField`'s widget with a fresh `UnfoldAdminSelectWidget()`, but Django's choices are only synced from field to widget at assignment time. The new widget starts with `choices = []`.

## What Changes

- Re-sync `choices` from the field to the new widget after `_apply_unfold_widget()` swaps it for `ChoiceField` instances.
- Add a test that verifies choices survive Unfold widget replacement.

## Capabilities

### New Capabilities

### Modified Capabilities

- `command-hooks`: No requirement changes — only affects `_apply_unfold_widget()` in `forms.py`, which is unrelated to hooks. (No spec change needed.)

## Impact

- **Files**: `src/django_admin_runner/forms.py` (one-line fix in `_apply_unfold_widget`), `tests/test_forms.py` (new test)
- **No breaking changes**, no new dependencies, no API changes
