import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


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
