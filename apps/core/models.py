from django.conf import settings
from django.db import models


class SiteSettings(models.Model):
    key = models.CharField(max_length=100, unique=True)
    value = models.JSONField(null=True, blank=True)
    value_type = models.CharField(max_length=20, default="text")  # text, json, boolean, image
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "site settings"

    def __str__(self):
        return self.key


class AuditLog(models.Model):
    """Every significant admin/editor/author action, for compliance & debugging."""
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="audit_logs"
    )
    action = models.CharField(max_length=100)  # e.g. "post.approved", "user.suspended"
    target_type = models.CharField(max_length=100, blank=True)  # e.g. "Post"
    target_id = models.CharField(max_length=50, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
