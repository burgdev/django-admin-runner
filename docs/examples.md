# Examples

Four complete example projects are included in the repository under `examples/`.
Each demonstrates a different runner and integration pattern.

=== "Classic"

    ## Classic — Synchronous execution

    The simplest setup. Commands run synchronously using Django's built-in
    `ImmediateBackend` — no external workers or brokers needed. Perfect for
    development, low-traffic deployments, or quick tasks.

    ### Architecture

    ```mermaid
    graph LR
        A[Admin UI] --> B[DjangoTaskRunner]
        B --> C[ImmediateBackend]
        C --> D[Command runs inline]
        D --> E[Result saved to DB]
    ```

    ### Setup

    ```bash
    cd examples/classic
    make init    # install deps, migrate, create superuser (root/root)
    make run     # start dev server on port 8765
    ```

    Then visit `http://127.0.0.1:8765/admin/` and log in.

    ### Key configuration

    ```python
    # settings.py — Django 6.0 Tasks with ImmediateBackend (synchronous)
    TASKS = {
        "default": {
            "BACKEND": "django.tasks.backends.immediate.ImmediateBackend",
        }
    }
    # No ADMIN_RUNNER_BACKEND needed — DjangoTaskRunner is the default
    ```

    ### Example command

    ```python
    # books/management/commands/import_books.py
    from django_admin_runner import register_command, set_result_html

    @register_command(group="Import", params=["source", "dry_run", "limit"])
    class Command(BaseCommand):
        help = "Import books from a source file"

        def add_arguments(self, parser):
            parser.add_argument("--source", default="books.csv")
            parser.add_argument("--dry-run", action="store_true")
            parser.add_argument("--limit", type=int, default=0)

        def handle(self, *args, **options):
            count = min(options["limit"], 3) if options["limit"] else 3
            action = "Would import" if options["dry_run"] else "Imported"
            set_result_html(f"<h2>{action} {count} book(s)</h2>...")
    ```

=== "Unfold + Celery"

    ## Unfold + Celery — Async production setup

    A production-ready configuration with Celery for async task execution,
    Valkey (Redis-compatible) as the broker, and the Unfold admin theme
    for a polished UI. Demonstrates `FileOrPathField` for file uploads.

    ### Architecture

    ```mermaid
    graph LR
        A[Admin UI<br>Unfold theme] --> B[CeleryCommandRunner]
        B --> C[Celery broker<br>Valkey/Redis]
        C --> D[Celery worker]
        D --> E[Command executes]
        E --> F[Result saved to DB]
    ```

    ### Setup

    ```bash
    cd examples/unfold_celery
    docker compose up -d    # start Valkey
    make init                # install deps, migrate, create superuser
    make run                 # start Django on port 8765
    make worker              # start Celery worker (separate terminal)
    ```

    ### Key configuration

    ```python
    # settings.py
    ADMIN_RUNNER_BACKEND = "celery"
    ADMIN_RUNNER_UPLOAD_PATH = os.path.join(BASE_DIR, "uploads")

    CELERY_BROKER_URL = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND = "django-db"
    CELERY_RESULT_EXTENDED = True
    ```

    ### FileOrPathField demo

    This example shows `FileOrPathField` — users can either upload a file
    or type a server-side path:

    ```python
    # books/management/commands/import_books.py
    from django_admin_runner import FileOrPathField, register_command, set_result_html

    @register_command(group="Import", params=["source", "dry_run", "limit"])
    class Command(BaseCommand):
        help = "Import books from a CSV file"

        def add_arguments(self, parser):
            parser.add_argument(
                "--source",
                widget=FileOrPathField(),
                default="books.csv",
                help="CSV file path or upload",
            )
            parser.add_argument("--dry-run", action="store_true")
            parser.add_argument("--limit", type=int, default=0)

        def handle(self, *args, **options):
            with open(options["source"]) as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    # process each row...
                    ...
            set_result_html(f"<h2>Imported {count} book(s)</h2>...")
    ```

