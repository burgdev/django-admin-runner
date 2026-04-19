## ADDED Requirements

### Requirement: Django-Q2 runner enqueues commands asynchronously
The `DjangoQ2CommandRunner` SHALL use `django_q.tasks.async_task` to enqueue `execute_command` for background execution. The runner SHALL set `backend = "django-q2"` on the execution record before enqueueing.

#### Scenario: Successful enqueue
- **WHEN** `run()` is called with a valid command name, kwargs, user, and execution
- **THEN** the execution's `backend` field SHALL be set to `"django-q2"`, the task SHALL be enqueued via `async_task`, the execution's `task_id` SHALL be set to the returned task ID, and `RunResult.is_async` SHALL be `True`

#### Scenario: Broker unreachable
- **WHEN** `async_task` raises an exception (e.g. broker not connected)
- **THEN** the execution SHALL be marked `FAILED` with the error message in `stderr`, `RunResult.is_async` SHALL be `False`, and `task_id` SHALL be empty

### Requirement: Django-Q2 runner is selectable via ADMIN_RUNNER_BACKEND
The `get_runner()` factory SHALL recognize `"django-q2"` as a built-in backend string and return a `DjangoQ2CommandRunner` instance.

#### Scenario: Backend string django-q2
- **WHEN** `ADMIN_RUNNER_BACKEND` is set to `"django-q2"`
- **THEN** `get_runner()` SHALL return a `DjangoQ2CommandRunner` with `backend == "django-q2"`

### Requirement: django-q2 optional dependency extra
The package SHALL declare a `django-q2` optional dependency extra in `pyproject.toml` that depends on `django-q2`.

#### Scenario: Installing the extra
- **WHEN** a user installs `django-admin-runner[django-q2]`
- **THEN** `django-q2` SHALL be installed as a dependency

### Requirement: Django-Q2 example project with Unfold theme and ORM broker
An example project at `examples/unfold_django_q2/` SHALL demonstrate the django-q2 runner with the Unfold admin theme and the Django ORM broker (no external services). It SHALL include the same `books` app with sample commands as other examples, and use `Q_CLUSTER = {'name': 'DJANGORM', 'orm': 'default'}`.

#### Scenario: Example project runs end-to-end with no external services
- **WHEN** a user follows the example README instructions (run init, start Django, start qcluster)
- **THEN** the admin SHALL be accessible with Unfold theme and commands SHALL execute asynchronously via django-q2 using only the Django ORM database as broker
