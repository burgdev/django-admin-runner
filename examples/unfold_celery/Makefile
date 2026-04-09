.PHONY: help init run worker beat

help:
	@echo "Available targets:"
	@echo "  init    - Set up the project (install deps, migrate, create superuser)"
	@echo "  run     - Start the Django dev server on port 8765"
	@echo "  worker  - Start the Celery worker"
	@echo "  beat    - Start Celery Beat scheduler (with Django DB backend)"

init:
	uv sync
	uv run manage.py migrate
	DJANGO_SUPERUSER_PASSWORD=root uv run manage.py createsuperuser \
		--username root --email root@example.com --noinput

run:
	uv run manage.py runserver 8765

worker:
	uv run celery -A celery_app worker -l info

beat:
	uv run celery -A celery_app beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
