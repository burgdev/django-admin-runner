from django.core.management.base import BaseCommand

from django_admin_runner.registry import register_command


@register_command(group="Test")
class Command(BaseCommand):
    help = "Writes a configurable number of 'x' characters to stdout"

    def add_arguments(self, parser):
        parser.add_argument("--chars", type=int, default=100)

    def handle(self, *args, **options):
        self.stdout.write("x" * options["chars"])
