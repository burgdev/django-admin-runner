# Admin Themes

## Plain Django admin

Works out of the box with no additional configuration. Templates in
`django_admin_runner/base/` extend `admin/base_site.html`.

## Unfold

Install `django-unfold` and add `"unfold"` **before** `"django.contrib.admin"`
in `INSTALLED_APPS`. The package auto-detects Unfold at runtime and uses
the `django_admin_runner/unfold/` templates instead.

```python
INSTALLED_APPS = [
    "unfold",              # must come before django.contrib.admin
    "django.contrib.admin",
    ...
    "django_admin_runner",
]
```

No other configuration is needed.

## Model admin integration

Use `CommandRunnerModelAdminMixin` to attach command run links to a model's
admin change-list. Works with both plain Django admin and Unfold:

```python
from django.contrib import admin
from django_admin_runner.admin import CommandRunnerModelAdminMixin
from myapp.models import Book


@admin.register(Book)
class BookAdmin(CommandRunnerModelAdminMixin, admin.ModelAdmin):
    list_display = ["title", "author"]
```

Commands registered with `models=[Book]` will appear as links in the Book
change-list context under the `admin_runner_commands` template variable.
