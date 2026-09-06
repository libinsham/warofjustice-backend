from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class Role(models.Model):
    """
    super_admin | admin | author | reader
    (Editor is treated as an Admin with a narrower permission set, per the
    RBAC design below — see Permission.group == 'editor_scope'.)
    """
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    AUTHOR = "author"
    READER = "reader"

    ROLE_CHOICES = [
        (SUPER_ADMIN, "Super Admin"),
        (ADMIN, "Admin / Editor"),
        (AUTHOR, "Author / User"),
        (READER, "Reader"),
    ]

    name = models.CharField(max_length=32, choices=ROLE_CHOICES, unique=True)
    label = models.CharField(max_length=64)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.label


class Permission(models.Model):
    """Fine-grained permission, assignable to roles (or individually to a user)."""
    codename = models.CharField(max_length=100, unique=True)  # e.g. "posts.approve"
    label = models.CharField(max_length=150)
    group = models.CharField(max_length=50, blank=True)  # posts, users, media, settings...
    roles = models.ManyToManyField(Role, related_name="permissions", blank=True)

    def __str__(self):
        return self.codename


class User(AbstractUser):
    """Custom user model. AUTH_USER_MODEL points here."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    PENDING = "pending"
    STATUS_CHOICES = [
        (ACTIVE, "Active"),
        (SUSPENDED, "Suspended"),
        (PENDING, "Pending Approval"),
    ]

    email = models.EmailField(unique=True)
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name="users")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=ACTIVE)
    slug = models.SlugField(max_length=255, unique=True, null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    # ---- RBAC helpers, used by DRF permission classes ----

    def has_role(self, *role_names) -> bool:
        return self.role_id is not None and self.role.name in role_names

    def is_super_admin(self) -> bool:
        return self.has_role(Role.SUPER_ADMIN)

    def has_permission(self, codename: str) -> bool:
        if self.is_super_admin():
            return True
        return self.role.permissions.filter(codename=codename).exists()

    def __str__(self):
        return self.email


class Profile(models.Model):
    """Extended, editable public-facing profile info, separate from auth fields."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    full_name = models.CharField(max_length=150, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    whatsapp_number = models.CharField(max_length=20, blank=True)
    avatar_url = models.URLField(blank=True)  # Cloudflare R2 URL
    bio = models.TextField(blank=True)
    twitter = models.CharField(max_length=100, blank=True)
    facebook = models.CharField(max_length=100, blank=True)
    website = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile<{self.user.email}>"


class SubscriberApplication(models.Model):
    """
    Created when a member of the public registers as a Subscriber.
    Tracks the "follow our official channels" confirmation shown on the
    registration form and gives every applicant a human-readable
    reference number (e.g. WOJ-2026-00042) shown on the success screen
    and usable for support inquiries.
    """
    PENDING = "pending"
    VERIFIED = "verified"
    STATUS_CHOICES = [(PENDING, "Pending Review"), (VERIFIED, "Verified")]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="subscriber_application")
    application_id = models.CharField(max_length=20, unique=True, editable=False)
    channels_confirmed = models.JSONField(default=list, blank=True)  # e.g. ["youtube","facebook"]
    declaration_confirmed = models.BooleanField(default=False)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.application_id:
            self.application_id = self._generate_application_id()
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_application_id() -> str:
        import random

        year = timezone.now().year
        while True:
            candidate = f"WOJ-{year}-{random.randint(10000, 99999)}"
            if not SubscriberApplication.objects.filter(application_id=candidate).exists():
                return candidate

    def __str__(self):
        return self.application_id
