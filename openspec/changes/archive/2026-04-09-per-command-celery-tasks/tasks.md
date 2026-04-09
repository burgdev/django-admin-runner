## 1. Registry Updates

- [x] 1.1 Add `display_name` parameter to `register_command()` decorator in `registry.py`
- [x] 1.2 Derive default `display_name` from command name (underscore-to-space + title case) and store in registry entry

## 2. Dynamic Celery Task Registration

- [x] 2.1 Create `_register_celery_tasks()` function in `celery_tasks.py` that iterates `_registry` and creates one `shared_task` per command
- [x] 2.2 Each task uses name `<app_label>.<command_name>`, description from `Command.help`, and signature `(kwargs=None, execution_pk=None)`
- [x] 2.3 Task body: if `execution_pk` is None, create `CommandExecution`; then call `execute_command`
- [x] 2.4 Store task references in a lookup dict `_celery_tasks` keyed by command name
- [x] 2.5 Guard entire registration with try/except on celery import — no-op when Celery unavailable
- [x] 2.6 Call `_register_celery_tasks()` from `autodiscover_commands()` in `registry.py` after registry is populated

## 3. Runner Refactor

- [x] 3.1 Update `CeleryCommandRunner.run()` to look up per-command task from `_celery_tasks` and call `.delay(kwargs=..., execution_pk=...)`
- [x] 3.2 Remove import of generic `execute_command_task` from `runners/celery.py`

## 4. Cleanup

- [x] 4.1 Remove `execute_command_task` and `schedule_command` from `celery_tasks.py`
- [x] 4.2 Update docstring in `celery_tasks.py` to reflect new per-command task pattern

## 5. Verification

- [x] 5.1 Run existing tests to verify no regressions
- [x] 5.2 Verify per-command tasks appear in Celery task registry
