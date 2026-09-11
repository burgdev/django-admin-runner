"""TIMEOUT status, in-process soft-limit mapping, and the stale-run sweeper."""

import errno
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils.timezone import now

from django_admin_runner import tasks as tasks_mod
from django_admin_runner.models import CommandExecution
from django_admin_runner.tasks import execute_command, sweep_stale_executions


class SoftTimeLimitExceeded(Exception):
    """Name-matched stand-in for celery's SoftTimeLimitExceeded."""


def _make_execution(superuser, **kwargs) -> CommandExecution:
    defaults = {"command_name": "simple_command", "triggered_by": superuser}
    defaults.update(kwargs)
    return CommandExecution.objects.create(**defaults)


def _dead_pid(monkeypatch) -> int:
    """Make os.kill(pid, 0) report ESRCH (process gone) for any pid."""

    def fake_kill(pid, sig):
        if sig == 0:
            raise OSError(errno.ESRCH, "No such process")
        return None

    monkeypatch.setattr("os.kill", fake_kill)
    return 12345


def _alive_pid(monkeypatch) -> int:
    monkeypatch.setattr("os.kill", lambda pid, sig: None)
    return 12345


# ---------------------------------------------------------------------------
# In-process soft-time-limit mapping
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSoftTimeLimitMapping:
    def test_soft_limit_finalizes_timeout(self, superuser, monkeypatch):
        ex = _make_execution(superuser)

        def raise_timeout(*args, **kwargs):
            raise SoftTimeLimitExceeded("Soft time limit exceeded")

        monkeypatch.setattr(tasks_mod, "call_command", raise_timeout)
        with pytest.raises(SoftTimeLimitExceeded):
            execute_command("simple_command", {}, ex.pk)
        ex.refresh_from_db()
        assert ex.status == CommandExecution.Status.TIMEOUT
        assert ex.finished_at is not None
        assert "Soft time limit" in ex.output_text("stderr")

    def test_stop_request_wins_over_timeout(self, superuser, monkeypatch):
        ex = _make_execution(superuser)

        def raise_timeout(*args, **kwargs):
            raise SoftTimeLimitExceeded("Soft time limit exceeded")

        monkeypatch.setattr(tasks_mod, "call_command", raise_timeout)
        monkeypatch.setattr(tasks_mod, "_stop_requested", lambda exec: True)
        execute_command("simple_command", {}, ex.pk)
        ex.refresh_from_db()
        assert ex.status == CommandExecution.Status.CANCELLED

    def test_other_exceptions_still_failed(self, superuser, monkeypatch):
        ex = _make_execution(superuser)

        def boom(*args, **kwargs):
            raise RuntimeError("boom")

        monkeypatch.setattr(tasks_mod, "call_command", boom)
        with pytest.raises(RuntimeError):
            execute_command("simple_command", {}, ex.pk)
        ex.refresh_from_db()
        assert ex.status == CommandExecution.Status.FAILED


