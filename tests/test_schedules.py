"""Tests for scheduling: value objects, model, entry point, materializer, sync, admin."""

import ast
import sys
import unittest.mock
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import Client, override_settings
from django.utils.timezone import localtime

from django_admin_runner.models import CommandExecution, RegisteredCommand, ScheduledCommand
from django_admin_runner.registry import _registry
from django_admin_runner.runners import BaseCommandRunner, ScheduleNotSupportedError
from django_admin_runner.schedules import (
    ClockedSchedule,
    CronSchedule,
    IntervalSchedule,
    Schedule,
    materialize_schedule,
    remove_native_schedule,
)
from django_admin_runner.sync import sync_declarative_schedules
from django_admin_runner.tasks import run_scheduled_command


@pytest.fixture(autouse=True)
def _registry_snapshot():
    """Restore registry entries after tests that mutate declarations."""
    snapshot = {name: dict(entry) for name, entry in _registry.items()}
    yield
    _registry.clear()
    _registry.update(snapshot)


@pytest.fixture
def active_command(db):
    sync_commands()
    return RegisteredCommand.objects.get(name="simple_command")


def sync_commands():
    from django_admin_runner.sync import sync_registered_commands

    sync_registered_commands()


# ---------------------------------------------------------------------------
# Value objects (4.3)
# ---------------------------------------------------------------------------


class TestScheduleValueObjects:
    def test_cron_valid(self):
        sched = CronSchedule("15 4 * * *")
        assert sched.kind == "cron"
        assert sched.cron == "15 4 * * *"
        assert sched.enabled is True
        assert sched.model_kwargs()["cron"] == "15 4 * * *"

    def test_cron_invalid_raises_at_construction(self):
        with pytest.raises(ValueError, match="[Cc]ron"):
            CronSchedule("not-a-cron")

    def test_interval_positive_required(self):
        assert IntervalSchedule(30).interval_minutes == 30
        with pytest.raises(ValueError, match="positive"):
            IntervalSchedule(0)
        with pytest.raises(ValueError, match="positive"):
            IntervalSchedule(-5)

    def test_clocked_requires_future(self):
        with pytest.raises(ValueError, match="future"):
            ClockedSchedule(datetime.now(UTC) - timedelta(minutes=1))

    def test_clocked_naive_made_aware(self):
        at = datetime(2999, 1, 1, 12, 0, 0)
        sched = ClockedSchedule(at)
        assert sched.run_at.tzinfo is not None

    def test_clocked_requires_datetime(self):
        with pytest.raises(TypeError):
            ClockedSchedule("2999-01-01")

    def test_unknown_kind_rejected(self):
        with pytest.raises(ValueError, match="kind"):
            Schedule("weekly")

    def test_frozen(self):
        sched = CronSchedule("0 0 * * *")
        with pytest.raises(AttributeError):
            sched.cron = "1 0 * * *"


class TestRegisterCommandSchedules:
    def test_single_defaults_name_to_command(self):
        sched = CronSchedule("0 12 * * *")

        @register_with("renamed_single", sched)
        def _apply():
            pass

        assert _registry["renamed_single"]["schedules"][0].name == "renamed_single"

    def test_multiple_require_explicit_names(self):
        with pytest.raises(ValueError, match="explicit"):
            register_entry("multi_cmd", [CronSchedule("0 1 * * *"), IntervalSchedule(5)])

    def test_duplicate_names_rejected(self):
        with pytest.raises(ValueError, match="[Dd]uplicate"):
            register_entry(
                "dup_cmd",
                [CronSchedule("0 1 * * *", name="x"), IntervalSchedule(5, name="x")],
            )

    def test_multiple_recorded(self):
        register_entry(
            "multi_cmd",
            [
                CronSchedule("0 1 * * *", name="nightly", kwargs={"full": True}),
                IntervalSchedule(15, name="often"),
            ],
        )
        names = [s.name for s in _registry["multi_cmd"]["schedules"]]
        assert names == ["nightly", "often"]


def register_entry(name, schedule):
    from django_admin_runner.registry import _normalize_schedules

    _registry[name] = {"name": name, "schedules": _normalize_schedules(schedule, name)}


def register_with(name, schedule):
    def deco(fn):
        register_entry(name, schedule)
        return fn

    return deco


