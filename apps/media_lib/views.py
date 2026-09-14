from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.models import AuditLog
from apps.core.permissions import IsAdminOrEditor, IsAuthorRole

from .models import Media
from .r2 import generate_presigned_put
from .serializers import ConfirmUploadSerializer, MediaSerializer, PresignRequestSerializer


class MediaViewSet(viewsets.ModelViewSet):
    """
    /api/v1/dashboard/media/presign/  - get a presigned R2 PUT URL
    /api/v1/dashboard/media/confirm/  - record metadata after the browser
                                         has uploaded the file straight to R2
    /api/v1/dashboard/media/          - list/delete own uploads
    /api/v1/admin/media/              - full media library (Admin/Editor/Super Admin)
    """
    serializer_class = MediaSerializer
    permission_classes = [IsAuthenticated, IsAuthorRole]

    def get_queryset(self):
        user = self.request.user
        qs = Media.objects.select_related("post", "uploaded_by")
        if user.is_super_admin() or user.has_role("admin"):
            return qs
        return qs.filter(uploaded_by=user)

    def perform_destroy(self, instance):
        user = self.request.user
        is_privileged = user.is_super_admin() or user.has_role("admin")
        if not is_privileged and instance.uploaded_by_id != user.id:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You can only delete your own media.")
        # NOTE: also delete the object from R2 here in production, e.g.
        # get_r2_client().delete_object(Bucket=..., Key=instance.r2_key)
        instance.delete()

    @action(detail=False, methods=["post"])
    def presign(self, request):
        """Step 1: client asks for a signed URL before it uploads anything."""
        serializer = PresignRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        result = generate_presigned_put(
            file_name=data["file_name"], content_type=data["content_type"]
        )
        return Response(result, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"])
    def confirm(self, request):
        """Step 2: after the browser PUTs the file to R2 directly, the
        client confirms so we persist the Media row (metadata only —
        the binary already lives in R2, never on this server)."""
        serializer = ConfirmUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        from django.conf import settings
        public_url = f"{settings.R2_PUBLIC_BASE_URL.rstrip('/')}/{d['key']}"

        media = Media.objects.create(
            post_id=d.get("post"),
            uploaded_by=request.user,
            type=Media.IMAGE,
            file_name=d["file_name"],
            r2_key=d["key"],
            url=public_url,
            mime_type=d["mime_type"],
            size_bytes=d["size_bytes"],
            width=d.get("width"),
            height=d.get("height"),
            alt_text=d.get("alt_text", ""),
        )
        AuditLog.objects.create(
            actor=request.user, action="media.uploaded",
            target_type="Media", target_id=str(media.id),
        )
        return Response(MediaSerializer(media).data, status=status.HTTP_201_CREATED)


class AdminMediaViewSet(viewsets.ReadOnlyModelViewSet):
    """Full media library across all users — for the Super Admin/Admin media grid."""
    serializer_class = MediaSerializer
    permission_classes = [IsAuthenticated, IsAdminOrEditor]
    queryset = Media.objects.select_related("post", "uploaded_by").all()

    def get_queryset(self):
        qs = super().get_queryset()
        if search := self.request.query_params.get("search"):
            qs = qs.filter(file_name__icontains=search)
        if media_type := self.request.query_params.get("type"):
            qs = qs.filter(type=media_type)
        return qs
