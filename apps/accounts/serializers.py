from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Profile, Role, SubscriberApplication, User


class UpdateProfileSerializer(serializers.ModelSerializer):
    """Handles PATCH /auth/me/ — updates username plus nested profile
    fields (bio/avatar/social links) in one call."""
    bio = serializers.CharField(required=False, allow_blank=True, write_only=True)
    avatar_url = serializers.URLField(required=False, allow_blank=True, write_only=True)
    twitter = serializers.CharField(required=False, allow_blank=True, write_only=True)
    facebook = serializers.CharField(required=False, allow_blank=True, write_only=True)
    website = serializers.URLField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = User
        fields = ["username", "bio", "avatar_url", "twitter", "facebook", "website"]

    def update(self, instance, validated_data):
        profile_fields = ["bio", "avatar_url", "twitter", "facebook", "website"]
        profile_data = {f: validated_data.pop(f) for f in profile_fields if f in validated_data}

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if profile_data:
            profile, _ = Profile.objects.get_or_create(user=instance)
            for attr, value in profile_data.items():
                setattr(profile, attr, value)
            profile.save()

        return instance


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField()
    new_password = serializers.CharField(validators=[validate_password])


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(validators=[validate_password])


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["id", "name", "label", "description"]


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ["full_name", "phone_number", "whatsapp_number", "avatar_url", "bio", "twitter", "facebook", "website"]


class SubscriberApplicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriberApplication
        fields = ["application_id", "channels_confirmed", "status", "created_at"]


class UserSerializer(serializers.ModelSerializer):
    role = RoleSerializer(read_only=True)
    profile = ProfileSerializer(read_only=True)
    subscriber_application = SubscriberApplicationSerializer(read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "username", "slug", "role", "status", "profile", "subscriber_application", "date_joined"]


class RegisterReaderSerializer(serializers.ModelSerializer):
    """Public sign-up -> always creates a 'reader' account."""
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ["email", "username", "password"]

    def create(self, validated_data):
        role, _ = Role.objects.get_or_create(
            name=Role.READER, defaults={"label": "Reader"}
        )
        user = User(
            email=validated_data["email"],
            username=validated_data["username"],
            role=role,
            status=User.ACTIVE,
        )
        user.set_password(validated_data["password"])
        user.save()
        Profile.objects.create(user=user)
        return user


VALID_CHANNELS = {"youtube", "whatsapp", "facebook", "instagram", "twitter"}


class SubscriberRegisterSerializer(serializers.ModelSerializer):
    """
    Full public "Subscriber" application flow — Account Credentials +
    Contact Information + a declaration that the applicant has followed
    the official channels, matching the subscription-form design. Creates
    a User (role=reader), a Profile with the contact fields, and a
    SubscriberApplication with a generated reference ID (e.g.
    WOJ-2026-00042) returned to the frontend for the success screen.
    """
    password = serializers.CharField(write_only=True, validators=[validate_password])
    full_name = serializers.CharField(max_length=150)
    phone_number = serializers.CharField(max_length=20)
    whatsapp_number = serializers.CharField(max_length=20, required=False, allow_blank=True)
    channels_confirmed = serializers.ListField(
        child=serializers.ChoiceField(choices=sorted(VALID_CHANNELS)),
        required=False,
        default=list,
    )
    declaration_confirmed = serializers.BooleanField()

    class Meta:
        model = User
        fields = [
            "email", "username", "password",
            "full_name", "phone_number", "whatsapp_number",
            "channels_confirmed", "declaration_confirmed",
        ]

    def validate_declaration_confirmed(self, value):
        if not value:
            raise serializers.ValidationError(
                "You must confirm you've followed the official channels before submitting."
            )
        return value

    def create(self, validated_data):
        role, _ = Role.objects.get_or_create(name=Role.READER, defaults={"label": "Reader"})

        user = User(
            email=validated_data["email"],
            username=validated_data["username"],
            role=role,
            status=User.ACTIVE,
        )
        user.set_password(validated_data["password"])
        user.save()

        Profile.objects.create(
            user=user,
            full_name=validated_data["full_name"],
            phone_number=validated_data["phone_number"],
            whatsapp_number=validated_data.get("whatsapp_number", ""),
        )

        SubscriberApplication.objects.create(
            user=user,
            channels_confirmed=validated_data.get("channels_confirmed", []),
            declaration_confirmed=validated_data["declaration_confirmed"],
        )

        return user


class RegisterAuthorSerializer(serializers.ModelSerializer):
    """
    Author/reporter sign-up. Account starts as `pending` so a Super Admin
    or Admin must approve it before the author can log in and publish-flow
    content — prevents anonymous sign-ups from immediately posting.
    """
    password = serializers.CharField(write_only=True, validators=[validate_password])
    bio = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = User
        fields = ["email", "username", "password", "bio"]

    def create(self, validated_data):
        bio = validated_data.pop("bio", "")
        role, _ = Role.objects.get_or_create(
            name=Role.AUTHOR, defaults={"label": "Author / User"}
        )
        user = User(
            email=validated_data["email"],
            username=validated_data["username"],
            role=role,
            status=User.PENDING,
        )
        user.set_password(validated_data["password"])
        user.save()
        Profile.objects.create(user=user, bio=bio)
        return user
