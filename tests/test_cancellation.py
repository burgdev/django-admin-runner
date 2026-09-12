"""Cancellation: graceful stop, force stop, button visibility, races."""

import sys
import unittest.mock

import pytest
from django.urls import reverse

from django_admin_runner import tasks as tasks_mod
from django_admin_runner.models import CommandExecution
from django_admin_runner.tasks import WorkerStoppedError, execute_command

CHANGE_URL_NAME = "admin:django_admin_runner_commandexecution_change"
STOP_URL_NAME = "admin:django_admin_runner_commandexecution_stop"


def _make_execution(superuser, **kwargs) -> CommandExecution:
    defaults = {"command_name": "loop_command", "triggered_by": superuser}
    defaults.update(kwargs)
    return CommandExecution.objects.create(**defaults)


def _run_with_stop(monkeypatch, settings, execution, stop_after=3, **exec_kwargs):
    """Run ``loop_command`` with ``_stop_requested`` stubbed.

    The stub returns True after ``stop_after`` probes so the flush
    heartbeat raises ``CommandCancelledError`` mid-command,
    deterministically (no threads sharing the in-memory DB).
    """
    settings.ADMIN_RUNNER_FLUSH_INTERVAL = 0.001
    calls = {"n": 0}

    def fake_stop_requested(exec):
        calls["n"] += 1
        return calls["n"] >= stop_after

    monkeypatch.setattr(tasks_mod, "_stop_requested", fake_stop_requested)
    execute_command("loop_command", {"iterations": 10000, "interval": 0.001}, execution.pk)
    execution.refresh_from_db()
    return execution


# ---------------------------------------------------------------------------
# Graceful stop via the flush heartbeat
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGracefulStop:
    def test_cancelled_status(self, superuser, monkeypatch, settings):
        ex = _make_execution(superuser)
        _run_with_stop(monkeypatch, settings, ex, stop_after=3)
        assert ex.status == CommandExecution.Status.CANCELLED
        assert ex.finished_at is not None

    def test_output_preserved_and_note_appended(self, superuser, monkeypatch, settings):
        ex = _make_execution(superuser)
        _run_with_stop(monkeypatch, settings, ex, stop_after=3)
        stdout = ex.output_text("stdout")
        assert "line 0" in stdout
        assert "done" not in stdout  # stopped before finishing
        assert "cancelled" in ex.output_text("stderr").lower()

    def test_cancellation_not_reraised(self, superuser, monkeypatch, settings):
        # The task backend must not see a failure (which could trigger
        # retries) for an intended stop.
        ex = _make_execution(superuser)
        _run_with_stop(monkeypatch, settings, ex, stop_after=3)
        assert ex.status == CommandExecution.Status.CANCELLED

    def test_worker_stopped_with_stop_flag_is_cancelled(self, superuser, monkeypatch):
        ex = _make_execution(superuser, command_name="simple_command")

        def raise_stopped(*args, **kwargs):
            raise WorkerStoppedError("worker received SIGTERM")

        monkeypatch.setattr(tasks_mod, "call_command", raise_stopped)
        monkeypatch.setattr(tasks_mod, "_stop_requested", lambda exec: True)
        execute_command("simple_command", {}, ex.pk)
        ex.refresh_from_db()
        assert ex.status == CommandExecution.Status.CANCELLED

    def test_worker_stopped_without_stop_flag_is_failed(self, superuser, monkeypatch):
        ex = _make_execution(superuser, command_name="simple_command")

        def raise_stopped(*args, **kwargs):
            raise WorkerStoppedError("worker received SIGTERM")

        monkeypatch.setattr(tasks_mod, "call_command", raise_stopped)
        monkeypatch.setattr(tasks_mod, "_stop_requested", lambda exec: False)
        with pytest.raises(WorkerStoppedError):
            execute_command("simple_command", {}, ex.pk)
        ex.refresh_from_db()
        assert ex.status == CommandExecution.Status.FAILED


# ---------------------------------------------------------------------------
# worker_pid + idempotency guard
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestWorkerPidAndIdempotency:
    def test_worker_pid_recorded(self, superuser):
        import os

        ex = _make_execution(superuser, command_name="simple_command")
        execute_command("simple_command", {}, ex.pk)
        ex.refresh_from_db()
        assert ex.worker_pid == os.getpid()

    def test_duplicate_attempt_is_noop(self, superuser):
        ex = _make_execution(superuser, command_name="simple_command")
        execute_command("simple_command", {}, ex.pk)  # SUCCESS
        # A re-delivered task must not touch the finished execution.
        execute_command("simple_command", {}, ex.pk)
        ex.refresh_from_db()
        assert ex.status == CommandExecution.Status.SUCCESS
        assert ex.output_text("stdout").count("simple output") == 1


