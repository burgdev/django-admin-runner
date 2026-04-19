import os

import pytest
from django.test import override_settings

from django_admin_runner.hooks import (
    CommandHook,
    HookContext,
    TempFileHook,
    get_hooks,
    reset_hooks_cache,
)


@pytest.fixture(autouse=True)
def _clear_hooks_cache():
    yield
    reset_hooks_cache()


# ---------------------------------------------------------------------------
# HookContext
# ---------------------------------------------------------------------------


class TestHookContext:
    def test_set_and_get(self):
        ctx = HookContext()
        ctx["key"] = "value"
        assert ctx["key"] == "value"

    def test_get_with_default(self):
        ctx = HookContext()
        assert ctx.get("missing") is None
        assert ctx.get("missing", "fallback") == "fallback"

    def test_fresh_per_execution(self):
        ctx1 = HookContext()
        ctx1["dir"] = "/a"
        ctx2 = HookContext()
        assert ctx2.get("dir") is None


# ---------------------------------------------------------------------------
# get_hooks
# ---------------------------------------------------------------------------


class TestGetHooks:
    def test_no_hooks_without_settings(self):
        reset_hooks_cache()
        with override_settings(ADMIN_RUNNER_HOOKS=[], ADMIN_RUNNER_UPLOAD_PATH=""):
            hooks = get_hooks()
        assert hooks == []

    def test_temp_file_hook_auto_registered_with_upload_path(self, tmp_path):
        reset_hooks_cache()
        with override_settings(ADMIN_RUNNER_HOOKS=[], ADMIN_RUNNER_UPLOAD_PATH=str(tmp_path)):
            hooks = get_hooks()
        assert len(hooks) == 1
        assert isinstance(hooks[0], TempFileHook)

    def test_user_hook_loaded(self, tmp_path):
        reset_hooks_cache()
        with override_settings(
            ADMIN_RUNNER_HOOKS=["django_admin_runner.hooks.TempFileHook"],
            ADMIN_RUNNER_UPLOAD_PATH="",
        ):
            hooks = get_hooks()
        assert len(hooks) == 1
        assert isinstance(hooks[0], TempFileHook)

    def test_invalid_hook_path_raises(self):
        reset_hooks_cache()
        with (
            override_settings(
                ADMIN_RUNNER_HOOKS=["nonexistent.Module.Hook"],
                ADMIN_RUNNER_UPLOAD_PATH="",
            ),
            pytest.raises(ImportError),
        ):
            get_hooks()

    def test_non_hook_subclass_raises(self):
        reset_hooks_cache()
        with (
            override_settings(
                ADMIN_RUNNER_HOOKS=["django_admin_runner.hooks.HookContext"],
                ADMIN_RUNNER_UPLOAD_PATH="",
            ),
            pytest.raises(TypeError, match="not a CommandHook subclass"),
        ):
            get_hooks()


# ---------------------------------------------------------------------------
# TempFileHook
# ---------------------------------------------------------------------------


class TestTempFileHook:
    def test_setup_creates_directory(self, tmp_path):
        from django_admin_runner.models import CommandExecution

        hook = TempFileHook()
        ctx = HookContext()
        with override_settings(ADMIN_RUNNER_UPLOAD_PATH=str(tmp_path)):
            execution = CommandExecution(command_name="test")
            hook.setup("test_cmd", {}, execution, ctx)
        upload_dir = ctx.get("upload_dir")
        assert upload_dir is not None
        assert os.path.isdir(upload_dir)
        assert str(tmp_path) in upload_dir

    def test_teardown_removes_directory(self, tmp_path):
        from django_admin_runner.models import CommandExecution

        hook = TempFileHook()
        ctx = HookContext()
        with override_settings(ADMIN_RUNNER_UPLOAD_PATH=str(tmp_path)):
            execution = CommandExecution(command_name="test")
            hook.setup("test_cmd", {}, execution, ctx)
            upload_dir = ctx["upload_dir"]
            assert os.path.isdir(upload_dir)
            hook.post_save("test_cmd", {}, execution, ctx)
        assert not os.path.exists(upload_dir)

    def test_setup_noop_without_upload_path(self):
        from django_admin_runner.models import CommandExecution

        hook = TempFileHook()
        ctx = HookContext()
        with override_settings(ADMIN_RUNNER_UPLOAD_PATH=""):
            execution = CommandExecution(command_name="test")
            hook.setup("test_cmd", {}, execution, ctx)
        assert ctx.get("upload_dir") is None

    def test_teardown_noop_without_upload_dir(self):
        from django_admin_runner.models import CommandExecution

        hook = TempFileHook()
        ctx = HookContext()
        execution = CommandExecution(command_name="test")
        # Should not raise
        hook.post_save("test_cmd", {}, execution, ctx)


