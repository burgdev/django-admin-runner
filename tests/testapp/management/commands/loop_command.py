import time

from django.core.management.base import BaseCommand

from django_admin_runner.registry import register_command


@register_command(group="Test")
class Command(BaseCommand):
    help = "Prints lines in a loop (used to test graceful cancellation)"

    def add_arguments(self, parser):
        parser.add_argument("--iterations", type=int, default=1000)
        parser.add_argument("--interval", type=float, default=0.01)

    def handle(self, *args, **options):
        for i in range(options["iterations"]):
            self.stdout.write(f"line {i}")
            time.sleep(options["interval"])
        self.stdout.write("done")
