from django.conf import settings
from django.db import models
from django.utils.text import slugify

from apps.categories.models import Category, Tag
from apps.videos.models import Video


class Post(models.Model):
    # =========================================================
    # POST STATUS
    # =========================================================

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

    # Author can edit posts only in these statuses
    AUTHOR_EDITABLE_STATUSES = {
        DRAFT,
        CHANGES_REQUESTED,
        REJECTED,
    }

    # =========================================================
    # POST CONTENT
    # =========================================================

    title = models.CharField(
        max_length=255
    )

    slug = models.SlugField(
        max_length=280,
        unique=True,
        blank=True,
    )

    short_description = models.CharField(
        max_length=500,
        blank=True,
    )

    content = models.TextField()

    featured_image_url = models.URLField(
        blank=True
    )

    # =========================================================
    # CATEGORY / TAGS / VIDEO
    # =========================================================

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="posts",
    )

    tags = models.ManyToManyField(
        Tag,
        blank=True,
        related_name="posts",
    )

    video = models.ForeignKey(
        Video,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="posts",
    )

    # =========================================================
    # AUTHOR / REVIEWER
    # =========================================================

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="posts",
    )

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_posts",
    )

    # =========================================================
    # STATUS / REVIEW
    # =========================================================

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=DRAFT,
    )

    review_note = models.TextField(
        blank=True
    )

    # =========================================================
    # SEO
    # =========================================================

    seo_title = models.CharField(
        max_length=255,
        blank=True,
    )

    seo_description = models.CharField(
        max_length=500,
        blank=True,
    )

    # =========================================================
    # NEWS SETTINGS
    # =========================================================

    views = models.PositiveBigIntegerField(
        default=0
    )

    is_breaking = models.BooleanField(
        default=False
    )

    is_featured = models.BooleanField(
        default=False
    )

    is_trending = models.BooleanField(
        default=False
    )

    # =========================================================
    # DATES
    # =========================================================

    submitted_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    published_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    # =========================================================
    # META
    # =========================================================

    class Meta:
        ordering = ["-created_at"]

        indexes = [
            models.Index(
                fields=["status", "published_at"]
            ),
            models.Index(
                fields=["author", "status"]
            ),
        ]

    # =========================================================
    # AUTOMATIC SLUG GENERATION
    # =========================================================

    def save(self, *args, **kwargs):
        """
        Automatically generate a unique slug.

        allow_unicode=True supports Tamil and other
        Unicode languages.
        """

        if not self.slug:
            # Generate slug from title
            base_slug = slugify(
                self.title,
                allow_unicode=True,
            )

            # Fallback if slug generation fails
            if not base_slug:
                base_slug = "article"

            slug = base_slug
            counter = 1

            # Ensure slug is unique
            while Post.objects.filter(
                slug=slug
            ).exclude(
                pk=self.pk
            ).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            self.slug = slug

        super().save(*args, **kwargs)

    # =========================================================
    # PERMISSIONS
    # =========================================================

    def is_editable_by_author(self) -> bool:
        """
        Check whether the author is allowed to edit
        this post.
        """

        return self.status in self.AUTHOR_EDITABLE_STATUSES

    # =========================================================
    # DISPLAY
    # =========================================================

    def __str__(self):
        return self.title


# =========================================================
# POST REVISION
# =========================================================

class PostRevision(models.Model):
    """
    Snapshot taken whenever an author or editor
    changes a post.
    """

    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="revisions",
    )

    edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )

    title = models.CharField(
        max_length=255
    )

    content = models.TextField()

    featured_image_url = models.URLField(
        blank=True
    )

    meta = models.JSONField(
        default=dict,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Revision: {self.post.title}"


# =========================================================
# POST APPROVAL HISTORY
# =========================================================

class PostApproval(models.Model):
    """
    Audit trail for post workflow actions.
    """

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

    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="approval_history",
    )

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )

    action = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES,
    )

    note = models.TextField(
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "post approvals"

    def __str__(self):
        return f"{self.post.title} - {self.action}"