from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers

from .models import (
    MemberContributorApplication,
    Profile,
    Role,
    SubscriberApplication,
    User,
)


# =========================================================
# PROFILE
# =========================================================

class UpdateProfileSerializer(serializers.ModelSerializer):
    """
    Handles PATCH /auth/me/
    Updates username plus nested profile fields.
    """

    bio = serializers.CharField(
        required=False,
        allow_blank=True,
        write_only=True,
    )

    avatar_url = serializers.URLField(
        required=False,
        allow_blank=True,
        write_only=True,
    )

    twitter = serializers.CharField(
        required=False,
        allow_blank=True,
        write_only=True,
    )

    facebook = serializers.CharField(
        required=False,
        allow_blank=True,
        write_only=True,
    )

    website = serializers.URLField(
        required=False,
        allow_blank=True,
        write_only=True,
    )

    class Meta:
        model = User
        fields = [
            "username",
            "bio",
            "avatar_url",
            "twitter",
            "facebook",
            "website",
        ]

    def update(self, instance, validated_data):
        profile_fields = [
            "bio",
            "avatar_url",
            "twitter",
            "facebook",
            "website",
        ]

        profile_data = {
            field: validated_data.pop(field)
            for field in profile_fields
            if field in validated_data
        }

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        if profile_data:
            profile, _ = Profile.objects.get_or_create(
                user=instance
            )

            for attr, value in profile_data.items():
                setattr(profile, attr, value)

            profile.save()

        return instance


# =========================================================
# PASSWORD
# =========================================================

class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField()

    new_password = serializers.CharField(
        validators=[validate_password]
    )


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()

    new_password = serializers.CharField(
        validators=[validate_password]
    )


# =========================================================
# ROLE
# =========================================================

class RoleSerializer(serializers.ModelSerializer):

    class Meta:
        model = Role
        fields = [
            "id",
            "name",
            "label",
            "description",
        ]


# =========================================================
# PROFILE
# =========================================================

class ProfileSerializer(serializers.ModelSerializer):

    class Meta:
        model = Profile
        fields = [
            "full_name",
            "phone_number",
            "whatsapp_number",
            "avatar_url",
            "bio",
            "twitter",
            "facebook",
            "website",
        ]


# =========================================================
# SUBSCRIBER APPLICATION
# =========================================================

class SubscriberApplicationSerializer(
    serializers.ModelSerializer
):

    class Meta:
        model = SubscriberApplication
        fields = [
            "application_id",
            "channels_confirmed",
            "created_at",
        ]


# =========================================================
# SUBSCRIBER APPLICATION
# ADMIN / READ SERIALIZER
# =========================================================

class AdminSubscriberApplicationSerializer(
    serializers.ModelSerializer
):
    """
    Read serializer used by the Admin Subscriber section.

    Subscriber registration is automatic, so the subscriber does
    not have an approval status on SubscriberApplication.

    The current account status is taken from User.status.
    This keeps the API compatible with the frontend while making
    ACTIVE the real subscriber account status.
    """

    name = serializers.CharField(
        source="user.profile.full_name",
        read_only=True,
    )

    email = serializers.EmailField(
        source="user.email",
        read_only=True,
    )

    phone = serializers.CharField(
        source="user.profile.phone_number",
        read_only=True,
    )

    whatsapp_number = serializers.CharField(
        source="user.profile.whatsapp_number",
        read_only=True,
    )

    website = serializers.URLField(
        source="user.profile.website",
        read_only=True,
        allow_blank=True,
    )

    # SubscriberApplication no longer has its own status field.
    # The real account status belongs to User.
    status = serializers.CharField(
        source="user.status",
        read_only=True,
    )

    class Meta:
        model = SubscriberApplication
        fields = [
            "id",
            "application_id",
            "name",
            "email",
            "phone",
            "whatsapp_number",
            "website",
            "channels_confirmed",
            "declaration_confirmed",
            "status",
            "created_at",
        ]
        read_only_fields = fields


# =========================================================
# MEMBER & CONTRIBUTOR
# ADMIN / READ SERIALIZER
# =========================================================

