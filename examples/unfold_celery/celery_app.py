import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

app = Celery("unfold_celery")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Register django-admin-runner's Celery Beat schedulable task.
# (autodiscover_tasks only finds 'tasks.py'; this module is named 'celery_tasks'.)
import django_admin_runner.celery_tasks  # noqa: F401, E402
