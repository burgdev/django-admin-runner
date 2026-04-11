## 1. Fix

- [x] 1.1 In `_apply_unfold_widget()` (forms.py), after `field.widget = UnfoldAdminSelectWidget()`, add `field.choices = field.choices` to re-sync choices to the new widget
- [x] 1.2 Add a code comment explaining why the re-sync is needed

## 2. Tests

- [x] 2.1 Add test: choices survive Unfold widget replacement (mock `is_unfold_installed` to return `True`, verify `field.widget.choices` is populated after `form_from_command`)
- [x] 2.2 Run `just tests` to confirm all existing tests still pass
- [x] 2.3 Run `just check` to confirm linting passes