class MemberContributorApplicationSerializer(
    serializers.ModelSerializer
):
    """
    Read serializer used by the Admin Member & Contributor
    section.

    Includes applicant information and uploaded document URLs.
    """

    class Meta:
        model = MemberContributorApplication

        fields = [
            "id",
            "application_id",

            # -------------------------------------------------
            # Personal information
            # -------------------------------------------------
            "full_name",
            "date_of_birth",
            "gender",
            "mobile_number",
            "email",
            "aadhaar_number",
            "pan_number",

            # -------------------------------------------------
            # Address
            # -------------------------------------------------
            "house_or_street",
            "village_town_city",
            "taluk",
            "mandal",
            "district",
            "state",
            "pin_code",

            # -------------------------------------------------
            # Applicant details
            # -------------------------------------------------
            "residential_status",
            "citizenship",
            "educational_status",
            "profession",
            "below_poverty_line",

            # -------------------------------------------------
            # Reporting
            # -------------------------------------------------
            "preferred_reporting_areas",

            # -------------------------------------------------
            # Membership
            # -------------------------------------------------
            "membership_category",
            "other_membership_category",

            # -------------------------------------------------
            # Documents
            # -------------------------------------------------
            "selfie_photo",
            "aadhaar_card",
            "pan_card",
            "identity_proof",
            "supporting_documents",

            # -------------------------------------------------
            # Declaration
            # -------------------------------------------------
            "declaration_accepted",
            "terms_accepted",
            "privacy_policy_accepted",
            "communication_consent",

            # -------------------------------------------------
            # Status
            # -------------------------------------------------
            "status",
            "approved_role",

            # -------------------------------------------------
            # Approval
            # -------------------------------------------------
            "approved_by",
            "approved_at",

            # -------------------------------------------------
            # Rejection
            # -------------------------------------------------
            "rejection_reason",
            "rejected_by",
            "rejected_at",

            # -------------------------------------------------
            # Dates
            # -------------------------------------------------
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "application_id",
            "status",
            "approved_role",
            "approved_by",
            "approved_at",
            "rejection_reason",
            "rejected_by",
            "rejected_at",
            "created_at",
            "updated_at",
        ]


# =========================================================
# MEMBER & CONTRIBUTOR
# PUBLIC REGISTRATION SERIALIZER
# =========================================================

