from django.core.management.base import BaseCommand

from django_admin_runner.registry import register_command


@register_command(group="Test")
class Command(BaseCommand):
    help = "Simple command with no arguments"

    def handle(self, *args, **options):
        self.stdout.write("simple output")
