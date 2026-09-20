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

## Terminal output view

Command output (`stdout` / `stderr`) is rendered by an embedded
[xterm.js](https://xtermjs.org/) terminal widget on the execution page —
vendored locally, no CDN required. ANSI control sequences (colors, cursor
movement, line erase) display exactly as they would in a real terminal, so
progress bars (e.g. from `rich`) render as a single updating line instead of
one line per redraw frame.

While a command is running, the widget polls a cursor-based delta endpoint
every 250 ms and transfers only newly written characters — regardless of how
much output the command has already produced. When the command finishes,
polling stops after one final fetch.

### Storage model

Output is stored as an ordered sequence of immutable **parts** of at most
512 KB each (`CommandOutputPart`). Every flush appends only the new
characters to the active part at the database level, so per-flush cost is
proportional to new output only. Sealed (non-active) parts are served with an
`ETag` and `Cache-Control: immutable` — repeat opens of an execution page are
served from the browser cache; only the active part and new output are
fetched. Large outputs replay in ~64 KB slices so the page stays responsive,
with a progress bar while loading.

Retention: when the total output for a field exceeds `ADMIN_RUNNER_MAX_OUTPUT`
(default 500 MB), the oldest sealed parts are pruned (the active part is
never touched, and no stored text is rewritten). If the terminal widget's
cursor predates pruned parts, it receives a `reset` response, clears the
screen, and replays the retained output with a truncation notice.

### Settings

| Setting | Default | Description |
| --- | --- | --- |
| `ADMIN_RUNNER_MAX_OUTPUT` | `500_000_000` | Total characters of output retained per field (stdout/stderr). The oldest sealed parts are pruned beyond this cap. |
| `ADMIN_RUNNER_TERM_COLS` | `120` | Terminal width exported as `COLUMNS` during command execution and used to size the widget, so output layout (e.g. progress bar width) is deterministic. |
| `ADMIN_RUNNER_TERM_ROWS` | `40` | Terminal height exported as `LINES` during command execution (e.g. rich lays out panels for this height). |
| `ADMIN_RUNNER_TERM_VIEW_ROWS` | `20` | Visible height of the embedded terminal widget. Taller output scrolls in the widget's scrollback. |
| `ADMIN_RUNNER_FLUSH_INTERVAL` | `0.5` | Seconds between worker output flushes (how often new output is persisted and the stop flag checked). Override per command with `flush_interval=` on `@register_command`. |

Terminal dimensions are a global setting — they apply to future runs and do
not depend on the caller's or browser's terminal size. URLs in output are not
clickable (terminals do not hyperlink); copy them as plain text instead.