class MemberContributorRegisterSerializer(
    serializers.ModelSerializer
):
    """
    Public Member & Contributor registration.

    IMPORTANT:
    The frontend uses different field names from the database
    model. This serializer maps the frontend names to the
    existing model fields.

    Expected frontend multipart/form-data:

        full_name
        date_of_birth
        gender
        mobile_number
        email
        aadhaar_number
        pan_number

        house_street
        village_town_city
        taluk
        mandal
        district
        state
        pin_code

        residency_status
        citizenship
        education
        profession
        bpl_status

        reporting_areas

        requested_role
        other_role

        selfie
        aadhaar_card
        pan_card
        identity_proof
        supporting_documents

        declaration_confirmed
        terms_confirmed
        privacy_confirmed
        communication_consent
    """

    # =====================================================
    # FRONTEND -> MODEL FIELD MAPPING
    # =====================================================

    house_street = serializers.CharField(
        source="house_or_street",
        required=True,
        allow_blank=False,
    )

    residency_status = serializers.CharField(
        source="residential_status",
        required=True,
        allow_blank=False,
    )

    education = serializers.CharField(
        source="educational_status",
        required=True,
        allow_blank=False,
    )

    reporting_areas = serializers.ListField(
        source="preferred_reporting_areas",
        child=serializers.CharField(),
        required=True,
    )

    requested_role = serializers.ChoiceField(
        source="membership_category",
        choices=MemberContributorApplication.MEMBERSHIP_CATEGORY_CHOICES,
        required=True,
    )

    other_role = serializers.CharField(
        source="other_membership_category",
        required=False,
        allow_blank=True,
        default="",
    )

    # -----------------------------------------------------
    # BPL
    # Frontend sends "yes" / "no"
    # Model stores BooleanField
    # -----------------------------------------------------

    bpl_status = serializers.ChoiceField(
        choices=[
            ("yes", "Yes"),
            ("no", "No"),
        ],
        required=True,
        write_only=True,
    )

    # -----------------------------------------------------
    # FILE MAPPING
    # -----------------------------------------------------

    selfie = serializers.ImageField(
        source="selfie_photo",
        required=True,
        allow_empty_file=False,
    )

    aadhaar_card = serializers.FileField(
        required=False,
        allow_empty_file=False,
        allow_null=True,
    )

    pan_card = serializers.FileField(
        required=False,
        allow_empty_file=False,
        allow_null=True,
    )

    identity_proof = serializers.FileField(
        required=True,
        allow_empty_file=False,
    )

    supporting_documents = serializers.FileField(
        required=False,
        allow_empty_file=False,
        allow_null=True,
    )

    # -----------------------------------------------------
    # DECLARATION MAPPING
    # -----------------------------------------------------

    declaration_confirmed = serializers.BooleanField(
        source="declaration_accepted",
        required=True,
    )

    terms_confirmed = serializers.BooleanField(
        source="terms_accepted",
        required=True,
    )

    privacy_confirmed = serializers.BooleanField(
        source="privacy_policy_accepted",
        required=True,
    )

    communication_consent = serializers.BooleanField(
        required=False,
        default=False,
    )

    class Meta:
        model = MemberContributorApplication

        fields = [
            # -------------------------------------------------
            # Personal
            # -------------------------------------------------
            "full_name",
            "date_of_birth",
            "gender",
            "mobile_number",
            "email",
            "aadhaar_number",
            "pan_number",

            # -------------------------------------------------
            # Address
            # -------------------------------------------------
            "house_street",
            "village_town_city",
            "taluk",
            "mandal",
            "district",
            "state",
            "pin_code",

            # -------------------------------------------------
            # Applicant
            # -------------------------------------------------
            "residency_status",
            "citizenship",
            "education",
            "profession",
            "bpl_status",

            # -------------------------------------------------
            # Reporting
            # -------------------------------------------------
            "reporting_areas",

            # -------------------------------------------------
            # Membership
            # -------------------------------------------------
            "requested_role",
            "other_role",

            # -------------------------------------------------
            # Documents
            # -------------------------------------------------
            "selfie",
            "aadhaar_card",
            "pan_card",
            "identity_proof",
            "supporting_documents",

            # -------------------------------------------------
            # Declaration
            # -------------------------------------------------
            "declaration_confirmed",
            "terms_confirmed",
            "privacy_confirmed",
            "communication_consent",
        ]

    # =====================================================
    # EMAIL VALIDATION
    # =====================================================

    def validate_email(self, value):

        normalized_email = value.strip().lower()

        existing_user = User.objects.filter(
            email__iexact=normalized_email
        ).first()

        if existing_user:
            raise serializers.ValidationError(
                "An account with this email address already exists."
            )

        return normalized_email

    # =====================================================
    # MOBILE VALIDATION
    # =====================================================

    def validate_mobile_number(self, value):

        value = value.strip()

        if len(value) < 8:
            raise serializers.ValidationError(
                "Please enter a valid mobile number."
            )

        return value

    # =====================================================
    # AADHAAR VALIDATION
    # =====================================================

    def validate_aadhaar_number(self, value):

        if not value:
            return value

        value = value.strip()

        if (
            len(value) != 12
            or not value.isdigit()
        ):
            raise serializers.ValidationError(
                "Aadhaar number must contain 12 digits."
            )

        return value

    # =====================================================
    # PAN VALIDATION
    # =====================================================

    def validate_pan_number(self, value):

        if not value:
            return value

        import re

        value = value.strip().upper()

        if not re.match(
            r"^[A-Z]{5}[0-9]{4}[A-Z]$",
            value,
        ):
            raise serializers.ValidationError(
                "Please enter a valid PAN number."
            )

        return value

    # =====================================================
    # REPORTING AREAS
    # =====================================================

    def validate_reporting_areas(self, value):

        if not isinstance(value, list):
            raise serializers.ValidationError(
                "Reporting areas must be a list."
            )

        if len(value) == 0:
            raise serializers.ValidationError(
                "Please select at least one reporting area."
            )

        return value

    # =====================================================
    # SELFIE VALIDATION
    # =====================================================

    def validate_selfie(self, value):

        # 5 MB maximum
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError(
                "Selfie image must be smaller than 5 MB."
            )

        return value

    # =====================================================
    # IDENTITY DOCUMENT VALIDATION
    # =====================================================

    def validate_identity_proof(self, value):

        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError(
                "Identity proof must be smaller than 5 MB."
            )

        return value

    # =====================================================
    # CROSS-FIELD VALIDATION
    # =====================================================

    def validate(self, attrs):

        membership_category = attrs.get(
            "membership_category"
        )

        other_category = attrs.get(
            "other_membership_category",
            "",
        ).strip()

        # -------------------------------------------------
        # Other membership category
        # -------------------------------------------------

        if (
            membership_category
            == MemberContributorApplication.CATEGORY_OTHER
            and not other_category
        ):
            raise serializers.ValidationError(
                {
                    "other_role": (
                        "Please specify the membership category."
                    )
                }
            )

        # -------------------------------------------------
        # Declaration
        # -------------------------------------------------

        if not attrs.get("declaration_accepted"):
            raise serializers.ValidationError(
                {
                    "declaration_confirmed": (
                        "You must accept the Declaration & Oath."
                    )
                }
            )

        # -------------------------------------------------
        # Terms
        # -------------------------------------------------

        if not attrs.get("terms_accepted"):
            raise serializers.ValidationError(
                {
                    "terms_confirmed": (
                        "You must accept the Terms & Conditions."
                    )
                }
            )

        # -------------------------------------------------
        # Privacy
        # -------------------------------------------------

        if not attrs.get("privacy_policy_accepted"):
            raise serializers.ValidationError(
                {
                    "privacy_confirmed": (
                        "You must accept the Privacy Policy."
                    )
                }
            )

        return attrs

    # =====================================================
    # CREATE APPLICATION
    # =====================================================

    @transaction.atomic
    def create(self, validated_data):
        """
        Creates:

        1. Pending User
        2. Profile
        3. MemberContributorApplication

        The application stays pending until an admin approves it.
        """

        # -------------------------------------------------
        # Extract values
        # -------------------------------------------------

        email = validated_data["email"]
        full_name = validated_data["full_name"]
        mobile_number = validated_data["mobile_number"]

        # -------------------------------------------------
        # Convert BPL yes/no -> Boolean
        # -------------------------------------------------

        bpl_status = validated_data.pop(
            "bpl_status",
            "no",
        )

        validated_data["below_poverty_line"] = (
            str(bpl_status).lower() == "yes"
        )

        # -------------------------------------------------
        # Temporary role
        #
        # User.role is mandatory.
        #
        # Applicant is NOT yet a Member or Contributor.
        # Therefore we use Subscriber temporarily and keep
        # User.status = pending.
        #
        # Admin approval will later change:
        #
        # subscriber -> member
        # OR
        # subscriber -> contributor
        # -------------------------------------------------

        role, _ = Role.objects.get_or_create(
            name=Role.SUBSCRIBER,
            defaults={
                "label": "Subscriber",
                "description": (
                    "Temporary role for pending public applications."
                ),
            },
        )

        # -------------------------------------------------
        # Generate username
        # -------------------------------------------------

        username = self._generate_username(
            email=email,
            full_name=full_name,
        )

        # -------------------------------------------------
        # Create pending user
        # -------------------------------------------------

        user = User(
            email=email,
            username=username,
            role=role,
            status=User.PENDING,
        )

        # No password is supplied by the public form.
        user.set_unusable_password()

        user.save()

        # -------------------------------------------------
        # Create profile
        # -------------------------------------------------

        Profile.objects.create(
            user=user,
            full_name=full_name,
            phone_number=mobile_number,
        )

        # -------------------------------------------------
        # Create application
        # -------------------------------------------------

        application = MemberContributorApplication.objects.create(
            user=user,
            **validated_data,
        )

        return application

    # =====================================================
    # USERNAME GENERATOR
    # =====================================================

    @staticmethod
    def _generate_username(
        email: str,
        full_name: str,
    ) -> str:

        from django.utils.text import slugify

        base = slugify(full_name)

        if not base:
            base = slugify(
                email.split("@")[0]
            )

        if not base:
            base = "applicant"

        base = base[:120]

        username = base
        counter = 1

        while User.objects.filter(
            username=username
        ).exists():

            suffix = f"-{counter}"

            username = (
                f"{base[:120 - len(suffix)]}"
                f"{suffix}"
            )

            counter += 1

        return username


