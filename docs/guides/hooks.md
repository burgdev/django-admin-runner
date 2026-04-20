# Hooks

Hooks let you run code before and after command execution — for setup and
cleanup tasks scoped to a single run.

## Built-in: TempFileHook

Automatically activated when `ADMIN_RUNNER_UPLOAD_PATH` is set. Creates a unique
upload directory before the command runs and removes it afterwards.

```python
# settings.py
ADMIN_RUNNER_UPLOAD_PATH = "/tmp/admin_runner_uploads"
```

## Custom hooks

```python
# myapp/hooks.py
from django_admin_runner.hooks import CommandHook


class AuditLogHook(CommandHook):
    def setup(self, command_name, kwargs, execution, ctx):
        ctx["started"] = timezone.now()

    def post_save(self, command_name, kwargs, execution, ctx):
        started = ctx.get("started")
        AuditLog.objects.create(
            command=command_name,
            user=execution.triggered_by,
            duration=timezone.now() - started,
        )
```

```python
# settings.py
ADMIN_RUNNER_HOOKS = ["myapp.hooks.AuditLogHook"]
```

## Hook lifecycle

Each hook can implement:

| Method | When | Use for |
|---|---|---|
| `setup()` | Before command execution | Prepare resources, create temp dirs |
| `pre_save()` | After execution, before DB save | Modify execution record |
| `post_save()` | After DB save | Cleanup, logging, notifications |

Hooks share a `HookContext` (dict-like) to pass data between lifecycle methods.
