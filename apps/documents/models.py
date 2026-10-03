import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Membership(models.Model):
    """
    Official War of Justice membership.

    This is separate from the application.

    Application:
        WOJ-MC-2026-12345

    Official Membership:
        WOJ-2026-00001

    An application becomes an official membership only after
    the required approval has been completed.
    """

    # =====================================================
    # MEMBERSHIP TYPES
    # =====================================================

    MEMBER = "member"
    CONTRIBUTOR = "contributor"
    SUBSCRIBER = "subscriber"

    MEMBERSHIP_TYPE_CHOICES = [
        (MEMBER, "Member"),
        (CONTRIBUTOR, "Contributor"),
        (SUBSCRIBER, "Subscriber"),
    ]

    # =====================================================
    # MEMBERSHIP STATUS
    # =====================================================

    PENDING = "pending"
    ACTIVE = "active"
    EXPIRED = "expired"
    SUSPENDED = "suspended"
    REVOKED = "revoked"

    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (ACTIVE, "Active"),
        (EXPIRED, "Expired"),
        (SUSPENDED, "Suspended"),
        (REVOKED, "Revoked"),
    ]

    # =====================================================
    # USER
    # =====================================================

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="membership",
    )

    # =====================================================
    # SOURCE APPLICATIONS
    # =====================================================

    member_contributor_application = models.OneToOneField(
        "accounts.MemberContributorApplication",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="membership",
    )

    subscriber_application = models.OneToOneField(
        "accounts.SubscriberApplication",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="membership",
    )

    # =====================================================
    # OFFICIAL MEMBERSHIP ID
    # =====================================================

    membership_id = models.CharField(
        max_length=30,
        unique=True,
        editable=False,
        blank=True,
    )

    # =====================================================
    # MEMBERSHIP TYPE
    # =====================================================

    membership_type = models.CharField(
        max_length=20,
        choices=MEMBERSHIP_TYPE_CHOICES,
    )

    # =====================================================
    # DESIGNATION
    # =====================================================

    designation = models.CharField(
        max_length=100,
        blank=True,
    )

    # =====================================================
    # ISSUE / EXPIRY
    # =====================================================

    issue_date = models.DateField(
        default=timezone.localdate,
    )

    expiry_date = models.DateField(
        null=True,
        blank=True,
    )

    # =====================================================
    # STATUS
    # =====================================================

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=PENDING,
    )

    # =====================================================
    # APPROVAL
    # =====================================================

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_memberships",
    )

    approved_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    # =====================================================
    # TIMESTAMPS
    # =====================================================

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.membership_id or f"Membership #{self.pk}"

    def clean(self):
        """
        Ensure a membership is connected to exactly one
        source application.
        """

        sources = [
            self.member_contributor_application_id,
            self.subscriber_application_id,
        ]

        source_count = sum(
            source_id is not None
            for source_id in sources
        )

        if source_count != 1:
            raise ValidationError(
                "A membership must be linked to exactly one "
                "source application."
            )

        if (
            self.membership_type
            == self.CONTRIBUTOR
            and self.member_contributor_application
        ):
            application = self.member_contributor_application

            if (
                application.membership_category
                != application.CATEGORY_CONTRIBUTOR
            ):
                raise ValidationError(
                    "Contributor membership must come from a "
                    "Contributor application."
                )

        if (
            self.membership_type == self.SUBSCRIBER
            and not self.subscriber_application_id
        ):
            raise ValidationError(
                "Subscriber membership must be linked to a "
                "Subscriber application."
            )

    @property
    def is_currently_valid(self):
        """
        Runtime validity check.

        This does not modify the database.
        """

        if self.status != self.ACTIVE:
            return False

        if (
            self.expiry_date
            and self.expiry_date < timezone.localdate()
        ):
            return False

        return True


