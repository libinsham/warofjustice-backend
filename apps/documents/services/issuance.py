from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.documents.models import Document, DocumentEvent, Membership
from apps.documents.services.numbering import assign_document_number


@transaction.atomic
def create_document(
    *,
    membership: Membership,
    document_type: str,
    issued_by=None,
    expiry_date=None,
) -> Document:
    """
    Create an official document for a membership.

    If an issued document of the same type already exists,
    return the existing document instead of creating a duplicate.

    If a previous version exists but is not currently issued,
    create the next version.
    """

    # ---------------------------------------------------------
    # RETURN EXISTING ISSUED DOCUMENT
    # ---------------------------------------------------------

    existing = (
        Document.objects
        .filter(
            membership=membership,
            document_type=document_type,
            status=Document.ISSUED,
        )
        .order_by("-version")
        .first()
    )

    if existing:
        return existing

    # ---------------------------------------------------------
    # DETERMINE NEXT VERSION
    # ---------------------------------------------------------

    latest = (
        Document.objects
        .filter(
            membership=membership,
            document_type=document_type,
        )
        .order_by("-version")
        .first()
    )

    version = 1

    if latest:
        version = latest.version + 1

    # ---------------------------------------------------------
    # CREATE DOCUMENT
    # ---------------------------------------------------------

    document = Document.objects.create(
        membership=membership,
        document_type=document_type,
        status=Document.DRAFT,
        version=version,
        expiry_date=(
            expiry_date
            if expiry_date is not None
            else membership.expiry_date
        ),
    )

    # ---------------------------------------------------------
    # ASSIGN OFFICIAL DOCUMENT NUMBER
    # ---------------------------------------------------------

    assign_document_number(document)

    # ---------------------------------------------------------
    # ISSUE DOCUMENT
    # ---------------------------------------------------------

    document.issue_date = timezone.localdate()
    document.issued_by = issued_by
    document.issued_at = timezone.now()
    document.status = Document.ISSUED

    document.save(
        update_fields=[
            "issue_date",
            "issued_by",
            "issued_at",
            "status",
            "updated_at",
        ]
    )

    # ---------------------------------------------------------
    # AUDIT EVENT: CREATED
    # ---------------------------------------------------------

    DocumentEvent.objects.create(
        document=document,
        actor=issued_by,
        event_type=DocumentEvent.CREATED,
        metadata={
            "document_type": document.document_type,
            "document_number": document.document_number,
            "version": document.version,
        },
    )

    # ---------------------------------------------------------
    # AUDIT EVENT: ISSUED
    # ---------------------------------------------------------

    DocumentEvent.objects.create(
        document=document,
        actor=issued_by,
        event_type=DocumentEvent.ISSUED,
        metadata={
            "document_number": document.document_number,
            "document_type": document.document_type,
            "version": document.version,
        },
    )

    return document


@transaction.atomic
def issue_membership_documents(
    *,
    membership: Membership,
    issued_by=None,
) -> dict:
    """
    Issue all official documents associated with a membership.

    MEMBER:
        - Membership ID Card
        - Membership Certificate

    CONTRIBUTOR:
        - Membership ID Card
        - Contributor Membership Certificate

    Existing issued documents are reused, so calling this
    function multiple times will not create duplicates.
    """

    documents = {}

    # =========================================================
    # 1. MEMBERSHIP ID CARD
    # =========================================================

    id_card = create_document(
        membership=membership,
        document_type=Document.ID_CARD,
        issued_by=issued_by,
    )

    documents["id_card"] = id_card

    # =========================================================
    # 2. MEMBERSHIP CERTIFICATE
    # =========================================================

    certificate = create_document(
        membership=membership,
        document_type=Document.CERTIFICATE,
        issued_by=issued_by,
    )

    documents["certificate"] = certificate

    return documents