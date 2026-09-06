from django.db.models import Q
from django.utils import timezone

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.core.models import AuditLog
from apps.core.permissions import IsAdminOrEditor, IsAuthorRole

from .models import Post, PostApproval, PostRevision
from .serializers import (
    ApprovePostSerializer,
    PostDetailSerializer,
    PostListSerializer,
    PostWriteSerializer,
    RejectOrRequestChangesSerializer,
    VideoFeedItemSerializer,
)


# =========================================================
# PUBLIC VIDEO API
# =========================================================

class PublicVideoViewSet(viewsets.ReadOnlyModelViewSet):
    """
    /api/v1/videos/            - published posts that have a video attached
    /api/v1/videos/{slug}/     - single video-post detail
    Public, unauthenticated — safe for anonymous readers and Flutter.
    """

    permission_classes = [AllowAny]
    serializer_class = VideoFeedItemSerializer
    lookup_field = "slug"

    def get_queryset(self):
        return (
            Post.objects.filter(
                status=Post.PUBLISHED,
                video__isnull=False,
            )
            .select_related("author", "category", "video")
            .order_by("-published_at")
        )


# =========================================================
# PHOTO GALLERY API
# =========================================================

class PhotoGalleryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    /api/v1/gallery/ - published posts that have a featured image.
    """

    permission_classes = [AllowAny]
    serializer_class = PostListSerializer

    def get_queryset(self):
        return (
            Post.objects.filter(status=Post.PUBLISHED)
            .exclude(featured_image_url="")
            .select_related("author", "category")
            .order_by("-published_at")
        )


# =========================================================
# PUBLIC POSTS API
# =========================================================

class PublicPostViewSet(viewsets.ReadOnlyModelViewSet):
    """
    /api/v1/posts/            - published posts only
    /api/v1/posts/{slug}/     - single published post
    Read-only and unauthenticated.
    """

    permission_classes = [AllowAny]
    lookup_field = "slug"

    def get_queryset(self):
        qs = (
            Post.objects.filter(status=Post.PUBLISHED)
            .select_related("author", "category")
            .prefetch_related("tags")
        )

        params = self.request.query_params

        if category := params.get("category"):
            qs = qs.filter(category__slug=category)

        if search := params.get("search"):
            qs = qs.filter(
                Q(title__icontains=search)
                | Q(content__icontains=search)
            )

        if params.get("breaking") == "true":
            qs = qs.filter(is_breaking=True)

        if params.get("trending") == "true":
            qs = qs.filter(is_trending=True)

        return qs

    def get_serializer_class(self):
        if self.action == "retrieve":
            return PostDetailSerializer
        return PostListSerializer

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()

        Post.objects.filter(pk=instance.pk).update(
            views=instance.views + 1
        )

        instance.refresh_from_db(fields=["views"])

        return Response(
            self.get_serializer(instance).data
        )


# =========================================================
# AUTHOR / DASHBOARD POSTS
# =========================================================

class DashboardPostViewSet(viewsets.ModelViewSet):
    """
    /api/v1/dashboard/posts/

    Authors manage their own posts.

    Admins and Super Admins can also access all posts through
    this endpoint.
    """

    permission_classes = [IsAuthenticated, IsAuthorRole]
    serializer_class = PostWriteSerializer

    def get_queryset(self):
        user = self.request.user

        qs = (
            Post.objects
            .select_related("author", "category")
            .prefetch_related("tags")
        )

        if user.is_super_admin() or user.has_role("admin"):
            return qs

        return qs.filter(author=user)

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return PostDetailSerializer

        return PostWriteSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)

        self.perform_create(serializer)

        output = PostDetailSerializer(
            serializer.instance
        )

        headers = self.get_success_headers(
            output.data
        )

        return Response(
            output.data,
            status=status.HTTP_201_CREATED,
            headers=headers,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)

        instance = self.get_object()

        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=partial,
        )

        serializer.is_valid(
            raise_exception=True
        )

        self.perform_update(serializer)

        return Response(
            PostDetailSerializer(
                serializer.instance
            ).data
        )

    def perform_create(self, serializer):
        serializer.save(
            author=self.request.user,
            status=Post.DRAFT,
        )

    def perform_update(self, serializer):
        post = self.get_object()
        user = self.request.user

        is_privileged = (
            user.is_super_admin()
            or user.has_role("admin")
        )

        if (
            not is_privileged
            and not post.is_editable_by_author()
        ):
            raise PermissionDenied(
                "This post can't be edited in its current "
                "status. Only drafts, rejected, or "
                "changes-requested posts are editable "
                "by authors."
            )

        # Preserve revision history
        PostRevision.objects.create(
            post=post,
            edited_by=user,
            title=post.title,
            content=post.content,
            featured_image_url=post.featured_image_url,
            meta={
                "category_id": post.category_id,
                "seo_title": post.seo_title,
            },
        )

        serializer.save()

    def perform_destroy(self, instance):
        user = self.request.user

        is_privileged = (
            user.is_super_admin()
            or user.has_role("admin")
        )

        # Admin/Super Admin can delete any post.
        if is_privileged:
            AuditLog.objects.create(
                actor=user,
                action="post.deleted",
                target_type="Post",
                target_id=str(instance.id),
                ip_address=self.request.META.get(
                    "REMOTE_ADDR"
                ),
            )

            instance.delete()
            return

        # Authors can only delete their own editable posts.
        if instance.author_id != user.id:
            raise PermissionDenied(
                "You can only delete your own posts."
            )

        if instance.status not in Post.AUTHOR_EDITABLE_STATUSES:
            raise PermissionDenied(
                "Published or in-review posts can't be "
                "deleted by the author."
            )

        instance.delete()

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        """
        draft / changes_requested / rejected -> submitted
        """

        post = self.get_object()

        if post.author_id != request.user.id and not (
            request.user.is_super_admin()
            or request.user.has_role("admin")
        ):
            raise PermissionDenied(
                "Only the author can submit this post."
            )

        if post.status not in (
            Post.DRAFT,
            Post.CHANGES_REQUESTED,
            Post.REJECTED,
        ):
            raise ValidationError(
                "Only draft, changes-requested, or "
                "rejected posts can be submitted."
            )

        was_resubmit = post.status in (
            Post.CHANGES_REQUESTED,
            Post.REJECTED,
        )

        post.status = Post.SUBMITTED
        post.submitted_at = timezone.now()
        post.review_note = ""

        post.save(
            update_fields=[
                "status",
                "submitted_at",
                "review_note",
            ]
        )

        PostApproval.objects.create(
            post=post,
            actor=request.user,
            action=(
                PostApproval.RESUBMITTED
                if was_resubmit
                else PostApproval.SUBMITTED
            ),
        )

        return Response(
            PostDetailSerializer(post).data
        )


# =========================================================
# ADMIN / EDITOR / SUPER ADMIN POSTS
# =========================================================

class AdminPostViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,  # Added: enables DELETE
    viewsets.GenericViewSet,
):
    """
    /api/v1/admin/posts/
    /api/v1/admin/posts/{id}/

    Admin / Editor / Super Admin approval workflow.

    Supported actions:
      - DELETE
      - under-review
      - approve
      - reject
      - request-changes
      - publish
      - archive
    """

    permission_classes = [
        IsAuthenticated,
        IsAdminOrEditor,
    ]

    serializer_class = PostDetailSerializer

    def get_queryset(self):
        qs = (
            Post.objects
            .select_related("author", "category")
            .prefetch_related("tags")
        )

        if status_filter := self.request.query_params.get(
            "status"
        ):
            qs = qs.filter(status=status_filter)

        return qs

    def get_serializer_class(self):
        return PostDetailSerializer

    # =====================================================
    # AUDIT / WORKFLOW LOGGING
    # =====================================================

    def _log(
        self,
        request,
        post,
        action_name,
        note="",
    ):
        PostApproval.objects.create(
            post=post,
            actor=request.user,
            action=action_name,
            note=note,
        )

        AuditLog.objects.create(
            actor=request.user,
            action=f"post.{action_name}",
            target_type="Post",
            target_id=str(post.id),
            ip_address=request.META.get(
                "REMOTE_ADDR"
            ),
        )

    # =====================================================
    # ADMIN DELETE
    # =====================================================

    def perform_destroy(self, instance):
        """
        Admin / Editor / Super Admin can permanently
        delete any post.

        This method is called by DRF's DELETE endpoint.
        """

        user = self.request.user

        # IsAdminOrEditor already protects the viewset,
        # but keep this explicit safety check as well.
        if not (
            user.is_super_admin()
            or user.has_role("admin")
            or user.has_role("editor")
        ):
            raise PermissionDenied(
                "Only Admin, Editor, or Super Admin "
                "can delete posts."
            )

        # Record deletion before removing the post.
        AuditLog.objects.create(
            actor=user,
            action="post.deleted",
            target_type="Post",
            target_id=str(instance.id),
            ip_address=self.request.META.get(
                "REMOTE_ADDR"
            ),
        )

        instance.delete()

    # =====================================================
    # MOVE TO UNDER REVIEW
    # =====================================================

    @action(
        detail=True,
        methods=["post"],
        url_path="under-review",
    )
    def mark_under_review(
        self,
        request,
        pk=None,
    ):
        post = self.get_object()

        if post.status != Post.SUBMITTED:
            raise ValidationError(
                "Only submitted posts can be moved "
                "to under review."
            )

        post.status = Post.UNDER_REVIEW
        post.reviewed_by = request.user

        post.save(
            update_fields=[
                "status",
                "reviewed_by",
            ]
        )

        self._log(
            request,
            post,
            "submitted",
            "Moved to under review",
        )

        return Response(
            PostDetailSerializer(post).data
        )

    # =====================================================
    # APPROVE
    # =====================================================

    @action(
        detail=True,
        methods=["post"],
    )
    def approve(
        self,
        request,
        pk=None,
    ):
        post = self.get_object()

        if post.status not in (
            Post.SUBMITTED,
            Post.UNDER_REVIEW,
        ):
            raise ValidationError(
                "Only submitted or under-review posts "
                "can be approved."
            )

        serializer = ApprovePostSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        publish_now = serializer.validated_data[
            "publish_immediately"
        ]

        post.status = (
            Post.PUBLISHED
            if publish_now
            else Post.APPROVED
        )

        post.reviewed_by = request.user

        post.published_at = (
            timezone.now()
            if publish_now
            else None
        )

        post.save(
            update_fields=[
                "status",
                "reviewed_by",
                "published_at",
            ]
        )

        self._log(
            request,
            post,
            "published"
            if publish_now
            else "approved",
        )

        return Response(
            PostDetailSerializer(post).data
        )

    # =====================================================
    # REJECT
    # =====================================================

    @action(
        detail=True,
        methods=["post"],
    )
    def reject(
        self,
        request,
        pk=None,
    ):
        post = self.get_object()

        if post.status not in (
            Post.SUBMITTED,
            Post.UNDER_REVIEW,
        ):
            raise ValidationError(
                "Only submitted or under-review posts "
                "can be rejected."
            )

        serializer = RejectOrRequestChangesSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        post.status = Post.REJECTED
        post.reviewed_by = request.user
        post.review_note = serializer.validated_data[
            "note"
        ]

        post.save(
            update_fields=[
                "status",
                "reviewed_by",
                "review_note",
            ]
        )

        self._log(
            request,
            post,
            "rejected",
            serializer.validated_data["note"],
        )

        return Response(
            PostDetailSerializer(post).data
        )

    # =====================================================
    # REQUEST CHANGES
    # =====================================================

    @action(
        detail=True,
        methods=["post"],
        url_path="request-changes",
    )
    def request_changes(
        self,
        request,
        pk=None,
    ):
        post = self.get_object()

        if post.status not in (
            Post.SUBMITTED,
            Post.UNDER_REVIEW,
        ):
            raise ValidationError(
                "Only submitted or under-review posts "
                "can have changes requested."
            )

        serializer = RejectOrRequestChangesSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        post.status = Post.CHANGES_REQUESTED
        post.reviewed_by = request.user
        post.review_note = serializer.validated_data[
            "note"
        ]

        post.save(
            update_fields=[
                "status",
                "reviewed_by",
                "review_note",
            ]
        )

        self._log(
            request,
            post,
            "changes_requested",
            serializer.validated_data["note"],
        )

        return Response(
            PostDetailSerializer(post).data
        )

    # =====================================================
    # PUBLISH
    # =====================================================

    @action(
        detail=True,
        methods=["post"],
    )
    def publish(
        self,
        request,
        pk=None,
    ):
        post = self.get_object()

        if post.status != Post.APPROVED:
            raise ValidationError(
                "Only approved posts can be published."
            )

        post.status = Post.PUBLISHED
        post.published_at = timezone.now()

        post.save(
            update_fields=[
                "status",
                "published_at",
            ]
        )

        self._log(
            request,
            post,
            "published",
        )

        return Response(
            PostDetailSerializer(post).data
        )

    # =====================================================
    # ARCHIVE
    # =====================================================

    @action(
        detail=True,
        methods=["post"],
    )
    def archive(
        self,
        request,
        pk=None,
    ):
        post = self.get_object()

        post.status = Post.ARCHIVED

        post.save(
            update_fields=["status"]
        )

        self._log(
            request,
            post,
            "archived",
        )

        return Response(
            PostDetailSerializer(post).data
        )