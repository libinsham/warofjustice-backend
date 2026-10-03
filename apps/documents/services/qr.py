"""
War of Justice QR verification service.

Each official document receives its own verification token.

The QR code does NOT contain private member information.

Example:

    https://warofjustice.news/verify/WOJ-CERT-2026-00001

The public verification page uses the document number to
retrieve the document's current status from Django.
"""

from __future__ import annotations

from urllib.parse import quote

from django.conf import settings

from apps.documents.models import Document


# ============================================================
# VERIFICATION URL
# ============================================================


def get_verification_base_url() -> str:
    """
    Return the public War of Justice verification base URL.

    Production:
        https://warofjustice.news/verify

    Development can override this through:

        DOCUMENT_VERIFICATION_BASE_URL
    """

    base_url = getattr(
        settings,
        "DOCUMENT_VERIFICATION_BASE_URL",
        "https://warofjustice.news/verify",
    )

    return base_url.rstrip("/")


def build_verification_url(
    document: Document,
) -> str:
    """
    Build the public verification URL for a document.

    Example:

        https://warofjustice.news/verify/WOJ-CERT-2026-00001

    The document number is URL encoded for safety.
    """

    if not document.document_number:
        raise ValueError(
            "Cannot create a verification URL before the "
            "document has a document number."
        )

    document_number = quote(
        document.document_number,
        safe="",
    )

    return (
        f"{get_verification_base_url()}/"
        f"{document_number}"
    )


# ============================================================
# TOKEN
# ============================================================


def get_verification_token(
    document: Document,
) -> str:
    """
    Return the unique verification token assigned to a document.

    The token is generated automatically by the Document model
    using UUID4.

    It is not exposed in the QR URL in this architecture.
    """

    if not document.verification_token:
        raise ValueError(
            "Document does not have a verification token."
        )

    return str(document.verification_token)


# ============================================================
# QR PAYLOAD
# ============================================================


def get_qr_payload(
    document: Document,
) -> str:
    """
    Return the exact data that should be encoded into the QR code.

    The QR contains only the public verification URL.

    It does NOT contain:
        - email
        - phone number
        - address
        - photograph
        - password
        - private application information
    """

    return build_verification_url(document)


# ============================================================
# VERIFICATION INFORMATION
# ============================================================


def get_verification_data(
    document: Document,
) -> dict:
    """
    Return safe information required by the QR/PDF generation layer.

    This data is intended for document generation.

    Private account information is deliberately excluded.
    """

    return {
        "document_number": document.document_number,
        "document_type": document.document_type,
        "verification_url": build_verification_url(document),
        "verification_token": get_verification_token(document),
        "status": document.status,
    }