## Why

When a management command uses `type=float` (or any non-`int` type) in `add_argument`, the auto-generated form falls back to a `CharField`. This means the command's `handle()` method receives a **string** instead of a properly typed Python value, causing `TypeError` when the code performs arithmetic or comparisons on the argument.

## What Changes

- Replace the hardcoded `int`-only type mapping with a generic approach: when `action.type` is a callable and no special-case field applies, wrap a `CharField` so its `clean()` method calls the type callable to coerce the string value.
- Keep special-case mappings for `int` (→ `IntegerField` with admin widget) and `float` (→ `FloatField`) for better form validation and widgets.
- Any other `type=` callable (e.g. `decimal.Decimal`, `pathlib.Path`, custom functions) works automatically via the generic wrapper.

## Capabilities

### New Capabilities

- `argparse-type-mapping`: Generic type conversion from argparse `type=` callables to properly typed Python values in form `cleaned_data`, with optimized field types for `int` and `float`.

### Modified Capabilities

_(None — this fixes a gap in existing auto-generation behavior.)_

## Impact

- `src/django_admin_runner/forms.py` — `_action_to_field()` function and a new helper `_TypedCharField`
- Tests — new test cases for `type=float`, custom type callables, etc.
