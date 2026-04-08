from django.apps import AppConfig


class AdminRunnerConfig(AppConfig):
    name = "django_admin_runner"
    verbose_name = "Admin Runner"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from .registry import autodiscover_commands

        autodiscover_commands()
