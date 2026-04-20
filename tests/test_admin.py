import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from django_admin_runner.models import CommandExecution

User = get_user_model()


# ---------------------------------------------------------------------------
# Run view — GET
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCommandRunViewGet:
    def test_run_view_ok(self, admin_client):
        url = reverse("admin:django_admin_runner_command_run", args=["simple_command"])
        response = admin_client.get(url)
        assert response.status_code == 200

    def test_run_view_has_form_in_context(self, admin_client):
        url = reverse("admin:django_admin_runner_command_run", args=["param_command"])
        response = admin_client.get(url)
        assert "form" in response.context

    def test_run_view_form_has_correct_fields(self, admin_client):
        url = reverse("admin:django_admin_runner_command_run", args=["param_command"])
        response = admin_client.get(url)
        form = response.context["form"]
        assert "count" in form.fields
        assert "mode" in form.fields
        assert "verbose" in form.fields

    def test_run_view_404_for_unknown_command(self, admin_client):
        url = reverse("admin:django_admin_runner_command_run", args=["nonexistent_command"])
        response = admin_client.get(url)
        assert response.status_code == 404

    def test_run_view_403_without_permission(self, staff_client):
        url = reverse("admin:django_admin_runner_command_run", args=["simple_command"])
        response = staff_client.get(url)
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Run view — POST
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCommandRunViewPost:
    def test_valid_post_creates_execution(self, admin_client):
        url = reverse("admin:django_admin_runner_command_run", args=["simple_command"])
        admin_client.post(url, {})
        assert CommandExecution.objects.filter(command_name="simple_command").exists()

    def test_valid_post_redirects(self, admin_client):
        url = reverse("admin:django_admin_runner_command_run", args=["simple_command"])
        response = admin_client.post(url, {})
        assert response.status_code == 302

    def test_valid_post_execution_sets_triggered_by(self, admin_client, superuser):
        url = reverse("admin:django_admin_runner_command_run", args=["simple_command"])
        admin_client.post(url, {})
        ex = CommandExecution.objects.filter(command_name="simple_command").first()
        assert ex.triggered_by == superuser

    def test_valid_post_with_params(self, admin_client):
        url = reverse("admin:django_admin_runner_command_run", args=["param_command"])
        admin_client.post(url, {"count": "3", "mode": "slow"})
        ex = CommandExecution.objects.filter(command_name="param_command").first()
        assert ex is not None

    def test_invalid_post_rerenders_form(self, admin_client):
        url = reverse("admin:django_admin_runner_command_run", args=["param_command"])
        # Pass an invalid integer for count
        response = admin_client.post(url, {"count": "not-a-number", "mode": "slow"})
        assert response.status_code == 200
        assert "form" in response.context
        assert response.context["form"].errors


# ---------------------------------------------------------------------------
# CommandExecutionAdmin queryset filtering
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCommandExecutionAdminQueryset:
    def test_superuser_sees_all_executions(self, admin_client, db):
        u1 = User.objects.create_user("u1", "u1@e.com", "pw")
        CommandExecution.objects.create(command_name="cmd", triggered_by=u1)
        CommandExecution.objects.create(command_name="cmd2", triggered_by=None)

        url = reverse("admin:django_admin_runner_commandexecution_changelist")
        response = admin_client.get(url)
        assert response.status_code == 200
        assert response.context["cl"].queryset.count() == 2

    def test_regular_user_sees_own_executions_only(self, client, db):
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        user = User.objects.create_user("limited", "l@e.com", "pw", is_staff=True)
        other = User.objects.create_user("other", "o@e.com", "pw")

        # Staff user needs at least view permission to access the changelist
        ct = ContentType.objects.get_for_model(CommandExecution)
        perm = Permission.objects.get(content_type=ct, codename="view_commandexecution")
        user.user_permissions.add(perm)

        CommandExecution.objects.create(command_name="mine", triggered_by=user)
        CommandExecution.objects.create(command_name="theirs", triggered_by=other)

        client.force_login(user)
        url = reverse("admin:django_admin_runner_commandexecution_changelist")
        response = client.get(url)
        assert response.status_code == 200
        qs = response.context["cl"].queryset
        assert qs.count() == 1
        assert qs.first().command_name == "mine"


# ---------------------------------------------------------------------------
# Result view
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestResultView:
    def test_result_view_with_result_html(self, admin_client, superuser):
        execution = CommandExecution.objects.create(
            command_name="simple_command",
            triggered_by=superuser,
            status="SUCCESS",
            result_html="<h1>Report</h1><p>Done</p>",
        )
        url = reverse("admin:django_admin_runner_commandexecution_result", args=[execution.pk])
        response = admin_client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "<h1>Report</h1>" in content

    def test_result_view_without_result_html_shows_stdout(self, admin_client, superuser):
        execution = CommandExecution.objects.create(
            command_name="simple_command",
            triggered_by=superuser,
            status="SUCCESS",
            stdout="Hello world output",
        )
        url = reverse("admin:django_admin_runner_commandexecution_result", args=[execution.pk])
        response = admin_client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Hello world output" in content

    def test_result_view_404_for_invalid_pk(self, admin_client):
        url = reverse("admin:django_admin_runner_commandexecution_result", args=[99999])
        response = admin_client.get(url)
        assert response.status_code == 404

    def test_result_view_permission_denied_for_other_user(self, client, db):
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        user = User.objects.create_user("limited", "l@e.com", "pw", is_staff=True)
        other = User.objects.create_superuser("admin2", "a2@e.com", "pw")
        ct = ContentType.objects.get_for_model(CommandExecution)
        perm = Permission.objects.get(content_type=ct, codename="view_commandexecution")
        user.user_permissions.add(perm)

        execution = CommandExecution.objects.create(
            command_name="cmd",
            triggered_by=other,
            result_html="<p>Secret</p>",
        )

        client.force_login(user)
        url = reverse("admin:django_admin_runner_commandexecution_result", args=[execution.pk])
        response = client.get(url)
        assert response.status_code == 404  # get_queryset filters it out