# ---------------------------------------------------------------------------
# Model validation (5.1)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestScheduledCommandValidation:
    def make(self, **kwargs):
        return ScheduledCommand(
            command_name=kwargs.pop("command_name", "simple_command"),
            kind=kwargs.pop("kind", ScheduledCommand.Kind.CRON),
            kwargs=kwargs.pop("kwargs", {}),
            **kwargs,
        )

    def test_valid_cron(self, active_command):
        self.make(cron="15 4 * * *").full_clean()

    def test_invalid_cron_rejected(self, active_command):
        with pytest.raises(ValidationError) as excinfo:
            self.make(cron="nonsense").full_clean()
        assert "cron" in excinfo.value.error_dict

    def test_missing_cron_rejected(self, active_command):
        with pytest.raises(ValidationError) as excinfo:
            self.make(cron="").full_clean()
        assert "cron" in excinfo.value.error_dict

    def test_interval_must_be_positive(self, active_command):
        sched = self.make(kind=ScheduledCommand.Kind.INTERVAL, interval_minutes=0)
        with pytest.raises(ValidationError) as excinfo:
            sched.full_clean()
        assert "interval_minutes" in excinfo.value.error_dict

    def test_clocked_must_be_future(self, active_command):
        sched = self.make(
            kind=ScheduledCommand.Kind.CLOCKED,
            run_at=datetime.now(UTC) - timedelta(hours=1),
        )
        with pytest.raises(ValidationError) as excinfo:
            sched.full_clean()
        assert "run_at" in excinfo.value.error_dict

    def test_unknown_command_rejected(self, active_command):
        with pytest.raises(ValidationError) as excinfo:
            self.make(command_name="no_such_command", cron="0 0 * * *").full_clean()
        assert "command_name" in excinfo.value.error_dict

    def test_inactive_command_rejected(self, active_command):
        RegisteredCommand.objects.filter(name="simple_command").update(active=False)
        with pytest.raises(ValidationError):
            self.make(cron="0 0 * * *").full_clean()

    def test_stale_kwargs_rejected(self, active_command):
        with pytest.raises(ValidationError) as excinfo:
            self.make(cron="0 0 * * *", kwargs={"no_longer_exists": 1}).full_clean()
        assert "kwargs" in excinfo.value.error_dict

    def test_valid_kwargs_accepted(self, active_command):
        # param_command has --count/--mode/--tag/--name/--verbose
        RegisteredCommand.objects.get_or_create(name="param_command")
        sched = ScheduledCommand(
            command_name="param_command",
            kind=ScheduledCommand.Kind.CRON,
            cron="0 0 * * *",
            kwargs={"count": 3, "mode": "fast", "verbose": True},
        )
        sched.full_clean()

    def test_multiple_schedules_per_command_independent(self, active_command):
        self.make(cron="0 1 * * *", label="a").save()
        self.make(kind=ScheduledCommand.Kind.INTERVAL, interval_minutes=5, label="b").save()
        assert ScheduledCommand.objects.filter(command_name="simple_command").count() == 2

    def test_schedule_summary(self, active_command):
        assert self.make(cron="*/5 * * * *").schedule_summary() == "*/5 * * * *"
        assert self.make(kind="interval", interval_minutes=7).schedule_summary() == "every 7 min"


# ---------------------------------------------------------------------------
# run_scheduled_command (5.3)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRunScheduledCommand:
    def test_execution_created_and_succeeds(self, active_command):
        run_scheduled_command("simple_command", {})
        execution = CommandExecution.objects.latest("pk")
        assert execution.command_name == "simple_command"
        assert execution.status == CommandExecution.Status.SUCCESS
        assert execution.triggered_by is None
        assert "simple output" in execution.output_text("stdout")

    def test_traceability_fk(self, active_command):
        schedule = ScheduledCommand.objects.create(
            command_name="simple_command", kind="cron", cron="0 0 * * *", label="daily"
        )
        run_scheduled_command("simple_command", {}, schedule_pk=schedule.pk)
        execution = CommandExecution.objects.latest("pk")
        assert execution.schedule_id == schedule.pk

    def test_overlapping_run_skipped(self, active_command):
        # One execution per schedule at a time: while a previous run is
        # still pending/running, the next slot is skipped.
        schedule = ScheduledCommand.objects.create(
            command_name="simple_command", kind="cron", cron="0 0 * * *", label="daily"
        )
        CommandExecution.objects.create(
            command_name="simple_command",
            schedule=schedule,
            status=CommandExecution.Status.RUNNING,
        )
        run_scheduled_command("simple_command", {}, schedule_pk=schedule.pk)
        assert CommandExecution.objects.count() == 1

    def test_stale_overlapping_run_does_not_block(self, active_command, settings):
        # A pending/running row older than ADMIN_RUNNER_STALE_AFTER is
        # assumed dead — the schedule must not starve.
        from datetime import timedelta

        from django.utils.timezone import now

        settings.ADMIN_RUNNER_STALE_AFTER = 60
        schedule = ScheduledCommand.objects.create(
            command_name="simple_command", kind="cron", cron="0 0 * * *", label="daily"
        )
        stale = CommandExecution.objects.create(
            command_name="simple_command",
            schedule=schedule,
            status=CommandExecution.Status.RUNNING,
        )
        CommandExecution.objects.filter(pk=stale.pk).update(created_at=now() - timedelta(hours=2))
        run_scheduled_command("simple_command", {}, schedule_pk=schedule.pk)
        assert CommandExecution.objects.count() == 2

    def test_failure_path(self, active_command):
        RegisteredCommand.objects.get_or_create(name="failing_command")
        with pytest.raises(Exception):
            run_scheduled_command("failing_command", {})
        execution = CommandExecution.objects.latest("pk")
        assert execution.status == CommandExecution.Status.FAILED
        assert execution.output_text("stderr")

    def test_fired_clocked_schedule_disabled(self, active_command):
        schedule = ScheduledCommand.objects.create(
            command_name="simple_command",
            kind="clocked",
            run_at=datetime.now(UTC) + timedelta(hours=1),
            backend_schedule_key="42",
        )
        run_scheduled_command("simple_command", {}, schedule_pk=schedule.pk)
        schedule.refresh_from_db()
        assert schedule.enabled is False
        assert schedule.backend_schedule_key == ""


