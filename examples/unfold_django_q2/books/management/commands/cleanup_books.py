from django.core.management.base import BaseCommand

from django_admin_runner import CronSchedule, register_command


@register_command(
    group="Maintenance",
    exclude_params=["verbosity"],
    # Declarative schedule: materialized as a `source=code` ScheduledCommand
    # row on startup and run nightly at 03:00 by qcluster.
    schedule=CronSchedule("0 3 * * *", kwargs={"older_than": 90}),
)
class Command(BaseCommand):
    help = "Remove duplicate and orphaned book records"

    def add_arguments(self, parser):
        parser.add_argument("--older-than", type=int, default=90, help="Days threshold")

    def handle(self, *args, **options):
        self.stdout.write(f"Cleaning up records older than {options['older_than']} days")
