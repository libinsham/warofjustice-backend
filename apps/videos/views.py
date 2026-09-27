
import hmac
from pathlib import PurePath

from botocore.exceptions import ClientError
from django.conf import settings
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import (
    AllowAny,
    BasePermission,
    IsAuthenticated,
)
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models import AuditLog
from apps.core.permissions import IsAuthorRole

from . import bunny
from .models import Video
from .r2 import (
    delete_r2_object,
    generate_presigned_get,
    generate_presigned_put,
    head_r2_object,
)
from .serializers import (
    BunnyWebhookSerializer,
    R2VideoConfirmSerializer,
    R2VideoUploadSerializer,
    VideoSerializer,
)


ALLOWED_VIDEO_TYPES = {
    "video/mp4",
    "video/webm",
    "video/quicktime",
    "video/x-m4v",
}

DEFAULT_MAX_VIDEO_BYTES = 5 * 1024 * 1024 * 1024


def get_max_video_bytes():
    """
    Return the configured maximum single-request video size.
    """
    return int(
        getattr(
            settings,
            "R2_VIDEO_MAX_BYTES",
            DEFAULT_MAX_VIDEO_BYTES,
        )
    )


def get_role_name(user):
    """
    Return the user's role name safely.
    """
    return getattr(
        getattr(user, "role", None),
        "name",
        "",
    )


def is_video_reviewer(user):
    """
    Check whether the user can review and download videos.
    """
    return get_role_name(user) in {
        "super_super_admin",
        "super_admin",
        "admin",
        "editor",
    }


# =========================================================
# ADMIN VIDEO REVIEW AND DOWNLOAD
# =========================================================

class IsVideoReviewer(BasePermission):
    """
    Only super admins, admins and editors can review
    and download uploaded videos.
    """

    def has_permission(self, request, view):
        return (
            bool(request.user)
            and request.user.is_authenticated
            and is_video_reviewer(request.user)
        )


class AdminVideoViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Admin video listing and temporary download links.

    Supports:
        GET /dashboard/videos/
        GET /dashboard/videos/{id}/
        GET /dashboard/videos/{id}/download/
    """

    serializer_class = VideoSerializer
    permission_classes = [
        IsAuthenticated,
        IsVideoReviewer,
    ]

    queryset = (
        Video.objects
        .select_related("uploaded_by")
        .order_by("-created_at")
    )

    @action(
        detail=True,
        methods=["get"],
        url_path="download",
    )
    def download(self, request, pk=None):
        """
        Generate a temporary download URL for an R2 video.
        """
        video = self.get_object()

        if not video.r2_key:
            return Response(
                {
                    "detail": (
                        "This is a legacy Bunny video. "
                        "R2 download is not available for it."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )

        try:
            download_url = generate_presigned_get(
                key=video.r2_key,
                file_name=video.file_name or "video",
                expires_in=600,
            )
        except ClientError:
            return Response(
                {
                    "detail": (
                        "Unable to generate the video "
                        "download link."
                    )
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            {
                "download_url": download_url,
                "expires_in": 600,
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# VIDEO UPLOAD AND PERSONAL VIDEO MANAGEMENT
# =========================================================

class VideoViewSet(viewsets.ModelViewSet):
    """
    Direct Cloudflare R2 video upload and personal
    video management.

    Supports:
        GET    /videos/
        POST   /videos/presign/
        POST   /videos/confirm/
        DELETE /videos/{id}/

    New uploads use R2. The old Bunny upload-slot
    endpoint is no longer exposed here.
    """

    serializer_class = VideoSerializer
    permission_classes = [
        IsAuthenticated,
        IsAuthorRole,
    ]

    http_method_names = [
        "get",
        "post",
        "delete",
        "head",
        "options",
    ]

    def get_queryset(self):
        """
        Admin-level users can list all videos.
        Other permitted users can see only their own.
        """
        role_name = get_role_name(self.request.user)

        if role_name in {
            "super_super_admin",
            "super_admin",
            "admin",
        }:
            return (
                Video.objects
                .select_related("uploaded_by")
                .order_by("-created_at")
            )

        return (
            Video.objects
            .filter(uploaded_by=self.request.user)
            .order_by("-created_at")
        )

    def create(self, request, *args, **kwargs):
        """
        Disable ordinary POST creation.
        New videos must use presign and confirm.
        """
        return Response(
            {
                "detail": (
                    "Use the presign and confirm endpoints "
                    "to upload a Cloudflare R2 video."
                )
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    # -----------------------------------------------------
    # PRESIGN VIDEO UPLOAD
    # -----------------------------------------------------

    @action(
        detail=False,
        methods=["post"],
        url_path="presign",
    )
    def presign(self, request):
        """
        Generate a short-lived R2 upload URL.

        The browser uploads the video directly to R2.
        Django does not proxy the video bytes.
        """
        serializer = R2VideoUploadSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        values = serializer.validated_data

        file_name = PurePath(
            values["file_name"].replace("\\", "/")
        ).name

        if not file_name:
            return Response(
                {
                    "detail": "A valid file name is required."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        content_type = values["content_type"].lower()
        size_bytes = values["size_bytes"]

        if content_type not in ALLOWED_VIDEO_TYPES:
            return Response(
                {
                    "detail": "Unsupported video format."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if size_bytes < 1 or size_bytes > get_max_video_bytes():
            return Response(
                {
                    "detail": (
                        "The video exceeds the permitted "
                        "upload size."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            upload = generate_presigned_put(
                file_name=file_name,
                content_type=content_type,
                folder=f"videos/{request.user.pk}",
            )
        except ClientError:
            return Response(
                {
                    "detail": (
                        "Unable to generate the R2 upload URL."
                    )
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            {
                "upload_url": upload["upload_url"],
                "key": upload["key"],
                "expires_in": 300,
            },
            status=status.HTTP_200_OK,
        )

    # -----------------------------------------------------
    # CONFIRM VIDEO UPLOAD
    # -----------------------------------------------------

    @action(
        detail=False,
        methods=["post"],
        url_path="confirm",
    )
    def confirm(self, request):
        """
        Verify the R2 object and create the Video record.

        The object must belong to the authenticated user.
        Its actual size and content type are checked against
        the upload request.
        """
        serializer = R2VideoConfirmSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        values = serializer.validated_data
        key = values["key"]

        expected_prefix = f"videos/{request.user.pk}/"

        # A user can confirm only objects under their own prefix.
        if not key.startswith(expected_prefix):
            return Response(
                {
                    "detail": (
                        "You cannot confirm this video."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Return an already-confirmed video instead of
        # creating a duplicate record.
        existing = Video.objects.filter(
            r2_key=key,
        ).first()

        if existing:
            if existing.uploaded_by_id != request.user.pk:
                return Response(
                    {
                        "detail": (
                            "You cannot access this video."
                        )
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            return Response(
                VideoSerializer(existing).data,
                status=status.HTTP_200_OK,
            )

        # Read the actual uploaded object metadata from R2.
        try:
            metadata = head_r2_object(key)

        except ClientError as exc:
            error_code = str(
                exc.response.get("Error", {}).get("Code", "")
            )

            if error_code in {
                "404",
                "NoSuchKey",
                "NotFound",
            }:
                return Response(
                    {
                        "detail": (
                            "The uploaded R2 video was not found."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            return Response(
                {
                    "detail": (
                        "Unable to verify the uploaded R2 video."
                    )
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        actual_size = int(
            metadata.get("ContentLength", 0)
        )

        actual_type = (
            metadata.get("ContentType", "")
            .split(";")[0]
            .strip()
            .lower()
        )

        expected_size = values["size_bytes"]
        expected_type = values["content_type"].lower()

        if actual_size != expected_size:
            return Response(
                {
                    "detail": (
                        "The uploaded video size does not match "
                        "the requested size."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if (
            actual_size < 1
            or actual_size > get_max_video_bytes()
        ):
            return Response(
                {
                    "detail": (
                        "The uploaded video size is not allowed."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if actual_type not in ALLOWED_VIDEO_TYPES:
            return Response(
                {
                    "detail": "Unsupported video format."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if actual_type != expected_type:
            return Response(
                {
                    "detail": (
                        "The uploaded video type does not match."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        file_name = PurePath(
            values["file_name"].replace("\\", "/")
        ).name

        title = (
            values.get("title", "").strip()
            or PurePath(file_name).stem
            or "Uploaded video"
        )

        # Create the video record only after verifying R2.
        video = Video.objects.create(
            uploaded_by=request.user,
            title=title,
            bunny_video_id=None,
            bunny_library_id="",
            r2_key=key,
            file_name=file_name,
            mime_type=actual_type,
            size_bytes=actual_size,
            status=Video.READY,
        )

        AuditLog.objects.create(
            actor=request.user,
            action="video.r2_uploaded",
            target_type="Video",
            target_id=str(video.id),
        )

        return Response(
            VideoSerializer(video).data,
            status=status.HTTP_201_CREATED,
        )

    # -----------------------------------------------------
    # DELETE VIDEO
    # -----------------------------------------------------

    def perform_destroy(self, instance):
        """
        Delete the file from its storage provider, then
        remove the database record.

        R2 is used for new videos. Bunny deletion remains
        available for legacy Bunny records.
        """
        if instance.r2_key:
            delete_r2_object(instance.r2_key)

        elif instance.bunny_video_id:
            # Legacy Bunny functionality retained for later.
            bunny.delete_video(
                instance.bunny_video_id
            )

        AuditLog.objects.create(
            actor=self.request.user,
            action="video.deleted",
            target_type="Video",
            target_id=str(instance.id),
        )

        instance.delete()


# =========================================================
# LEGACY BUNNY STREAM WEBHOOK
# =========================================================

class BunnyWebhookView(APIView):
    """
    Legacy Bunny Stream webhook.

    Retained for old Bunny videos and possible future use.
    New R2 uploads do not use this webhook.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        expected_secret = getattr(
            settings,
            "BUNNY_WEBHOOK_SECRET",
            "",
        )

        supplied_secret = request.headers.get(
            "X-Webhook-Secret",
            "",
        )

        if (
            not expected_secret
            or not supplied_secret
            or not hmac.compare_digest(
                str(supplied_secret),
                str(expected_secret),
            )
        ):
            return Response(
                {
                    "detail": "Invalid webhook secret."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = BunnyWebhookSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        values = serializer.validated_data
        video_guid = values["VideoGuid"]
        bunny_status = values["Status"]

        video = Video.objects.filter(
            bunny_video_id=video_guid,
        ).first()

        if not video:
            return Response(
                {
                    "detail": "Bunny video not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # Bunny status 3 means finished; 5 means failed.
        if bunny_status == 3:
            video.status = Video.READY
            video.playback_url = bunny.build_playback_url(
                video.bunny_video_id,
            )
            video.thumbnail_url = bunny.build_thumbnail_url(
                video.bunny_video_id,
            )

            audit_action = "video.bunny_ready"

        elif bunny_status == 5:
            video.status = Video.FAILED
            audit_action = "video.bunny_failed"

        else:
            # Ignore other Bunny processing statuses.
            return Response(
                {
                    "detail": "Webhook status ignored."
                },
                status=status.HTTP_200_OK,
            )

        video.save(
            update_fields=[
                "status",
                "playback_url",
                "thumbnail_url",
                "updated_at",
            ]
        )

        AuditLog.objects.create(
            actor=None,
            action=audit_action,
            target_type="Video",
            target_id=str(video.id),
        )

        return Response(
            {
                "detail": "Bunny webhook processed.",
                "video_id": video.id,
                "status": video.status,
            },
            status=status.HTTP_200_OK,
        )