## 1. Core Implementation

- [x] 1.1 Create `_TypedCharField` subclass of `CharField` that calls the argparse `type` callable in `clean()` and surfaces errors as `ValidationError`
- [x] 1.2 Add `float` → `FloatField` mapping in `_action_to_field()`
- [x] 1.3 Replace the plain `CharField` fallback with `_TypedCharField` when `action.type` is a callable (and not `int`/`float`)

## 2. Tests

- [x] 2.1 Add test: `type=float` argument generates a `FloatField` in the form
- [x] 2.2 Add test: `type=float` form input is cleaned to a Python `float`
- [x] 2.3 Add test: `type=decimal.Decimal` argument produces a `Decimal` value via generic coercion
- [x] 2.4 Add test: custom `type=` callable (e.g. lambda) is invoked and returns the typed value
- [x] 2.5 Add test: invalid input for a typed field shows a validation error
- [x] 2.6 Add test: argument without `type=` stays a plain `CharField`
- [x] 2.7 Run full test suite to confirm no regressions
