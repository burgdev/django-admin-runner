import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from django_admin_runner.models import RegisteredCommand
from django_admin_runner.sync import sync_registered_commands

User = get_user_model()


@pytest.mark.django_db
class TestRegisteredCommandAdminPermissions:
    def test_has_add_permission_is_false(self, admin_client):
        url = reverse("admin:django_admin_runner_registeredcommand_add")
        response = admin_client.get(url)
        assert response.status_code == 403

    def test_has_change_permission_is_false(self, admin_client):
        sync_registered_commands()
        rc = RegisteredCommand.objects.first()
        url = reverse("admin:django_admin_runner_registeredcommand_change", args=[rc.pk])
        admin_client.post(url, {"name": "hacked"})
        # POST to change should be blocked (read-only)
        rc.refresh_from_db()
        assert rc.name != "hacked"

    def test_superuser_can_delete(self, admin_client, superuser):
        sync_registered_commands()
        rc = RegisteredCommand.objects.first()
        url = reverse("admin:django_admin_runner_registeredcommand_delete", args=[rc.pk])
        response = admin_client.get(url)
        assert response.status_code == 200

    def test_non_superuser_cannot_delete(self, staff_client):
        sync_registered_commands()
        rc = RegisteredCommand.objects.first()
        url = reverse("admin:django_admin_runner_registeredcommand_delete", args=[rc.pk])
        response = staff_client.get(url)
        assert response.status_code == 403


@pytest.mark.django_db
class TestRegisteredCommandAdminChangelist:
    def _create_commands(self):
        RegisteredCommand.objects.create(
            name="active_cmd", group="G1", display_name="Active Command", active=True
        )
        RegisteredCommand.objects.create(
            name="inactive_cmd", group="G1", display_name="Inactive Command", active=False
        )

    def test_default_redirects_to_active_yes(self, admin_client):
        self._create_commands()
        url = reverse("admin:django_admin_runner_registeredcommand_changelist")
        response = admin_client.get(url)
        # Redirects to add ?active=1
        assert response.status_code == 302
        assert "active=1" in response.url

    def test_default_filter_shows_active_only(self, admin_client):
        self._create_commands()
        url = reverse("admin:django_admin_runner_registeredcommand_changelist")
        response = admin_client.get(url, follow=True)
        assert response.status_code == 200
        qs = response.context["cl"].queryset
        assert qs.filter(name="active_cmd").exists()
        assert not qs.filter(name="inactive_cmd").exists()

    def test_active_filter_can_show_inactive(self, admin_client):
        self._create_commands()
        url = reverse("admin:django_admin_runner_registeredcommand_changelist")
        # Filtering by active=0 (No) shows inactive commands
        response = admin_client.get(url, {"active": "0"})
        assert response.status_code == 200
        qs = response.context["cl"].queryset
        assert qs.filter(name="inactive_cmd").exists()
        assert not qs.filter(name="active_cmd").exists()

    def test_active_filter_true_shows_active(self, admin_client):
        self._create_commands()
        url = reverse("admin:django_admin_runner_registeredcommand_changelist")
        response = admin_client.get(url, {"active": "1"})
        assert response.status_code == 200
        qs = response.context["cl"].queryset
        assert qs.filter(name="active_cmd").exists()
        assert not qs.filter(name="inactive_cmd").exists()

    def test_run_link_visible_for_active(self, admin_client):
        self._create_commands()
        url = reverse("admin:django_admin_runner_registeredcommand_changelist")
        # Override the default filter to see the active command
        response = admin_client.get(url, {"active": "1"})
        assert response.status_code == 200
        content = response.content.decode()
        assert "active_cmd" in content
        run_url = reverse("admin:django_admin_runner_command_run", args=["active_cmd"])
        assert run_url in content

    def test_run_link_dash_for_inactive(self, admin_client):
        self._create_commands()
        url = reverse("admin:django_admin_runner_registeredcommand_changelist")
        response = admin_client.get(url, {"active": "0"})
        assert response.status_code == 200
        content = response.content.decode()
        assert "inactive_cmd" in content
        run_url = reverse("admin:django_admin_runner_command_run", args=["inactive_cmd"])
        assert run_url not in content

    def test_name_link_shows_display_name(self, admin_client):
        RegisteredCommand.objects.create(
            name="my_cmd", group="G1", display_name="My Command", active=True
        )
        url = reverse("admin:django_admin_runner_registeredcommand_changelist")
        response = admin_client.get(url, follow=True)
        content = response.content.decode()
        assert "<strong>My Command</strong>" in content

    def test_name_link_shows_description(self, admin_client):
        RegisteredCommand.objects.create(
            name="my_cmd",
            group="G1",
            display_name="My Command",
            description="Some help text",
            active=True,
        )
        url = reverse("admin:django_admin_runner_registeredcommand_changelist")
        response = admin_client.get(url, follow=True)
        content = response.content.decode()
        assert "Some help text" in content

    def test_history_link_present(self, admin_client):
        self._create_commands()
        url = reverse("admin:django_admin_runner_registeredcommand_changelist")
        response = admin_client.get(url, {"active": "1"})
        assert response.status_code == 200
        content = response.content.decode()
        history_url = (
            reverse("admin:django_admin_runner_commandexecution_changelist")
            + "?command_name=active_cmd"
        )
        assert history_url in content

    def test_search_by_name(self, admin_client):
        self._create_commands()
        url = reverse("admin:django_admin_runner_registeredcommand_changelist")
        response = admin_client.get(url, {"q": "active_cmd"}, follow=True)
        assert response.status_code == 200
        qs = response.context["cl"].queryset
        assert qs.filter(name="active_cmd").exists()

    def test_search_by_display_name(self, admin_client):
        self._create_commands()
        url = reverse("admin:django_admin_runner_registeredcommand_changelist")
        response = admin_client.get(url, {"q": "Active Command"}, follow=True)
        assert response.status_code == 200
        qs = response.context["cl"].queryset
        assert qs.filter(name="active_cmd").exists()