# ---------------------------------------------------------------------------
# Hooks integration in execute_command
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestHooksIntegration:
    def test_setup_and_post_save_called(self, superuser, tmp_path):
        """Hooks setup and post_save are called around command execution."""
        from django_admin_runner.models import CommandExecution
        from django_admin_runner.tasks import execute_command

        calls = []

        class TrackingHook(CommandHook):
            def setup(self, command_name, kwargs, execution, ctx):
                calls.append(("setup", command_name))

            def post_save(self, command_name, kwargs, execution, ctx):
                calls.append(("post_save", command_name))

        import django_admin_runner.hooks as hooks_module

        original_get_hooks = hooks_module.get_hooks
        hooks_module.get_hooks = lambda: [TrackingHook()]
        try:
            execution = CommandExecution.objects.create(
                command_name="simple_command",
                triggered_by=superuser,
            )
            execute_command("simple_command", {}, execution.pk)
            execution.refresh_from_db()
            assert execution.status == "SUCCESS"
            assert calls == [("setup", "simple_command"), ("post_save", "simple_command")]
        finally:
            hooks_module.get_hooks = original_get_hooks

    def test_post_save_called_on_failure(self, superuser):
        """Post_save runs even when command fails."""
        from django_admin_runner.models import CommandExecution
        from django_admin_runner.tasks import execute_command

        calls = []

        class TrackingHook(CommandHook):
            def setup(self, command_name, kwargs, execution, ctx):
                calls.append("setup")

            def post_save(self, command_name, kwargs, execution, ctx):
                calls.append("post_save")

        import django_admin_runner.hooks as hooks_module

        original_get_hooks = hooks_module.get_hooks
        hooks_module.get_hooks = lambda: [TrackingHook()]
        try:
            execution = CommandExecution.objects.create(
                command_name="failing_command",
                triggered_by=superuser,
            )
            with pytest.raises(Exception):
                execute_command("failing_command", {}, execution.pk)
            execution.refresh_from_db()
            assert execution.status == "FAILED"
            assert "post_save" in calls
        finally:
            hooks_module.get_hooks = original_get_hooks

    def test_post_save_error_does_not_override_status(self, superuser):
        """Post_save errors are logged but don't override command status."""
        from django_admin_runner.models import CommandExecution
        from django_admin_runner.tasks import execute_command

        class BrokenPostSaveHook(CommandHook):
            def setup(self, command_name, kwargs, execution, ctx):
                pass

            def post_save(self, command_name, kwargs, execution, ctx):
                raise RuntimeError("post_save exploded")

        import django_admin_runner.hooks as hooks_module

        original_get_hooks = hooks_module.get_hooks
        hooks_module.get_hooks = lambda: [BrokenPostSaveHook()]
        try:
            execution = CommandExecution.objects.create(
                command_name="simple_command",
                triggered_by=superuser,
            )
            execute_command("simple_command", {}, execution.pk)
            execution.refresh_from_db()
            # Status should be SUCCESS, not affected by post_save error
            assert execution.status == "SUCCESS"
        finally:
            hooks_module.get_hooks = original_get_hooks

    def test_hooks_called_in_correct_order(self, superuser):
        """Multiple hooks: setup/pre_save forward, post_save reverse."""
        from django_admin_runner.models import CommandExecution
        from django_admin_runner.tasks import execute_command

        order = []

        class HookA(CommandHook):
            def setup(self, cn, kw, ex, ctx):
                order.append("setup_A")

            def pre_save(self, cn, kw, ex, ctx):
                order.append("pre_save_A")

            def post_save(self, cn, kw, ex, ctx):
                order.append("post_save_A")

        class HookB(CommandHook):
            def setup(self, cn, kw, ex, ctx):
                order.append("setup_B")

            def pre_save(self, cn, kw, ex, ctx):
                order.append("pre_save_B")

            def post_save(self, cn, kw, ex, ctx):
                order.append("post_save_B")

        import django_admin_runner.hooks as hooks_module

        original_get_hooks = hooks_module.get_hooks
        hooks_module.get_hooks = lambda: [HookA(), HookB()]
        try:
            execution = CommandExecution.objects.create(
                command_name="simple_command",
                triggered_by=superuser,
            )
            execute_command("simple_command", {}, execution.pk)
            assert order == [
                "setup_A",
                "setup_B",
                "pre_save_A",
                "pre_save_B",
                "post_save_B",
                "post_save_A",
            ]
        finally:
            hooks_module.get_hooks = original_get_hooks

    def test_pre_save_hook_can_set_result_html(self, superuser):
        """Pre_save hooks can modify execution state before save."""
        from django_admin_runner.models import CommandExecution
        from django_admin_runner.tasks import execute_command

        class ResultSetterHook(CommandHook):
            def pre_save(self, command_name, kwargs, execution, ctx):
                execution.result_html = "<div>Hook Result</div>"

        import django_admin_runner.hooks as hooks_module

        original_get_hooks = hooks_module.get_hooks
        hooks_module.get_hooks = lambda: [ResultSetterHook()]
        try:
            execution = CommandExecution.objects.create(
                command_name="simple_command",
                triggered_by=superuser,
            )
            execute_command("simple_command", {}, execution.pk)
            execution.refresh_from_db()
            assert execution.status == "SUCCESS"
            assert execution.result_html == "<div>Hook Result</div>"
        finally:
            hooks_module.get_hooks = original_get_hooks

    def test_pre_save_and_post_save_run_on_failure(self, superuser):
        """Pre_save and post_save run even when the command fails."""
        from django_admin_runner.models import CommandExecution
        from django_admin_runner.tasks import execute_command

        calls = []

        class TrackingHook(CommandHook):
            def pre_save(self, cn, kw, ex, ctx):
                calls.append("pre_save")

            def post_save(self, cn, kw, ex, ctx):
                calls.append("post_save")

        import django_admin_runner.hooks as hooks_module

        original_get_hooks = hooks_module.get_hooks
        hooks_module.get_hooks = lambda: [TrackingHook()]
        try:
            execution = CommandExecution.objects.create(
                command_name="failing_command",
                triggered_by=superuser,
            )
            with pytest.raises(Exception):
                execute_command("failing_command", {}, execution.pk)
            execution.refresh_from_db()
            assert execution.status == "FAILED"
            assert "pre_save" in calls
            assert "post_save" in calls
        finally:
            hooks_module.get_hooks = original_get_hooks