# ---------------------------------------------------------------------------
# Runner API
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRunnerStopApi:
    def test_base_stop_sets_flag_conditionally(self, superuser):
        from django_admin_runner.runners import BaseCommandRunner

        ex = _make_execution(superuser, status=CommandExecution.Status.RUNNING)
        BaseCommandRunner().stop(ex)
        ex.refresh_from_db()
        assert ex.stop_requested is True

    def test_base_stop_ignores_non_running(self, superuser):
        from django_admin_runner.runners import BaseCommandRunner

        ex = _make_execution(superuser, status=CommandExecution.Status.SUCCESS)
        BaseCommandRunner().stop(ex)
        ex.refresh_from_db()
        assert ex.stop_requested is False

    def test_base_force_stop_unsupported(self, superuser):
        from django_admin_runner.runners import BaseCommandRunner

        assert BaseCommandRunner().force_stop(_make_execution(superuser)) is False

    def test_celery_runner_revoke_signals(self, superuser, monkeypatch):
        from django_admin_runner.runners.celery import CeleryCommandRunner

        calls = []

        class _Control:
            @staticmethod
            def revoke(task_id, terminate, signal):
                calls.append((task_id, terminate, signal))

        class _App:
            control = _Control()

        fake_celery = unittest.mock.MagicMock(current_app=_App())
        monkeypatch.setitem(sys.modules, "celery", fake_celery)

        ex = _make_execution(superuser, status=CommandExecution.Status.RUNNING, task_id="t-1")
        runner = CeleryCommandRunner()
        assert runner.supports_force_stop is True
        runner.stop(ex)
        assert calls == [("t-1", True, "SIGTERM")]
        assert runner.force_stop(ex) is True
        assert calls[-1] == ("t-1", True, "SIGKILL")

    def test_celery_force_stop_without_task_id(self, superuser):
        from django_admin_runner.runners.celery import CeleryCommandRunner

        ex = _make_execution(superuser, status=CommandExecution.Status.RUNNING, task_id="")
        assert CeleryCommandRunner().force_stop(ex) is False

    def test_q2_enqueue_disables_retry(self, superuser, monkeypatch):
        from django_admin_runner.runners.django_q2 import DjangoQ2CommandRunner

        captured = {}

        def fake_async_task(func, *args, **kwargs):
            captured.update(kwargs)
            return "q2-id"

        mock_tasks = unittest.mock.MagicMock(async_task=fake_async_task)
        mock_django_q = unittest.mock.MagicMock(tasks=mock_tasks)
        monkeypatch.setitem(sys.modules, "django_q", mock_django_q)
        monkeypatch.setitem(sys.modules, "django_q.tasks", mock_tasks)

        ex = _make_execution(superuser)
        DjangoQ2CommandRunner().run("simple_command", {}, superuser, ex)
        assert captured["q_options"]["retry"] == -1

    def test_q2_pid_reuse_guard(self, superuser, monkeypatch):
        from django.utils.timezone import now as tz_now

        from django_admin_runner.runners.django_q2 import DjangoQ2CommandRunner

        runner = DjangoQ2CommandRunner()
        ex = _make_execution(
            superuser,
            status=CommandExecution.Status.RUNNING,
            worker_pid=12345,
            started_at=tz_now(),
        )
        # PID's process started before the execution → reused → no signal.
        from datetime import timedelta

        monkeypatch.setattr(
            runner, "_proc_starttime", staticmethod(lambda pid: tz_now() - timedelta(hours=1))
        )
        killed = []
        monkeypatch.setattr("os.kill", lambda pid, sig: killed.append((pid, sig)))
        assert runner.force_stop(ex) is False
        assert killed == []


