"""Tests for the admin_runner_sync management command."""

from io import StringIO

import pytest
from django.core.management import call_command

from django_admin_runner.models import RegisteredCommand, ScheduledCommand
from django_admin_runner.registry import _registry
from django_admin_runner.schedules import CronSchedule, IntervalSchedule


@pytest.fixture(autouse=True)
def _registry_snapshot():
    """Restore registry entries after tests that mutate declarations."""
    snapshot = {name: dict(entry) for name, entry in _registry.items()}
    yield
    _registry.clear()
    _registry.update(snapshot)


@pytest.mark.django_db
class TestAdminRunnerSyncCommand:
    def test_syncs_registered_commands(self):
        RegisteredCommand.objects.all().delete()
        ScheduledCommand.objects.all().delete()

        call_command("admin_runner_sync", verbosity=0)

        assert set(RegisteredCommand.objects.values_list("name", flat=True)) == set(_registry)
        assert RegisteredCommand.objects.filter(active=True).count() == len(_registry)

    def test_syncs_declarative_schedules(self):
        RegisteredCommand.objects.all().delete()
        ScheduledCommand.objects.all().delete()
        _registry["simple_command"]["schedules"] = [
            CronSchedule("15 4 * * *", name="nightly"),
            IntervalSchedule(15, name="often"),
        ]

        call_command("admin_runner_sync", verbosity=0)

        rows = ScheduledCommand.objects.filter(source=ScheduledCommand.Source.CODE)
        assert rows.get(label="nightly").cron == "15 4 * * *"
        assert rows.get(label="often").interval_minutes == 15

    def test_writes_success_message(self):
        out = StringIO()
        call_command("admin_runner_sync", stdout=out)
        assert "synced" in out.getvalue()

    def test_idempotent(self):
        call_command("admin_runner_sync", verbosity=0)
        count = RegisteredCommand.objects.count()
        call_command("admin_runner_sync", verbosity=0)
        assert RegisteredCommand.objects.count() == count
