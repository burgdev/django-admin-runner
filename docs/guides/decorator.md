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
    widgets=None,
    form_class=None,
    display_name=None,
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

### `widgets`
Per-parameter widget or field overrides at the decorator level.

Keys are argument `dest` names. Values can be:

- A **`Widget` instance** — keeps the auto-detected field type but replaces
  its HTML widget.
- A **`Field` instance** — replaces the auto-detected field entirely (widget
  *and* validation), e.g. `FileOrPathField()`, `forms.FileField()`,
  `forms.ImageField()`.

```python
from django import forms
from django_admin_runner import register_command, FileOrPathField

@register_command(
    widgets={
        "source": FileOrPathField(),          # file upload OR server path
        "notes": forms.Textarea(attrs={"rows": 4}),   # swap to textarea widget
        "photo": forms.ImageField(required=False),    # image upload
    }
)
class Command(BaseCommand):
    ...
```

User-specified widgets are **never** replaced by the Unfold auto-styling.
Use `add_argument(widget=...)` inside `add_arguments` for the highest-priority
override (see [Widget customisation](widgets.md)).

### `form_class`
A fully custom `Form` class. When set, `form_from_command` returns it directly
— all auto-generation, `params`/`exclude_params` filtering, `widgets`
overrides, and Unfold widget replacement are bypassed.

```python
from django import forms
from django_admin_runner import register_command

class ImportForm(forms.Form):
    source = forms.CharField(label="File path", initial="data.csv")
    dry_run = forms.BooleanField(required=False, label="Dry run")
    limit = forms.IntegerField(required=False, min_value=0, initial=0)

    def clean_limit(self):
        v = self.cleaned_data["limit"]
        if v < 0:
            raise forms.ValidationError("Must be ≥ 0.")
        return v

@register_command(form_class=ImportForm)
class Command(BaseCommand):
    ...
```

### `display_name`
Human-readable name shown in the admin command list. Defaults to the command
name with underscores replaced by spaces and title-cased (e.g. `"import_books"`
becomes `"Import Books"`).

```python
@register_command(display_name="Import Books from CSV")
class Command(BaseCommand):
    ...
```

---

## Per-argument options in `add_arguments`

### `hidden=True`

Pass `hidden=True` to `add_argument` to exclude that specific argument from the
form while keeping it in the command's argparse parser.

```python
def add_arguments(self, parser):
    parser.add_argument("--public", help="Shown in the form")
    parser.add_argument("--internal", hidden=True, help="Not shown in the form")
```

### `widget=`

Pass a `Widget` or `Field` instance as `widget=` to override how a specific
argument is rendered in the form. This is the highest-priority override — it
takes precedence over the `widgets` dict on the decorator.

```python
from django_admin_runner import FileOrPathField

def add_arguments(self, parser):
    # Field instance — replaces the auto-detected field entirely
    parser.add_argument(
        "--source",
        widget=FileOrPathField(),
        default="data.csv",
        help="Upload a file or enter a server path",
    )
    # Widget instance — keeps CharField validation, swaps the HTML widget
    parser.add_argument(
        "--notes",
        widget=forms.Textarea(attrs={"rows": 4}),
        help="Free-text notes",
    )
```

See [Widget customisation](widgets.md) for the full priority order and available
field types.
