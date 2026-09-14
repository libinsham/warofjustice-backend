import pytest
from django.urls import reverse

from apps.accounts.models import User


@pytest.mark.django_db
class TestRegistration:
    def test_register_reader_creates_active_user(self, api_client, roles):
        response = api_client.post(
            "/api/v1/auth/register/",
            {"email": "newreader@test.com", "username": "newreader", "password": "SecurePass123!"},
        )
        assert response.status_code == 201
        user = User.objects.get(email="newreader@test.com")
        assert user.status == User.ACTIVE
        assert user.role.name == "reader"
        # refresh token must NOT be in the body — only in the httpOnly cookie
        assert "refresh" not in response.data
        assert "access" in response.data

    def test_register_author_starts_pending(self, api_client, roles):
        response = api_client.post(
            "/api/v1/auth/register-author/",
            {"email": "newauthor@test.com", "username": "newauthor", "password": "SecurePass123!"},
        )
        assert response.status_code == 201
        user = User.objects.get(email="newauthor@test.com")
        assert user.status == User.PENDING
        assert user.role.name == "author"
        # no tokens issued for a pending account
        assert "access" not in response.data

    def test_duplicate_email_rejected(self, api_client, author):
        response = api_client.post(
            "/api/v1/auth/register/",
            {"email": author.email, "username": "someoneelse", "password": "SecurePass123!"},
        )
        assert response.status_code == 400


@pytest.mark.django_db
class TestLogin:
    def test_login_success_sets_httponly_cookie(self, api_client, author):
        response = api_client.post(
            "/api/v1/auth/login/", {"email": author.email, "password": "JanePass123!"}
        )
        assert response.status_code == 200
        assert "access" in response.data
        assert "refresh" not in response.data  # never in the body
        cookie = response.cookies.get("newshub_refresh_token")
        assert cookie is not None
        assert cookie["httponly"] is True

    def test_login_wrong_password_rejected(self, api_client, author):
        response = api_client.post(
            "/api/v1/auth/login/", {"email": author.email, "password": "WrongPassword"}
        )
        assert response.status_code == 401

    def test_pending_author_cannot_login(self, api_client, roles):
        pending_user = User.objects.create(
            username="pendingauthor", email="pending@test.com", role=roles["author"], status=User.PENDING
        )
        pending_user.set_password("SecurePass123!")
        pending_user.save()

        response = api_client.post(
            "/api/v1/auth/login/", {"email": "pending@test.com", "password": "SecurePass123!"}
        )
        assert response.status_code == 401
        assert "pending" in response.data["detail"].lower()

    def test_suspended_user_cannot_login(self, api_client, roles):
        suspended = User.objects.create(
            username="suspendeduser", email="suspended@test.com", role=roles["reader"], status=User.SUSPENDED
        )
        suspended.set_password("SecurePass123!")
        suspended.save()

        response = api_client.post(
            "/api/v1/auth/login/", {"email": "suspended@test.com", "password": "SecurePass123!"}
        )
        assert response.status_code == 401
        assert "suspended" in response.data["detail"].lower()


@pytest.mark.django_db
class TestPasswordFlows:
    def test_change_password_requires_correct_current_password(self, api_client, author):
        from tests.conftest import authed_client
        client = authed_client(api_client, author)

        response = client.post(
            "/api/v1/auth/change-password/",
            {"current_password": "WrongPassword", "new_password": "NewSecurePass123!"},
        )
        assert response.status_code == 400

    def test_change_password_success(self, api_client, author):
        from tests.conftest import authed_client
        client = authed_client(api_client, author)

        response = client.post(
            "/api/v1/auth/change-password/",
            {"current_password": "JanePass123!", "new_password": "NewSecurePass123!"},
        )
        assert response.status_code == 200

        author.refresh_from_db()
        assert author.check_password("NewSecurePass123!")

    def test_forgot_password_never_reveals_whether_email_exists(self, api_client, author):
        real_response = api_client.post("/api/v1/auth/forgot-password/", {"email": author.email})
        fake_response = api_client.post("/api/v1/auth/forgot-password/", {"email": "nobody@test.com"})

        assert real_response.status_code == 200
        assert fake_response.status_code == 200
        assert real_response.data["message"] == fake_response.data["message"]
