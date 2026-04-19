## 1. Runner Implementation

- [x] 1.1 Create `src/django_admin_runner/runners/django_q2.py` with `DjangoQ2CommandRunner` class: set `backend = "django-q2"`, implement `run()` using `django_q.tasks.async_task(execute_command, ...)`, handle enqueue failures by marking execution as FAILED, store `task_id` from `async_task` return value
- [x] 1.2 Register `"django-q2"` in `get_runner()` in `src/django_admin_runner/runners/__init__.py` — add `if backend == "django-q2"` branch with lazy import

## 2. Package Configuration

- [x] 2.1 Add `django-q2` optional dependency extra to `pyproject.toml`: `django-q2 = ["django-q2>=1.5"]`

## 3. Tests

- [x] 3.1 Add `DjangoQ2CommandRunner` tests to `tests/test_runners.py`: mock `django_q.tasks.async_task`, verify backend field set to `"django-q2"`, task_id populated, is_async is True, enqueue failure marks execution FAILED
- [x] 3.2 Add `get_runner` factory test for `"django-q2"` backend string

## 4. Example Project

- [x] 4.1 Create `examples/unfold_django_q2/` directory structure: `manage.py`, `settings.py`, `urls.py`, `pyproject.toml`, `Makefile`, `README.md`, `.gitignore`
- [x] 4.2 Copy `books` app from `examples/unfold_celery/books/` into `examples/unfold_django_q2/books/` (same commands, admin, models, migrations)
- [x] 4.3 Write `settings.py` with: `INSTALLED_APPS` including `django_q`, `unfold`, `django_admin_runner`, `books`; `Q_CLUSTER` with `'orm': 'default'` (Django ORM broker, no external services); `ADMIN_RUNNER_BACKEND = "django-q2"`; Unfold sidebar navigation including Scheduled Tasks section
- [x] 4.4 Write `pyproject.toml` with dependencies: `django-admin-runner[django-q2,unfold]` (no Redis needed)
- [x] 4.5 Write `Makefile` with targets: `init`, `run` (port 8766), `worker` (runs `python manage.py qcluster`)
- [x] 4.6 Write `README.md` with setup instructions matching the other examples' style, highlighting zero external dependencies
- [x] 4.7 Add sample `books.csv` data file

## 5. Custom Schedule Admin (Example Project)

- [x] 5.1 Create `examples/unfold_django_q2/admin.py` that unregisters django-q2's default `ScheduleAdmin` and registers a custom one
- [x] 5.2 Implement custom `ScheduleAdmin` that overrides `get_form()` to replace the `func` field widget with a `Select` dropdown listing all registered management commands from `_registry`, plus a blank option for free-text entry. Each choice value is `django_admin_runner.tasks.execute_command` and the label is the command's display name
- [x] 5.3 Add the custom Schedule admin to the Unfold sidebar navigation with appropriate icon

## 6. Documentation

- [x] 6.1 Update `docs/guides/runners.md` — add `"django-q2"` section describing `DjangoQ2CommandRunner`, ORM broker config, and the `Q_CLUSTER` setting example
- [x] 6.2 Update `docs/getting-started/installation.md` — add `pip install "django-admin-runner[django-q2]"` to the Optional extras section and add `"django-q2"` to the Task backend code examples
- [x] 6.3 Update `docs/examples.md` — add a new "Unfold + Django-Q2" tab with architecture diagram, setup instructions (no Docker needed), key configuration, and Schedule admin description; update the Comparison table with a new column for Django-Q2
- [x] 6.4 Update `docs/api/runners.md` — add `::: django_admin_runner.runners.django_q2.DjangoQ2CommandRunner` entry for auto-generated API docs
