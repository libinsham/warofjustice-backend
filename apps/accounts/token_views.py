"""
Custom JWT login/refresh that:
1. Blocks suspended/pending accounts at login.
2. Sends the refresh token as an httpOnly, Secure, SameSite=Lax cookie
   instead of in the JSON response body — a script running on the page
   (including an XSS payload) can never read it, only the browser can
   send it back automatically. The access token still goes in the JSON
   body since the frontend needs to read it to set the Authorization
   header, and it's short-lived (15 min) so the exposure window is small.

This is what apps/frontend/src/lib/token-storage.ts on the Next.js side
already expects (it sends `withCredentials: true` and calls
POST /auth/refresh/ with no body, relying on the cookie).
"""
from django.conf import settings
from rest_framework_simplejwt.exceptions import AuthenticationFailed, InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.response import Response

from .models import User
from .serializers import UserSerializer

REFRESH_COOKIE_NAME = "newshub_refresh_token"
REFRESH_COOKIE_MAX_AGE = 60 * 60 * 24 * 7  # 7 days, matches SIMPLE_JWT REFRESH_TOKEN_LIFETIME


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        refresh_token,
        max_age=REFRESH_COOKIE_MAX_AGE,
        httponly=True,
        secure=not settings.DEBUG,  # requires HTTPS in production; plain HTTP is fine for local dev
        samesite="Lax",
        path="/api/v1/auth/",  # only sent to auth endpoints, not the whole API
    )


class NewshubTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)  # raises AuthenticationFailed on bad credentials

        if self.user.status == User.SUSPENDED:
            raise AuthenticationFailed("Your account has been suspended.")
        if self.user.status == User.PENDING:
            raise AuthenticationFailed("Your account is pending admin approval.")

        data["user"] = UserSerializer(self.user).data
        return data


class NewshubTokenObtainPairView(TokenObtainPairView):
    serializer_class = NewshubTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            refresh_token = response.data.pop("refresh", None)
            if refresh_token:
                _set_refresh_cookie(response, refresh_token)
        return response


class NewshubTokenRefreshView(TokenRefreshView):
    """
    Reads the refresh token from the httpOnly cookie instead of the
    request body — the frontend calls this with no body, just
    `withCredentials: true` so the cookie is sent automatically.
    """

    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get(REFRESH_COOKIE_NAME)
        if not refresh_token:
            return Response({"detail": "No refresh token cookie found."}, status=401)

        serializer = TokenRefreshSerializer(data={"refresh": refresh_token})
        try:
            serializer.is_valid(raise_exception=True)
        except (InvalidToken, TokenError):
            response = Response({"detail": "Refresh token is invalid or expired."}, status=401)
            response.delete_cookie(REFRESH_COOKIE_NAME, path="/api/v1/auth/")
            return response

        data = dict(serializer.validated_data)
        new_refresh = data.pop("refresh", None)  # present because ROTATE_REFRESH_TOKENS=True

        response = Response(data, status=200)
        if new_refresh:
            _set_refresh_cookie(response, new_refresh)
        return response
