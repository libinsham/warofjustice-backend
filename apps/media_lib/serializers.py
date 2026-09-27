
from django.conf import settings
from rest_framework import serializers

from .models import Video


ALLOWED_VIDEO_TYPES = (
    "video/mp4",
    "video/webm",
    "video/quicktime",
    "video/x-m4v",
)


def get_max_video_size():
    return int(
        getattr(
            settings,
            "R2_VIDEO_MAX_BYTES",
            5 * 1024 * 1024 * 1024,
        )
    )


class VideoSerializer(serializers.ModelSerializer):
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
        if obj.r2_key:
            base_url = settings.R2_PUBLIC_BASE_URL.rstrip("/")
            return f"{base_url}/{obj.r2_key}"

        # Keep URLs for legacy Bunny records.
        return obj.playback_url or None


class R2VideoUploadSerializer(serializers.Serializer):
    title = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
    )
    file_name = serializers.CharField(
        max_length=255,
    )
    content_type = serializers.ChoiceField(
        choices=ALLOWED_VIDEO_TYPES,
    )
    size_bytes = serializers.IntegerField(min_value=1)

    def validate_size_bytes(self, value):
        if value > get_max_video_size():
            raise serializers.ValidationError(
                "Video exceeds the permitted upload size."
            )
        return value


class R2VideoConfirmSerializer(R2VideoUploadSerializer):
    key = serializers.CharField(max_length=1024)


class BunnyWebhookSerializer(serializers.Serializer):
    # Retain this serializer for the legacy Bunny webhook.
    VideoGuid = serializers.CharField()
    Status = serializers.IntegerField()