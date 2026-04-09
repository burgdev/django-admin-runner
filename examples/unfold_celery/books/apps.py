from django.apps import AppConfig


class BooksConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "books"

    def ready(self):
        # Import celery_app so it becomes the default Celery application.
        # Without this, the Django web process never sees celery_app.py and
        # shared_task() falls back to Celery's default AMQP broker.
        import celery_app  # noqa: F401
