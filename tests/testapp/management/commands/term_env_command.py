import os

from django.core.management.base import BaseCommand

from django_admin_runner.registry import register_command


@register_command(group="Test")
class Command(BaseCommand):
    help = "Writes COLUMNS/LINES from the environment to stdout"

    def handle(self, *args, **options):
        self.stdout.write(f"COLUMNS={os.environ.get('COLUMNS')}")
        self.stdout.write(f"LINES={os.environ.get('LINES')}")
