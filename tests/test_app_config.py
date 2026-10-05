"""AppConfig.ready() must not touch the database.

Regression tests for the gunicorn ``--preload`` incident: DB access during
``django.setup()`` opens pooled connections pre-fork, and wedges forked
workers when the pool's background threads die. The sync runs via the
``post_migrate`` signal and the ``admin_runner_sync`` command instead.
"""

from unittest.mock import patch

import pytest
from django.apps import apps
from django.core.management import call_command
from django.db import connection
from django.db.backends.signals import connection_created
from django.db.models.signals import post_migrate
from django.test import override_settings
from django.test.utils import CaptureQueriesContext

from django_admin_runner.models import RegisteredCommand, ScheduledCommand
from django_admin_runner.registry import _registry


class TestReadyPerformsNoDatabaseAccess:
    @pytest.mark.django_db
    def test_ready_executes_no_queries(self):
        config = apps.get_app_config("django_admin_runner")
        with CaptureQueriesContext(connection) as ctx:
            config.ready()
        assert len(ctx.captured_queries) == 0

    def test_ready_opens_no_connection(self):
        config = apps.get_app_config("django_admin_runner")
        created = []

        def on_connection_created(sender, connection, **kwargs):
            created.append(connection.alias)

        connection_created.connect(on_connection_created, weak=False)
        try:
            config.ready()
        finally:
            connection_created.disconnect(on_connection_created)
        assert created == []

    def test_ready_does_not_call_sync(self):
        config = apps.get_app_config("django_admin_runner")
        with (
            patch("django_admin_runner.sync.sync_registered_commands") as sync_commands,
            patch("django_admin_runner.sync.sync_declarative_schedules") as sync_schedules,
        ):
            config.ready()
        sync_commands.assert_not_called()
        sync_schedules.assert_not_called()

    def test_sync_on_ready_opt_in(self):
        """ADMIN_RUNNER_SYNC_ON_READY=True restores the legacy ready() sync."""
        config = apps.get_app_config("django_admin_runner")
        with (
            override_settings(ADMIN_RUNNER_SYNC_ON_READY=True),
            patch("django_admin_runner.sync.sync_registered_commands") as sync_commands,
            patch("django_admin_runner.sync.sync_declarative_schedules") as sync_schedules,
        ):
            config.ready()
        sync_commands.assert_called_once()
        sync_schedules.assert_called_once()


@pytest.mark.django_db
class TestPostMigrateSync:
    def test_signal_for_this_app_syncs(self):
        RegisteredCommand.objects.all().delete()
        ScheduledCommand.objects.all().delete()

        config = apps.get_app_config("django_admin_runner")
        post_migrate.send(
            sender=config,
            app_config=config,
            using="default",
            verbosity=0,
            interactive=False,
        )

        assert set(RegisteredCommand.objects.values_list("name", flat=True)) == set(_registry)
        assert RegisteredCommand.objects.filter(active=True).count() == len(_registry)

    def test_signal_for_other_apps_ignored(self):
        RegisteredCommand.objects.all().delete()

        other = apps.get_app_config("auth")
        post_migrate.send(
            sender=other,
            app_config=other,
            using="default",
            verbosity=0,
            interactive=False,
        )

        assert RegisteredCommand.objects.count() == 0

    def test_full_signal_round_syncs_once(self):
        """post_migrate fires once per installed app — sync must run exactly once."""
        with (
            patch("django_admin_runner.sync.sync_registered_commands") as sync_commands,
            patch("django_admin_runner.sync.sync_declarative_schedules") as sync_schedules,
        ):
            for config in apps.get_app_configs():
                post_migrate.send(
                    sender=config,
                    app_config=config,
                    using="default",
                    verbosity=0,
                    interactive=False,
                )
        sync_commands.assert_called_once()
        sync_schedules.assert_called_once()

    @pytest.mark.django_db(transaction=True)
    def test_migrate_command_triggers_sync(self):
        """End to end: migrate emits post_migrate, which materializes the rows."""
        RegisteredCommand.objects.all().delete()
        ScheduledCommand.objects.all().delete()

        call_command("migrate", verbosity=0, interactive=False)

        assert RegisteredCommand.objects.count() == len(_registry)
        for name in _registry:
            assert RegisteredCommand.objects.filter(name=name, active=True).exists()
