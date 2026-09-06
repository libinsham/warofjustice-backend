from rest_framework import serializers

from .models import Video


class VideoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Video
        fields = [
            "id", "title", "bunny_video_id", "thumbnail_url",
            "playback_url", "duration_seconds", "status", "created_at",
        ]
        read_only_fields = ["bunny_video_id", "thumbnail_url", "playback_url", "status"]


class CreateVideoSlotSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)


class BunnyWebhookSerializer(serializers.Serializer):
    """Bunny POSTs here when a video finishes processing (or fails)."""
    VideoGuid = serializers.CharField()
    Status = serializers.IntegerField()  # Bunny's numeric status code