# ---------------------------------------------------------------------------
# Stale-run sweeper
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSweepStaleExecutions:
    def test_dead_worker_swept_failed_with_note(self, superuser, monkeypatch):
        pid = _dead_pid(monkeypatch)
        ex = _make_execution(superuser, status=CommandExecution.Status.RUNNING, worker_pid=pid)
        ex.started_at = now() - timedelta(minutes=10)
        ex.save(update_fields=["started_at"])
        swept = sweep_stale_executions()
        ex.refresh_from_db()
        assert swept == 1
        assert ex.status == CommandExecution.Status.FAILED
        assert ex.finished_at is not None
        assert "worker lost" in ex.output_text("stderr")

    def test_live_worker_never_swept(self, superuser, monkeypatch):
        pid = _alive_pid(monkeypatch)
        ex = _make_execution(superuser, status=CommandExecution.Status.RUNNING, worker_pid=pid)
        ex.started_at = now() - timedelta(hours=3)
        ex.save(update_fields=["started_at"])
        assert sweep_stale_executions() == 0
        ex.refresh_from_db()
        assert ex.status == CommandExecution.Status.RUNNING

    def test_fresh_running_execution_untouched(self, superuser, monkeypatch):
        _dead_pid(monkeypatch)
        ex = _make_execution(superuser, status=CommandExecution.Status.RUNNING, worker_pid=12345)
        ex.started_at = now()  # inside the grace period
        ex.save(update_fields=["started_at"])
        assert sweep_stale_executions() == 0
        ex.refresh_from_db()
        assert ex.status == CommandExecution.Status.RUNNING

    def test_legacy_row_without_pid_swept_by_age(self, superuser, monkeypatch):
        _alive_pid(monkeypatch)  # liveness must not matter without a pid
        ex = _make_execution(superuser, status=CommandExecution.Status.RUNNING)
        ex.started_at = now() - timedelta(hours=2)
        ex.save(update_fields=["started_at"])
        assert sweep_stale_executions() == 1
        ex.refresh_from_db()
        assert ex.status == CommandExecution.Status.FAILED

    def test_legacy_row_recent_untouched(self, superuser, monkeypatch):
        _alive_pid(monkeypatch)
        ex = _make_execution(superuser, status=CommandExecution.Status.RUNNING)
        ex.started_at = now() - timedelta(minutes=5)
        ex.save(update_fields=["started_at"])
        assert sweep_stale_executions() == 0
        ex.refresh_from_db()
        assert ex.status == CommandExecution.Status.RUNNING

    def test_terminal_states_never_swept(self, superuser, monkeypatch):
        _dead_pid(monkeypatch)
        for status in (
            CommandExecution.Status.PENDING,
            CommandExecution.Status.SUCCESS,
            CommandExecution.Status.FAILED,
        ):
            ex = _make_execution(superuser, status=status, worker_pid=12345)
            ex.started_at = now() - timedelta(hours=2)
            ex.save(update_fields=["started_at"])
        assert sweep_stale_executions() == 0

    def test_attribution_via_finalize_stale(self, superuser, monkeypatch):
        pid = _dead_pid(monkeypatch)
        ex = _make_execution(superuser, status=CommandExecution.Status.RUNNING, worker_pid=pid)
        ex.started_at = now() - timedelta(minutes=10)
        ex.save(update_fields=["started_at"])

        class Runner:
            def finalize_stale(self, execution):
                return (
                    CommandExecution.Status.TIMEOUT,
                    "Killed by django-q2 timeout: exceeded 300s",
                )

        from django_admin_runner import runners as runners_mod

        monkeypatch.setattr(runners_mod, "get_runner", lambda: Runner())
        assert sweep_stale_executions() == 1
        ex.refresh_from_db()
        assert ex.status == CommandExecution.Status.TIMEOUT
        assert "django-q2 timeout" in ex.output_text("stderr")

    def test_attribution_failure_falls_back(self, superuser, monkeypatch):
        pid = _dead_pid(monkeypatch)
        ex = _make_execution(superuser, status=CommandExecution.Status.RUNNING, worker_pid=pid)
        ex.started_at = now() - timedelta(minutes=10)
        ex.save(update_fields=["started_at"])

        class Runner:
            def finalize_stale(self, execution):
                raise RuntimeError("broker down")

        from django_admin_runner import runners as runners_mod

        monkeypatch.setattr(runners_mod, "get_runner", lambda: Runner())
        assert sweep_stale_executions() == 1
        ex.refresh_from_db()
        assert ex.status == CommandExecution.Status.FAILED
        assert "worker lost" in ex.output_text("stderr")


