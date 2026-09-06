from django.conf import settings
from django.db import models


class Video(models.Model):
    """A video hosted on Bunny Stream. We never store the file itself —
    only Bunny's identifiers and the playback/thumbnail URLs it returns."""

    UPLOADING = "uploading"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    STATUS_CHOICES = [
        (UPLOADING, "Uploading"),
        (PROCESSING, "Processing"),
        (READY, "Ready"),
        (FAILED, "Failed"),
    ]

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="videos"
    )
    title = models.CharField(max_length=255, blank=True)
    bunny_video_id = models.CharField(max_length=100, unique=True)  # Bunny GUID
    bunny_library_id = models.CharField(max_length=50)
    thumbnail_url = models.URLField(blank=True)
    playback_url = models.URLField(blank=True)  # HLS/iframe embed URL
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=UPLOADING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title or self.bunny_video_id
