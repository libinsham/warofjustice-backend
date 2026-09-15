from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import AuditLog

from .serializers import (
    MemberContributorApplicationSerializer,
    MemberContributorRegisterSerializer,
    RegisterAuthorSerializer,
    RegisterReaderSerializer,
    SubscriberRegisterSerializer,
    UpdateProfileSerializer,
    UserSerializer,
)


# =========================================================
# TOKEN HELPER
# =========================================================

def issue_tokens(user):
    """
    Create a fresh JWT access + refresh token pair.

    Only the access token is returned in JSON.
    The refresh token is stored in an httpOnly cookie.
    """
    refresh = RefreshToken.for_user(user)

    return {
        "access": str(refresh.access_token)
    }, str(refresh)


# =========================================================
# READER / BASIC SUBSCRIBER REGISTRATION
# =========================================================

class RegisterReaderView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        from .token_views import _set_refresh_cookie

        serializer = RegisterReaderSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        user = serializer.save()

        access_data, refresh_token = issue_tokens(
            user
        )

        response = Response(
            {
                "user": UserSerializer(
                    user,
                    context={"request": request},
                ).data,
                **access_data,
            },
            status=status.HTTP_201_CREATED,
        )

        _set_refresh_cookie(
            response,
            refresh_token,
        )

        return response


# =========================================================
# SUBSCRIBER REGISTRATION
# =========================================================

class SubscriberRegisterView(APIView):
    """
    Public Subscriber registration.

    Creates:
    - User
    - Profile
    - SubscriberApplication

    Returns:
    - User
    - Access token
    - Subscriber application information
    """

    permission_classes = [AllowAny]

    def post(self, request):
        from .token_views import _set_refresh_cookie

        serializer = SubscriberRegisterSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        user = serializer.save()

        access_data, refresh_token = issue_tokens(
            user
        )

        response = Response(
            {
                "user": UserSerializer(
                    user,
                    context={"request": request},
                ).data,
                **access_data,
            },
            status=status.HTTP_201_CREATED,
        )

        _set_refresh_cookie(
            response,
            refresh_token,
        )

        return response


# =========================================================
# MEMBER & CONTRIBUTOR REGISTRATION
# =========================================================

class MemberContributorRegisterView(APIView):
    """
    Public Member & Contributor application.

    Accepts multipart/form-data.

    Supported uploads:

    - Selfie photograph
    - Aadhaar card
    - PAN card
    - Identity proof
    - Supporting document

    The application is created as PENDING.

    The applicant does not receive the Member or Contributor
    role until an administrator approves the application.
    """

    permission_classes = [AllowAny]

    # IMPORTANT:
    # Required for request.FILES / multipart/form-data.
    parser_classes = [
        MultiPartParser,
        FormParser,
    ]

    def post(self, request):
        serializer = MemberContributorRegisterSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        application = serializer.save()

        application_data = (
            MemberContributorApplicationSerializer(
                application,
                context={
                    "request": request,
                },
            ).data
        )

        return Response(
            {
                "message": (
                    "Your Member & Contributor application "
                    "has been submitted successfully."
                ),
                "application": application_data,
            },
            status=status.HTTP_201_CREATED,
        )


# =========================================================
# AUTHOR REGISTRATION
# =========================================================

class RegisterAuthorView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterAuthorSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        user = serializer.save()

        AuditLog.objects.create(
            actor=None,
            action="author.registered",
            target_type="User",
            target_id=str(user.id),
        )

        return Response(
            {
                "message": (
                    "Registration received. Your author "
                    "account is pending admin approval."
                ),
                "user": UserSerializer(
                    user,
                    context={"request": request},
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )


# =========================================================
# CURRENT USER
# =========================================================

class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(
            UserSerializer(
                request.user,
                context={
                    "request": request,
                },
            ).data
        )

    def patch(self, request):
        """
        Self-service profile update.

        Allows:
        - username
        - bio
        - avatar URL
        - social links
        - website

        Does NOT allow:
        - email changes
        - role changes
        - account status changes
        """

        serializer = UpdateProfileSerializer(
            request.user,
            data=request.data,
            partial=True,
            context={
                "request": request,
            },
        )

        serializer.is_valid(
            raise_exception=True
        )

        serializer.save()

        return Response(
            UserSerializer(
                request.user,
                context={
                    "request": request,
                },
            ).data
        )


# =========================================================
# LOGOUT
# =========================================================

class LogoutView(APIView):
    """
    Blacklists the refresh token and removes the
    refresh-token cookie.

    Access tokens are short-lived and are not blacklisted.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        from .token_views import REFRESH_COOKIE_NAME

        refresh_token = request.COOKIES.get(
            REFRESH_COOKIE_NAME
        )

        if refresh_token:
            try:
                RefreshToken(
                    refresh_token
                ).blacklist()

            except Exception:
                # Token may already be expired,
                # invalid, or blacklisted.
                pass

        response = Response(
            {
                "message": "Logged out."
            }
        )

        response.delete_cookie(
            REFRESH_COOKIE_NAME,
            path="/api/v1/auth/",
        )

        return response