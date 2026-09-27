
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.models import AuditLog
from apps.core.permissions import (
    IsAdminOrEditor,
    IsAuthorRole,
    is_super_admin,
)

from .models import Media
from .r2 import generate_presigned_put
from .serializers import (
    ConfirmUploadSerializer,
    MediaSerializer,
    PresignRequestSerializer,
)


class MediaViewSet(viewsets.ModelViewSet):
    """
    /api/v1/dashboard/media/presign/
        Get a presigned R2 PUT URL.

    /api/v1/dashboard/media/confirm/
        Record metadata after the browser uploads directly to R2.

    /api/v1/dashboard/media/
        List and delete media.

    /api/v1/admin/media/
        Full media library for administrators.
    """

    serializer_class = MediaSerializer
    permission_classes = [IsAuthenticated, IsAuthorRole]

    def get_queryset(self):
        user = self.request.user

        qs = Media.objects.select_related(
            "post",
            "uploaded_by",
        )

        # Super Super Admin and Super Admin can view
        # the complete dashboard media collection.
        if is_super_admin(user) or user.has_role("admin"):
            return qs

        # Other authorized users can view only their own uploads.
        return qs.filter(uploaded_by=user)

    def perform_destroy(self, instance):
        user = self.request.user

        is_privileged = (
            is_super_admin(user)
            or user.has_role("admin")
        )

        if (
            not is_privileged
            and instance.uploaded_by_id != user.id
        ):
            raise PermissionDenied(
                "You can only delete your own media."
            )

        # R2 object deletion is not implemented here.
        # Configure it separately before relying on permanent
        # media deletion from the R2 bucket.
        instance.delete()

    @action(detail=False, methods=["post"])
    def presign(self, request):
        """
        Step 1: Generate a signed URL for direct R2 upload.
        Requires authentication and an authorized role.
        """
        serializer = PresignRequestSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        result = generate_presigned_put(
            file_name=data["file_name"],
            content_type=data["content_type"],
        )

        return Response(
            result,
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"])
    def confirm(self, request):
        """
        Step 2: Confirm the uploaded object and save its metadata.
        """
        serializer = ConfirmUploadSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        from django.conf import settings

        public_url = (
            f"{settings.R2_PUBLIC_BASE_URL.rstrip('/')}/"
            f"{data['key']}"
        )

        media = Media.objects.create(
            post_id=data.get("post"),
            uploaded_by=request.user,
            type=Media.IMAGE,
            file_name=data["file_name"],
            r2_key=data["key"],
            url=public_url,
            mime_type=data["mime_type"],
            size_bytes=data["size_bytes"],
            width=data.get("width"),
            height=data.get("height"),
            alt_text=data.get("alt_text", ""),
        )

        AuditLog.objects.create(
            actor=request.user,
            action="media.uploaded",
            target_type="Media",
            target_id=str(media.id),
        )

        return Response(
            MediaSerializer(media).data,
            status=status.HTTP_201_CREATED,
        )


class AdminMediaViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Full media library across all users.
    """

    serializer_class = MediaSerializer
    permission_classes = [
        IsAuthenticated,
        IsAdminOrEditor,
    ]

    queryset = Media.objects.select_related(
        "post",
        "uploaded_by",
    ).all()

    def get_queryset(self):
        qs = super().get_queryset()

        if search := self.request.query_params.get("search"):
            qs = qs.filter(file_name__icontains=search)

        if media_type := self.request.query_params.get("type"):
            qs = qs.filter(type=media_type)

        return qs