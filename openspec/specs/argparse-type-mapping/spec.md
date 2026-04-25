### Requirement: Float arguments produce FloatField
When a management command defines `parser.add_argument("--interval", type=float)`, the auto-generated form SHALL use a `forms.FloatField` for that argument. The value in `cleaned_data` SHALL be a Python `float`.

#### Scenario: Float argument renders as FloatField
- **WHEN** a command has `add_argument("--delay", type=float)`
- **THEN** the generated form contains a `FloatField` named `delay`

#### Scenario: Float form input is converted to float type
- **WHEN** a user submits `"0.5"` for a `type=float` argument
- **THEN** `cleaned_data["delay"]` is the Python `float` `0.5`, not the string `"0.5"`

### Requirement: Int arguments remain IntegerField
The existing `type=int` → `IntegerField` mapping SHALL continue to work unchanged.

#### Scenario: Int argument unchanged
- **WHEN** a command has `add_argument("--count", type=int)`
- **THEN** the generated form contains an `IntegerField` named `count`

### Requirement: Generic type callable coercion
When `action.type` is a callable that is not `int` or `float`, the auto-generated form SHALL wrap a `CharField` that calls the type callable during cleaning. The value in `cleaned_data` SHALL be the result of calling `action.type(user_input)`. This covers `decimal.Decimal`, `pathlib.Path`, custom lambdas, and any other type callable.

#### Scenario: Decimal type produces Decimal value
- **WHEN** a command has `add_argument("--amount", type=decimal.Decimal)`
- **THEN** the generated form contains a typed field that produces a Python `Decimal` in `cleaned_data`

#### Scenario: Custom type callable is invoked
- **WHEN** a command has `add_argument("--data", type=my_callable)`
- **THEN** the generated form calls `my_callable(user_input)` and returns the result in `cleaned_data`

#### Scenario: Custom type raises error on invalid input
- **WHEN** a user submits `"abc"` for an argument with `type=decimal.Decimal`
- **THEN** the form shows a validation error instead of crashing

### Requirement: Arguments without type remain CharField
When `action.type` is `None` (no `type=` specified in `add_argument`), the field SHALL be a plain `CharField` as before.

#### Scenario: No type specified stays CharField
- **WHEN** a command has `add_argument("--name")` without `type=`
- **THEN** the generated form contains a plain `CharField` named `name`
