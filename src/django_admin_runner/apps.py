from django.apps import AppConfig
from django.conf import settings


class AdminRunnerConfig(AppConfig):
    name = "django_admin_runner"
    verbose_name = "Admin Runner"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from .registry import autodiscover_commands

        # Import-time registry population only. ready() runs inside
        # django.setup() — gunicorn --preload masters, collectstatic during
        # image builds, ... — where the database may be unreachable or must
        # not be touched (e.g. pooled connections opened pre-fork). Syncing
        # happens on post_migrate and via the admin_runner_sync command.
        autodiscover_commands()

        from django.db.models.signals import post_migrate

        post_migrate.connect(
            _sync_on_post_migrate,
            dispatch_uid="django_admin_runner.sync_on_post_migrate",
        )

        # Legacy opt-in for consumers that cannot run migrate or the sync
        # command during deploy. Default is off: no DB access at ready().
        if getattr(settings, "ADMIN_RUNNER_SYNC_ON_READY", False):
            from .sync import sync_all

            sync_all()


def _sync_on_post_migrate(sender, *, app_config=None, **kwargs) -> None:
    """Run the full sync once per migrate — the signal fires for every app."""
    config = app_config if app_config is not None else sender
    if getattr(config, "label", None) != "django_admin_runner":
        return

    from .sync import sync_all

    sync_all()