# ---------------------------------------------------------------------------
# Runner attribution implementations
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestFinalizeStaleRunners:
    def test_base_runner_returns_none(self, superuser):
        from django_admin_runner.runners import BaseCommandRunner

        assert BaseCommandRunner().finalize_stale(_make_execution(superuser)) is None

    def test_q2_timeout_attribution(self, superuser, monkeypatch):
        import sys
        import types
        import unittest.mock

        from django_admin_runner.runners.django_q2 import DjangoQ2CommandRunner

        task = unittest.mock.MagicMock(success=False, stopped=now(), result="timeout")
        fake_models = types.ModuleType("django_q.models")
        fake_models.Task = type("Task", (), {"objects": unittest.mock.MagicMock()})
        fake_models.Task.objects.filter = unittest.mock.MagicMock(
            return_value=unittest.mock.MagicMock(first=lambda: task)
        )
        fake_q = types.ModuleType("django_q")
        fake_q.models = fake_models
        monkeypatch.setitem(sys.modules, "django_q", fake_q)
        monkeypatch.setitem(sys.modules, "django_q.models", fake_models)

        ex = _make_execution(superuser, status=CommandExecution.Status.RUNNING, task_id="t-1")
        status, note = DjangoQ2CommandRunner().finalize_stale(ex)
        assert status == CommandExecution.Status.TIMEOUT
        assert "django-q2 timeout" in note

    def test_q2_no_record_returns_none(self, superuser, monkeypatch):
        import sys
        import types
        import unittest.mock

        from django_admin_runner.runners.django_q2 import DjangoQ2CommandRunner

        fake_models = types.ModuleType("django_q.models")
        fake_models.Task = type("Task", (), {"objects": unittest.mock.MagicMock()})
        fake_models.Task.objects.filter = unittest.mock.MagicMock(
            return_value=unittest.mock.MagicMock(first=lambda: None)
        )
        fake_q = types.ModuleType("django_q")
        fake_q.models = fake_models
        monkeypatch.setitem(sys.modules, "django_q", fake_q)
        monkeypatch.setitem(sys.modules, "django_q.models", fake_models)

        ex = _make_execution(superuser, status=CommandExecution.Status.RUNNING, task_id="t-1")
        assert DjangoQ2CommandRunner().finalize_stale(ex) is None

    def test_celery_revoked_attribution(self, superuser, monkeypatch):
        import sys
        import types
        import unittest.mock

        from django_admin_runner.runners.celery import CeleryCommandRunner

        fake_result = unittest.mock.MagicMock(state="REVOKED")
        fake_result_mod = types.ModuleType("celery.result")
        fake_result_mod.AsyncResult = lambda task_id: fake_result
        monkeypatch.setitem(sys.modules, "celery.result", fake_result_mod)

        ex = _make_execution(superuser, status=CommandExecution.Status.RUNNING, task_id="t-1")
        status, note = CeleryCommandRunner().finalize_stale(ex)
        assert status == CommandExecution.Status.TIMEOUT
        assert "Celery" in note


# ---------------------------------------------------------------------------
# Admin wiring + display
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSweepWiringAndDisplay:
    def test_output_poll_sweeps_and_reports(self, admin_client, superuser, monkeypatch):
        from django_admin_runner.admin import _sweep_state
        from django_admin_runner.models import CommandOutputPart

        # The rate limiter may have fired earlier in the suite — reset it.
        _sweep_state["last"] = 0.0
        pid = _dead_pid(monkeypatch)
        ex = _make_execution(superuser, status=CommandExecution.Status.RUNNING, worker_pid=pid)
        ex.started_at = now() - timedelta(minutes=10)
        ex.save(update_fields=["started_at"])
        CommandOutputPart.objects.create(execution=ex, field="stdout", seq=0, text="x")

        url = reverse("admin:django_admin_runner_commandexecution_output", args=[ex.pk])
        data = admin_client.get(url, {"field": "stdout"}).json()
        assert data["status"] == "FAILED"  # swept before the response
        assert data["finished"] is True

    def test_sweep_rate_limited(self, db, monkeypatch, settings):
        from django_admin_runner.admin import _maybe_sweep_stale, _sweep_state

        calls = []
        monkeypatch.setattr(tasks_mod, "sweep_stale_executions", lambda: calls.append(1))
        settings.ADMIN_RUNNER_SWEEP_INTERVAL = 60
        _sweep_state["last"] = 0.0
        _maybe_sweep_stale()
        _maybe_sweep_stale()  # within the interval: skipped
        assert len(calls) == 1

    def test_timeout_badge(self, superuser):
        from django_admin_runner.admin import _status_badge

        ex = _make_execution(superuser, status=CommandExecution.Status.TIMEOUT)
        html = str(_status_badge(ex))
        assert "TIMEOUT" in html
        assert "Timed out" in html
