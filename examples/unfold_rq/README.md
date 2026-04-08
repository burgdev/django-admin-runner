# Example: Unfold + Django-RQ

Unfold-themed admin with asynchronous command execution via Django-RQ and
Valkey. Demonstrates how to implement a **custom runner** by subclassing
`BaseCommandRunner` (see `runners.py`).

## Prerequisites

- Docker (for Valkey)

## Setup

```bash
cd examples/unfold_rq
uv sync
docker compose up -d          # starts Valkey on port 6379
uv run python manage.py migrate
uv run python manage.py createsuperuser
```

## Run

Open two terminals:

```bash
# Terminal 1 — Django dev server
uv run python manage.py runserver

# Terminal 2 — RQ worker
uv run python manage.py rqworker
```

Visit http://localhost:8000/admin/ and navigate to
**Admin Runner → Run Management Commands**.

## Custom runner

`runners.py` contains `RqCommandRunner`, a minimal example of writing your own
runner for any queue backend:

```python
ADMIN_RUNNER_BACKEND = "runners.RqCommandRunner"
```

The class subclasses `BaseCommandRunner`, enqueues the built-in
`execute_command` function via `django_rq.enqueue`, and returns a `RunResult`.
