from django import forms
from django.core.management.base import BaseCommand

from django_admin_runner import FileOrPathField, register_command


@register_command(group="Test")
class Command(BaseCommand):
    help = "Command that uses widget= kwarg in add_argument"

    def add_arguments(self, parser):
        # widget= as a Widget instance — auto-detects CharField, swaps widget
        parser.add_argument(
            "--notes",
            widget=forms.Textarea(attrs={"rows": 3}),
            help="Notes field",
        )
        # widget= as a Field instance — replaces the field entirely
        parser.add_argument(
            "--source",
            widget=FileOrPathField(),
            default="input.csv",
            help="Source file or path",
        )
        # Plain arg — auto-detected, gets admin widget
        parser.add_argument("--name", help="Plain text field")

    def handle(self, *args, **options):
        pass
