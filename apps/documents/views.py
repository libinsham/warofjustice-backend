from __future__ import annotations

from django.db.models import Q
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.documents.models import Document, DocumentEvent, Membership
from apps.documents.serializers import (
    DocumentSerializer,
    MyDocumentSerializer,
    PublicDocumentVerificationSerializer,
)
from apps.documents.services.pdf import generate_and_store_document_pdf


# ============================================================
# MY DOCUMENTS
# ============================================================


class MyDocumentsView(APIView):
    """
    Return documents belonging to the currently authenticated user.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        documents = (
            Document.objects
            .select_related(
                "membership",
                "membership__user",
            )
            .filter(
                membership__user=request.user,
            )
            .order_by(
                "-created_at",
            )
        )

        serializer = MyDocumentSerializer(
            documents,
            many=True,
        )

        return Response(
            {
                "count": documents.count(),
                "results": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


# ============================================================
# MY DOCUMENT DETAIL
# ============================================================


class MyDocumentDetailView(APIView):
    """
    Return one document belonging to the authenticated user.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, document_number):
        document = get_object_or_404(
            Document.objects.select_related(
                "membership",
                "membership__user",
            ),
            document_number=document_number,
            membership__user=request.user,
        )

        serializer = MyDocumentSerializer(
            document,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )


# ============================================================
# DOCUMENT DOWNLOAD
# ============================================================