# =========================================================
# USER SERIALIZER
# =========================================================

class UserSerializer(serializers.ModelSerializer):

    role = RoleSerializer(
        read_only=True
    )

    profile = ProfileSerializer(
        read_only=True
    )

    subscriber_application = (
        SubscriberApplicationSerializer(
            read_only=True
        )
    )

    member_contributor_application = (
        MemberContributorApplicationSerializer(
            read_only=True
        )
    )

    class Meta:
        model = User

        fields = [
            "id",
            "email",
            "username",
            "slug",
            "role",
            "status",
            "profile",
            "subscriber_application",
            "member_contributor_application",
            "date_joined",
        ]


# =========================================================
# EXISTING PUBLIC REGISTRATION
# READER / SUBSCRIBER
# =========================================================

class RegisterReaderSerializer(
    serializers.ModelSerializer
):
    """
    Public sign-up -> creates a subscriber account.
    """

    password = serializers.CharField(
        write_only=True,
        validators=[validate_password],
    )

    class Meta:
        model = User

        fields = [
            "email",
            "username",
            "password",
        ]

    def create(self, validated_data):

        role, _ = Role.objects.get_or_create(
            name=Role.SUBSCRIBER,
            defaults={
                "label": "Subscriber",
            },
        )

        user = User(
            email=validated_data["email"],
            username=validated_data["username"],
            role=role,
            status=User.ACTIVE,
        )

        user.set_password(
            validated_data["password"]
        )

        user.save()

        Profile.objects.create(
            user=user
        )

        return user


