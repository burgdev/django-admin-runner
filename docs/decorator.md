# @register_command

```python
from django_admin_runner import register_command

@register_command(
    name=None,
    *,
    group=None,
    permission="superuser",
    params=None,
    exclude_params=None,
    models=None,
)
class Command(BaseCommand):
    ...
```

## Parameters

### `name`
Command name as it appears in the admin. Defaults to the module's filename
(e.g. `import_books` for `management/commands/import_books.py`).

### `group`
Group label used to organise the command list. Defaults to the app label.

### `permission`
Controls who can see and run the command.

| Value | Behaviour |
|-------|-----------|
| `"superuser"` (default) | Only Django superusers |
| `"myapp.change_mymodel"` | Users with that Django permission |
| `["perm.a", "perm.b"]` | Users who hold **all** listed permissions (AND) |

Superusers always bypass permission checks regardless of this setting.

### `params`
Allowlist of argparse `dest` names. Only these arguments appear in the form.

```python
@register_command(params=["source", "dry_run"])
```

### `exclude_params`
Denylist of argparse `dest` names. These are excluded from the form.

```python
@register_command(exclude_params=["verbosity"])
```

### `models`
List of Django model classes. A **Run** link for this command is added to each
model's admin change-list page when `CommandRunnerModelAdminMixin` is used.

```python
from myapp.models import Book

@register_command(models=[Book])
```

## Hiding individual arguments

Pass `hidden=True` to `add_argument` to exclude that specific argument from the
form while keeping it in the management command's argparse parser.

```python
def add_arguments(self, parser):
    parser.add_argument("--public", help="Shown in the form")
    parser.add_argument("--internal", hidden=True, help="Not shown in the form")
```
