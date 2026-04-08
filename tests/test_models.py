import pytest
from django.contrib.auth import get_user_model

from django_admin_runner.models import CommandExecution

User = get_user_model()


@pytest.mark.django_db
class TestCommandExecution:
    def test_default_status_is_pending(self):
        ex = CommandExecution.objects.create(command_name="test_cmd")
        assert ex.status == CommandExecution.Status.PENDING

    def test_str_representation(self):
        ex = CommandExecution(command_name="my_cmd", status="SUCCESS")
        assert "my_cmd" in str(ex)
        assert "SUCCESS" in str(ex)

    def test_triggered_by_nullable(self):
        ex = CommandExecution.objects.create(command_name="test_cmd", triggered_by=None)
        assert ex.triggered_by is None

    def test_triggered_by_survives_user_deletion(self):
        user = User.objects.create_user("tempuser", "t@example.com", "pw")
        ex = CommandExecution.objects.create(command_name="test_cmd", triggered_by=user)
        user.delete()
        ex.refresh_from_db()
        assert ex.triggered_by is None

    def test_kwargs_stored_as_json(self):
        payload = {"count": 5, "mode": "fast", "nested": {"key": "value"}}
        ex = CommandExecution.objects.create(command_name="test_cmd", kwargs=payload)
        ex.refresh_from_db()
        assert ex.kwargs == payload

    def test_ordering_is_newest_first(self):
        ex1 = CommandExecution.objects.create(command_name="cmd_a")
        ex2 = CommandExecution.objects.create(command_name="cmd_b")
        qs = list(CommandExecution.objects.all())
        # ex2 was created after ex1, so it should appear first
        assert qs[0].pk == ex2.pk
        assert qs[1].pk == ex1.pk

    def test_timestamps_initially_null(self):
        ex = CommandExecution.objects.create(command_name="test_cmd")
        assert ex.started_at is None
        assert ex.finished_at is None

    def test_created_at_auto_set(self):
        ex = CommandExecution.objects.create(command_name="test_cmd")
        assert ex.created_at is not None

    def test_blank_backend_and_task_id(self):
        ex = CommandExecution.objects.create(command_name="test_cmd")
        assert ex.backend == ""
        assert ex.task_id == ""
