from rest_framework import serializers

from .models import Media

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/avif", "image/gif"}
MAX_UPLOAD_SIZE_BYTES = 15 * 1024 * 1024  # 15MB


class PresignRequestSerializer(serializers.Serializer):
    file_name = serializers.CharField(max_length=255)
    content_type = serializers.CharField(max_length=100)
    size_bytes = serializers.IntegerField(min_value=1)

    def validate_content_type(self, value):
        if value not in ALLOWED_IMAGE_TYPES:
            raise serializers.ValidationError(
                f"Unsupported file type '{value}'. Allowed: {', '.join(sorted(ALLOWED_IMAGE_TYPES))}"
            )
        return value

    def validate_size_bytes(self, value):
        if value > MAX_UPLOAD_SIZE_BYTES:
            raise serializers.ValidationError("File exceeds the 15MB upload limit.")
        return value


class MediaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Media
        fields = [
            "id", "post", "type", "file_name", "url", "mime_type",
            "size_bytes", "width", "height", "alt_text", "created_at",
        ]
        read_only_fields = ["url"]


class ConfirmUploadSerializer(serializers.Serializer):
    """Client calls this after successfully PUTting the file to R2, so we
    record the metadata. We never trust the client's claimed URL blindly —
    it must match a key we issued (checked in the view)."""
    key = serializers.CharField(max_length=500)
    file_name = serializers.CharField(max_length=255)
    mime_type = serializers.CharField(max_length=100)
    size_bytes = serializers.IntegerField(min_value=1)
    width = serializers.IntegerField(required=False, allow_null=True)
    height = serializers.IntegerField(required=False, allow_null=True)
    alt_text = serializers.CharField(required=False, allow_blank=True, max_length=255)
    post = serializers.IntegerField(required=False, allow_null=True)
