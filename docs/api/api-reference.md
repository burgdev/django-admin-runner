# API Reference

Auto-generated documentation from source code docstrings.

## Registry

| Symbol | Description |
|---|---|
| [`register_command`](register-command.md) | Decorator to register a management command with the admin runner |

## Context

| Symbol | Description |
|---|---|
| [`is_admin_runner`](context.md#django_admin_runner.context.is_admin_runner) | Return `True` during an admin-runner command execution |
| [`set_result_html`](context.md#django_admin_runner.context.set_result_html) | Store HTML as the rich result for the current execution |

## Forms

| Symbol | Description |
|---|---|
| [`FileOrPathField`](forms.md#django_admin_runner.forms.FileOrPathField) | Form field accepting an uploaded file or a server-side path |
| [`FileOrPathWidget`](forms.md#django_admin_runner.forms.FileOrPathWidget) | Widget with file-upload and text-path inputs side by side |
| [`FileField`](forms.md#django_admin_runner.forms.FileField) | File-upload-only field |
| [`ImageField`](forms.md#django_admin_runner.forms.ImageField) | Image-upload-only field (requires Pillow) |
| [`form_from_command`](forms.md#django_admin_runner.forms.form_from_command) | Build a Django Form class from a command's argparse parser |

## Hooks

| Symbol | Description |
|---|---|
| [`CommandHook`](hooks.md#django_admin_runner.hooks.CommandHook) | Base class for command execution hooks |
| [`HookContext`](hooks.md#django_admin_runner.hooks.HookContext) | Dict-like state bag scoped to a single command execution |
| [`TempFileHook`](hooks.md#django_admin_runner.hooks.TempFileHook) | Creates a unique upload directory and removes it after execution |

## Runners

| Symbol | Description |
|---|---|
| [`BaseCommandRunner`](runners.md#django_admin_runner.runners.BaseCommandRunner) | Abstract base class for command runners |
| [`RunResult`](runners.md#django_admin_runner.runners.RunResult) | Data class returned by runner `run()` implementations |
| [`SyncCommandRunner`](runners.md#django_admin_runner.runners.sync.SyncCommandRunner) | Runs commands inline in the current thread |
| [`DjangoTaskRunner`](runners.md#django_admin_runner.runners.django_tasks.DjangoTaskRunner) | Enqueues commands using Django's built-in task system |
| [`CeleryCommandRunner`](runners.md#django_admin_runner.runners.celery.CeleryCommandRunner) | Enqueues commands as Celery tasks |
| [`get_runner`](runners.md#django_admin_runner.runners.get_runner) | Instantiate the runner configured by `ADMIN_RUNNER_BACKEND` |

## Models

| Symbol | Description |
|---|---|
| [`CommandExecution`](models.md#django_admin_runner.models.CommandExecution) | Model storing the results of command executions |
| [`RegisteredCommand`](models.md#django_admin_runner.models.RegisteredCommand) | Model storing registered commands and their metadata |

## Admin

| Symbol | Description |
|---|---|
| [`CommandRunnerModelAdminMixin`](admin.md#django_admin_runner.admin.CommandRunnerModelAdminMixin) | Mixin for ModelAdmin to add "Run" links for attached commands |
