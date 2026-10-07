"""Heartbeat-based worker liveness.

Covers the stale-run sweeper's heartbeat verdict (authoritative across
hosts/containers), the legacy pid rules for pre-heartbeat rows (including
the PID-reuse guard), the heartbeat recorded by ``execute_command``, the
worker-side heartbeat thread, and the stdin-EOF guard against hanging
interactive prompts.
"""

import errno
import socket
import time
from datetime import timedelta

import pytest
from django.test import override_settings
from django.utils.timezone import now

import django_admin_runner.tasks as tasks_mod
from django_admin_runner.models import CommandExecution
from django_admin_runner.tasks import execute_command, sweep_stale_executions


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


# ---------------------------------------------------------------------------
# Sweeper — heartbeat verdict
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestHeartbeatSweep:
    def test_fresh_heartbeat_prevents_sweep(self, superuser, monkeypatch):
        """A live heartbeat wins even when the pid is invisible (other pod)."""
        _dead_pid(monkeypatch)
        ex = _make_execution(
            superuser,
            status=CommandExecution.Status.RUNNING,
            worker_pid=12345,
            worker_host="some-other-pod",
            worker_started_at=now() - timedelta(minutes=10),
            started_at=now() - timedelta(minutes=10),
            last_heartbeat_at=now() - timedelta(seconds=10),
        )
        assert sweep_stale_executions() == 0
        ex.refresh_from_db()
        assert ex.status == CommandExecution.Status.RUNNING

    def test_stale_heartbeat_swept_with_note(self, superuser, monkeypatch):
        _dead_pid(monkeypatch)
        ex = _make_execution(
            superuser,
            status=CommandExecution.Status.RUNNING,
            worker_pid=12345,
            worker_host="some-other-pod",
            worker_started_at=now() - timedelta(minutes=10),
            started_at=now() - timedelta(minutes=10),
            last_heartbeat_at=now() - timedelta(seconds=600),
        )
        swept = sweep_stale_executions()
        ex.refresh_from_db()
        assert swept == 1
        assert ex.status == CommandExecution.Status.FAILED
        assert ex.finished_at is not None
        assert "worker lost" in ex.output_text("stderr")
        assert "heartbeat" in ex.output_text("stderr")

    def test_heartbeat_staleness_threshold_configurable(self, superuser, monkeypatch):
        _dead_pid(monkeypatch)
        ex = _make_execution(
            superuser,
            status=CommandExecution.Status.RUNNING,
            worker_pid=12345,
            worker_host="some-other-pod",
            last_heartbeat_at=now() - timedelta(seconds=60),
        )
        with override_settings(ADMIN_RUNNER_HEARTBEAT_STALE_AFTER=30):
            assert sweep_stale_executions() == 1
        ex.refresh_from_db()
        assert ex.status == CommandExecution.Status.FAILED