# ---------------------------------------------------------------------------
# Fake django_q for materializer tests (not installed in CI)
# ---------------------------------------------------------------------------


class _FakeQuerySet:
    def __init__(self, store, keys):
        self._store = store
        self._keys = keys

    def first(self):
        return self._store[self._keys[0]] if self._keys else None

    def delete(self):
        for key in self._keys:
            del self._store[key]


class _FakeScheduleManager:
    def __init__(self):
        self.store: dict[str, dict] = {}
        self._next_pk = 0

    def create(self, **kwargs):
        self._next_pk += 1
        kwargs["pk"] = str(self._next_pk)
        obj = _FakeScheduleRow(self, kwargs)
        self.store[str(obj.pk)] = obj
        return obj

    def filter(self, pk=None):
        keys = [str(pk)] if str(pk) in self.store else []
        return _FakeQuerySet(self.store, keys)


class _FakeScheduleRow:
    def __init__(self, manager, values):
        self._manager = manager
        self.pk = values.pop("pk")
        for key, value in values.items():
            setattr(self, key, value)

    def save(self):
        pass

    def delete(self):
        self._manager.store.pop(str(self.pk), None)


@contextmanager
def fake_django_q():
    manager = _FakeScheduleManager()
    models = unittest.mock.MagicMock(Schedule=unittest.mock.MagicMock(objects=manager))
    models.Schedule.objects = manager
    mock_django_q = unittest.mock.MagicMock(models=models)
    saved = {k: sys.modules.get(k) for k in ("django_q", "django_q.models")}
    sys.modules["django_q"] = mock_django_q
    sys.modules["django_q.models"] = models
    try:
        yield manager
    finally:
        for key, orig in saved.items():
            if orig is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = orig


