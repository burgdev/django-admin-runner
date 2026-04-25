## Context

The `_action_to_field()` function in `forms.py` maps argparse actions to Django form fields. Currently it handles:

- `type=int` → `IntegerField`
- `store_true`/`store_false` → `BooleanField`
- `choices` → `ChoiceField`
- Everything else → `CharField` (string, no type conversion)

The "everything else → CharField" catch-all means that `type=float`, `type=Decimal`, `pathlib.Path`, and any other argparse type silently produces strings. Django form validation on `CharField` does no type coercion, so `cleaned_data` contains raw strings.

## Goals / Non-Goals

**Goals:**

- Ensure `type=float` gets a proper `FloatField`.
- Ensure `type=int` stays as `IntegerField` (already works).
- Ensure **any** `type=` callable works — not just hardcoded types — by generically calling the type function during form cleaning.
- Keep special-case mappings for `int` and `float` to get the best widgets and validation messages.
- Maintain backwards compatibility for arguments without a `type=` (stay `CharField`).

**Non-Goals:**

- Adding explicit field mappings for every Python type (`Decimal`, `Path`, etc.) — the generic approach handles them.
- Changing how defaults are handled — that's a separate concern.

## Decisions

**Decision 1: Generic `_TypedCharField` for any `type=` callable**

Create a `_TypedCharField(CharField)` subclass that overrides `clean()` to call the argparse `type` callable on the string value after normal `CharField` validation. This means `type=decimal.Decimal`, `type=pathlib.Path`, custom lambdas, etc. all work automatically.

**Decision 2: Keep special-case fields for `int` and `float`**

`IntegerField` and `FloatField` provide better validation messages, min/max support, and admin widgets. These remain as explicit branches. The generic `_TypedCharField` is the fallback for everything else.

Alternative considered: A mapping table of `{type: FieldClass}`. Rejected — a generic callable wrapper is simpler, more extensible, and handles custom types without enumeration.

## Risks / Trade-offs

- **Risk: Custom type callables that raise unexpected exceptions** → `_TypedCharField.clean()` wraps the type call; `ValidationError` from Django and `ArgumentError`-style errors are surfaced as form validation errors.
- **Risk: Breaking existing commands that expect strings** → Unlikely; commands using typed arguments would already fail at runtime when doing type-specific operations. The fix makes them work correctly.
