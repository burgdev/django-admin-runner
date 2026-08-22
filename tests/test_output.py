"""Tests for the cursor delta endpoint, output parts, and terminal size env."""

import os

import pytest
from django.urls import reverse

from django_admin_runner.models import CommandExecution
from django_admin_runner.tasks import _append_output, _terminal_size, execute_command


def _output_url(pk):
    return reverse("admin:django_admin_runner_commandexecution_output", args=[pk])


def _part_url(pk, seq=0):
    return reverse("admin:django_admin_runner_commandexecution_output_part", args=[pk, seq])


# ---------------------------------------------------------------------------
# 3.x Cursor delta endpoint
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestOutputEndpoint:
    def _make(self, superuser, text="x" * 250, field="stdout", **kwargs):
        defaults = dict(command_name="cmd", status="RUNNING")
        defaults.update(kwargs)
        ex = CommandExecution.objects.create(triggered_by=superuser, **defaults)
        if text:
            _append_output(ex, field, text)
        return ex

    def test_replay_from_start(self, admin_client, superuser):
        ex = self._make(superuser)
        response = admin_client.get(_output_url(ex.pk), {"field": "stdout", "cursor": ""})
        assert response.status_code == 200
        data = response.json()
        assert data["chunk"] == "x" * 250
        assert data["cursor"] == "0:250"
        assert data["status"] == "RUNNING"
        assert data["finished"] is False
        assert data["reset"] is False

    def test_delta_request(self, admin_client, superuser):
        ex = self._make(superuser)
        response = admin_client.get(_output_url(ex.pk), {"field": "stdout", "cursor": "0:100"})
        data = response.json()
        assert data["chunk"] == "x" * 150
        assert data["cursor"] == "0:250"

    def test_empty_delta(self, admin_client, superuser):
        ex = self._make(superuser)
        response = admin_client.get(_output_url(ex.pk), {"field": "stdout", "cursor": "0:250"})
        data = response.json()
        assert data["chunk"] == ""
        assert data["cursor"] == "0:250"

    def test_delta_across_parts(self, admin_client, superuser, monkeypatch):
        from django_admin_runner.models import CommandOutputPart

        monkeypatch.setattr(CommandOutputPart, "PART_SIZE", 100)
        ex = self._make(superuser, text="ab" * 100)  # two parts
        response = admin_client.get(_output_url(ex.pk), {"field": "stdout", "cursor": "0:50"})
        data = response.json()
        assert data["chunk"] == ("ab" * 100)[50:]
        assert data["cursor"] == "1:100"

    def test_reset_after_pruning(self, admin_client, superuser, monkeypatch):
        from django_admin_runner.models import CommandOutputPart

        monkeypatch.setattr(CommandOutputPart, "PART_SIZE", 100)
        ex = self._make(superuser)  # parts: 0..2 (100/100/50)
        # Simulate retention pruning of the first part
        ex.output_parts_for("stdout").filter(seq=0).delete()
        response = admin_client.get(_output_url(ex.pk), {"field": "stdout", "cursor": "0:100"})
        data = response.json()
        assert data["reset"] is True
        assert data["chunk"] == "x" * 150  # full retained output
        assert data["cursor"] == "2:50"

    def test_no_parts(self, admin_client, superuser):
        ex = self._make(superuser, text="")
        response = admin_client.get(_output_url(ex.pk), {"field": "stdout", "cursor": ""})
        data = response.json()
        assert data["chunk"] == ""
        assert data["cursor"] == ""

    def test_invalid_cursor_rejected(self, admin_client, superuser):
        ex = self._make(superuser)
        for cursor in ("garbage", "-1:0", "0:-5", "1:2:3"):
            response = admin_client.get(_output_url(ex.pk), {"field": "stdout", "cursor": cursor})
            assert response.status_code == 400, cursor

    def test_invalid_field_rejected(self, admin_client, superuser):
        ex = self._make(superuser)
        response = admin_client.get(_output_url(ex.pk), {"field": "result_html"})
        assert response.status_code == 400

    def test_stderr_field(self, admin_client, superuser):
        ex = self._make(superuser, text="err" * 10, field="stderr")
        response = admin_client.get(_output_url(ex.pk), {"field": "stderr", "cursor": "0:10"})
        data = response.json()
        assert data["chunk"] == ("err" * 10)[10:]

    def test_finished_flag(self, admin_client, superuser):
        ex = self._make(superuser, status="SUCCESS")
        response = admin_client.get(_output_url(ex.pk), {"field": "stdout", "cursor": ""})
        assert response.json()["finished"] is True

    def test_permission_denied_for_other_user(self, client, db):
        from django.contrib.auth.models import Permission
        from django.contrib.auth.models import User as UserModel
        from django.contrib.contenttypes.models import ContentType

        user = UserModel.objects.create_user("limited", "l@e.com", "pw", is_staff=True)
        other = UserModel.objects.create_superuser("admin2", "a2@e.com", "pw")
        ct = ContentType.objects.get_for_model(CommandExecution)
        perm = Permission.objects.get(content_type=ct, codename="view_commandexecution")
        user.user_permissions.add(perm)

        ex = CommandExecution.objects.create(command_name="cmd", triggered_by=other)
        _append_output(ex, "stdout", "secret")

        client.force_login(user)
        response = client.get(_output_url(ex.pk), {"field": "stdout", "cursor": ""})
        assert response.status_code == 404  # queryset filters it out


