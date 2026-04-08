from django.core.management.base import BaseCommand

from django_admin_runner.registry import register_command


@register_command(group="Test", exclude_params=["internal"])
class Command(BaseCommand):
    help = "Command to test hidden= and exclude_params"

    def add_arguments(self, parser):
        parser.add_argument("--public", help="Visible parameter")
        parser.add_argument("--secret", hidden=True, help="Hidden via hidden=True")
        parser.add_argument("--internal", help="Excluded via exclude_params registry option")

    def handle(self, *args, **options):
        self.stdout.write("hidden command ran")
