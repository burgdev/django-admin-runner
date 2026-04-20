# Widget & Form Customisation

django-admin-runner auto-generates a form for every registered command by
introspecting its argparse arguments.  You can customise how individual
parameters are rendered — from swapping a widget to replacing the entire field
or providing a hand-crafted form class.

---

## Default widgets

By default, argparse arguments are mapped to Django form fields with Django
admin-styled widgets so the run form blends with the rest of the admin
interface:

| argparse type / action | Form field | Default widget |
|---|---|---|
| `action="store_true/false"` | `BooleanField` | Checkbox |
| `choices=[…]` | `ChoiceField` | `Select` |
| `type=int` | `IntegerField` | `AdminIntegerFieldWidget` |
| everything else | `CharField` | `AdminTextInputWidget` |

When **Unfold** is installed, widgets are automatically upgraded to their
Unfold-styled equivalents (`UnfoldAdminTextInputWidget`, etc.).

---

## Three levels of customisation

### 1. `widget=` in `add_argument` *(highest priority)*

Pass a `Widget` or `Field` instance directly on `add_argument`.  This keeps
the override right next to the argument definition.

```python
from django import forms
from django.core.management.base import BaseCommand
from django_admin_runner import FileOrPathField, register_command


@register_command(group="Import")
class Command(BaseCommand):
    help = "Import records"

    def add_arguments(self, parser):
        # Field instance — replaces field type AND widget
        parser.add_argument(
            "--source",
            widget=FileOrPathField(),
            default="data.csv",
            help="Upload a file or enter a server-side path",
        )
        # Widget instance — keeps CharField, just swaps the HTML widget
        parser.add_argument(
            "--notes",
            widget=forms.Textarea(attrs={"rows": 3}),
            help="Optional notes",
        )
        # Image upload (requires Pillow)
        parser.add_argument(
            "--thumbnail",
            widget=forms.ImageField(required=False),
            help="Thumbnail image",
        )
```

### 2. `widgets=` on `@register_command` *(decorator-level)*

Useful when you don't own the command file, or prefer to keep widget config
separate from the command.

```python
from django import forms
from django_admin_runner import FileOrPathField, register_command


@register_command(
    group="Import",
    widgets={
        "source": FileOrPathField(),                       # full field override
        "notes": forms.Textarea(attrs={"rows": 3}),        # widget swap
        "photo": forms.ImageField(required=False),         # image upload
    },
)
class Command(BaseCommand):
    ...
```

Values can be a **`Widget` instance** (swaps the widget, keeps auto-detected
field type and validation) or a **`Field` instance** (replaces the field
entirely).

### 3. `form_class=` on `@register_command` *(full custom form)*

Skip auto-generation entirely and provide your own `Form` class — the same
pattern as `ModelAdmin.form`:

```python
from django import forms
from django_admin_runner import register_command


class ImportForm(forms.Form):
    source = forms.CharField(label="File path", initial="data.csv")
    dry_run = forms.BooleanField(required=False)
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

When `form_class` is set, `params`, `exclude_params`, `widgets`, and Unfold
widget replacement are all ignored.

---

## Priority order

When multiple overrides apply to the same parameter, the highest wins:

```
add_argument(widget=...)   ←  highest
widgets={...} decorator
auto-detected from argparse  ←  lowest
```

User-specified overrides (levels 1 and 2) are **never** replaced by Unfold's
auto-styling.

---

## Built-in field types

Import these from `django_admin_runner` or `django_admin_runner.forms`:

```python
from django_admin_runner import FileOrPathField, FileField, ImageField
```

| Class | Description |
|---|---|
| `FileOrPathField` | Combined file upload **or** server-side path text input. The user can either upload a file or type a path. Uploaded files are saved to a temporary directory; the cleaned value is always a path string. |
| `FileField` | File-upload-only field. Alias for `django.forms.FileField`. |
| `ImageField` | Image-upload-only field. Alias for `django.forms.ImageField`. Requires Pillow. |

### `FileOrPathField` example

```python
from django_admin_runner import FileOrPathField

parser.add_argument(
    "--source",
    widget=FileOrPathField(),
    default="data.csv",
    help="Upload a CSV file or enter a path on the server",
)
```

The form renders a file input and a text input side by side.  If a file is
uploaded it takes precedence.

---

## Positional arguments

Positional argparse arguments (those without `--`) are also included in the
generated form.  They respect `required=True` by default, matching argparse's
own behaviour:

```python
def add_arguments(self, parser):
    parser.add_argument("filename", help="Input file path")   # required in form
    parser.add_argument("--count", type=int, default=1)       # optional in form
```

Use `nargs="?"` to make a positional argument optional in both argparse and the
generated form.

---

## Hiding arguments from the form

Use `hidden=True` on `add_argument` to keep an argument in the management
command's parser but exclude it from the admin form:

```python
parser.add_argument("--internal-key", hidden=True, help="Not shown in the form")
```

Alternatively, list it in `exclude_params` on the decorator:

```python
@register_command(exclude_params=["internal_key"])
```
