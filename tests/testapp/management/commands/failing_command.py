from django.core.management.base import BaseCommand, CommandError

from django_admin_runner.registry import register_command


@register_command(group="Test")
class Command(BaseCommand):
    help = "Command that always raises CommandError"

    def handle(self, *args, **options):
        raise CommandError("intentional failure")