# ---------------------------------------------------------------------------
# Stop endpoint
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestStopEndpoint:
    def test_stop_sets_flag(self, admin_client, superuser):
        ex = _make_execution(superuser, status=CommandExecution.Status.RUNNING)
        url = reverse(STOP_URL_NAME, args=[ex.pk])
        response = admin_client.post(url)
        assert response.status_code == 302
        ex.refresh_from_db()
        assert ex.stop_requested is True
        assert ex.status == CommandExecution.Status.RUNNING

    def test_force_stop_finalizes_cancelled(self, admin_client, superuser, monkeypatch):
        from django_admin_runner import admin as admin_mod

        ex = _make_execution(superuser, status=CommandExecution.Status.RUNNING, worker_pid=999999)
        monkeypatch.setattr(type(admin_mod.get_runner()), "force_stop", lambda self, exec: True)
        url = reverse(STOP_URL_NAME, args=[ex.pk])
        response = admin_client.post(url, {"force": "1"})
        assert response.status_code == 302
        ex.refresh_from_db()
        assert ex.status == CommandExecution.Status.CANCELLED
        assert ex.finished_at is not None

    def test_force_stop_without_worker_finalizes_cancelled(self, admin_client, superuser):
        # Default test backend is django-tasks: force kill is impossible —
        # but nothing is running either, so the row must still finalize.
        ex = _make_execution(superuser, status=CommandExecution.Status.RUNNING)
        url = reverse(STOP_URL_NAME, args=[ex.pk])
        response = admin_client.post(url, {"force": "1"})
        assert response.status_code == 302
        ex.refresh_from_db()
        assert ex.status == CommandExecution.Status.CANCELLED
        assert ex.finished_at is not None

    def test_get_rejected(self, admin_client, superuser):
        ex = _make_execution(superuser, status=CommandExecution.Status.RUNNING)
        url = reverse(STOP_URL_NAME, args=[ex.pk])
        assert admin_client.get(url).status_code == 400

    def test_stop_on_finished_is_noop_redirect(self, admin_client, superuser):
        ex = _make_execution(superuser, status=CommandExecution.Status.SUCCESS)
        url = reverse(STOP_URL_NAME, args=[ex.pk])
        assert admin_client.post(url).status_code == 302
        ex.refresh_from_db()
        assert ex.status == CommandExecution.Status.SUCCESS
        assert ex.stop_requested is False

    def test_permission_denied_for_staff_without_change_perm(self, staff_client, staff_user):
        # Owned by the staff user so the queryset gate passes; the stop
        # permission check must still reject the request.
        ex = _make_execution(staff_user, status=CommandExecution.Status.RUNNING)
        url = reverse(STOP_URL_NAME, args=[ex.pk])
        response = staff_client.post(url)
        assert response.status_code == 403
        ex.refresh_from_db()
        assert ex.stop_requested is False


# ---------------------------------------------------------------------------
# Button visibility (change page context)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestStopButtonVisibility:
    def _context(self, admin_client, ex):
        response = admin_client.get(reverse(CHANGE_URL_NAME, args=[ex.pk]))
        assert response.status_code == 200
        return response.context

    def test_stop_button_while_running(self, admin_client, superuser):
        ex = _make_execution(superuser, status=CommandExecution.Status.RUNNING)
        ctx = self._context(admin_client, ex)
        assert ctx["dar_stop_url"]
        assert ctx["dar_stop_force"] is False

    def test_force_stop_after_stop_requested(self, admin_client, superuser, monkeypatch):
        from django_admin_runner import admin as admin_mod

        monkeypatch.setattr(type(admin_mod.get_runner()), "supports_force_stop", True)
        ex = _make_execution(superuser, status=CommandExecution.Status.RUNNING, stop_requested=True)
        ctx = self._context(admin_client, ex)
        assert ctx["dar_stop_url"]
        assert ctx["dar_stop_force"] is True

    def test_force_stop_hidden_when_unsupported(self, admin_client, superuser):
        # Default backend (django-tasks) has no force stop.
        ex = _make_execution(superuser, status=CommandExecution.Status.RUNNING, stop_requested=True)
        ctx = self._context(admin_client, ex)
        assert "dar_stop_url" not in ctx

    def test_no_button_when_not_running(self, admin_client, superuser):
        for status in (
            CommandExecution.Status.PENDING,
            CommandExecution.Status.SUCCESS,
            CommandExecution.Status.FAILED,
            CommandExecution.Status.CANCELLED,
        ):
            ex = _make_execution(superuser, status=status)
            ctx = self._context(admin_client, ex)
            assert "dar_stop_url" not in ctx, status

    def test_no_button_without_permission(self, client, staff_user):
        from django.contrib.auth.models import Permission

        # View (but not change) permission: the page renders, the stop
        # control must not.
        staff_user.user_permissions.add(Permission.objects.get(codename="view_commandexecution"))
        client.force_login(staff_user)
        ex = _make_execution(staff_user, status=CommandExecution.Status.RUNNING)
        ctx = self._context(client, ex)
        assert "dar_stop_url" not in ctx


