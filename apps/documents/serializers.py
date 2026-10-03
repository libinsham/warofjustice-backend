from __future__ import annotations

from django.utils import timezone
from rest_framework import serializers

from apps.documents.models import Document, Membership
from apps.documents.services.qr import build_verification_url


class DocumentSerializer(serializers.ModelSerializer):
    """
    Serializer for authenticated users and authorized admins.

    Contains document information but does not expose
    sensitive member information or private storage URLs.
    """

    document_type_display = serializers.CharField(
        source="get_document_type_display",
        read_only=True,
    )

    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )

    verification_url = serializers.SerializerMethodField()

    has_pdf = serializers.SerializerMethodField()

    class Meta:
        model = Document

        fields = [
            "id",
            "document_number",
            "document_type",
            "document_type_display",
            "status",
            "status_display",
            "version",
            "template_version",
            "issue_date",
            "expiry_date",
            "verification_url",
            "has_pdf",
            "created_at",
            "updated_at",
        ]

        read_only_fields = fields

    def get_verification_url(
        self,
        obj: Document,
    ) -> str | None:
        if not obj.document_number:
            return None

        return build_verification_url(obj)

    def get_has_pdf(
        self,
        obj: Document,
    ) -> bool:
        return bool(obj.pdf_file)


class MyDocumentSerializer(serializers.ModelSerializer):
    """
    Serializer used by the member dashboard.

    Provides document information needed by the logged-in
    member without exposing private storage details.
    """

    document_type_display = serializers.CharField(
        source="get_document_type_display",
        read_only=True,
    )

    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )

    verification_url = serializers.SerializerMethodField()

    has_pdf = serializers.SerializerMethodField()

    class Meta:
        model = Document

        fields = [
            "document_number",
            "document_type",
            "document_type_display",
            "status",
            "status_display",
            "version",
            "template_version",
            "issue_date",
            "expiry_date",
            "verification_url",
            "has_pdf",
        ]

        read_only_fields = fields

    def get_verification_url(
        self,
        obj: Document,
    ) -> str | None:
        if not obj.document_number:
            return None

        return build_verification_url(obj)

    def get_has_pdf(
        self,
        obj: Document,
    ) -> bool:
        return bool(obj.pdf_file)


class PublicDocumentVerificationSerializer(
    serializers.ModelSerializer
):
    """
    PUBLIC serializer.

    Only safe verification information is exposed.

    NEVER expose:
    - email
    - phone
    - address
    - Aadhaar
    - PAN
    - private file URL
    - R2 credentials
    - verification_token
    """

    document_type_display = serializers.CharField(
        source="get_document_type_display",
        read_only=True,
    )

    verification_status = serializers.SerializerMethodField()

    member_name = serializers.SerializerMethodField()

    designation = serializers.SerializerMethodField()

    is_valid = serializers.SerializerMethodField()

    class Meta:
        model = Document

        fields = [
            "document_number",
            "document_type",
            "document_type_display",
            "member_name",
            "designation",
            "issue_date",
            "expiry_date",
            "verification_status",
            "is_valid",
        ]

        read_only_fields = fields

    def get_member_name(
        self,
        obj: Document,
    ) -> str:
        membership = obj.membership
        user = membership.user

        # User's get_full_name()
        if hasattr(user, "get_full_name"):
            full_name = user.get_full_name().strip()

            if full_name:
                return full_name

        # Profile fallback
        profile = getattr(
            user,
            "profile",
            None,
        )

        if profile:
            for field_name in [
                "full_name",
                "name",
                "display_name",
            ]:
                value = getattr(
                    profile,
                    field_name,
                    "",
                )

                if value:
                    return str(value).strip()

        # Application fallback
        application = (
            membership.member_contributor_application
        )

        if application:
            for field_name in [
                "full_name",
                "name",
                "applicant_name",
            ]:
                value = getattr(
                    application,
                    field_name,
                    "",
                )

                if value:
                    return str(value).strip()

        return "War of Justice Member"

    def get_designation(
        self,
        obj: Document,
    ) -> str:
        membership = obj.membership

        designation = (
            membership.designation or ""
        ).strip()

        if designation:
            return designation

        if membership.membership_type == (
            Membership.CONTRIBUTOR
        ):
            return "Contributor"

        if membership.membership_type == (
            Membership.SUBSCRIBER
        ):
            return "Subscriber"

        return "Member"

    def get_verification_status(
        self,
        obj: Document,
    ) -> str:
        """
        Calculate the public verification status
        from the current database state.
        """

        if obj.status == Document.REVOKED:
            return "Revoked"

        if obj.status == Document.SUPERSEDED:
            return "Superseded"

        if obj.status == Document.EXPIRED:
            return "Expired"

        if (
            obj.status == Document.ISSUED
            and obj.expiry_date
            and obj.expiry_date < timezone.localdate()
        ):
            return "Expired"

        if obj.is_valid:
            return "Valid"

        return "Invalid"

    def get_is_valid(
        self,
        obj: Document,
    ) -> bool:
        return obj.is_valid