# ---------------------------------------------------------------------------
# Part endpoint (immutable caching)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPartEndpoint:
    def _make(self, superuser, monkeypatch):
        from django_admin_runner.models import CommandOutputPart

        monkeypatch.setattr(CommandOutputPart, "PART_SIZE", 100)
        ex = CommandExecution.objects.create(
            command_name="cmd", triggered_by=superuser, status="RUNNING"
        )
        _append_output(ex, "stdout", "a" * 250)
        return ex

    def test_sealed_part_immutable(self, admin_client, superuser, monkeypatch):
        ex = self._make(superuser, monkeypatch)
        response = admin_client.get(_part_url(ex.pk, 0), {"field": "stdout"})
        assert response.status_code == 200
        assert response.content.decode() == "a" * 100
        assert response.headers["Cache-Control"] == "private, max-age=31536000, immutable"
        assert response.headers["ETag"] == f'"{ex.pk}:stdout:0"'
        assert response.headers["X-Dar-Total-Parts"] == "3"

    def test_active_part_not_immutable(self, admin_client, superuser, monkeypatch):
        ex = self._make(superuser, monkeypatch)
        response = admin_client.get(_part_url(ex.pk, 2), {"field": "stdout"})
        assert response.headers["Cache-Control"] == "no-cache"

    def test_etag_304(self, admin_client, superuser, monkeypatch):
        ex = self._make(superuser, monkeypatch)
        etag = f'"{ex.pk}:stdout:0"'
        response = admin_client.get(
            _part_url(ex.pk, 0), {"field": "stdout"}, HTTP_IF_NONE_MATCH=etag
        )
        assert response.status_code == 304

    def test_missing_part_404(self, admin_client, superuser, monkeypatch):
        ex = self._make(superuser, monkeypatch)
        response = admin_client.get(_part_url(ex.pk, 99), {"field": "stdout"})
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Execution end-to-end (output written to parts)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestExecuteCommandOutput:
    def test_output_stored_in_parts(self, superuser):
        ex = CommandExecution.objects.create(command_name="simple_command", triggered_by=superuser)
        execute_command("simple_command", {}, ex.pk)
        ex.refresh_from_db()
        assert ex.status == "SUCCESS", ex.output_text("stderr")
        assert "simple output" in ex.output_text("stdout")

    def test_failure_traceback_replaces_stderr(self, superuser):
        ex = CommandExecution.objects.create(command_name="failing_command", triggered_by=superuser)
        with pytest.raises(Exception, match="intentional failure"):
            execute_command("failing_command", {}, ex.pk)
        ex.refresh_from_db()
        assert ex.status == "FAILED"
        stderr = ex.output_text("stderr")
        assert "Traceback" in stderr or "intentional" in stderr.lower()

    def test_capped_output_pruned_without_marker(self, superuser, settings, monkeypatch):
        from django_admin_runner.models import CommandOutputPart

        monkeypatch.setattr(CommandOutputPart, "PART_SIZE", 50)
        settings.ADMIN_RUNNER_MAX_OUTPUT = 50
        ex = CommandExecution.objects.create(
            command_name="verbose_output_command", triggered_by=superuser
        )
        execute_command("verbose_output_command", {"chars": 200}, ex.pk)
        ex.refresh_from_db()
        text = ex.output_text("stdout")
        # Only raw output is kept (no truncation marker), capped at ~50 chars;
        # the active part is never pruned so it can slightly exceed the cap.
        assert "truncated" not in text
        assert len(text) <= 100


# ---------------------------------------------------------------------------
# 3.x Terminal size
# ---------------------------------------------------------------------------


class TestTerminalSize:
    def test_defaults(self, settings):
        assert _terminal_size() == (120, 40)

    def test_configured(self, settings):
        settings.ADMIN_RUNNER_TERM_COLS = 80
        settings.ADMIN_RUNNER_TERM_ROWS = 24
        assert _terminal_size() == (80, 24)

    def test_bounds_clamped(self, settings):
        settings.ADMIN_RUNNER_TERM_COLS = 10_000
        settings.ADMIN_RUNNER_TERM_ROWS = 1
        cols, rows = _terminal_size()
        assert cols <= 500
        assert rows >= 5


@pytest.mark.django_db
class TestTerminalEnvExport:
    def _run(self, superuser, name="term_env_command"):
        ex = CommandExecution.objects.create(command_name=name, triggered_by=superuser)
        execute_command(name, {}, ex.pk)
        ex.refresh_from_db()
        assert ex.status == "SUCCESS", ex.output_text("stderr")
        return ex

    def test_env_set_from_defaults(self, superuser):
        os.environ.pop("COLUMNS", None)
        os.environ.pop("LINES", None)
        ex = self._run(superuser)
        assert "COLUMNS=120" in ex.output_text("stdout")
        assert "LINES=40" in ex.output_text("stdout")

    def test_env_set_from_settings(self, superuser, settings):
        settings.ADMIN_RUNNER_TERM_COLS = 80
        ex = self._run(superuser)
        assert "COLUMNS=80" in ex.output_text("stdout")

    def test_env_restored_after_run(self, superuser):
        old = {"COLUMNS": os.environ.get("COLUMNS"), "LINES": os.environ.get("LINES")}
        os.environ["COLUMNS"] = "77"
        os.environ["LINES"] = "11"
        try:
            self._run(superuser)
            assert os.environ["COLUMNS"] == "77"
            assert os.environ["LINES"] == "11"
        finally:
            for key, value in old.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_env_restored_when_absent_before(self, superuser):
        os.environ.pop("COLUMNS", None)
        os.environ.pop("LINES", None)
        self._run(superuser)
        assert "COLUMNS" not in os.environ
        assert "LINES" not in os.environ