# ---------------------------------------------------------------------------
# Sweeper — legacy pid rules (rows without heartbeat)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestLegacyPidSweep:
    def test_reused_pid_is_dead(self, superuser, monkeypatch):
        """PID occupied by an older process → original worker is gone.

        Regression test for rows hanging RUNNING forever after a pod
        restart recycled the pid (the pre-heartbeat sweep treated any
        living pid as a live worker).
        """
        monkeypatch.setattr("os.kill", lambda pid, sig: None)  # pid alive
        ex = _make_execution(
            superuser,
            status=CommandExecution.Status.RUNNING,
            worker_pid=17,
            started_at=now() - timedelta(minutes=10),
        )
        started = ex.started_at
        # The process holding the pid started an hour before the execution.
        monkeypatch.setattr(tasks_mod, "_proc_starttime", lambda pid: started - timedelta(hours=1))
        assert sweep_stale_executions() == 1
        ex.refresh_from_db()
        assert ex.status == CommandExecution.Status.FAILED

    def test_matching_pid_starttime_is_alive(self, superuser, monkeypatch):
        monkeypatch.setattr("os.kill", lambda pid, sig: None)  # pid alive
        ex = _make_execution(
            superuser,
            status=CommandExecution.Status.RUNNING,
            worker_pid=17,
            started_at=now() - timedelta(minutes=10),
        )
        started = ex.started_at
        monkeypatch.setattr(tasks_mod, "_proc_starttime", lambda pid: started)
        assert sweep_stale_executions() == 0
        ex.refresh_from_db()
        assert ex.status == CommandExecution.Status.RUNNING

    def test_unknown_pid_starttime_is_alive(self, superuser, monkeypatch):
        """Cannot read the process start time → assume alive (conservative)."""
        monkeypatch.setattr("os.kill", lambda pid, sig: None)  # pid alive
        monkeypatch.setattr(tasks_mod, "_proc_starttime", lambda pid: None)
        ex = _make_execution(
            superuser,
            status=CommandExecution.Status.RUNNING,
            worker_pid=17,
            started_at=now() - timedelta(minutes=10),
        )
        assert sweep_stale_executions() == 0
        ex.refresh_from_db()
        assert ex.status == CommandExecution.Status.RUNNING

    def test_pidless_row_uses_stale_after(self, superuser, monkeypatch):
        monkeypatch.setattr("os.kill", lambda pid, sig: None)
        young = _make_execution(
            superuser,
            status=CommandExecution.Status.RUNNING,
            worker_pid=None,
            started_at=now() - timedelta(minutes=10),
        )
        assert sweep_stale_executions() == 0
        old = _make_execution(
            superuser,
            status=CommandExecution.Status.RUNNING,
            worker_pid=None,
            started_at=now() - timedelta(hours=3),
        )
        assert sweep_stale_executions() == 1
        old.refresh_from_db()
        young.refresh_from_db()
        assert old.status == CommandExecution.Status.FAILED
        assert young.status == CommandExecution.Status.RUNNING


# ---------------------------------------------------------------------------
# execute_command — recorded liveness data + heartbeat thread
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestExecuteCommandLiveness:
    def test_claim_records_host_and_heartbeat(self, superuser, monkeypatch):
        ex = _make_execution(superuser)
        execute_command("simple_command", {}, ex.pk)
        ex.refresh_from_db()
        assert ex.status == CommandExecution.Status.SUCCESS
        assert ex.worker_host == socket.gethostname()
        assert ex.last_heartbeat_at is not None

    def test_heartbeat_thread_refreshes_while_running(self, superuser, monkeypatch):
        ex = _make_execution(superuser)

        def slow_command(*args, **kwargs):
            time.sleep(0.4)

        monkeypatch.setattr(tasks_mod, "call_command", slow_command)
        with override_settings(ADMIN_RUNNER_HEARTBEAT_INTERVAL=0.05):
            execute_command("simple_command", {}, ex.pk)
        ex.refresh_from_db()
        # The worker thread must have refreshed the heartbeat several
        # times while the command was running (transaction=True so the
        # side thread's writes are visible to this connection).
        assert ex.last_heartbeat_at is not None
        assert ex.last_heartbeat_at > ex.started_at + timedelta(seconds=0.1)


# ---------------------------------------------------------------------------
# stdin EOF guard (no hanging interactive prompts)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_interactive_prompt_gets_eof(superuser, monkeypatch):
    """A command calling input() must fail fast, not hang the worker."""
    ex = _make_execution(superuser)

    def blocked_command(*args, **kwargs):
        input("Limit of entries to add [100000]: ")

    monkeypatch.setattr(tasks_mod, "call_command", blocked_command)
    with pytest.raises(EOFError):
        # execute_command re-raises the command's exception so the task
        # backend records the failure — the EOF must surface, not hang.
        execute_command("simple_command", {}, ex.pk)
    ex.refresh_from_db()
    assert ex.status == CommandExecution.Status.FAILED
    assert "EOFError" in ex.output_text("stderr")
