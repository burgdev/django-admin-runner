import decimal

from django.core.management.base import BaseCommand

from django_admin_runner.registry import register_command


@register_command(group="Test")
class Command(BaseCommand):
    help = "Command with various type= arguments"

    def add_arguments(self, parser):
        parser.add_argument("--interval", type=float, default=0.5, help="Polling interval")
        parser.add_argument("--amount", type=decimal.Decimal, default="1.00", help="Amount")
        parser.add_argument("--name", default="world", help="A name (no type)")

    def handle(self, *args, **options):
        self.stdout.write(f"interval={options['interval']} amount={options['amount']}")
