"""
Password reset flow using Django's built-in token generator (same
mechanism Django's own admin password reset uses — no extra dependency).

Flow:
1. POST /auth/forgot-password/ {email} -> generates a uidb64+token pair
   and emails a link to
   {FRONTEND_URL}/reset-password?uid=<uidb64>&token=<token>
2. POST /auth/reset-password/ {uid, token, new_password} -> validates and
   sets the new password.

Always returns a generic success message on step 1 regardless of whether
the email exists, to avoid leaking which emails are registered.
"""
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import User
from .serializers import ChangePasswordSerializer, ForgotPasswordSerializer, ResetPasswordSerializer


class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        generic_response = {
            "message": "If an account exists for that email, a reset link has been sent."
        }

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(generic_response)

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        reset_url = f"{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}"

        send_mail(
            subject="Reset your War of Justice password",
            message=render_to_string(
                "accounts/password_reset_email.txt",
                {"user": user, "reset_url": reset_url},
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )

        return Response(generic_response)


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            uid = force_str(urlsafe_base64_decode(data["uid"]))
            user = User.objects.get(pk=uid)
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            return Response({"detail": "Invalid reset link."}, status=status.HTTP_400_BAD_REQUEST)

        if not default_token_generator.check_token(user, data["token"]):
            return Response({"detail": "This reset link is invalid or has expired."}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(data["new_password"])
        user.save(update_fields=["password"])
        return Response({"message": "Password has been reset. You can now log in."})


class ChangePasswordView(APIView):
    """For a logged-in user changing their own password (author/admin
    settings page) — distinct from the forgot/reset flow above, which is
    for users who are logged out and can't authenticate."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if not request.user.check_password(data["current_password"]):
            return Response({"detail": "Current password is incorrect."}, status=status.HTTP_400_BAD_REQUEST)

        request.user.set_password(data["new_password"])
        request.user.save(update_fields=["password"])
        return Response({"message": "Password changed successfully."})
