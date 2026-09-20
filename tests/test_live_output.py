"""Tests for the live output buffer flush behaviour (append-to-parts)."""

from __future__ import annotations

import asyncio

import pytest
from django.contrib.auth import get_user_model

from django_admin_runner.models import CommandExecution
from django_admin_runner.tasks import _append_output, _LiveTtyStringIO


@pytest.fixture
def execution(django_db_setup) -> CommandExecution:
    """A CommandExecution row to flush into."""
    user = get_user_model().objects.create_user(username="u", email="u@example.com", password="x")
    return CommandExecution.objects.create(
        command_name="param_command",
        triggered_by=user,
    )


@pytest.mark.django_db(transaction=True)
class TestLiveFlush:
    def test_flush_from_sync_context(self, execution) -> None:
        """Writes from a sync thread persist as parts (drained)."""
        buf = _LiveTtyStringIO(execution, "stdout", flush_bytes=1)
        buf.write("hello")
        buf.final_flush()  # appends are async via the executor
        assert execution.output_text("stdout") == "hello"

    def test_flush_appends_only_new_chars(self, execution) -> None:
        """Second flush appends only the delta — no new part, no full rewrite."""
        buf = _LiveTtyStringIO(execution, "stdout", flush_bytes=1)
        buf.write("hello")
        buf.write(" world")
        buf.final_flush()  # appends are async via the executor
        parts = list(execution.output_parts_for("stdout").values_list("text", flat=True))
        assert parts == ["hello world"]  # appended into the same active part

    def test_final_flush_persists_remaining_tail(self, execution) -> None:
        buf = _LiveTtyStringIO(execution, "stdout", flush_bytes=10_000)
        buf.write("hello")
        assert execution.output_parts_for("stdout").count() == 0
        buf.final_flush()
        assert execution.output_text("stdout") == "hello"

    def test_flush_from_async_context_does_not_raise(self, execution) -> None:
        """Writes from inside a running event loop do not raise to the coroutine.

        Regression test: async pipelines that print progress used to hit
        ``SynchronousOnlyOperation`` because the flush wrote to the DB from
        within the event loop. Appends now always go through the append
        executor (in tests: the inline executor from conftest), and errors
        are contained by ``_append_output_logged`` — nothing may surface
        out of ``write()`` on the loop thread.
        """
        calls: list[str] = []
        original = _append_output
        import django_admin_runner.tasks as tasks_mod

        def recording_append(exec, field, chunk):
            calls.append(chunk)
            # Skip the real DB write: test SQLite is in-memory and
            # per-connection, so the executor thread cannot see this row.
            return None

        tasks_mod._append_output = recording_append

        async def write_from_coroutine() -> None:
            buf = _LiveTtyStringIO(execution, "stdout", flush_bytes=1)
            buf.write("async hello")
            buf.final_flush()

        try:
            asyncio.run(write_from_coroutine())
        finally:
            tasks_mod._append_output = original

        # No exception propagated out of the coroutine, and the append ran.
        assert calls == ["async hello"]

    def test_fixed_cadence_regardless_of_size(self, execution) -> None:
        """The interval is a constant — no size-based tiers anymore."""
        from django_admin_runner.tasks import (
            DEFAULT_FLUSH_INTERVAL,
        )

        assert DEFAULT_FLUSH_INTERVAL == 0.5
        buf = _LiveTtyStringIO(execution, "stdout", flush_bytes=10)
        buf.write("x" * 100)
        buf.final_flush()  # appends are async via the executor
        assert execution.output_text("stdout") == "x" * 100  # byte trigger flushed
        # Simulate a multi-megabyte buffer: the interval must not change.
        buf.write = lambda s: None  # avoid actually appending 10 MB
        buf._maybe_flush()  # would flush if the interval had elapsed
        assert buf._flush_interval == DEFAULT_FLUSH_INTERVAL
        assert not hasattr(buf, "_flush_interval_for")

    def test_flush_interval_setting_override(
        self,
        execution,
        settings,
    ) -> None:
        """ADMIN_RUNNER_FLUSH_INTERVAL overrides the global default."""
        from django_admin_runner.tasks import _flush_interval_for_command

        settings.ADMIN_RUNNER_FLUSH_INTERVAL = 0.25
        assert _flush_interval_for_command("param_command") == 0.25

    def test_flush_interval_per_command_override(self, execution) -> None:
        """register_command(flush_interval=...) beats the global setting."""
        from django_admin_runner.registry import _registry
        from django_admin_runner.tasks import _flush_interval_for_command

        _registry["param_command"]["flush_interval"] = 0.1
        try:
            assert _flush_interval_for_command("param_command") == 0.1
        finally:
            _registry["param_command"]["flush_interval"] = None

    def test_concurrent_writes_do_not_duplicate(self, execution) -> None:
        """Writes from multiple threads append each character exactly once.

        Regression test: two threads flushing concurrently used to read the
        same watermark slice and append duplicated chunks (visible as
        repeated progress-bar blocks in the terminal view). ``_append_output``
        is replaced by a recorder so the test does not depend on the
        per-thread in-memory test database.
        """
        import threading

        from django_admin_runner import tasks as tasks_mod

        appended = []
        append_lock = threading.Lock()

        def fake_append(exec, field, chunk):
            with append_lock:
                appended.append(chunk)

        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(tasks_mod, "_append_output", fake_append)
        try:
            buf = _LiveTtyStringIO(execution, "stdout", flush_bytes=1)
            threads = []
            for t in range(4):

                def writer(tag=t):
                    for _i in range(200):
                        buf.write(chr(ord("a") + tag) * 10)

                th = threading.Thread(target=writer)
                threads.append(th)
            for th in threads:
                th.start()
            for th in threads:
                th.join()
            buf.final_flush()
        finally:
            monkeypatch.undo()

        stored = "".join(appended)
        buffer_content = buf.getvalue()
        # No chunk lost, none duplicated, order within the buffer preserved.
        assert len(stored) == len(buffer_content)
        for tag in range(4):
            ch = chr(ord("a") + tag)
            assert stored.count(ch) == buffer_content.count(ch)
            assert buffer_content.count(ch) == 200 * 10

    def test_sigterm_marks_execution_failed(self, execution) -> None:
        """SIGTERM during a command fails the execution gracefully."""
        import os
        import signal
        import threading
        import time

        from django_admin_runner.tasks import execute_command

        def send_sigterm():
            time.sleep(0.3)
            os.kill(os.getpid(), signal.SIGTERM)

        thread = threading.Thread(target=send_sigterm)
        thread.start()
        with pytest.raises(Exception, match="SIGTERM"):
            execute_command(
                "slow_command",
                {"seconds": 10},
                execution.pk,
            )
        thread.join()

        execution.refresh_from_db()
        assert execution.status == "FAILED"
        stderr_text = execution.output_text("stderr")
        assert "SIGTERM" in stderr_text

    def test_seals_parts_at_part_size(self, execution, monkeypatch) -> None:
        from django_admin_runner.models import CommandOutputPart

        monkeypatch.setattr(CommandOutputPart, "PART_SIZE", 100)
        _append_output(execution, "stdout", "a" * 250)
        parts = list(execution.output_parts_for("stdout").values_list("seq", "text"))
        assert parts == [(0, "a" * 100), (1, "a" * 100), (2, "a" * 50)]

    def test_pruning_drops_oldest_sealed_only(self, execution, settings, monkeypatch) -> None:
        from django_admin_runner.models import CommandOutputPart

        monkeypatch.setattr(CommandOutputPart, "PART_SIZE", 100)
        settings.ADMIN_RUNNER_MAX_OUTPUT = 250
        _append_output(execution, "stdout", "a" * 450)
        parts = list(execution.output_parts_for("stdout").values_list("seq", "text"))
        # 450 chars → 5 parts (4×100 + 50); cap 250 prunes seq 0 and 1,
        # never the active part (seq 4, 50 chars).
        assert parts == [(2, "a" * 100), (3, "a" * 100), (4, "a" * 50)]

    def test_deleting_execution_cascades_to_parts(self, execution) -> None:
        from django_admin_runner.models import CommandOutputPart

        _append_output(execution, "stdout", "hello")
        _append_output(execution, "stderr", "oops")
        assert CommandOutputPart.objects.count() == 2
        execution.delete()
        assert CommandOutputPart.objects.count() == 0
