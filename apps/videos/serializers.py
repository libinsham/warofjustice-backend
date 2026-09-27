
from pathlib import PurePath

from django.conf import settings
from rest_framework import serializers

from .models import Video


# =========================================================
# VIDEO CONSTANTS
# =========================================================

ALLOWED_VIDEO_TYPES = (
    "video/mp4",
    "video/webm",
    "video/quicktime",
    "video/x-m4v",
)


def get_max_video_size():
    """Return the configured maximum video upload size."""
    return int(
        getattr(
            settings,
            "R2_VIDEO_MAX_BYTES",
            5 * 1024 * 1024 * 1024,
        )
    )


# =========================================================
# VIDEO SERIALIZER
# =========================================================

class VideoSerializer(serializers.ModelSerializer):
    """
    Serializer for legacy Bunny videos and new R2 videos.
    """

    url = serializers.SerializerMethodField()

    class Meta:
        model = Video
        fields = [
            "id",
            "title",
            "bunny_video_id",
            "thumbnail_url",
            "playback_url",
            "duration_seconds",
            "r2_key",
            "file_name",
            "mime_type",
            "size_bytes",
            "status",
            "url",
            "created_at",
        ]
        read_only_fields = fields

    def get_url(self, obj):
        """
        Return the R2 URL for new videos or the
        playback URL for legacy Bunny videos.
        """
        if obj.r2_key:
            base_url = settings.R2_PUBLIC_BASE_URL.rstrip("/")
            return f"{base_url}/{obj.r2_key}"

        return obj.playback_url or None


# =========================================================
# R2 VIDEO UPLOAD REQUEST
# =========================================================

class R2VideoUploadSerializer(serializers.Serializer):
    """
    Validate the details required to generate
    a presigned Cloudflare R2 upload URL.
    """

    title = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        default="",
    )

    file_name = serializers.CharField(
        max_length=255,
    )

    content_type = serializers.ChoiceField(
        choices=tuple(
            (item, item) for item in ALLOWED_VIDEO_TYPES
        ),
    )

    size_bytes = serializers.IntegerField(
        min_value=1,
    )

    def validate_file_name(self, value):
        """
        Keep only the filename, not any directory path.
        """
        file_name = PurePath(
            value.replace("\\", "/")
        ).name

        if not file_name or file_name in {".", ".."}:
            raise serializers.ValidationError(
                "A valid video filename is required."
            )

        return file_name

    def validate_size_bytes(self, value):
        """Reject videos exceeding the configured limit."""
        if value > get_max_video_size():
            raise serializers.ValidationError(
                "Video exceeds the permitted upload size."
            )

        return value


# =========================================================
# R2 VIDEO UPLOAD CONFIRMATION
# =========================================================

class R2VideoConfirmSerializer(R2VideoUploadSerializer):
    """
    Validate the R2 object confirmation request.

    Includes the upload details plus the R2 object key.
    The view verifies the actual object metadata in R2.
    """

    key = serializers.CharField(
        max_length=1024,
    )


# =========================================================
# LEGACY BUNNY WEBHOOK SERIALIZER
# =========================================================

class BunnyWebhookSerializer(serializers.Serializer):
    """
    Retained for legacy Bunny Stream webhook events.
    New R2 uploads do not use this serializer.
    """

    VideoGuid = serializers.CharField(
        max_length=100,
    )

    Status = serializers.IntegerField()