# ---------------------------------------------------------------------------
# Thread-aware stop (rich Live refresh threads write from background threads)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestThreadAwareStop:
    def test_background_thread_latches_but_does_not_raise(self, superuser):
        import threading

        from django_admin_runner.tasks import CommandCancelledError, _LiveTtyStringIO

        calls = {"n": 0}

        def stop_check():
            calls["n"] += 1
            return True

        buf = _LiveTtyStringIO(
            _make_execution(superuser), "stdout", flush_interval=0, stop_check=stop_check
        )

        raised = []

        def bg_write():
            try:
                buf.write("from background\n")
            except CommandCancelledError as exc:  # pragma: no cover
                raised.append(exc)

        t = threading.Thread(target=bg_write)
        t.start()
        t.join()
        assert raised == []  # never raises in a background thread
        assert buf._stop_seen is True  # flag latched

        calls["n"] = 0  # main thread must raise without another DB probe
        with pytest.raises(CommandCancelledError):
            buf.write("from main\n")
        assert calls["n"] == 0


# ---------------------------------------------------------------------------
# CANCELLED status display
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCancelledStatusDisplay:
    def test_finished_flag_includes_cancelled(self, admin_client, superuser):
        from django_admin_runner.models import CommandOutputPart

        ex = _make_execution(superuser, status=CommandExecution.Status.CANCELLED)
        CommandOutputPart.objects.create(execution=ex, field="stdout", seq=0, text="x")
        url = reverse("admin:django_admin_runner_commandexecution_output", args=[ex.pk])
        response = admin_client.get(url, {"field": "stdout"})
        assert response.json()["finished"] is True
        assert response.json()["status"] == "CANCELLED"

    def test_poll_carries_stop_info(self, admin_client, superuser):
        from django_admin_runner.models import CommandOutputPart

        CommandOutputPart.objects.create(
            execution=_make_execution(superuser, status=CommandExecution.Status.RUNNING),
            field="stdout",
            seq=0,
            text="x",
        )
        ex = CommandExecution.objects.latest("created_at")
        url = reverse("admin:django_admin_runner_commandexecution_output", args=[ex.pk])
        data = admin_client.get(url, {"field": "stdout"}).json()
        assert data["stop"]["force"] is False
        # Stop requested → force stop (django-tasks default backend:
        # unsupported → no control at all).
        ex.stop_requested = True
        ex.save(update_fields=["stop_requested"])
        data = admin_client.get(url, {"field": "stdout"}).json()
        assert data["stop"] is None

    def test_badge_renders_cancelled(self, admin_client, superuser):
        from django_admin_runner.admin import _status_badge

        ex = _make_execution(superuser, status=CommandExecution.Status.CANCELLED)
        assert "CANCELLED" in _status_badge(ex)


@pytest.mark.django_db
class TestResultsRowStopButton:
    """Stop / Force Stop in the results changelist Actions column."""

    def _list(self, admin_client, superuser, **kwargs):
        ex = _make_execution(superuser, **kwargs)
        url = reverse("admin:django_admin_runner_commandexecution_changelist")
        body = admin_client.get(url).content.decode()
        return ex, body

    def _stop_url(self, ex):
        return reverse("admin:django_admin_runner_commandexecution_stop", args=[ex.pk])

    def test_stop_button_while_running(self, admin_client, superuser):
        ex, body = self._list(admin_client, superuser, status=CommandExecution.Status.RUNNING)
        assert f'href="{self._stop_url(ex)}"' in body
        # Stop replaces the rerun button while running.
        run_url = reverse("admin:django_admin_runner_command_run", args=[ex.command_name])
        assert f"{run_url}?rerun={ex.pk}" not in body

    def test_no_stop_button_when_stop_requested_unsupported(self, admin_client, superuser):
        # django-tasks default backend: no force support → after a stop
        # request the row shows no stop control at all.
        ex, body = self._list(
            admin_client,
            superuser,
            status=CommandExecution.Status.RUNNING,
            stop_requested=True,
        )
        assert f'href="{self._stop_url(ex)}"' not in body

    def test_no_stop_button_when_not_running(self, admin_client, superuser):
        ex, body = self._list(admin_client, superuser, status=CommandExecution.Status.SUCCESS)
        assert f'href="{self._stop_url(ex)}"' not in body
