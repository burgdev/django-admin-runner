import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings

from django_admin_runner.models import CommandExecution
from django_admin_runner.runners import get_runner
from django_admin_runner.runners.django_tasks import _is_immediate_backend
from django_admin_runner.runners.sync import SyncCommandRunner

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user("runner_user", "r@example.com", "pw")


@pytest.fixture
def execution(db):
    return CommandExecution.objects.create(command_name="simple_command")


@pytest.fixture
def failing_execution(db):
    return CommandExecution.objects.create(command_name="failing_command")


# ---------------------------------------------------------------------------
# SyncCommandRunner
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSyncCommandRunner:
    def test_success_status(self, user, execution):
        runner = SyncCommandRunner()
        runner.run("simple_command", {}, user, execution)
        execution.refresh_from_db()
        assert execution.status == CommandExecution.Status.SUCCESS

    def test_success_stdout_populated(self, user, execution):
        runner = SyncCommandRunner()
        runner.run("simple_command", {}, user, execution)
        execution.refresh_from_db()
        assert "simple output" in execution.stdout

    def test_failure_status(self, user, failing_execution):
        runner = SyncCommandRunner()
        runner.run("failing_command", {}, user, failing_execution)
        failing_execution.refresh_from_db()
        assert failing_execution.status == CommandExecution.Status.FAILED

    def test_failure_stderr_populated(self, user, failing_execution):
        runner = SyncCommandRunner()
        runner.run("failing_command", {}, user, failing_execution)
        failing_execution.refresh_from_db()
        assert "intentional failure" in failing_execution.stderr

    def test_backend_field_set(self, user, execution):
        runner = SyncCommandRunner()
        runner.run("simple_command", {}, user, execution)
        execution.refresh_from_db()
        assert execution.backend == "sync"

    def test_timestamps_set(self, user, execution):
        runner = SyncCommandRunner()
        runner.run("simple_command", {}, user, execution)
        execution.refresh_from_db()
        assert execution.started_at is not None
        assert execution.finished_at is not None

    def test_is_async_false(self, user, execution):
        runner = SyncCommandRunner()
        result = runner.run("simple_command", {}, user, execution)
        assert result.is_async is False


# ---------------------------------------------------------------------------
# DjangoTaskRunner with ImmediateBackend
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDjangoTaskRunner:
    def test_success_status(self, user, db):
        from django_admin_runner.runners.django_tasks import DjangoTaskRunner

        execution = CommandExecution.objects.create(command_name="simple_command")
        runner = DjangoTaskRunner()
        runner.run("simple_command", {}, user, execution)
        execution.refresh_from_db()
        assert execution.status == CommandExecution.Status.SUCCESS

    def test_backend_field_set(self, user, db):
        from django_admin_runner.runners.django_tasks import DjangoTaskRunner

        execution = CommandExecution.objects.create(command_name="simple_command")
        runner = DjangoTaskRunner()
        runner.run("simple_command", {}, user, execution)
        execution.refresh_from_db()
        assert execution.backend == "django"

    def test_task_id_populated(self, user, db):
        from django_admin_runner.runners.django_tasks import DjangoTaskRunner

        execution = CommandExecution.objects.create(command_name="simple_command")
        runner = DjangoTaskRunner()
        result = runner.run("simple_command", {}, user, execution)
        assert result.task_id != ""

    def test_is_async_false_with_immediate_backend(self, user, db):
        from django_admin_runner.runners.django_tasks import DjangoTaskRunner

        execution = CommandExecution.objects.create(command_name="simple_command")
        runner = DjangoTaskRunner()
        result = runner.run("simple_command", {}, user, execution)
        assert result.is_async is False

    def test_failure_status(self, user, db):
        from django_admin_runner.runners.django_tasks import DjangoTaskRunner

        execution = CommandExecution.objects.create(command_name="failing_command")
        runner = DjangoTaskRunner()
        runner.run("failing_command", {}, user, execution)
        execution.refresh_from_db()
        assert execution.status == CommandExecution.Status.FAILED


# ---------------------------------------------------------------------------
# _is_immediate_backend
# ---------------------------------------------------------------------------


def test_is_immediate_backend_true():
    settings = {
        "TASKS": {
            "default": {
                "BACKEND": "django.tasks.backends.immediate.ImmediateBackend"
            }
        }
    }
    with override_settings(**settings):
        assert _is_immediate_backend() is True


def test_is_immediate_backend_false():
    settings = {
        "TASKS": {
            "default": {
                "BACKEND": "django.tasks.backends.database.DatabaseBackend"
            }
        }
    }
    with override_settings(**settings):
        assert _is_immediate_backend() is False


def test_is_immediate_backend_no_tasks_setting():
    with override_settings(TASKS={}):
        assert _is_immediate_backend() is False


# ---------------------------------------------------------------------------
# get_runner factory
# ---------------------------------------------------------------------------


def test_get_runner_default_returns_django_task_runner():
    with override_settings(ADMIN_RUNNER_BACKEND="django"):
        runner = get_runner()
        assert runner.backend == "django"


def test_get_runner_sync():
    with override_settings(ADMIN_RUNNER_BACKEND="sync"):
        runner = get_runner()
        assert runner.backend == "sync"


def test_get_runner_no_setting_defaults_to_django():
    # Remove the setting entirely
    from django.conf import settings as django_settings

    original = getattr(django_settings, "ADMIN_RUNNER_BACKEND", None)
    if hasattr(django_settings, "ADMIN_RUNNER_BACKEND"):
        delattr(django_settings, "ADMIN_RUNNER_BACKEND")
    try:
        runner = get_runner()
        assert runner.backend == "django"
    finally:
        if original is not None:
            django_settings.ADMIN_RUNNER_BACKEND = original


def test_get_runner_dotted_path():
    with override_settings(
        ADMIN_RUNNER_BACKEND="django_admin_runner.runners.sync.SyncCommandRunner"
    ):
        runner = get_runner()
        assert runner.backend == "sync"
