from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

from .managers import CustomUserManager


# =========================================================
# ROLE
# =========================================================

class Role(models.Model):
    """
    Available user roles.
    """

    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    AUTHOR = "author"
    MEMBER = "member"
    CONTRIBUTOR = "contributor"
    SUBSCRIBER = "subscriber"

    ROLE_CHOICES = [
        (SUPER_ADMIN, "Super Admin"),
        (ADMIN, "Admin / Editor"),
        (AUTHOR, "Author"),
        (MEMBER, "Member"),
        (CONTRIBUTOR, "Contributor"),
        (SUBSCRIBER, "Subscriber"),
    ]

    name = models.CharField(
        max_length=32,
        choices=ROLE_CHOICES,
        unique=True,
    )

    label = models.CharField(
        max_length=64,
    )

    description = models.TextField(
        blank=True,
    )

    def __str__(self):
        return self.label


# =========================================================
# PERMISSION
# =========================================================

class Permission(models.Model):
    """Fine-grained permission, assignable to roles."""

    codename = models.CharField(
        max_length=100,
        unique=True,
    )

    label = models.CharField(
        max_length=150,
    )

    group = models.CharField(
        max_length=50,
        blank=True,
    )

    roles = models.ManyToManyField(
        Role,
        related_name="permissions",
        blank=True,
    )

    def __str__(self):
        return self.codename


# =========================================================
# USER
# =========================================================

