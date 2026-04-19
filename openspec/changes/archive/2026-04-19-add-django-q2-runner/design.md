## Context

django-admin-runner currently ships three built-in runners: **sync**, **Celery**, and **Django Tasks**. A fourth runner (RQ) exists as a custom dotted-path example in `examples/unfold_rq/`. Each built-in runner is a `BaseCommandRunner` subclass registered in `get_runner()` with a short string key (e.g. `"celery"`).

**django-q2** is a native Django task queue that can use Django's ORM as its message broker — requiring zero external services. It provides async execution, scheduled/recurring tasks, result tracking, and an admin interface. It's lighter than Celery while still providing guaranteed delivery via the ORM broker. Adding it as a built-in backend follows the same pattern as Celery.

The `execute_command()` function in `tasks.py` is intentionally backend-agnostic — every runner calls it directly or enqueues it, so the new runner only needs to handle the enqueue/dispatch step.

## Goals / Non-Goals

**Goals:**
- Add a `DjangoQ2CommandRunner` that enqueues `execute_command` via `django_q.tasks.async_task`
- Register `"django-q2"` as a built-in backend in `get_runner()`
- Gate the import behind a `django-q2` optional dependency extra
- Add test coverage mirroring the existing runner test patterns
- Add an `unfold_django_q2` example project using the Django ORM broker (no external services), with Unfold theme and custom Schedule admin

**Non-Goals:**
- Built-in per-command Schedule registration in the library itself (the Schedule admin is an example-project feature showing the pattern)
- Supporting django-q (original, unmaintained fork) — only django-q2
- Custom queue name configuration via runner settings (use Django-Q2's own `Q_CLUSTER` settings for this)

## Decisions

### 1. Use `async_task` for enqueueing

**Decision**: Use `django_q.tasks.async_task(execute_command, command_name, kwargs, execution_pk)` to enqueue commands.

**Rationale**: `async_task` is the primary API in django-q2. It returns a task ID that can be stored on `CommandExecution.task_id`, matching the pattern used by Celery (`result.id`) and RQ (`job.id`).

**Alternative considered**: Using `django_q.tasks.schedule` for cron-like scheduling — out of scope for the runner itself (but covered by the example's custom Schedule admin).

### 2. Error handling: catch enqueue failures like Celery runner

**Decision**: Wrap the `async_task` call in a try/except, marking the execution as `FAILED` if the broker is unreachable — exactly like `CeleryCommandRunner` does.

**Rationale**: Consistency with the Celery runner's error handling. If the task cluster is down, the user gets immediate feedback in the admin rather than a hanging "PENDING" status.

### 3. Import pattern: lazy import inside `run()`

**Decision**: Import `django_q.tasks` inside the `run()` method, not at module level.

**Rationale**: Matches the pattern used by `CeleryCommandRunner` (imports `celery_tasks` inside `run()`) and `DjangoTaskRunner` (imports `django.tasks` lazily). Keeps the top-level import clean and only requires django-q2 when the backend is actually used.

### 4. `is_async` always `True`

**Decision**: `DjangoQ2CommandRunner` always returns `is_async=True`.

**Rationale**: Unlike the Django Tasks runner (which has an `ImmediateBackend` for sync testing), django-q2 always enqueues tasks asynchronously. There's no "immediate" mode in django-q2.

### 5. Example project uses Django ORM broker only

**Decision**: The example project configures `Q_CLUSTER = {'name': 'DJANGORM', 'orm': 'default'}` and does not require Docker Compose, Redis, or any external service.

**Rationale**: The ORM broker is the key differentiator of django-q2 — zero external dependencies. This makes the example easy to try (just `make init && make run && make worker`). Users who need Redis for higher throughput can switch to the Redis broker by changing `Q_CLUSTER` config.

### 6. Custom Schedule admin with registered command choices

**Decision**: In the example project, replace django-q2's default `ScheduleAdmin` with a custom version that changes the `func` field from a plain text input to a dropdown listing all registered management commands (from `_registry`).

**Implementation**: Unregister django-q2's default `ScheduleAdmin`, then register a custom `ModelAdmin` that overrides `get_form()` to set `func`'s widget to a `Select` with choices built from `_registry`. Each choice value is the dotted path to `execute_command` with the command name as args (e.g. `django_admin_runner.tasks.execute_command`), and the label is the command's display name. The user still fills in `args`/`kwargs` fields for command arguments.

**Alternative considered**: Auto-creating schedules per command (like Celery Beat tasks) — rejected because django-q2's Schedule model is general-purpose and the admin dropdown is a lighter, more flexible approach.

### 7. No per-command task registration (unlike Celery)

**Decision**: Use `async_task` directly with `execute_command`, without pre-registering named tasks per command.

**Rationale**: Unlike Celery (where named tasks appear in Flower/Beat), django-q2's task model is simpler. The `task_id` on `CommandExecution` is sufficient for tracking. This keeps the implementation minimal. Per-command named tasks can be added later if needed.

## Risks / Trade-offs

- **[Broker connectivity]** → Mitigated by try/except around `async_task`, marking execution as FAILED immediately.
- **[django-q2 import at test time]** → The `django-q2` extra is optional. Tests that require it should be gated behind a `pytest.importorskip("django_q")` or similar, or use mocking so CI doesn't need django-q2 installed for the main test suite.
- **[Duplicate pattern with RQ example]** → The RQ runner is intentionally a custom example showing the dotted-path interface. The django-q2 runner is a built-in first-class backend — different level of support, so the overlap is acceptable.
- **[ORM broker performance]** → The ORM broker uses database polling, which is fine for medium traffic. The example documents this trade-off and points users to the Redis broker for high-throughput scenarios.
