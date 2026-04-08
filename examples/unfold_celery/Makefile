.PHONY: init run worker beat

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