class User(AbstractUser):
    """Custom user model."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    PENDING = "pending"

    STATUS_CHOICES = [
        (ACTIVE, "Active"),
        (SUSPENDED, "Suspended"),
        (PENDING, "Pending Approval"),
    ]

    email = models.EmailField(
        unique=True,
    )

    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name="users",
    )

    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=ACTIVE,
    )

    slug = models.SlugField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
    )

    # Login using email
    USERNAME_FIELD = "email"

    # Django createsuperuser will also ask for username
    REQUIRED_FIELDS = ["username"]

    # Custom manager
    objects = CustomUserManager()

    # ---------------------------------------------------------
    # RBAC helpers
    # ---------------------------------------------------------

    def has_role(self, *role_names) -> bool:
        return (
            self.role_id is not None
            and self.role.name in role_names
        )

    def is_super_admin(self) -> bool:
        return self.has_role(Role.SUPER_ADMIN)

    def is_subscriber(self) -> bool:
        return self.has_role(Role.SUBSCRIBER)

    def is_member(self) -> bool:
        return self.has_role(Role.MEMBER)

    def is_contributor(self) -> bool:
        return self.has_role(Role.CONTRIBUTOR)

    def has_permission(self, codename: str) -> bool:
        # Super Admin has all permissions
        if self.is_super_admin():
            return True

        # Users without a role have no permissions
        if not self.role_id:
            return False

        return self.role.permissions.filter(
            codename=codename
        ).exists()

    def __str__(self):
        return self.email


# =========================================================
# PROFILE
# =========================================================

class Profile(models.Model):
    """Extended public-facing profile information."""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
    )

    full_name = models.CharField(
        max_length=150,
        blank=True,
    )

    phone_number = models.CharField(
        max_length=20,
        blank=True,
    )

    whatsapp_number = models.CharField(
        max_length=20,
        blank=True,
    )

    avatar_url = models.URLField(
        blank=True,
    )

    bio = models.TextField(
        blank=True,
    )

    twitter = models.CharField(
        max_length=100,
        blank=True,
    )

    facebook = models.CharField(
        max_length=100,
        blank=True,
    )

    website = models.URLField(
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return f"Profile<{self.user.email}>"


# =========================================================
# SUBSCRIBER
# =========================================================

class SubscriberApplication(models.Model):
    """
    Subscriber account information.

    Subscriber registration is automatic.
    No admin approval is required.

    Flow:

        Register
            ↓
        User created
            ↓
        Profile created
            ↓
        SubscriberApplication created
            ↓
        User status = ACTIVE

    Future:
        If subscriber approval is required later, an approval
        status/workflow can be added here without changing the
        current registration flow.
    """

    # ---------------------------------------------------------
    # User relationship
    # ---------------------------------------------------------

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="subscriber_application",
    )

    # ---------------------------------------------------------
    # Subscriber ID
    # ---------------------------------------------------------

    application_id = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
    )

    # ---------------------------------------------------------
    # Confirmed channels
    # ---------------------------------------------------------

    channels_confirmed = models.JSONField(
        default=list,
        blank=True,
    )

    # ---------------------------------------------------------
    # Registration declaration
    # ---------------------------------------------------------

    declaration_confirmed = models.BooleanField(
        default=False,
    )

    # ---------------------------------------------------------
    # Timestamp
    # ---------------------------------------------------------

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    # ---------------------------------------------------------
    # Save
    # ---------------------------------------------------------

    def save(self, *args, **kwargs):
        if not self.application_id:
            self.application_id = self._generate_application_id()

        super().save(*args, **kwargs)

    # ---------------------------------------------------------
    # Subscriber ID generator
    # ---------------------------------------------------------

    @staticmethod
    def _generate_application_id() -> str:
        import random

        year = timezone.now().year

        while True:
            candidate = (
                f"WOJ-{year}-{random.randint(10000, 99999)}"
            )

            if not SubscriberApplication.objects.filter(
                application_id=candidate
            ).exists():
                return candidate

    # ---------------------------------------------------------
    # String representation
    # ---------------------------------------------------------

    def __str__(self):
        return self.application_id


# =========================================================
# MEMBER & CONTRIBUTOR APPLICATION
# =========================================================

class MemberContributorApplication(models.Model):
    """
    Member & Contributor application submitted through
    the public registration form.
    """

    # ---------------------------------------------------------
    # Application status
    # ---------------------------------------------------------

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

    STATUS_CHOICES = [
        (PENDING, "Pending Review"),
        (APPROVED, "Approved"),
        (REJECTED, "Rejected"),
    ]

    # ---------------------------------------------------------
    # Approved account role
    # ---------------------------------------------------------

    MEMBER = "member"
    CONTRIBUTOR = "contributor"

    APPROVED_ROLE_CHOICES = [
        (MEMBER, "Member"),
        (CONTRIBUTOR, "Contributor"),
    ]

    # ---------------------------------------------------------
    # Membership categories
    # ---------------------------------------------------------

    CATEGORY_MEMBER = "member"
    CATEGORY_CONTRIBUTOR = "contributor"
    CATEGORY_REPORTER = "reporter"
    CATEGORY_MEDIA_STAFF = "media_staff"
    CATEGORY_EDITOR = "editor"
    CATEGORY_BUREAU_CHIEF = "bureau_chief"
    CATEGORY_CAMERA_PERSON = "camera_person"
    CATEGORY_VOLUNTEER = "volunteer"
    CATEGORY_DISTRICT_COORDINATOR = "district_coordinator"
    CATEGORY_STATE_COORDINATOR = "state_coordinator"
    CATEGORY_OTHER = "other"

    MEMBERSHIP_CATEGORY_CHOICES = [
        (CATEGORY_MEMBER, "Member"),
        (CATEGORY_CONTRIBUTOR, "Contributor"),
        (CATEGORY_REPORTER, "Reporter"),
        (CATEGORY_MEDIA_STAFF, "Media Staff"),
        (CATEGORY_EDITOR, "Editor"),
        (CATEGORY_BUREAU_CHIEF, "Bureau Chief"),
        (CATEGORY_CAMERA_PERSON, "Camera Person"),
        (CATEGORY_VOLUNTEER, "Volunteer"),
        (
            CATEGORY_DISTRICT_COORDINATOR,
            "District Coordinator",
        ),
        (
            CATEGORY_STATE_COORDINATOR,
            "State Coordinator",
        ),
        (CATEGORY_OTHER, "Other"),
    ]

    # ---------------------------------------------------------
    # User relationship
    # ---------------------------------------------------------

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="member_contributor_application",
    )

    # ---------------------------------------------------------
    # Application ID
    # ---------------------------------------------------------

    application_id = models.CharField(
        max_length=30,
        unique=True,
        editable=False,
    )

    # ---------------------------------------------------------
    # Personal Information
    # ---------------------------------------------------------

    full_name = models.CharField(
        max_length=150,
    )

    date_of_birth = models.DateField(
        null=True,
        blank=True,
    )

    GENDER_MALE = "male"
    GENDER_FEMALE = "female"
    GENDER_TRANSGENDER = "transgender"
    GENDER_OTHER = "other"

    GENDER_CHOICES = [
        (GENDER_MALE, "Male"),
        (GENDER_FEMALE, "Female"),
        (GENDER_TRANSGENDER, "Transgender"),
        (GENDER_OTHER, "Other"),
    ]

    gender = models.CharField(
        max_length=20,
        choices=GENDER_CHOICES,
        blank=True,
    )

    mobile_number = models.CharField(
        max_length=20,
    )

    email = models.EmailField()

    aadhaar_number = models.CharField(
        max_length=12,
        blank=True,
    )

    pan_number = models.CharField(
        max_length=10,
        blank=True,
    )

    # ---------------------------------------------------------
    # Residential Address
    # ---------------------------------------------------------

    house_or_street = models.CharField(
        max_length=255,
        blank=True,
    )

    village_town_city = models.CharField(
        max_length=150,
        blank=True,
    )

    taluk = models.CharField(
        max_length=150,
        blank=True,
    )

    mandal = models.CharField(
        max_length=150,
        blank=True,
    )

    district = models.CharField(
        max_length=150,
        blank=True,
    )

    state = models.CharField(
        max_length=150,
        blank=True,
    )

    pin_code = models.CharField(
        max_length=10,
        blank=True,
    )

    # ---------------------------------------------------------
    # Applicant Details
    # ---------------------------------------------------------

    residential_status = models.CharField(
        max_length=100,
        blank=True,
    )

    citizenship = models.CharField(
        max_length=100,
        default="Indian",
    )

    educational_status = models.CharField(
        max_length=150,
        blank=True,
    )

    profession = models.CharField(
        max_length=150,
        blank=True,
    )

    below_poverty_line = models.BooleanField(
        default=False,
    )

    # ---------------------------------------------------------
    # Preferred Reporting Areas
    # ---------------------------------------------------------

    preferred_reporting_areas = models.JSONField(
        default=list,
        blank=True,
    )

    # ---------------------------------------------------------
    # Membership Category
    # ---------------------------------------------------------

    membership_category = models.CharField(
        max_length=50,
        choices=MEMBERSHIP_CATEGORY_CHOICES,
        blank=True,
    )

    other_membership_category = models.CharField(
        max_length=150,
        blank=True,
    )

    # ---------------------------------------------------------
    # Uploaded Documents
    # ---------------------------------------------------------

    selfie_photo = models.FileField(
        upload_to="member-contributor/selfies/",
        blank=True,
        null=True,
    )

    aadhaar_card = models.FileField(
        upload_to="member-contributor/aadhaar/",
        blank=True,
        null=True,
    )

    pan_card = models.FileField(
        upload_to="member-contributor/pan/",
        blank=True,
        null=True,
    )

    identity_proof = models.FileField(
        upload_to="member-contributor/identity-proof/",
        blank=True,
        null=True,
    )

    supporting_documents = models.FileField(
        upload_to="member-contributor/supporting-documents/",
        blank=True,
        null=True,
    )

    # ---------------------------------------------------------
    # Declaration & Terms
    # ---------------------------------------------------------

    declaration_accepted = models.BooleanField(
        default=False,
    )

    terms_accepted = models.BooleanField(
        default=False,
    )

    privacy_policy_accepted = models.BooleanField(
        default=False,
    )

    communication_consent = models.BooleanField(
        default=False,
    )

    # ---------------------------------------------------------
    # Application status
    # ---------------------------------------------------------

    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=PENDING,
    )

    # ---------------------------------------------------------
    # Admin approval
    # ---------------------------------------------------------

    approved_role = models.CharField(
        max_length=20,
        choices=APPROVED_ROLE_CHOICES,
        blank=True,
        null=True,
    )

    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_member_contributor_applications",
    )

    approved_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    # ---------------------------------------------------------
    # Rejection
    # ---------------------------------------------------------

    rejection_reason = models.TextField(
        blank=True,
    )

    rejected_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rejected_member_contributor_applications",
    )

    rejected_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    # ---------------------------------------------------------
    # Timestamps
    # ---------------------------------------------------------

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    # ---------------------------------------------------------
    # Save
    # ---------------------------------------------------------

    def save(self, *args, **kwargs):
        if not self.application_id:
            self.application_id = self._generate_application_id()

        super().save(*args, **kwargs)

    # ---------------------------------------------------------
    # Application ID generator
    # ---------------------------------------------------------

    @staticmethod
    def _generate_application_id() -> str:
        import random

        year = timezone.now().year

        while True:
            candidate = (
                f"WOJ-MC-{year}-{random.randint(10000, 99999)}"
            )

            if not MemberContributorApplication.objects.filter(
                application_id=candidate
            ).exists():
                return candidate

    def __str__(self):
        return self.application_id