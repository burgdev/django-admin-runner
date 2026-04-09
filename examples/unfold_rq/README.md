# Example: Unfold + Django-RQ

Unfold-themed admin with asynchronous command execution via Django-RQ and
Valkey. Demonstrates how to implement a **custom runner** by subclassing
`BaseCommandRunner` (see `runners.py`).

## Prerequisites

- Docker (for Valkey)

## Setup & run

```bash
cd examples/unfold_rq
docker compose up -d   # start Valkey on port 6379
make init              # install deps, migrate, create superuser (root/root)
make run               # start Django dev server on port 8765
```

Open a second terminal for the RQ worker:

```bash
make worker            # start RQ worker
```

Visit <http://localhost:8765/admin/> (login: `root` / `root`) and navigate to
**Run Commands** in the sidebar.

## Available `make` targets

```
make          # show this help
make init     # install deps, migrate, create superuser
make run      # start Django dev server on port 8765
make worker   # start RQ worker
```

## Custom runner

`runners.py` contains `RqCommandRunner`, a minimal example of writing your own
runner for any queue backend:

```python
ADMIN_RUNNER_BACKEND = "runners.RqCommandRunner"
```

The class subclasses `BaseCommandRunner`, enqueues the built-in
`execute_command` function via `django_rq.enqueue`, and returns a `RunResult`.
