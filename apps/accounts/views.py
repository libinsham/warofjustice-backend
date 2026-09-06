from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import AuditLog

from .serializers import (
    RegisterAuthorSerializer,
    RegisterReaderSerializer,
    SubscriberRegisterSerializer,
    UpdateProfileSerializer,
    UserSerializer,
)


def issue_tokens(user):
    """Returns only the access token — the refresh token is set as an
    httpOnly cookie by the caller (see _set_refresh_cookie in token_views),
    never returned in the JSON body. Kept as a small helper since two
    endpoints (register-reader here, login in token_views) both need to
    mint a fresh token pair."""
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token)}, str(refresh)


class RegisterReaderView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        from .token_views import _set_refresh_cookie

        serializer = RegisterReaderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        access_data, refresh_token = issue_tokens(user)
        response = Response(
            {"user": UserSerializer(user).data, **access_data},
            status=status.HTTP_201_CREATED,
        )
        _set_refresh_cookie(response, refresh_token)
        return response


class SubscriberRegisterView(APIView):
    """
    Public "Subscriber" application — Account Credentials + Contact
    Information + official-channels declaration. Returns the same
    access token + user shape as other registration endpoints, plus the
    generated application_id nested under user.subscriber_application
    for the success screen.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        from .token_views import _set_refresh_cookie

        serializer = SubscriberRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        access_data, refresh_token = issue_tokens(user)
        response = Response(
            {"user": UserSerializer(user).data, **access_data},
            status=status.HTTP_201_CREATED,
        )
        _set_refresh_cookie(response, refresh_token)
        return response


class RegisterAuthorView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterAuthorSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        AuditLog.objects.create(
            actor=None,
            action="author.registered",
            target_type="User",
            target_id=str(user.id),
        )
        return Response(
            {
                "message": "Registration received. Your author account is pending admin approval.",
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        """Self-service profile update — username + Profile fields only.
        Email, role, and status changes are deliberately excluded here;
        those go through dedicated, more guarded flows (Super Admin
        endpoints for role/status; a real email-change flow with
        re-verification would be a separate addition)."""
        serializer = UpdateProfileSerializer(
            request.user, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserSerializer(request.user).data)


class LogoutView(APIView):
    """
    Blacklists the refresh token (so it can't be used again even if
    somehow leaked) and clears the httpOnly cookie. The access token
    isn't blacklisted — it's short-lived (15 min) and SimpleJWT doesn't
    blacklist access tokens by design; the meaningful "log out" action is
    invalidating the refresh token and removing it from the browser.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from rest_framework_simplejwt.tokens import RefreshToken

        from .token_views import REFRESH_COOKIE_NAME

        refresh_token = request.COOKIES.get(REFRESH_COOKIE_NAME)
        if refresh_token:
            try:
                RefreshToken(refresh_token).blacklist()
            except Exception:
                pass  # already invalid/expired — nothing more to do

        response = Response({"message": "Logged out."})
        response.delete_cookie(REFRESH_COOKIE_NAME, path="/api/v1/auth/")
        return response
