"""
Tests for the full content approval workflow — the most important
behavior in the whole platform. Every rule here was originally verified
by hand with live curl commands during development; this suite locks
those same behaviors in so future changes can't silently break them.
"""
import pytest

from apps.posts.models import Post
from tests.conftest import authed_client


@pytest.mark.django_db
class TestPostCreationAndEditing:
    def test_author_can_create_draft(self, api_client, author, category):
        client = authed_client(api_client, author)
        response = client.post(
            "/api/v1/dashboard/posts/",
            {"title": "My First Post", "content": "Some content", "category": category.id},
        )
        assert response.status_code == 201
        assert response.data["status"] == "draft"
        assert "id" in response.data  # regression check for the id-missing bug found during dev

    def test_author_cannot_set_status_directly(self, api_client, author, category):
        """PostWriteSerializer excludes `status` — even if a client sends
        it, it must be silently ignored, never applied."""
        client = authed_client(api_client, author)
        response = client.post(
            "/api/v1/dashboard/posts/",
            {"title": "Sneaky Post", "content": "x", "category": category.id, "status": "published"},
        )
        assert response.status_code == 201
        assert response.data["status"] == "draft"

    def test_author_cannot_edit_another_authors_post(self, api_client, author, another_author, category):
        post = Post.objects.create(title="Bob's post", content="x", category=category, author=another_author)
        client = authed_client(api_client, author)
        response = client.put(
            f"/api/v1/dashboard/posts/{post.id}/",
            {"title": "Hijacked", "content": "x", "category": category.id},
        )
        assert response.status_code in (403, 404)

    def test_author_cannot_edit_post_under_review(self, api_client, author, category):
        post = Post.objects.create(
            title="Submitted post", content="x", category=category, author=author, status=Post.SUBMITTED
        )
        client = authed_client(api_client, author)
        response = client.put(
            f"/api/v1/dashboard/posts/{post.id}/",
            {"title": "Trying to sneak an edit in", "content": "x", "category": category.id},
        )
        assert response.status_code == 403

    def test_author_can_edit_rejected_post(self, api_client, author, category):
        post = Post.objects.create(
            title="Rejected post", content="x", category=category, author=author, status=Post.REJECTED
        )
        client = authed_client(api_client, author)
        response = client.put(
            f"/api/v1/dashboard/posts/{post.id}/",
            {"title": "Fixed post", "content": "x", "category": category.id},
        )
        assert response.status_code == 200
        assert response.data["title"] == "Fixed post"


@pytest.mark.django_db
class TestSubmissionAndReview:
    def test_full_happy_path_draft_to_published(self, api_client, author, admin_user, category):
        author_client = authed_client(api_client, author)

        create_resp = author_client.post(
            "/api/v1/dashboard/posts/",
            {"title": "Big Story", "content": "Breaking news", "category": category.id},
        )
        post_id = create_resp.data["id"]

        submit_resp = author_client.post(f"/api/v1/dashboard/posts/{post_id}/submit/")
        assert submit_resp.data["status"] == "submitted"

        admin_client = authed_client(APIClient_new(), admin_user)
        approve_resp = admin_client.post(
            f"/api/v1/admin/posts/{post_id}/approve/", {"publish_immediately": True}
        )
        assert approve_resp.status_code == 200
        assert approve_resp.data["status"] == "published"
        assert approve_resp.data["published_at"] is not None

    def test_author_cannot_approve_own_post(self, api_client, author, category):
        client = authed_client(api_client, author)
        create_resp = client.post(
            "/api/v1/dashboard/posts/", {"title": "Post", "content": "x", "category": category.id}
        )
        post_id = create_resp.data["id"]
        client.post(f"/api/v1/dashboard/posts/{post_id}/submit/")

        response = client.post(f"/api/v1/admin/posts/{post_id}/approve/", {"publish_immediately": True})
        assert response.status_code == 403

    def test_reject_requires_a_note(self, api_client, author, admin_user, category):
        author_client = authed_client(api_client, author)
        create_resp = author_client.post(
            "/api/v1/dashboard/posts/", {"title": "Post", "content": "x", "category": category.id}
        )
        post_id = create_resp.data["id"]
        author_client.post(f"/api/v1/dashboard/posts/{post_id}/submit/")

        admin_client = authed_client(APIClient_new(), admin_user)
        response = admin_client.post(f"/api/v1/admin/posts/{post_id}/reject/", {})
        assert response.status_code == 400

    def test_changes_requested_then_resubmit_flow(self, api_client, author, admin_user, category):
        author_client = authed_client(api_client, author)
        create_resp = author_client.post(
            "/api/v1/dashboard/posts/", {"title": "Draft story", "content": "x", "category": category.id}
        )
        post_id = create_resp.data["id"]
        author_client.post(f"/api/v1/dashboard/posts/{post_id}/submit/")

        admin_client = authed_client(APIClient_new(), admin_user)
        changes_resp = admin_client.post(
            f"/api/v1/admin/posts/{post_id}/request-changes/", {"note": "Add a source."}
        )
        assert changes_resp.data["status"] == "changes_requested"

        edit_resp = author_client.put(
            f"/api/v1/dashboard/posts/{post_id}/",
            {"title": "Draft story (sourced)", "content": "x, with citation", "category": category.id},
        )
        assert edit_resp.status_code == 200

        resubmit_resp = author_client.post(f"/api/v1/dashboard/posts/{post_id}/submit/")
        assert resubmit_resp.data["status"] == "submitted"

        history_resp = author_client.get(f"/api/v1/dashboard/posts/{post_id}/")
        actions = [h["action"] for h in history_resp.data["approval_history"]]
        assert "changes_requested" in actions
        assert "resubmitted" in actions

    def test_published_post_is_publicly_visible(self, api_client, author, admin_user, category):
        author_client = authed_client(api_client, author)
        create_resp = author_client.post(
            "/api/v1/dashboard/posts/", {"title": "Public story", "content": "x", "category": category.id}
        )
        post_id = create_resp.data["id"]
        author_client.post(f"/api/v1/dashboard/posts/{post_id}/submit/")

        admin_client = authed_client(APIClient_new(), admin_user)
        admin_client.post(f"/api/v1/admin/posts/{post_id}/approve/", {"publish_immediately": True})

        anon_client = APIClient_new()
        response = anon_client.get("/api/v1/posts/")
        titles = [p["title"] for p in response.data["results"]]
        assert "Public story" in titles

    def test_draft_post_not_publicly_visible(self, api_client, author, category):
        client = authed_client(api_client, author)
        client.post("/api/v1/dashboard/posts/", {"title": "Secret draft", "content": "x", "category": category.id})

        anon_client = APIClient_new()
        response = anon_client.get("/api/v1/posts/")
        titles = [p["title"] for p in response.data["results"]]
        assert "Secret draft" not in titles


def APIClient_new():
    """Small helper so each admin/anon client in a test gets a clean,
    uncredentialed APIClient rather than reusing the author's."""
    from rest_framework.test import APIClient
    return APIClient()
