from django.apps import AppConfig


class BooksConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "books"

    def ready(self):
        import admin  # noqa: F401 — registers Unfold-styled django-q2 admins