class Document(models.Model):
    """
    Official generated War of Justice documents.

    Currently supported:

        ID_CARD
        CERTIFICATE

    The actual PDF is stored using Django's configured
    private storage, which is Cloudflare R2 in the current
    project configuration.
    """

    # =====================================================
    # DOCUMENT TYPES
    # =====================================================

    ID_CARD = "id_card"
    CERTIFICATE = "certificate"

    DOCUMENT_TYPE_CHOICES = [
        (ID_CARD, "Membership ID Card"),
        (CERTIFICATE, "Contributor Membership Certificate"),
    ]

    # =====================================================
    # DOCUMENT STATUS
    # =====================================================

    DRAFT = "draft"
    ISSUED = "issued"
    EXPIRED = "expired"
    REVOKED = "revoked"
    SUPERSEDED = "superseded"

    STATUS_CHOICES = [
        (DRAFT, "Draft"),
        (ISSUED, "Issued"),
        (EXPIRED, "Expired"),
        (REVOKED, "Revoked"),
        (SUPERSEDED, "Superseded"),
    ]

    # =====================================================
    # MEMBERSHIP
    # =====================================================

    membership = models.ForeignKey(
        Membership,
        on_delete=models.PROTECT,
        related_name="documents",
    )

    # =====================================================
    # DOCUMENT NUMBER
    # =====================================================

    document_number = models.CharField(
        max_length=40,
        unique=True,
        editable=False,
        blank=True,
    )

    # =====================================================
    # DOCUMENT TYPE
    # =====================================================

    document_type = models.CharField(
        max_length=20,
        choices=DOCUMENT_TYPE_CHOICES,
    )

    # =====================================================
    # STATUS
    # =====================================================

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=DRAFT,
    )

    # =====================================================
    # VERIFICATION
    # =====================================================

    verification_token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )

    # =====================================================
    # GENERATED PDF
    # =====================================================

    pdf_file = models.FileField(
        upload_to="documents/generated/",
        blank=True,
        null=True,
    )

    # =====================================================
    # TEMPLATE VERSION
    # =====================================================

    template_version = models.CharField(
        max_length=30,
        default="v1",
    )

    # =====================================================
    # DOCUMENT VERSION
    # =====================================================

    version = models.PositiveIntegerField(
        default=1,
    )

    supersedes = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="replacement_documents",
    )

    # =====================================================
    # ISSUE INFORMATION
    # =====================================================

    issue_date = models.DateField(
        null=True,
        blank=True,
    )

    expiry_date = models.DateField(
        null=True,
        blank=True,
    )

    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="issued_documents",
    )

    issued_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    # =====================================================
    # REVOCATION
    # =====================================================

    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="revoked_documents",
    )

    revoked_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    revocation_reason = models.TextField(
        blank=True,
    )

    # =====================================================
    # TIMESTAMPS
    # =====================================================

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-created_at"]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "membership",
                    "document_type",
                    "version",
                ],
                name="unique_membership_document_version",
            ),
        ]

    def __str__(self):
        return (
            self.document_number
            or f"{self.get_document_type_display()} #{self.pk}"
        )

    @property
    def verification_url(self):
        """
        Public verification URL.

        The actual frontend domain is resolved later by the
        document verification service/settings.
        """

        return (
            f"/verify/{self.document_number}"
            if self.document_number
            else None
        )

    @property
    def is_valid(self):
        """
        Current public validity status.
        """

        if self.status != self.ISSUED:
            return False

        if (
            self.expiry_date
            and self.expiry_date < timezone.localdate()
        ):
            return False

        return True

    def clean(self):
        """
        Business validation for official documents.
        """

        if self.document_type == self.CERTIFICATE:
            if (
                self.membership.membership_type
                != Membership.CONTRIBUTOR
            ):
                raise ValidationError(
                    "Contributor membership certificate can only "
                    "be issued to a Contributor membership."
                )

        if self.status == self.ISSUED:
            if not self.issue_date:
                raise ValidationError(
                    "An issued document must have an issue date."
                )

            if not self.issued_by_id:
                raise ValidationError(
                    "An issued document must record who issued it."
                )

        if self.status == self.REVOKED:
            if not self.revoked_at:
                raise ValidationError(
                    "A revoked document must have a revoked timestamp."
                )

            if not self.revocation_reason.strip():
                raise ValidationError(
                    "A revocation reason is required."
                )


class DocumentEvent(models.Model):
    """
    Immutable-ish issuance history for official documents.

    This is separate from the general AuditLog.

    AuditLog:
        Tracks general system/admin activity.

    DocumentEvent:
        Tracks the lifecycle of a specific official document.
    """

    # =====================================================
    # EVENT TYPES
    # =====================================================

    CREATED = "created"
    PREVIEWED = "previewed"
    ISSUED = "issued"
    DOWNLOADED = "downloaded"
    REGENERATED = "regenerated"
    REVOKED = "revoked"
    REISSUED = "reissued"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"

    EVENT_TYPE_CHOICES = [
        (CREATED, "Created"),
        (PREVIEWED, "Previewed"),
        (ISSUED, "Issued"),
        (DOWNLOADED, "Downloaded"),
        (REGENERATED, "Regenerated"),
        (REVOKED, "Revoked"),
        (REISSUED, "Reissued"),
        (EXPIRED, "Expired"),
        (SUPERSEDED, "Superseded"),
    ]

    # =====================================================
    # DOCUMENT
    # =====================================================

    document = models.ForeignKey(
        Document,
        on_delete=models.PROTECT,
        related_name="events",
    )

    # =====================================================
    # ACTOR
    # =====================================================

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="document_events",
    )

    # =====================================================
    # EVENT
    # =====================================================

    event_type = models.CharField(
        max_length=20,
        choices=EVENT_TYPE_CHOICES,
    )

    # =====================================================
    # EVENT DETAILS
    # =====================================================

    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
    )

    user_agent = models.TextField(
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"{self.document} - "
            f"{self.get_event_type_display()}"
        )