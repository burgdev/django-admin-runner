import time

from django.core.management.base import BaseCommand

from django_admin_runner.registry import register_command


@register_command(group="Test")
class Command(BaseCommand):
    help = "Sleeps for a while (used to test worker shutdown)"

    def add_arguments(self, parser):
        parser.add_argument("--seconds", type=float, default=5.0)

    def handle(self, *args, **options):
        time.sleep(options["seconds"])
        self.stdout.write("done")