# =========================================================
# SUBSCRIBER REGISTRATION
# =========================================================

VALID_CHANNELS = {
    "youtube",
    "whatsapp",
    "facebook",
    "instagram",
    "twitter",
}


class SubscriberRegisterSerializer(
    serializers.ModelSerializer
):
    """
    Full public Subscriber application flow.

    Creates:
    - User
    - Profile
    - SubscriberApplication
    """

    password = serializers.CharField(
        write_only=True,
        validators=[validate_password],
    )

    full_name = serializers.CharField(
        max_length=150
    )

    phone_number = serializers.CharField(
        max_length=20
    )

    whatsapp_number = serializers.CharField(
        max_length=20,
        required=False,
        allow_blank=True,
    )

    channels_confirmed = serializers.ListField(
        child=serializers.ChoiceField(
            choices=sorted(VALID_CHANNELS)
        ),
        required=False,
        default=list,
    )

    declaration_confirmed = serializers.BooleanField()

    class Meta:
        model = User

        fields = [
            "email",
            "username",
            "password",
            "full_name",
            "phone_number",
            "whatsapp_number",
            "channels_confirmed",
            "declaration_confirmed",
        ]

    def validate_declaration_confirmed(
        self,
        value,
    ):

        if not value:
            raise serializers.ValidationError(
                "You must confirm you've followed the official channels before submitting."
            )

        return value

    def create(self, validated_data):

        role, _ = Role.objects.get_or_create(
            name=Role.SUBSCRIBER,
            defaults={
                "label": "Subscriber",
            },
        )

        user = User(
            email=validated_data["email"],
            username=validated_data["username"],
            role=role,
            status=User.ACTIVE,
        )

        user.set_password(
            validated_data["password"]
        )

        user.save()

        Profile.objects.create(
            user=user,
            full_name=validated_data[
                "full_name"
            ],
            phone_number=validated_data[
                "phone_number"
            ],
            whatsapp_number=validated_data.get(
                "whatsapp_number",
                "",
            ),
        )

        SubscriberApplication.objects.create(
            user=user,
            channels_confirmed=validated_data.get(
                "channels_confirmed",
                [],
            ),
            declaration_confirmed=validated_data[
                "declaration_confirmed"
            ],
        )

        return user


# =========================================================
# AUTHOR REGISTRATION
# =========================================================

class RegisterAuthorSerializer(
    serializers.ModelSerializer
):
    """
    Author/reporter sign-up.

    Account starts as pending.
    Admin/Super Admin must approve before login/publishing.
    """

    password = serializers.CharField(
        write_only=True,
        validators=[validate_password],
    )

    bio = serializers.CharField(
        required=False,
        allow_blank=True,
        write_only=True,
    )

    class Meta:
        model = User

        fields = [
            "email",
            "username",
            "password",
            "bio",
        ]

    def create(self, validated_data):

        bio = validated_data.pop(
            "bio",
            "",
        )

        role, _ = Role.objects.get_or_create(
            name=Role.AUTHOR,
            defaults={
                "label": "Author / User",
            },
        )

        user = User(
            email=validated_data["email"],
            username=validated_data["username"],
            role=role,
            status=User.PENDING,
        )

        user.set_password(
            validated_data["password"]
        )

        user.save()

        Profile.objects.create(
            user=user,
            bio=bio,
        )

        return user