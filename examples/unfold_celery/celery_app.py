import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

app = Celery("unfold_celery")
app.config_from_object("django.conf:settings", namespace="CELERY")

# Discover tasks in installed apps ('tasks.py') and also our custom module.
app.autodiscover_tasks()
app.autodiscover_tasks(["django_admin_runner"], related_name="celery_tasks")
