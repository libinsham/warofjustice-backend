"""RBAC boundary tests — every one of these mirrors a live curl check
done by hand during development (categories write, settings write, user
management, admin videos)."""
import pytest

from tests.conftest import authed_client


@pytest.mark.django_db
class TestCategoryPermissions:
    def test_anyone_can_read_categories(self, api_client, category):
        response = api_client.get("/api/v1/categories/")
        assert response.status_code == 200

    def test_author_cannot_create_category(self, api_client, author):
        client = authed_client(api_client, author)
        response = client.post("/api/v1/categories/", {"name": "World"})
        assert response.status_code == 403

    def test_admin_can_create_category(self, api_client, admin_user):
        client = authed_client(api_client, admin_user)
        response = client.post("/api/v1/categories/", {"name": "World"})
        assert response.status_code == 201


@pytest.mark.django_db
class TestSiteSettingsPermissions:
    def test_anonymous_can_read_settings(self, api_client):
        response = api_client.get("/api/v1/settings/")
        assert response.status_code == 200

    def test_anonymous_cannot_write_settings(self, api_client):
        response = api_client.post("/api/v1/settings/", {"key": "site_name", "value": "Hacked"})
        assert response.status_code == 401

    def test_admin_cannot_write_settings(self, api_client, admin_user):
        """Only Super Admin can write settings — a plain Admin/Editor gets a real 403."""
        client = authed_client(api_client, admin_user)
        response = client.post("/api/v1/settings/", {"key": "site_name", "value": "NEWSHUB"})
        assert response.status_code == 403

    def test_super_admin_can_write_settings(self, api_client, super_admin):
        client = authed_client(api_client, super_admin)
        response = client.post(
            "/api/v1/settings/", {"key": "site_name", "value": "NEWSHUB"}, format="json"
        )
        assert response.status_code == 201


@pytest.mark.django_db
class TestUserManagementPermissions:
    def test_author_cannot_list_users(self, api_client, author):
        client = authed_client(api_client, author)
        response = client.get("/api/v1/super-admin/users/")
        assert response.status_code == 403

    def test_admin_cannot_list_users(self, api_client, admin_user):
        """Only Super Admin, not a plain Admin, per spec."""
        client = authed_client(api_client, admin_user)
        response = client.get("/api/v1/super-admin/users/")
        assert response.status_code == 403

    def test_super_admin_can_approve_pending_author(self, api_client, super_admin, roles):
        from apps.accounts.models import User

        pending = User.objects.create(
            username="pendingguy", email="pending2@test.com", role=roles["author"], status=User.PENDING
        )
        client = authed_client(api_client, super_admin)
        response = client.post(f"/api/v1/super-admin/users/{pending.id}/set-status/", {"status": "active"})
        assert response.status_code == 200
        pending.refresh_from_db()
        assert pending.status == "active"


@pytest.mark.django_db
class TestAdminVideosPermissions:
    def test_author_cannot_access_admin_videos(self, api_client, author):
        client = authed_client(api_client, author)
        response = client.get("/api/v1/admin/videos/")
        assert response.status_code == 403

    def test_admin_can_access_admin_videos(self, api_client, admin_user):
        client = authed_client(api_client, admin_user)
        response = client.get("/api/v1/admin/videos/")
        assert response.status_code == 200


@pytest.mark.django_db
class TestCommentModeration:
    def test_new_comment_is_pending_and_hidden(self, api_client, reader, author, category):
        from apps.posts.models import Post

        post = Post.objects.create(
            title="Story", content="x", category=category, author=author, status=Post.PUBLISHED
        )
        client = authed_client(api_client, reader)
        create_resp = client.post("/api/v1/comments/", {"post": post.id, "body": "Nice article!"})
        assert create_resp.status_code == 201

        anon_client = api_client.__class__()
        list_resp = anon_client.get(f"/api/v1/comments/?post={post.id}")
        assert list_resp.data["count"] == 0  # pending, not yet visible

    def test_admin_can_approve_comment(self, api_client, reader, admin_user, author, category):
        from apps.comments.models import Comment
        from apps.posts.models import Post

        post = Post.objects.create(
            title="Story", content="x", category=category, author=author, status=Post.PUBLISHED
        )
        comment = Comment.objects.create(post=post, user=reader, body="Great read")

        admin_client = authed_client(api_client, admin_user)
        response = admin_client.post(f"/api/v1/admin/comments/{comment.id}/moderate/", {"status": "approved"})
        assert response.status_code == 200

        comment.refresh_from_db()
        assert comment.status == "approved"
