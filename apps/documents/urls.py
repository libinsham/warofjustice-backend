from django.urls import path

from apps.documents.views import (
    AdminDocumentDetailView,
    AdminRegenerateDocumentView,
    AdminRevokeDocumentView,
    DocumentDownloadView,
    MyDocumentDetailView,
    MyDocumentsView,
    PublicDocumentVerificationView,
)


urlpatterns = [
    # ========================================================
    # AUTHENTICATED MEMBER DOCUMENTS
    # ========================================================

    path(
        "my/",
        MyDocumentsView.as_view(),
        name="my-documents",
    ),

    path(
        "my/<str:document_number>/",
        MyDocumentDetailView.as_view(),
        name="my-document-detail",
    ),

    path(
        "my/<str:document_number>/download/",
        DocumentDownloadView.as_view(),
        name="my-document-download",
    ),


    # ========================================================
    # PUBLIC VERIFICATION
    # ========================================================

    path(
        "verify/<str:document_number>/",
        PublicDocumentVerificationView.as_view(),
        name="public-document-verification",
    ),


    # ========================================================
    # ADMIN DOCUMENT MANAGEMENT
    # ========================================================

    path(
        "admin/<str:document_number>/",
        AdminDocumentDetailView.as_view(),
        name="admin-document-detail",
    ),

    path(
        "admin/<str:document_number>/regenerate/",
        AdminRegenerateDocumentView.as_view(),
        name="admin-document-regenerate",
    ),

    path(
        "admin/<str:document_number>/revoke/",
        AdminRevokeDocumentView.as_view(),
        name="admin-document-revoke",
    ),
]