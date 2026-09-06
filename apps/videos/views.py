from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.conf import settings as dj_settings

from apps.core.models import AuditLog
from apps.core.permissions import IsAdminOrEditor, IsAuthorRole

from . import bunny
from .models import Video
from .serializers import BunnyWebhookSerializer, CreateVideoSlotSerializer, VideoSerializer


class AdminVideoViewSet(viewsets.ReadOnlyModelViewSet):
    """
    /api/v1/admin/videos/  - full video library across all users, for the
    Super Admin/Admin media library's Videos tab. Read-only — video
    lifecycle (create/delete) stays in VideoViewSet, scoped to the
    uploader (or admins, via its own get_queryset).
    """
    serializer_class = VideoSerializer
    permission_classes = [IsAuthenticated, IsAdminOrEditor]
    queryset = Video.objects.select_related("uploaded_by").order_by("-created_at")


class VideoViewSet(viewsets.ModelViewSet):
    """
    /api/v1/dashboard/videos/create-slot/  - step 1: ask Bunny for a video
                                              guid + upload signature
    /api/v1/dashboard/videos/              - list own videos
    """
    serializer_class = VideoSerializer
    permission_classes = [IsAuthenticated, IsAuthorRole]
    http_method_names = ["get", "post", "delete"]

    def get_queryset(self):
        user = self.request.user
        qs = Video.objects.all()
        if user.is_super_admin() or user.has_role("admin"):
            return qs
        return qs.filter(uploaded_by=user)

    @action(detail=False, methods=["post"], url_path="create-slot")
    def create_slot(self, request):
        serializer = CreateVideoSlotSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        title = serializer.validated_data["title"]

        bunny_video = bunny.create_video(title)
        guid = bunny_video["guid"]

        video = Video.objects.create(
            uploaded_by=request.user,
            title=title,
            bunny_video_id=guid,
            bunny_library_id=str(dj_settings.BUNNY_STREAM_LIBRARY_ID),
            status=Video.UPLOADING,
        )

        upload_info = bunny.generate_upload_signature(guid)
        return Response(
            {"video": VideoSerializer(video).data, "upload": upload_info},
            status=status.HTTP_201_CREATED,
        )

    def perform_destroy(self, instance):
        bunny.delete_video(instance.bunny_video_id)
        instance.delete()


class BunnyWebhookView(APIView):
    """
    Bunny calls this when transcoding finishes. Not user-authenticated —
    verified instead via a shared secret query param/header, since Bunny
    doesn't sign webhook payloads with our JWTs.
    """
    permission_classes = [AllowAny]

    # Bunny's numeric status codes: 3 = Finished, 5 = Error (per Bunny docs)
    STATUS_MAP = {3: Video.READY, 5: Video.FAILED}

    def post(self, request):
        provided_secret = request.headers.get("X-Webhook-Secret", "")
        if not dj_settings.BUNNY_WEBHOOK_SECRET or provided_secret != dj_settings.BUNNY_WEBHOOK_SECRET:
            return Response({"detail": "Invalid webhook secret."}, status=status.HTTP_401_UNAUTHORIZED)

        serializer = BunnyWebhookSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        guid = serializer.validated_data["VideoGuid"]
        bunny_status = serializer.validated_data["Status"]

        try:
            video = Video.objects.get(bunny_video_id=guid)
        except Video.DoesNotExist:
            return Response({"detail": "Unknown video."}, status=status.HTTP_404_NOT_FOUND)

        video.status = self.STATUS_MAP.get(bunny_status, Video.PROCESSING)
        if video.status == Video.READY:
            video.playback_url = bunny.build_playback_url(guid)
            video.thumbnail_url = bunny.build_thumbnail_url(guid)
        video.save()

        AuditLog.objects.create(
            actor=None, action="video.status_updated",
            target_type="Video", target_id=str(video.id),
            metadata={"bunny_status": bunny_status},
        )
        return Response({"detail": "ok"})
