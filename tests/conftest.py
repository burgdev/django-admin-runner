import concurrent.futures

import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


class _InlineFuture(concurrent.futures.Future):
    """Already-completed future returned by the inline test executor."""

    def __init__(self):
        super().__init__()
        self.set_result(None)


class InlineAppendExecutor:
    """Runs submitted appends synchronously on the calling thread.

    The production append executor is a separate worker thread, which the
    per-connection in-memory test database cannot share. Inline execution
    preserves the guarantees under test (FIFO ordering, no overlap) while
    keeping the writes visible to the test thread.
    """

    def submit(self, fn, /, *args, **kwargs):
        fn(*args, **kwargs)
        return _InlineFuture()


@pytest.fixture(autouse=True)
def _inline_append_executor(monkeypatch):
    """Route output appends through the inline executor for all tests."""
    from django_admin_runner import tasks as tasks_mod

    monkeypatch.setattr(tasks_mod, "_APPEND_EXECUTOR", InlineAppendExecutor())


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser("admin", "admin@example.com", "password")


@pytest.fixture
def regular_user(db):
    return User.objects.create_user("user", "user@example.com", "password")


@pytest.fixture
def staff_user(db):
    return User.objects.create_user("staff", "staff@example.com", "password", is_staff=True)


@pytest.fixture
def admin_client(client, superuser):
    client.force_login(superuser)
    return client


@pytest.fixture
def staff_client(client, staff_user):
    client.force_login(staff_user)
    return client