=== "Unfold + Django-Q2"

    ## Unfold + Django-Q2 — Zero-dependency async

    Async command execution using Django-Q2 with the Django ORM as the message
    broker. No Docker, no Redis — just the database. Unfold admin theme for a
    polished UI.

    ### Architecture

    ```mermaid
    graph LR
        A[Admin UI<br>Unfold theme] --> B[DjangoQ2CommandRunner]
        B --> C[Django ORM broker]
        C --> D[qcluster worker]
        D --> E[Command executes]
        E --> F[Result saved to DB]
    ```

    ### Setup

    ```bash
    cd examples/unfold_django_q2
    make init    # install deps, migrate, create superuser
    make run     # start Django on port 8766
    make worker  # start qcluster (separate terminal)
    ```

    No Docker or external services required.

    ### Key configuration

    ```python
    # settings.py
    ADMIN_RUNNER_BACKEND = "django-q2"

    Q_CLUSTER = {
        "name": "DJANGORM",
        "orm": "default",  # Django ORM as broker — no Redis needed
    }
    ```

    ### Scheduled tasks

    The example includes a custom `ScheduleAdmin` that replaces django-q2's
    default admin with a dropdown listing all registered management commands,
    making it easy to set up recurring commands without knowing dotted paths.

=== "Unfold + RQ"

    ## Unfold + RQ — Custom runner

    Demonstrates how to implement a custom runner for any queue backend.
    Uses Django-RQ with a `RqCommandRunner` subclassing `BaseCommandRunner`.
    The same pattern applies to Huey, Dramatiq, or any other task system.

    ### Architecture

    ```mermaid
    graph LR
        A[Admin UI<br>Unfold theme] --> B[RqCommandRunner<br>custom]
        B --> C[RQ queue<br>Valkey/Redis]
        C --> D[RQ worker]
        D --> E[Command executes]
        E --> F[Result saved to DB]
    ```

    ### Setup

    ```bash
    cd examples/unfold_rq
    docker compose up -d    # start Valkey
    make init                # install deps, migrate, create superuser
    make run                 # start Django on port 8765
    make worker              # start RQ worker (separate terminal)
    ```

    ### Key configuration

    ```python
    # settings.py
    ADMIN_RUNNER_BACKEND = "runners.RqCommandRunner"

    RQ_QUEUES = {
        "default": {"HOST": "localhost", "PORT": 6379, "DB": 0}
    }
    ```

    ### Custom runner implementation

    ```python
    # runners.py
    import django_rq
    from django.urls import reverse
    from django_admin_runner.runners import BaseCommandRunner, RunResult
    from django_admin_runner.tasks import execute_command

    class RqCommandRunner(BaseCommandRunner):
        backend = "rq"

        def run(self, command_name, kwargs, triggered_by, execution) -> RunResult:
            execution.backend = self.backend
            execution.save(update_fields=["backend"])

            job = django_rq.enqueue(execute_command, command_name, kwargs, execution.pk)

            execution.task_id = job.id
            execution.save(update_fields=["task_id"])

            return RunResult(
                execution=execution,
                redirect_url=reverse(
                    "admin:django_admin_runner_commandexecution_change",
                    args=[execution.pk],
                ),
                is_async=True,
                backend=self.backend,
                task_id=job.id,
            )
    ```

    See [Custom Runner](guides/custom-runner.md) for the full guide on implementing
    your own runner.

---

## Comparison

| | Classic | Unfold + Celery | Unfold + Django-Q2 | Unfold + RQ |
|---|---|---|---|---|
| **Runner** | DjangoTaskRunner (default) | CeleryCommandRunner | DjangoQ2CommandRunner | Custom RqCommandRunner |
| **Execution** | Synchronous | Asynchronous | Asynchronous | Asynchronous |
| **Broker** | None | Valkey/Redis | Django ORM | Valkey/Redis |
| **Worker** | None | Celery worker | qcluster | RQ worker |
| **Theme** | Plain Django admin | Unfold | Unfold | Unfold |
| **File uploads** | No | Yes (`FileOrPathField`) | No | No |
| **Best for** | Dev / simple tasks | Production async | Lightweight async | Learning custom runners |
