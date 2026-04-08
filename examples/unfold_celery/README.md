# Example: Unfold + Celery

Unfold-themed admin with asynchronous command execution via Celery and Valkey
(Redis-compatible broker). Demonstrates `ADMIN_RUNNER_BACKEND = "celery"`.

## Prerequisites

- Docker (for Valkey)

## Setup

```bash
cd examples/unfold_celery
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

# Terminal 2 — Celery worker
uv run celery -A celery_app worker -l info
```

Visit http://localhost:8000/admin/ and navigate to
**Admin Runner → Run Management Commands**.

Commands are dispatched to the Celery worker asynchronously. Refresh the
execution record to see the result once the worker finishes.

## Notes

- `CELERY_BROKER_URL` defaults to `redis://localhost:6379/0` and can be
  overridden via the environment variable of the same name.
- `django-celery-results` is used as the result backend (`CELERY_RESULT_BACKEND
  = "django-db"`), storing task results in Django's database.
- `django-celery-beat` is included for periodic task scheduling (optional for
  running commands from the admin).
