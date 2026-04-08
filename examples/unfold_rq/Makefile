.PHONY: init run worker

init:
	uv sync
	uv run manage.py migrate
	DJANGO_SUPERUSER_PASSWORD=root uv run manage.py createsuperuser \
		--username root --email root@example.com --noinput

run:
	uv run manage.py runserver 8765

worker:
	uv run manage.py rqworker
