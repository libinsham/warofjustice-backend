from django.conf import settings
from django.db import models

from apps.posts.models import Post


class Media(models.Model):
    """A single image/file stored in Cloudflare R2. Only the R2 key + resulting
    CDN URL are kept here — the binary itself never touches this server."""

    IMAGE = "image"
    DOCUMENT = "document"
    TYPE_CHOICES = [(IMAGE, "Image"), (DOCUMENT, "Document")]

    post = models.ForeignKey(
        Post, null=True, blank=True, on_delete=models.CASCADE, related_name="media_items"
    )
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    type = models.CharField(max_length=16, choices=TYPE_CHOICES, default=IMAGE)
    file_name = models.CharField(max_length=255)
    r2_key = models.CharField(max_length=500)  # object key inside the R2 bucket
    url = models.URLField()  # public/CDN URL
    mime_type = models.CharField(max_length=100, blank=True)
    size_bytes = models.PositiveBigIntegerField(null=True, blank=True)
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    alt_text = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "media"

    def __str__(self):
        return self.file_name
