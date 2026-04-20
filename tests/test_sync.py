from unittest.mock import patch

import pytest

from django_admin_runner.models import RegisteredCommand
from django_admin_runner.registry import _registry
from django_admin_runner.sync import sync_registered_commands


@pytest.mark.django_db
class TestSyncRegisteredCommands:
    def test_fresh_db_creates_rows(self):
        """On a fresh DB, every _registry entry gets a RegisteredCommand row."""
        sync_registered_commands()
        assert RegisteredCommand.objects.count() == len(_registry)
        for name in _registry:
            assert RegisteredCommand.objects.filter(name=name, active=True).exists()

    def test_sync_creates_correct_metadata(self):
        """Created rows have metadata matching their registry entries."""
        sync_registered_commands()
        for name, entry in _registry.items():
            rc = RegisteredCommand.objects.get(name=name)
            assert rc.group == entry["group"]
            assert rc.display_name == entry["display_name"]
            assert rc.app_label == entry["app_label"]
            assert rc.active is True

    def test_update_existing(self):
        """Metadata changes in _registry are propagated to existing rows."""
        sync_registered_commands()
        # Simulate a group change in the registry
        entry = _registry["simple_command"]
        original_group = entry["group"]
        entry["group"] = "New Group"
        try:
            sync_registered_commands()
            rc = RegisteredCommand.objects.get(name="simple_command")
            assert rc.group == "New Group"
        finally:
            entry["group"] = original_group

    def test_deactivate_removed(self):
        """Commands in DB but not in _registry are deactivated."""
        sync_registered_commands()
        # Create a phantom command not in registry
        RegisteredCommand.objects.create(
            name="phantom_command",
            group="Phantom",
            display_name="Phantom Command",
        )
        assert RegisteredCommand.objects.filter(name="phantom_command", active=True).exists()

        sync_registered_commands()
        rc = RegisteredCommand.objects.get(name="phantom_command")
        assert rc.active is False

    def test_reactivate_re_added(self):
        """A deactivated command that reappears in _registry is reactivated."""
        sync_registered_commands()
        # Deactivate an existing command and remove it from registry
        entry = _registry.pop("simple_command")
        sync_registered_commands()
        rc = RegisteredCommand.objects.get(name="simple_command")
        assert rc.active is False

        # Re-add it
        _registry["simple_command"] = entry
        sync_registered_commands()
        rc.refresh_from_db()
        assert rc.active is True

    def test_idempotent(self):
        """Running sync twice with same state produces same result."""
        sync_registered_commands()
        count_after_first = RegisteredCommand.objects.count()
        sync_registered_commands()
        count_after_second = RegisteredCommand.objects.count()
        assert count_after_first == count_after_second

    def test_missing_table_handled_gracefully(self):
        """OperationalError (table not exist) is handled silently."""
        from django.db import OperationalError

        with patch.object(
            RegisteredCommand.objects, "all", side_effect=OperationalError("no such table")
        ):
            # Should not raise
            sync_registered_commands()
