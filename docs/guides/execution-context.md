# Execution Context

When a management command runs through the admin runner, you can detect the
context and store rich output.

## Detecting admin-runner execution

```python
from django_admin_runner import is_admin_runner

def handle(self, *args, **options):
    if is_admin_runner():
        self.stdout.write("Running from the admin")
    else:
        self.stdout.write("Running from the CLI")
```

`is_admin_runner()` returns `True` only during an admin-runner execution. Use it
to skip interactive prompts, adjust logging, or change output formatting.

## Rich HTML results

Store HTML that will be displayed on the execution result page:

```python
from django_admin_runner import set_result_html

def handle(self, *args, **options):
    count = self._process(options["source"])
    set_result_html(
        f'<h2>Import complete</h2>'
        f'<p>Processed <strong>{count}</strong> records.</p>'
    )
```

The HTML is stored in the `CommandExecution.result_html` field and rendered on
the execution detail page in the admin. Last writer wins if called multiple
times.

## Hooks

Hooks let you run code before and after command execution. See the
[Hooks guide](hooks.md) for details on TempFileHook, custom hooks, and the
hook lifecycle.

## ANSI output

Standard output and stderr are automatically converted from ANSI escape codes
to styled HTML. Colored output from management commands renders correctly in
the admin interface.

If the `rich` package is installed, tracebacks are rendered with rich formatting
for improved readability.
