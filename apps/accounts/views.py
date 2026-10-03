
from django.db import transaction
from django.utils import timezone

from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import AuditLog

from apps.documents.services.membership import (
    create_or_get_membership,
)
from apps.documents.services.issuance import (
    issue_membership_documents,
)

from .models import (
    MemberContributorApplication,
    Role,
    SubscriberApplication,
    User,
)

from .serializers import (
    AdminSubscriberApplicationSerializer,
    MemberContributorApplicationSerializer,
    MemberContributorRegisterSerializer,
    RegisterAuthorSerializer,
    RegisterReaderSerializer,
    SubscriberRegisterSerializer,
    UpdateProfileSerializer,
    UserSerializer,
)


# =========================================================
# ROLE AND PERMISSION HELPERS
# =========================================================

ADMIN_ROLES = {
    "admin",
    "super_admin",
    "super_super_admin",
    "editor",
    "bureau_chief",
}


def get_role_name(user):
    """Return the authenticated user's role name."""
    return getattr(
        getattr(user, "role", None),
        "name",
        "",
    )


def has_admin_access(user):
    """Check access to existing administrative APIs."""
    return bool(
        user
        and user.is_authenticated
        and get_role_name(user) in ADMIN_ROLES
    )


def admin_access_denied(message):
    return Response(
        {"detail": message},
        status=status.HTTP_403_FORBIDDEN,
    )


# =========================================================
# TOKEN HELPER
# =========================================================

def issue_tokens(user):
    """Create a JWT access and refresh token pair."""
    refresh = RefreshToken.for_user(user)

    return {
        "access": str(refresh.access_token),
    }, str(refresh)


# =========================================================
# READER REGISTRATION
# =========================================================

class RegisterReaderView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        from .token_views import _set_refresh_cookie

        serializer = RegisterReaderSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        access_data, refresh_token = issue_tokens(user)

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

        _set_refresh_cookie(response, refresh_token)
        return response


# =========================================================
# SUBSCRIBER REGISTRATION
# =========================================================

class SubscriberRegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        from .token_views import _set_refresh_cookie

        serializer = SubscriberRegisterSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        access_data, refresh_token = issue_tokens(user)

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

        _set_refresh_cookie(response, refresh_token)
        return response


# =========================================================
# MEMBER AND CONTRIBUTOR REGISTRATION
# =========================================================

class MemberContributorRegisterView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = MemberContributorRegisterSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)
        application = serializer.save()

        application_data = MemberContributorApplicationSerializer(
            application,
            context={"request": request},
        ).data

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
# SUBSCRIBER APPLICATIONS
# ADMIN AND SUPER ADMIN LIST
# =========================================================

class SubscriberApplicationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not has_admin_access(request.user):
            return admin_access_denied(
                "You do not have permission to view "
                "subscriber applications."
            )

        applications = (
            SubscriberApplication.objects
            .select_related("user", "user__profile")
            .all()
            .order_by("-created_at")
        )

        serializer = AdminSubscriberApplicationSerializer(
            applications,
            many=True,
            context={"request": request},
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )


# =========================================================
# MEMBER AND CONTRIBUTOR APPLICATIONS
# ADMIN AND SUPER ADMIN LIST
# =========================================================

class MemberContributorApplicationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not has_admin_access(request.user):
            return admin_access_denied(
                "You do not have permission to view applications."
            )

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

        serializer = MemberContributorApplicationSerializer(
            applications,
            many=True,
            context={"request": request},
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )


# =========================================================
# APPROVE MEMBER AND CONTRIBUTOR APPLICATION
# =========================================================

class MemberContributorApplicationApproveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not has_admin_access(request.user):
            return admin_access_denied(
                "You do not have permission to approve applications."
            )

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

        if application.status != MemberContributorApplication.PENDING:
            return Response(
                {
                    "detail": (
                        "Only pending applications can be approved."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        target_role, _ = Role.objects.get_or_create(
            name=Role.AUTHOR,
            defaults={
                "label": "Author / Member & Contributor",
                "description": (
                    "Member & Contributor publishing access."
                ),
            },
        )

        with transaction.atomic():
            application.status = MemberContributorApplication.APPROVED
            application.approved_role = None
            application.approved_by = request.user
            application.approved_at = timezone.now()

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

            user = application.user
            user.role = target_role
            user.status = User.ACTIVE
            user.save(
                update_fields=[
                    "role",
                    "status",
                ]
            )

            # =================================================
            # CREATE / GET OFFICIAL MEMBERSHIP
            # =================================================
            #
            # AUTHOR remains the user's account role.
            # Membership is the official membership record.
            #
            # Contributor applications become CONTRIBUTOR
            # memberships. All other Member & Contributor
            # categories become MEMBER memberships.
            #
            membership_type = (
                "contributor"
                if application.membership_category
                == MemberContributorApplication.CATEGORY_CONTRIBUTOR
                else "member"
            )

            membership = create_or_get_membership(
                user=user,
                application=application,
                membership_type=membership_type,
                approved_by=request.user,
                designation="",
            )

            # =================================================
            # ISSUE OFFICIAL MEMBERSHIP DOCUMENTS
            # =================================================
            #
            # Every approved membership receives:
            #   1. Membership ID Card
            #   2. Membership Certificate
            #
            # The existing issuance service prevents duplicate
            # issued documents for the same membership.
            documents = issue_membership_documents(
                membership=membership,
                issued_by=request.user,
            )

            AuditLog.objects.create(
                actor=request.user,
                action="member_contributor.approved",
                target_type="MemberContributorApplication",
                target_id=str(application.id),
            )

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
# MEMBER AND CONTRIBUTOR APPLICATION DOCUMENTS
# =========================================================

class MemberContributorApplicationDocumentView(APIView):
    permission_classes = [IsAuthenticated]

    DOCUMENT_FIELDS = {
        "selfie": "selfie_photo",
        "identity-proof": "identity_proof",
        "aadhaar": "aadhaar_card",
        "pan": "pan_card",
        "supporting": "supporting_documents",
    }

    def get(self, request, pk, document_type):
        if not has_admin_access(request.user):
            return admin_access_denied(
                "You do not have permission to view application documents."
            )

        field_name = self.DOCUMENT_FIELDS.get(
            str(document_type).strip().lower()
        )

        if not field_name:
            return Response(
                {"detail": "Invalid document type."},
                status=status.HTTP_400_BAD_REQUEST,
            )

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

        document = getattr(application, field_name, None)

        if not document:
            return Response(
                {"detail": "This document has not been uploaded."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            return Response(
                {
                    "url": document.url,
                    "document_type": document_type,
                    "application_id": application.application_id,
                },
                status=status.HTTP_200_OK,
            )
        except Exception:
            return Response(
                {"detail": "Unable to retrieve this document."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# =========================================================
# REJECT MEMBER AND CONTRIBUTOR APPLICATION
# =========================================================

class MemberContributorApplicationRejectView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not has_admin_access(request.user):
            return admin_access_denied(
                "You do not have permission to reject applications."
            )

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

        if application.status != MemberContributorApplication.PENDING:
            return Response(
                {
                    "detail": (
                        "Only pending applications can be rejected."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        reason = str(request.data.get("reason", "")).strip()

        if not reason:
            return Response(
                {"detail": "A rejection reason is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            application.status = MemberContributorApplication.REJECTED
            application.approved_role = None
            application.rejection_reason = reason
            application.rejected_by = request.user
            application.rejected_at = timezone.now()

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

            AuditLog.objects.create(
                actor=request.user,
                action="member_contributor.rejected",
                target_type="MemberContributorApplication",
                target_id=str(application.id),
            )

        serializer = MemberContributorApplicationSerializer(
            application,
            context={"request": request},
        )

        return Response(
            {
                "message": "Application rejected successfully.",
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
                context={"request": request},
            ).data
        )

    def patch(self, request):
        serializer = UpdateProfileSerializer(
            request.user,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            UserSerializer(
                request.user,
                context={"request": request},
            ).data
        )


# =========================================================
# LOGOUT
# =========================================================

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from .token_views import REFRESH_COOKIE_NAME

        refresh_token = request.COOKIES.get(
            REFRESH_COOKIE_NAME
        )

        if refresh_token:
            try:
                RefreshToken(refresh_token).blacklist()
            except Exception:
                # The token may already be expired, invalid,
                # or blacklisted.
                pass

        response = Response({"message": "Logged out."})

        response.delete_cookie(
            REFRESH_COOKIE_NAME,
            path="/api/v1/auth/",
        )

        return response