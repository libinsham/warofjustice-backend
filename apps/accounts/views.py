from django.db import transaction
from django.utils import timezone

from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import AuditLog

from .models import (
    MemberContributorApplication,
    Role,
    User,
)

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
                    context={
                        "request": request,
                    },
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
                    context={
                        "request": request,
                    },
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
# MEMBER & CONTRIBUTOR APPLICATIONS
# ADMIN LIST
# =========================================================

class MemberContributorApplicationListView(APIView):
    """
    Returns real Member & Contributor applications
    for the Admin dashboard.

    GET:
        /api/v1/auth/member-contributor-applications/
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        # -----------------------------------------------------
        # Check administrator access
        # -----------------------------------------------------

        role_name = getattr(
            getattr(
                request.user,
                "role",
                None,
            ),
            "name",
            "",
        )

        allowed_roles = {
            "admin",
            "super_admin",
            "editor",
            "bureau_chief",
        }

        if role_name not in allowed_roles:
            return Response(
                {
                    "detail": (
                        "You do not have permission "
                        "to view applications."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # -----------------------------------------------------
        # Get applications
        # -----------------------------------------------------

        applications = (
            MemberContributorApplication.objects
            .select_related(
                "user",
                "approved_by",
                "rejected_by",
            )
            .all()
            .order_by("-created_at")
        )

        # -----------------------------------------------------
        # Serialize
        # -----------------------------------------------------

        serializer = MemberContributorApplicationSerializer(
            applications,
            many=True,
            context={
                "request": request,
            },
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )


# =========================================================
# MEMBER & CONTRIBUTOR APPLICATION
# APPROVE
# =========================================================

class MemberContributorApplicationApproveView(APIView):
    """
    Approve a pending Member & Contributor application.

    There is only ONE access level for approved Member & Contributor
    accounts in this project: the existing AUTHOR role.

    POST:
        /api/v1/auth/member-contributor-applications/<id>/approve/
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        # -----------------------------------------------------
        # Check administrator access
        # -----------------------------------------------------
        role_name = getattr(
            getattr(request.user, "role", None),
            "name",
            "",
        )

        allowed_roles = {
            "admin",
            "super_admin",
            "editor",
            "bureau_chief",
        }

        if role_name not in allowed_roles:
            return Response(
                {
                    "detail": (
                        "You do not have permission "
                        "to approve applications."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # -----------------------------------------------------
        # Get application
        # -----------------------------------------------------
        try:
            application = (
                MemberContributorApplication.objects
                .select_related("user", "user__role")
                .get(pk=pk)
            )
        except MemberContributorApplication.DoesNotExist:
            return Response(
                {"detail": "Application not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # -----------------------------------------------------
        # Only pending applications
        # -----------------------------------------------------
        if application.status != MemberContributorApplication.PENDING:
            return Response(
                {
                    "detail": (
                        "Only pending applications "
                        "can be approved."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------------------------------
        # Use the existing AUTHOR role.
        # No separate member/contributor account roles.
        # -----------------------------------------------------
        target_role, _ = Role.objects.get_or_create(
            name=Role.AUTHOR,
            defaults={
                "label": "Author / Member & Contributor",
                "description": (
                    "Member & Contributor publishing access."
                ),
            },
        )

        # -----------------------------------------------------
        # Atomic approval
        # -----------------------------------------------------
        with transaction.atomic():
            application.status = (
                MemberContributorApplication.APPROVED
            )

            # Kept for backwards compatibility with the current
            # database field. It is NOT used as a separate account
            # permission/access role.
            application.approved_role = None

            application.approved_by = request.user
            application.approved_at = timezone.now()

            # Clear rejection information
            application.rejection_reason = ""
            application.rejected_by = None
            application.rejected_at = None

            application.save(
                update_fields=[
                    "status",
                    "approved_role",
                    "approved_by",
                    "approved_at",
                    "rejection_reason",
                    "rejected_by",
                    "rejected_at",
                    "updated_at",
                ]
            )

            # -------------------------------------------------
            # Activate user + assign shared AUTHOR access
            # -------------------------------------------------
            user = application.user
            user.role = target_role
            user.status = User.ACTIVE

            user.save(
                update_fields=[
                    "role",
                    "status",
                ]
            )

            # -------------------------------------------------
            # Audit
            # -------------------------------------------------
            AuditLog.objects.create(
                actor=request.user,
                action="member_contributor.approved",
                target_type="MemberContributorApplication",
                target_id=str(application.id),
            )

        # -----------------------------------------------------
        # Return updated application
        # -----------------------------------------------------
        serializer = MemberContributorApplicationSerializer(
            application,
            context={"request": request},
        )

        return Response(
            {
                "message": (
                    "Member & Contributor application "
                    "approved successfully."
                ),
                "application": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# MEMBER & CONTRIBUTOR APPLICATION
# DOCUMENT VIEW
# =========================================================

class MemberContributorApplicationDocumentView(APIView):
    """
    Return the stored URL for a private application document
    after checking that the requester has admin-level access.

    GET:
        /api/v1/auth/member-contributor-applications/<id>/document/<document_type>/

    Supported document_type values:
        selfie
        identity-proof
        aadhaar
        pan
        supporting
    """

    permission_classes = [IsAuthenticated]

    DOCUMENT_FIELDS = {
        "selfie": "selfie_photo",
        "identity-proof": "identity_proof",
        "aadhaar": "aadhaar_card",
        "pan": "pan_card",
        "supporting": "supporting_documents",
    }

    def get(self, request, pk, document_type):
        # -----------------------------------------------------
        # Check administrator access
        # -----------------------------------------------------
        role_name = getattr(
            getattr(request.user, "role", None),
            "name",
            "",
        )

        allowed_roles = {
            "admin",
            "super_admin",
            "editor",
            "bureau_chief",
        }

        if role_name not in allowed_roles:
            return Response(
                {
                    "detail": (
                        "You do not have permission "
                        "to view application documents."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # -----------------------------------------------------
        # Validate document type
        # -----------------------------------------------------
        field_name = self.DOCUMENT_FIELDS.get(
            str(document_type).strip().lower()
        )

        if not field_name:
            return Response(
                {
                    "detail": (
                        "Invalid document type."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------------------------------
        # Get application
        # -----------------------------------------------------
        try:
            application = (
                MemberContributorApplication.objects
                .select_related("user")
                .get(pk=pk)
            )
        except MemberContributorApplication.DoesNotExist:
            return Response(
                {"detail": "Application not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # -----------------------------------------------------
        # Get document
        # -----------------------------------------------------
        try:
            document = getattr(
                application,
                field_name,
                None,
            )

            if not document:
                return Response(
                    {
                        "detail": (
                            "This document has not been uploaded."
                        )
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            url = document.url

            return Response(
                {
                    "url": url,
                    "document_type": document_type,
                    "application_id": (
                        application.application_id
                    ),
                },
                status=status.HTTP_200_OK,
            )

        except Exception:
            return Response(
                {
                    "detail": (
                        "Unable to retrieve this document."
                    )
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class MemberContributorApplicationRejectView(APIView):
    """
    Reject a pending Member & Contributor application.

    POST:
        /api/v1/auth/member-contributor-applications/<id>/reject/

    JSON:
        {
            "reason": "Documents could not be verified."
        }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        # -----------------------------------------------------
        # Check administrator access
        # -----------------------------------------------------

        role_name = getattr(
            getattr(
                request.user,
                "role",
                None,
            ),
            "name",
            "",
        )

        allowed_roles = {
            "admin",
            "super_admin",
            "editor",
            "bureau_chief",
        }

        if role_name not in allowed_roles:
            return Response(
                {
                    "detail": (
                        "You do not have permission "
                        "to reject applications."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # -----------------------------------------------------
        # Get application
        # -----------------------------------------------------

        try:
            application = (
                MemberContributorApplication.objects
                .select_related(
                    "user",
                    "user__role",
                )
                .get(pk=pk)
            )

        except MemberContributorApplication.DoesNotExist:
            return Response(
                {
                    "detail": "Application not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # -----------------------------------------------------
        # Only pending applications
        # -----------------------------------------------------

        if application.status != (
            MemberContributorApplication.PENDING
        ):
            return Response(
                {
                    "detail": (
                        "Only pending applications "
                        "can be rejected."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------------------------------
        # Rejection reason
        # -----------------------------------------------------

        reason = str(
            request.data.get(
                "reason",
                "",
            )
        ).strip()

        if not reason:
            return Response(
                {
                    "detail": (
                        "A rejection reason is required."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------------------------------
        # Atomic rejection
        # -----------------------------------------------------

        with transaction.atomic():

            application.status = (
                MemberContributorApplication.REJECTED
            )

            application.approved_role = None

            application.rejection_reason = reason

            application.rejected_by = (
                request.user
            )

            application.rejected_at = (
                timezone.now()
            )

            # Clear approval information
            application.approved_by = None
            application.approved_at = None

            application.save(
                update_fields=[
                    "status",
                    "approved_role",
                    "rejection_reason",
                    "rejected_by",
                    "rejected_at",
                    "approved_by",
                    "approved_at",
                    "updated_at",
                ]
            )

            # -------------------------------------------------
            # Audit
            # -------------------------------------------------

            AuditLog.objects.create(
                actor=request.user,
                action="member_contributor.rejected",
                target_type=(
                    "MemberContributorApplication"
                ),
                target_id=str(
                    application.id
                ),
            )

        # -----------------------------------------------------
        # Return updated application
        # -----------------------------------------------------

        serializer = (
            MemberContributorApplicationSerializer(
                application,
                context={
                    "request": request,
                },
            )
        )

        return Response(
            {
                "message": (
                    "Application rejected successfully."
                ),
                "application": serializer.data,
            },
            status=status.HTTP_200_OK,
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
            target_id=str(
                user.id
            ),
        )

        return Response(
            {
                "message": (
                    "Registration received. Your author "
                    "account is pending admin approval."
                ),
                "user": UserSerializer(
                    user,
                    context={
                        "request": request,
                    },
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