@pytest.mark.django_db
class TestDjangoQ2Materializer:
    def make_schedule(self, **kwargs):
        return ScheduledCommand.objects.create(
            command_name="simple_command",
            kind=kwargs.pop("kind", "cron"),
            cron=kwargs.pop("cron", "15 4 * * *"),
            **kwargs,
        )

    def runner(self):
        from django_admin_runner.runners.django_q2 import DjangoQ2CommandRunner

        return DjangoQ2CommandRunner()

    def test_supported_kinds(self):
        assert self.runner().supported_schedule_kinds == frozenset({"cron", "interval", "clocked"})

    def test_create_maps_func_and_args(self, active_command):
        with fake_django_q() as manager:
            sched = self.make_schedule(kwargs={"count": 2})
            runner = self.runner()
            key = runner.create_schedule(sched)
            (native,) = manager.store.values()
            assert native.func == "django_admin_runner.tasks.run_scheduled_command"
            assert ast.literal_eval(native.args) == ("simple_command", {"count": 2}, sched.pk)
            assert native.schedule_type == "C"
            assert native.cron == "15 4 * * *"
            assert key == native.pk

    def test_interval_and_clocked_mapping(self, active_command):
        with fake_django_q() as manager:
            runner = self.runner()
            sched = self.make_schedule(kind="interval", cron="", interval_minutes=10)
            runner.create_schedule(sched)
            sched2 = self.make_schedule(kind="clocked", cron="", run_at=datetime.now(UTC))
            runner.create_schedule(sched2)
            types = {n.schedule_type for n in manager.store.values()}
            assert types == {"I", "O"}

    def test_args_parse_with_django_q_scheduler(self, active_command):
        """django-q2 parses ``Schedule.args`` with ``ast.literal_eval`` —
        JSON booleans/null would crash the scheduler ("Could not create
        task from schedule")."""
        import ast

        RegisteredCommand.objects.get_or_create(name="param_command")
        sched = ScheduledCommand.objects.create(
            command_name="param_command",
            kind="cron",
            cron="0 0 * * *",
            kwargs={"verbose": True, "count": 3, "mode": None},
        )
        with fake_django_q() as manager:
            self.runner().create_schedule(sched)
            (native,) = manager.store.values()
            parsed = ast.literal_eval(native.args)  # exactly what scheduler.py does
        assert parsed == ("param_command", {"verbose": True, "count": 3, "mode": None}, sched.pk)

    def test_args_unpack_into_run_scheduled_command(self, active_command):
        """django-q2 wraps literal_eval results that are not tuples as a
        single argument — the stored args must parse to a *tuple* so the
        worker can unpack (name, kwargs, schedule_pk)."""
        import ast
        import inspect

        from django_admin_runner.tasks import run_scheduled_command

        sched = self.make_schedule(kwargs={"count": 2})
        with fake_django_q() as manager:
            self.runner().create_schedule(sched)
            (native,) = manager.store.values()
            parsed = ast.literal_eval(native.args)
        assert isinstance(parsed, tuple)
        params = list(inspect.signature(run_scheduled_command).parameters)
        assert len(parsed) == len(params)

    def test_interval_repeats_mapped(self, active_command):
        with fake_django_q() as manager:
            runner = self.runner()
            sched = self.make_schedule(kind="interval", cron="", interval_minutes=5)
            forever_key = runner.create_schedule(sched)
            assert manager.store[forever_key].repeats == -1  # None = forever

            sched2 = self.make_schedule(kind="interval", cron="", interval_minutes=5, repeats=3)
            limited_key = runner.create_schedule(sched2)
            assert manager.store[limited_key].minutes == 5
            assert manager.store[limited_key].repeats == 3

    def test_update_in_place(self, active_command):
        with fake_django_q() as manager:
            sched = self.make_schedule()
            runner = self.runner()
            sched.backend_schedule_key = runner.create_schedule(sched)
            sched.cron = "30 5 * * *"
            key = runner.update_schedule(sched)
            assert key == sched.backend_schedule_key
            assert len(manager.store) == 1
            assert manager.store[key].cron == "30 5 * * *"

    def test_update_missing_native_recreates(self, active_command):
        with fake_django_q() as manager:
            sched = self.make_schedule(backend_schedule_key="999")
            key = self.runner().update_schedule(sched)
            assert key in manager.store

    def test_delete_by_key(self, active_command):
        with fake_django_q() as manager:
            sched = self.make_schedule()
            sched.backend_schedule_key = self.runner().create_schedule(sched)
            self.runner().delete_schedule(sched)
            assert manager.store == {}

    def test_next_run(self, active_command):
        with fake_django_q() as manager:
            sched = self.make_schedule()
            sched.backend_schedule_key = self.runner().create_schedule(sched)
            native = manager.store[sched.backend_schedule_key]
            native.next_run = "soon"
            assert self.runner().schedule_next_run(sched) == "soon"

    def test_disable_reenable_round_trip(self, active_command):
        with fake_django_q() as manager, override_settings(ADMIN_RUNNER_BACKEND="django-q2"):
            sched = self.make_schedule()
            materialize_schedule(sched)
            key = sched.backend_schedule_key
            assert key in manager.store

            # Disable: native removed, row kept, key cleared.
            sched.enabled = False
            sched.save(update_fields=["enabled"])
            materialize_schedule(sched)
            sched.refresh_from_db()
            assert sched.enabled is False
            assert sched.backend_schedule_key == ""
            assert manager.store == {}
            assert ScheduledCommand.objects.filter(pk=sched.pk).exists()

            # Re-enable: native recreated.
            sched.enabled = True
            materialize_schedule(sched)
            sched.refresh_from_db()
            assert sched.backend_schedule_key
            assert len(manager.store) == 1

    def test_remove_native_schedule(self, active_command):
        with fake_django_q() as manager, override_settings(ADMIN_RUNNER_BACKEND="django-q2"):
            sched = self.make_schedule()
            materialize_schedule(sched)
            remove_native_schedule(sched)
            sched.refresh_from_db()
            assert sched.backend_schedule_key == ""
            assert manager.store == {}
            assert ScheduledCommand.objects.filter(pk=sched.pk).exists()

    def test_base_runner_raises_not_supported(self, active_command):
        sched = self.make_schedule()
        runner = BaseCommandRunner()
        for method in (runner.create_schedule, runner.update_schedule, runner.delete_schedule):
            with pytest.raises(ScheduleNotSupportedError):
                method(sched)


