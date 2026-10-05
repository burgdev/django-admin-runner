from django.core.management.base import BaseCommand

from django_admin_runner.sync import sync_all


class Command(BaseCommand):
    help = (
        "Sync @register_command registry entries into RegisteredCommand rows "
        "and materialize declarative (source=code) schedules. Runs "
        "automatically after migrate; call manually to re-sync after code "
        "changes or from worker entrypoints."
    )

    def handle(self, *args, **options):
        sync_all()
        if options.get("verbosity", 1):
            self.stdout.write(
                self.style.SUCCESS("django-admin-runner: commands and schedules synced")
            )