class DocumentDownloadView(APIView):
    """
    Securely download a document owned by the authenticated user.

    The actual PDF remains in private Cloudflare R2.

    Django checks ownership first and then generates a temporary
    signed storage URL.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, document_number):
        document = get_object_or_404(
            Document.objects.select_related(
                "membership",
                "membership__user",
            ),
            document_number=document_number,
            membership__user=request.user,
        )

        if document.status != Document.ISSUED:
            return Response(
                {
                    "detail": (
                        "This document is not currently available "
                        "for download."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if not document.pdf_file:
            return Response(
                {
                    "detail": (
                        "PDF has not been generated for this document."
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if (
            document.expiry_date
            and document.expiry_date < timezone.localdate()
        ):
            return Response(
                {
                    "detail": "This document has expired."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Record download event.
        DocumentEvent.objects.create(
            document=document,
            actor=request.user,
            event_type=DocumentEvent.DOWNLOADED,
            ip_address=self._get_client_ip(request),
            user_agent=request.META.get(
                "HTTP_USER_AGENT",
                "",
            ),
        )

        # django-storages generates a signed URL when
        # AWS_QUERYSTRING_AUTH=True.
        try:
            signed_url = document.pdf_file.url
        except Exception:
            return Response(
                {
                    "detail": (
                        "Unable to generate the document download URL."
                    )
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {
                "document_number": document.document_number,
                "download_url": signed_url,
            },
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def _get_client_ip(request):
        forwarded_for = request.META.get(
            "HTTP_X_FORWARDED_FOR"
        )

        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        return request.META.get(
            "REMOTE_ADDR"
        )


# ============================================================
# PUBLIC DOCUMENT VERIFICATION
# ============================================================


class PublicDocumentVerificationView(APIView):
    """
    Public QR verification endpoint.

    No authentication required.

    Only safe verification information is returned.

    This endpoint is JSON-only because the frontend
    verification page will consume this API.
    """

    permission_classes = [AllowAny]

    authentication_classes = []

    renderer_classes = [JSONRenderer]

    def get(self, request, document_number):
        document = (
            Document.objects
            .select_related(
                "membership",
                "membership__user",
                "membership__member_contributor_application",
            )
            .filter(
                document_number=document_number,
            )
            .first()
        )

        if not document:
            return Response(
                {
                    "verified": False,
                    "status": "Not Found",
                    "detail": (
                        "No document was found with this "
                        "verification number."
                    ),
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = PublicDocumentVerificationSerializer(
            document,
        )

        # Record public verification.
        DocumentEvent.objects.create(
            document=document,
            actor=None,
            event_type=DocumentEvent.PREVIEWED,
            ip_address=self._get_client_ip(request),
            user_agent=request.META.get(
                "HTTP_USER_AGENT",
                "",
            ),
        )

        return Response(
            {
                "verified": document.is_valid,
                "document": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def _get_client_ip(request):
        forwarded_for = request.META.get(
            "HTTP_X_FORWARDED_FOR"
        )

        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        return request.META.get(
            "REMOTE_ADDR"
        )


# ============================================================
# ADMIN DOCUMENT DETAIL
# ============================================================


class AdminDocumentDetailView(APIView):
    """
    Authorized document detail endpoint.

    Permission checking is intentionally kept in a dedicated
    helper so it can be aligned with your existing War of Justice
    admin permission system.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, document_number):
        self._check_admin_access(request)

        document = get_object_or_404(
            Document.objects.select_related(
                "membership",
                "membership__user",
            ),
            document_number=document_number,
        )

        serializer = DocumentSerializer(
            document,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    def _check_admin_access(self, request):
        user = request.user

        # Django superuser is always allowed.
        if user.is_superuser:
            return

        # Existing project role system.
        role = getattr(
            user,
            "role",
            None,
        )

        role_name = getattr(
            role,
            "name",
            "",
        )

        allowed_roles = {
            "SUPER_SUPER_ADMIN",
            "SUPER_ADMIN",
            "NORMAL_ADMIN",
        }

        if role_name in allowed_roles:
            return

        raise PermissionError(
            "You do not have permission to access documents."
        )


# ============================================================
# ADMIN REGENERATE DOCUMENT
# ============================================================


class AdminRegenerateDocumentView(APIView):
    """
    Regenerate the PDF for an existing document.

    This does not create a new document number.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, document_number):
        self._check_admin_access(request)

        document = get_object_or_404(
            Document.objects.select_related(
                "membership",
                "membership__user",
            ),
            document_number=document_number,
        )

        if document.status != Document.ISSUED:
            return Response(
                {
                    "detail": (
                        "Only issued documents can be regenerated."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        document = generate_and_store_document_pdf(
            document=document,
            actor=request.user,
        )

        serializer = DocumentSerializer(
            document,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    def _check_admin_access(self, request):
        user = request.user

        if user.is_superuser:
            return

        role = getattr(
            user,
            "role",
            None,
        )

        role_name = getattr(
            role,
            "name",
            "",
        )

        allowed_roles = {
            "SUPER_SUPER_ADMIN",
            "SUPER_ADMIN",
            "NORMAL_ADMIN",
        }

        if role_name in allowed_roles:
            return

        raise PermissionError(
            "You do not have permission to regenerate documents."
        )


# ============================================================
# ADMIN REVOKE DOCUMENT
# ============================================================


class AdminRevokeDocumentView(APIView):
    """
    Revoke an issued document.

    The existing QR code continues to work but verification
    will immediately show Revoked.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, document_number):
        self._check_admin_access(request)

        document = get_object_or_404(
            Document.objects.select_related(
                "membership",
                "membership__user",
            ),
            document_number=document_number,
        )

        if document.status == Document.REVOKED:
            return Response(
                {
                    "detail": "Document is already revoked."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

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
                        "A revocation reason is required."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        document.status = Document.REVOKED
        document.revoked_by = request.user
        document.revoked_at = timezone.now()
        document.revocation_reason = reason

        document.save(
            update_fields=[
                "status",
                "revoked_by",
                "revoked_at",
                "revocation_reason",
                "updated_at",
            ]
        )

        DocumentEvent.objects.create(
            document=document,
            actor=request.user,
            event_type=DocumentEvent.REVOKED,
            metadata={
                "reason": reason,
            },
            ip_address=self._get_client_ip(request),
            user_agent=request.META.get(
                "HTTP_USER_AGENT",
                "",
            ),
        )

        serializer = DocumentSerializer(
            document,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def _get_client_ip(request):
        forwarded_for = request.META.get(
            "HTTP_X_FORWARDED_FOR"
        )

        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        return request.META.get(
            "REMOTE_ADDR"
        )

    def _check_admin_access(self, request):
        user = request.user

        if user.is_superuser:
            return

        role = getattr(
            user,
            "role",
            None,
        )

        role_name = getattr(
            role,
            "name",
            "",
        )

        allowed_roles = {
            "SUPER_SUPER_ADMIN",
            "SUPER_ADMIN",
            "NORMAL_ADMIN",
        }

        if role_name in allowed_roles:
            return

        raise PermissionError(
            "You do not have permission to revoke documents."
        )