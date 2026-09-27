
from django.conf import settings
from django.db import models

from apps.posts.models import Post


class Media(models.Model):
    """
    A media file stored in Cloudflare R2.

    Supported types:
    - Image
    - Document
    - Video

    The database stores the R2 object key and the
    resulting CDN URL. File bytes are uploaded
    directly from the browser to R2.
    """

    IMAGE = "image"
    DOCUMENT = "document"
    VIDEO = "video"

    TYPE_CHOICES = [
        (IMAGE, "Image"),
        (DOCUMENT, "Document"),
        (VIDEO, "Video"),
    ]

    post = models.ForeignKey(
        Post,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="media_items",
    )

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )

    type = models.CharField(
        max_length=16,
        choices=TYPE_CHOICES,
        default=IMAGE,
    )

    file_name = models.CharField(
        max_length=255,
    )

    r2_key = models.CharField(
        max_length=500,
    )

    url = models.URLField()

    mime_type = models.CharField(
        max_length=100,
        blank=True,
    )

    size_bytes = models.PositiveBigIntegerField(
        null=True,
        blank=True,
    )

    width = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    height = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    alt_text = models.CharField(
        max_length=255,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        verbose_name_plural = "media"
        ordering = ["-created_at"]

    def __str__(self):
        return self.file_name