# ---------------------------------------------------------------------------
# Declarative schedule sync (4.3)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSyncDeclarativeSchedules:
    def declare(self, schedules, command="simple_command"):
        register_entry(command, schedules)

    def test_sync_creates_declared_schedules(self, active_command):
        self.declare(CronSchedule("15 4 * * *"))
        sync_declarative_schedules()
        sched = ScheduledCommand.objects.get(
            command_name="simple_command", source=ScheduledCommand.Source.CODE
        )
        assert sched.label == "simple_command"
        assert sched.cron == "15 4 * * *"
        assert sched.enabled is True

    def test_code_change_updates_spec(self, active_command):
        self.declare(CronSchedule("15 4 * * *"))
        sync_declarative_schedules()
        self.declare(CronSchedule("30 5 * * *"))
        sync_declarative_schedules()
        sched = ScheduledCommand.objects.get(source=ScheduledCommand.Source.CODE)
        assert sched.cron == "30 5 * * *"
        assert ScheduledCommand.objects.count() == 1

    def test_multiple_declarations(self, active_command):
        self.declare(
            [
                CronSchedule("0 1 * * *", name="nightly", kwargs={"a": 1}),
                IntervalSchedule(15, name="often"),
            ]
        )
        sync_declarative_schedules()
        assert ScheduledCommand.objects.filter(source="code").count() == 2
        nightly = ScheduledCommand.objects.get(label="nightly")
        assert nightly.kwargs == {"a": 1}

    def test_reorder_is_stable(self, active_command):
        self.declare(
            [
                CronSchedule("0 1 * * *", name="nightly", kwargs={"a": 1}),
                IntervalSchedule(15, name="often", kwargs={"b": 2}),
            ]
        )
        sync_declarative_schedules()
        self.declare(
            [
                IntervalSchedule(15, name="often", kwargs={"b": 2}),
                CronSchedule("0 1 * * *", name="nightly", kwargs={"a": 1}),
            ]
        )
        sync_declarative_schedules()
        assert ScheduledCommand.objects.filter(source="code").count() == 2
        assert ScheduledCommand.objects.get(label="nightly").kwargs == {"a": 1}
        assert ScheduledCommand.objects.get(label="often").kwargs == {"b": 2}

    def test_admin_pause_survives_sync(self, active_command):
        self.declare(CronSchedule("15 4 * * *"))
        sync_declarative_schedules()
        ScheduledCommand.objects.update(enabled=False)
        self.declare(CronSchedule("0 0 * * *"))
        sync_declarative_schedules()
        sched = ScheduledCommand.objects.get(source="code")
        assert sched.enabled is False
        assert sched.cron == "0 0 * * *"  # registry still wins for the spec

    def test_admin_schedules_untouched(self, active_command):
        ScheduledCommand.objects.create(
            command_name="simple_command",
            kind="cron",
            cron="5 5 * * *",
            label="manual",
            source=ScheduledCommand.Source.ADMIN,
        )
        self.declare(CronSchedule("15 4 * * *"))
        sync_declarative_schedules()
        admin_row = ScheduledCommand.objects.get(source=ScheduledCommand.Source.ADMIN)
        assert admin_row.cron == "5 5 * * *"
        assert ScheduledCommand.objects.count() == 2

    def test_removed_declaration_is_cleaned_up(self, active_command):
        self.declare(CronSchedule("15 4 * * *"))
        sync_declarative_schedules()
        assert ScheduledCommand.objects.count() == 1
        self.declare([])
        sync_declarative_schedules()
        assert ScheduledCommand.objects.count() == 0

    def test_deactivated_command_is_cleaned_up(self, active_command):
        self.declare(CronSchedule("15 4 * * *"))
        sync_declarative_schedules()
        RegisteredCommand.objects.filter(name="simple_command").update(active=False)
        sync_declarative_schedules()
        assert ScheduledCommand.objects.count() == 0

    def test_sync_materializes_via_runner(self, active_command):
        self.declare(CronSchedule("15 4 * * *"))
        with fake_django_q() as manager, override_settings(ADMIN_RUNNER_BACKEND="django-q2"):
            sync_declarative_schedules()
            assert len(manager.store) == 1
            sched = ScheduledCommand.objects.get(source="code")
            assert sched.backend_schedule_key


