import pytest

from django_admin_runner.registry import (
    _registry,
    has_permission,
    register_command,
)

# ---------------------------------------------------------------------------
# @register_command decorator
# ---------------------------------------------------------------------------


def test_register_stores_name():
    @register_command()
    class Cmd:
        __module__ = "myapp.management.commands.my_cmd"

    assert "my_cmd" in _registry
    assert _registry["my_cmd"]["name"] == "my_cmd"
    del _registry["my_cmd"]


def test_register_explicit_name():
    @register_command(name="explicit")
    class Cmd:
        __module__ = "myapp.management.commands.whatever"

    assert "explicit" in _registry
    del _registry["explicit"]


def test_register_default_group_is_app_label():
    @register_command()
    class Cmd:
        __module__ = "books.management.commands.import_books"

    entry = _registry["import_books"]
    assert entry["group"] == "books"
    assert entry["app_label"] == "books"
    del _registry["import_books"]


def test_register_explicit_group():
    @register_command(group="Import")
    class Cmd:
        __module__ = "books.management.commands.import_books"

    assert _registry["import_books"]["group"] == "Import"
    del _registry["import_books"]


def test_register_default_permission_is_superuser():
    @register_command()
    class Cmd:
        __module__ = "myapp.management.commands.cmd1"

    assert _registry["cmd1"]["permission"] == "superuser"
    del _registry["cmd1"]


def test_register_custom_permission_string():
    @register_command(permission="books.change_book")
    class Cmd:
        __module__ = "books.management.commands.cleanup"

    assert _registry["cleanup"]["permission"] == "books.change_book"
    del _registry["cleanup"]


def test_register_permission_list():
    @register_command(permission=["books.view_book", "orders.change_order"])
    class Cmd:
        __module__ = "books.management.commands.export"

    assert _registry["export"]["permission"] == ["books.view_book", "orders.change_order"]
    del _registry["export"]


def test_register_params():
    @register_command(params=["source", "dry_run"])
    class Cmd:
        __module__ = "myapp.management.commands.import_data"

    assert _registry["import_data"]["params"] == ["source", "dry_run"]
    del _registry["import_data"]


def test_register_exclude_params():
    @register_command(exclude_params=["verbosity"])
    class Cmd:
        __module__ = "myapp.management.commands.cleanup_data"

    assert _registry["cleanup_data"]["exclude_params"] == ["verbosity"]
    del _registry["cleanup_data"]


def test_register_models():
    class FakeModel:
        pass

    @register_command(models=[FakeModel])
    class Cmd:
        __module__ = "myapp.management.commands.attach_cmd"

    assert FakeModel in _registry["attach_cmd"]["models"]
    del _registry["attach_cmd"]


def test_register_duplicate_overwrites():
    @register_command(group="First")
    class Cmd:
        __module__ = "myapp.management.commands.dup_cmd"

    @register_command(group="Second")
    class Cmd2:
        __module__ = "myapp.management.commands.dup_cmd"
        __name__ = "Cmd2"

    # Only one entry; the second registration wins
    assert _registry["dup_cmd"]["group"] == "Second"
    del _registry["dup_cmd"]


# ---------------------------------------------------------------------------
# has_permission
# ---------------------------------------------------------------------------


class _FakeUser:
    def __init__(self, is_superuser=False, perms=()):
        self.is_superuser = is_superuser
        self._perms = set(perms)

    def has_perm(self, perm):
        return perm in self._perms


def test_superuser_always_allowed():
    entry = {"permission": "superuser"}
    assert has_permission(_FakeUser(is_superuser=True), entry) is True


def test_non_superuser_blocked_by_superuser_permission():
    entry = {"permission": "superuser"}
    assert has_permission(_FakeUser(), entry) is False


def test_single_perm_allowed():
    entry = {"permission": "books.change_book"}
    user = _FakeUser(perms=["books.change_book"])
    assert has_permission(user, entry) is True


def test_single_perm_denied():
    entry = {"permission": "books.change_book"}
    user = _FakeUser(perms=[])
    assert has_permission(user, entry) is False


def test_perm_list_and_logic_all_held():
    entry = {"permission": ["books.view_book", "orders.change_order"]}
    user = _FakeUser(perms=["books.view_book", "orders.change_order"])
    assert has_permission(user, entry) is True


def test_perm_list_and_logic_partial():
    entry = {"permission": ["books.view_book", "orders.change_order"]}
    user = _FakeUser(perms=["books.view_book"])
    assert has_permission(user, entry) is False


# ---------------------------------------------------------------------------
# autodiscover populates registry from installed apps
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_autodiscover_populates_registry():
    # Commands from tests.testapp should already be registered via AppConfig.ready()
    assert "simple_command" in _registry
    assert "param_command" in _registry
    assert "failing_command" in _registry
    assert "hidden_command" in _registry


@pytest.mark.django_db
def test_autodiscover_app_label():
    assert _registry["simple_command"]["app_label"] == "testapp"


@pytest.mark.django_db
def test_autodiscover_default_group():
    # group defaults to app_label when not specified
    assert _registry["simple_command"]["group"] == "Test"


@pytest.mark.django_db
def test_autodiscover_exclude_params_stored():
    assert _registry["hidden_command"]["exclude_params"] == ["internal"]
