from django.conf import settings
from django.db import models
from django.utils.text import slugify

from apps.categories.models import Category, Tag
from apps.videos.models import Video


class Post(models.Model):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    CHANGES_REQUESTED = "changes_requested"
    APPROVED = "approved"
    PUBLISHED = "published"
    REJECTED = "rejected"
    ARCHIVED = "archived"

    STATUS_CHOICES = [
        (DRAFT, "Draft"),
        (SUBMITTED, "Submitted for Review"),
        (UNDER_REVIEW, "Under Review"),
        (CHANGES_REQUESTED, "Changes Requested"),
        (APPROVED, "Approved"),
        (PUBLISHED, "Published"),
        (REJECTED, "Rejected"),
        (ARCHIVED, "Archived"),
    ]

    # States an author is allowed to edit / resubmit from.
    AUTHOR_EDITABLE_STATUSES = {DRAFT, CHANGES_REQUESTED, REJECTED}

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True, blank=True)
    short_description = models.CharField(max_length=500, blank=True)
    content = models.TextField()
    featured_image_url = models.URLField(blank=True)  # Cloudflare R2 URL

    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="posts")
    tags = models.ManyToManyField(Tag, blank=True, related_name="posts")
    video = models.ForeignKey(
        Video, null=True, blank=True, on_delete=models.SET_NULL, related_name="posts"
    )

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="posts"
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_posts",
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=DRAFT)
    review_note = models.TextField(blank=True)  # rejection / changes-requested feedback

    seo_title = models.CharField(max_length=255, blank=True)
    seo_description = models.CharField(max_length=500, blank=True)

    views = models.PositiveBigIntegerField(default=0)
    is_breaking = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    is_trending = models.BooleanField(default=False)

    submitted_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "published_at"]),
            models.Index(fields=["author", "status"]),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)
            slug = base
            i = 1
            while Post.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def is_editable_by_author(self) -> bool:
        return self.status in self.AUTHOR_EDITABLE_STATUSES

    def __str__(self):
        return self.title


class PostRevision(models.Model):
    """Snapshot taken every time an author or editor edits a post's content."""
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="revisions")
    edited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    content = models.TextField()
    featured_image_url = models.URLField(blank=True)
    meta = models.JSONField(default=dict, blank=True)  # snapshot of other fields
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class PostApproval(models.Model):
    """Audit trail for every workflow transition (submit/approve/reject/etc.)."""
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    CHANGES_REQUESTED = "changes_requested"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    RESUBMITTED = "resubmitted"

    ACTION_CHOICES = [
        (SUBMITTED, "Submitted"),
        (APPROVED, "Approved"),
        (REJECTED, "Rejected"),
        (CHANGES_REQUESTED, "Changes Requested"),
        (PUBLISHED, "Published"),
        (ARCHIVED, "Archived"),
        (RESUBMITTED, "Resubmitted"),
    ]

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="approval_history")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "post approvals"