# ---------------------------------------------------------------------------
# Admin views (5.4)
# ---------------------------------------------------------------------------


@pytest.fixture
def admin_client(superuser):
    client = Client()
    client.force_login(superuser)
    return client


@pytest.mark.django_db
class TestScheduleAdmin:
    def test_add_action_hidden_without_capability(self, admin_client, active_command):
        response = admin_client.get("/admin/django_admin_runner/registeredcommand/?active=1")
        assert b"Add schedule" not in response.content

    def test_add_action_removed_from_changelist(self, admin_client, active_command):
        # "Add schedule" lives on the run page only; the changelist keeps
        # its action column to Run / Results / Schedules.
        with override_settings(ADMIN_RUNNER_BACKEND="django-q2"):
            response = admin_client.get("/admin/django_admin_runner/registeredcommand/?active=1")
        assert b"Add schedule" not in response.content

    def test_run_page_shows_add_schedule_link(self, admin_client, active_command):
        with override_settings(ADMIN_RUNNER_BACKEND="django-q2"):
            response = admin_client.get(
                "/admin/django_admin_runner/commandexecution/commands/simple_command/run/"
            )
        assert b"Add schedule" in response.content

    def test_add_view_forbidden_without_capability(self, admin_client, active_command):
        response = admin_client.get(
            "/admin/django_admin_runner/scheduledcommand/add/simple_command/"
        )
        assert response.status_code == 403

    def test_add_view_renders_form(self, admin_client, active_command):
        RegisteredCommand.objects.get_or_create(name="param_command")
        with override_settings(ADMIN_RUNNER_BACKEND="django-q2"), fake_django_q():
            response = admin_client.get(
                "/admin/django_admin_runner/scheduledcommand/add/param_command/"
            )
        assert response.status_code == 200
        content = response.content.decode()
        # Parameters and Schedule as tabs (same fieldset markup as the
        # change view, so both the base tab fallback and Unfold tabs work).
        assert 'class="tab"' in content or "tab" in content
        assert "Parameters" in content
        assert "Schedule" in content
        assert 'name="count"' in content
        assert 'name="cron"' in content
        # Run-at uses a browser-native datetime chooser (base theme).
        assert 'name="run_at"' in content
        assert 'type="datetime-local"' in content
        # Interval schedules offer a repeats field.
        assert 'name="repeats"' in content
        # Cron field links to a cron expression helper.
        assert "crontab.guru" in content

    def test_add_view_prefills_query_parameters(self, admin_client, active_command):
        RegisteredCommand.objects.get_or_create(name="param_command")
        with override_settings(ADMIN_RUNNER_BACKEND="django-q2"), fake_django_q():
            response = admin_client.get(
                "/admin/django_admin_runner/scheduledcommand/add/param_command/",
                {"count": "7", "mode": "slow"},
            )
        content = response.content.decode()
        assert 'value="7"' in content
        assert '<option value="slow" selected' in content

    def test_create_schedule_flow(self, admin_client, active_command):
        RegisteredCommand.objects.get_or_create(name="param_command")
        url = "/admin/django_admin_runner/scheduledcommand/add/param_command/"
        with (
            override_settings(ADMIN_RUNNER_BACKEND="django-q2"),
            fake_django_q() as manager,
        ):
            response = admin_client.post(
                url,
                {
                    "count": "5",
                    "mode": "fast",
                    "verbose": "on",
                    "label": "nightly run",
                    "kind": "cron",
                    "cron": "15 4 * * *",
                    "enabled": "on",
                },
            )
            assert response.status_code == 302
            sched = ScheduledCommand.objects.get(label="nightly run")
            assert sched.command_name == "param_command"
            assert sched.source == ScheduledCommand.Source.ADMIN
            assert sched.kwargs["count"] == 5
            assert sched.kwargs["verbose"] is True
            assert sched.backend_schedule_key
            (native,) = manager.store.values()
            assert ast.literal_eval(native.args)[1]["count"] == 5

    def test_create_defaults_label_to_display_name(self, admin_client, active_command):
        url = "/admin/django_admin_runner/scheduledcommand/add/simple_command/"
        with override_settings(ADMIN_RUNNER_BACKEND="django-q2"), fake_django_q():
            response = admin_client.post(url, {"kind": "cron", "cron": "0 0 * * *"})
            assert response.status_code == 302
        sched = ScheduledCommand.objects.get()
        assert sched.label == "Simple Command"  # display_name of simple_command

    def test_create_clocked_with_datetime_local(self, admin_client, active_command):
        url = "/admin/django_admin_runner/scheduledcommand/add/simple_command/"
        with override_settings(ADMIN_RUNNER_BACKEND="django-q2"), fake_django_q():
            response = admin_client.post(
                url,
                {"kind": "clocked", "run_at": "2099-01-02T03:30"},
            )
            assert response.status_code == 302
        sched = ScheduledCommand.objects.get()
        assert sched.kind == "clocked"
        assert sched.run_at is not None
        local = localtime(sched.run_at)
        assert (local.year, local.hour, local.minute) == (2099, 3, 30)

    def test_param_named_source_not_shadowed(self, admin_client, active_command):
        """A ``--source`` parameter must not collide with the readonly
        ``source`` model field ("Created in admin")."""
        from unittest.mock import patch

        from django import forms as dj_forms

        FakeForm = type("FakeForm", (dj_forms.Form,), {"source": dj_forms.CharField()})
        url = "/admin/django_admin_runner/scheduledcommand/add/simple_command/"
        with (
            override_settings(ADMIN_RUNNER_BACKEND="django-q2"),
            fake_django_q(),
            patch("django_admin_runner.admin.form_from_command", return_value=FakeForm),
            patch("django_admin_runner.forms.form_from_command", return_value=FakeForm),
        ):
            response = admin_client.get(url, {"source": "books.csv"})
            html = response.content.decode()
            assert 'name="param_source"' in html
            assert 'value="books.csv"' in html

            response = admin_client.post(
                url,
                {"label": "s", "kind": "cron", "cron": "0 0 * * *", "param_source": "x.csv"},
            )
            assert response.status_code == 302
        sched = ScheduledCommand.objects.get(label="s")
        assert sched.kwargs == {"source": "x.csv"}
        assert sched.source == ScheduledCommand.Source.ADMIN

    def test_create_invalid_cron_shows_error(self, admin_client, active_command):
        url = "/admin/django_admin_runner/scheduledcommand/add/simple_command/"
        with override_settings(ADMIN_RUNNER_BACKEND="django-q2"), fake_django_q():
            response = admin_client.post(
                url,
                {"label": "bad", "kind": "cron", "cron": "nonsense", "enabled": "on"},
            )
        assert response.status_code == 200
        assert ScheduledCommand.objects.count() == 0

    def test_change_view_tabs(self, admin_client, active_command):
        RegisteredCommand.objects.get_or_create(name="param_command")
        sched = ScheduledCommand.objects.create(
            command_name="param_command",
            kind="interval",
            interval_minutes=10,
            kwargs={"count": 2},
            label="often",
        )
        with override_settings(ADMIN_RUNNER_BACKEND="django-q2"), fake_django_q():
            response = admin_client.get(
                f"/admin/django_admin_runner/scheduledcommand/{sched.pk}/change/"
            )
        assert response.status_code == 200
        content = response.content.decode()
        assert "Parameters" in content
        assert "Schedule" in content
        assert 'name="count"' in content

    def test_edit_rematerializes(self, admin_client, active_command):
        sched = ScheduledCommand.objects.create(
            command_name="simple_command", kind="interval", interval_minutes=10, label="often"
        )
        with (
            override_settings(ADMIN_RUNNER_BACKEND="django-q2"),
            fake_django_q() as manager,
        ):
            materialize_schedule(sched)
            sched.refresh_from_db()
            response = admin_client.post(
                f"/admin/django_admin_runner/scheduledcommand/{sched.pk}/change/",
                {
                    "label": "often",
                    "kind": "interval",
                    "interval_minutes": "20",
                    "enabled": "on",
                    "command_name": "simple_command",
                    "source": "admin",
                },
            )
            assert response.status_code == 302
            sched.refresh_from_db()
            assert sched.interval_minutes == 20
            (native,) = manager.store.values()
            assert native.minutes == 20

    def test_disable_keeps_row_removes_native(self, admin_client, active_command):
        sched = ScheduledCommand.objects.create(
            command_name="simple_command", kind="cron", cron="0 0 * * *", label="daily"
        )
        with (
            override_settings(ADMIN_RUNNER_BACKEND="django-q2"),
            fake_django_q() as manager,
        ):
            materialize_schedule(sched)
            sched.refresh_from_db()
            response = admin_client.post(
                f"/admin/django_admin_runner/scheduledcommand/{sched.pk}/change/",
                {
                    "label": "daily",
                    "kind": "cron",
                    "cron": "0 0 * * *",
                    "command_name": "simple_command",
                    "source": "admin",
                },
            )
            assert response.status_code == 302
            assert manager.store == {}
            sched.refresh_from_db()
            assert sched.enabled is False

    def test_delete_removes_native_first(self, admin_client, active_command):
        sched = ScheduledCommand.objects.create(
            command_name="simple_command", kind="cron", cron="0 0 * * *", label="daily"
        )
        with (
            override_settings(ADMIN_RUNNER_BACKEND="django-q2"),
            fake_django_q() as manager,
        ):
            materialize_schedule(sched)
            sched.refresh_from_db()
            response = admin_client.post(
                f"/admin/django_admin_runner/scheduledcommand/{sched.pk}/delete/",
                {"post": "yes"},
            )
            assert response.status_code == 302
            assert manager.store == {}
            assert not ScheduledCommand.objects.filter(pk=sched.pk).exists()

    def test_schedules_button_shown_when_schedules_exist(self, admin_client, active_command):
        ScheduledCommand.objects.create(
            command_name="simple_command", kind="cron", cron="0 0 * * *", label="daily"
        )
        response = admin_client.get("/admin/django_admin_runner/registeredcommand/?active=1")
        # Icon-only button with a tooltip.
        assert b'title="Schedules"' in response.content

    def test_schedules_button_hidden_without_schedules(self, admin_client, active_command):
        response = admin_client.get("/admin/django_admin_runner/registeredcommand/?active=1")
        assert b'title="Schedules"' not in response.content

    def test_results_button_disabled_without_executions(self, admin_client, active_command):
        response = admin_client.get("/admin/django_admin_runner/registeredcommand/?active=1")
        assert b'title="No results yet"' in response.content
        assert b"aria-disabled" in response.content

    def test_results_button_shows_last_status(self, admin_client, active_command, superuser):
        from django_admin_runner.models import CommandExecution

        CommandExecution.objects.create(
            command_name="simple_command",
            status=CommandExecution.Status.SUCCESS,
            triggered_by=superuser,
        )
        response = admin_client.get("/admin/django_admin_runner/registeredcommand/?active=1")
        assert b'title="Results - Success' in response.content

    def test_results_button_spins_while_running(self, admin_client, active_command, superuser):
        from django_admin_runner.models import CommandExecution

        CommandExecution.objects.create(
            command_name="simple_command",
            status=CommandExecution.Status.RUNNING,
            triggered_by=superuser,
        )
        response = admin_client.get("/admin/django_admin_runner/registeredcommand/?active=1")
        assert b"dar-spin" in response.content

    def test_global_changelist(self, admin_client, active_command):
        ScheduledCommand.objects.create(
            command_name="simple_command", kind="cron", cron="0 0 * * *", label="daily"
        )
        response = admin_client.get("/admin/django_admin_runner/scheduledcommand/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "daily" in content
        assert "0 0 * * *" in content

    def test_changelist_filter_by_command(self, admin_client, active_command):
        ScheduledCommand.objects.create(
            command_name="simple_command", kind="cron", cron="0 0 * * *", label="daily"
        )
        response = admin_client.get(
            "/admin/django_admin_runner/scheduledcommand/?command_name=simple_command"
        )
        assert "daily" in response.content.decode()
        response = admin_client.get(
            "/admin/django_admin_runner/scheduledcommand/?command_name=other"
        )
        assert "daily" not in response.content.decode()

    def test_execution_shows_schedule_traceability(self, admin_client, active_command):
        sched = ScheduledCommand.objects.create(
            command_name="simple_command", kind="cron", cron="0 0 * * *", label="daily"
        )
        run_scheduled_command("simple_command", {}, schedule_pk=sched.pk)
        execution = CommandExecution.objects.latest("pk")
        response = admin_client.get(
            f"/admin/django_admin_runner/commandexecution/{execution.pk}/change/"
        )
        assert response.status_code == 200


@pytest.mark.django_db(transaction=True)
class TestScheduledCommandConstraints:
    """DB-level enforcement of ScheduledCommand field choices."""

    def make_schedule(self, **kwargs):
        return ScheduledCommand.objects.create(
            command_name="simple_command",
            kind=kwargs.pop("kind", "cron"),
            cron=kwargs.pop("cron", "15 4 * * *"),
            **kwargs,
        )

    def test_invalid_source_rejected_at_db_level(self, active_command):
        with pytest.raises(IntegrityError):
            self.make_schedule(source="bogus")

    def test_valid_sources_accepted(self, active_command):
        assert self.make_schedule(source="code").source == "code"
        assert self.make_schedule(source="admin").source == "admin"

    def test_invalid_kind_rejected_at_db_level(self, active_command):
        with pytest.raises(IntegrityError):
            self.make_schedule(kind="bogus", cron="")
