import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.categories.models import Category


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def roles(db):
    """Seeds the same roles the seed_roles management command creates,
    scoped to a minimal set needed for tests (no permissions needed —
    User.is_super_admin()/has_role() only check role.name)."""
    return {
        "super_admin": Role.objects.create(name=Role.SUPER_ADMIN, label="Super Admin"),
        "admin": Role.objects.create(name=Role.ADMIN, label="Admin / Editor"),
        "author": Role.objects.create(name=Role.AUTHOR, label="Author / User"),
        "reader": Role.objects.create(name=Role.READER, label="Reader"),
    }


@pytest.fixture
def super_admin(roles):
    user = User.objects.create(
        username="root", email="root@test.com", role=roles["super_admin"], status=User.ACTIVE
    )
    user.set_password("RootPass123!")
    user.save()
    return user


@pytest.fixture
def admin_user(roles):
    user = User.objects.create(
        username="admin", email="admin@test.com", role=roles["admin"], status=User.ACTIVE
    )
    user.set_password("AdminPass123!")
    user.save()
    return user


@pytest.fixture
def author(roles):
    user = User.objects.create(
        username="jane", email="jane@test.com", role=roles["author"], status=User.ACTIVE
    )
    user.set_password("JanePass123!")
    user.save()
    return user


@pytest.fixture
def another_author(roles):
    user = User.objects.create(
        username="bob", email="bob@test.com", role=roles["author"], status=User.ACTIVE
    )
    user.set_password("BobPass123!")
    user.save()
    return user


@pytest.fixture
def reader(roles):
    user = User.objects.create(
        username="reader1", email="reader1@test.com", role=roles["reader"], status=User.ACTIVE
    )
    user.set_password("ReaderPass123!")
    user.save()
    return user


@pytest.fixture
def category(db):
    return Category.objects.create(name="Technology", slug="technology")


def authed_client(client, user):
    """Log in as `user` and return an APIClient with the Authorization
    header set — the fast path for tests that need an authenticated
    client without exercising the full login endpoint each time."""
    from rest_framework_simplejwt.tokens import RefreshToken

    token = RefreshToken.for_user(user).access_token
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client
