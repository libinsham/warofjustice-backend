
from rest_framework import serializers

from .models import Media


# =========================================================
# MEDIA SERIALIZER
# =========================================================

class MediaSerializer(serializers.ModelSerializer):
    """
    Serializer for media stored in Cloudflare R2.

    Supports image, document and video metadata.
    """

    class Meta:
        model = Media
        fields = [
            "id",
            "post",
            "uploaded_by",
            "type",
            "file_name",
            "r2_key",
            "url",
            "mime_type",
            "size_bytes",
            "width",
            "height",
            "alt_text",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "uploaded_by",
            "r2_key",
            "url",
            "size_bytes",
            "width",
            "height",
            "created_at",
        ]


# =========================================================
# R2 PRESIGNED UPLOAD REQUEST
# =========================================================

class PresignRequestSerializer(serializers.Serializer):
    """
    Validates the image or media upload request
    before generating an R2 presigned PUT URL.
    """

    file_name = serializers.CharField(
        max_length=255,
    )

    content_type = serializers.CharField(
        max_length=100,
    )

    size_bytes = serializers.IntegerField(
        min_value=1,
        required=False,
    )


# =========================================================
# R2 UPLOAD CONFIRMATION
# =========================================================

class ConfirmUploadSerializer(serializers.Serializer):
    """
    Validates the uploaded R2 object confirmation request.
    """

    key = serializers.CharField(
        max_length=500,
    )

    file_name = serializers.CharField(
        max_length=255,
    )

    mime_type = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
    )

    size_bytes = serializers.IntegerField(
        min_value=1,
        required=False,
    )