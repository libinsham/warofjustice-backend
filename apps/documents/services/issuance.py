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

    Existing issued document is returned instead of creating
    a duplicate.
    """

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

    document = Document.objects.create(
        membership=membership,
        document_type=document_type,
        status=Document.DRAFT,
        version=version,
        expiry_date=expiry_date or membership.expiry_date,
    )

    assign_document_number(document)

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

    DocumentEvent.objects.create(
        document=document,
        actor=issued_by,
        event_type=DocumentEvent.CREATED,
        metadata={
            "document_type": document.document_type,
            "version": document.version,
        },
    )

    DocumentEvent.objects.create(
        document=document,
        actor=issued_by,
        event_type=DocumentEvent.ISSUED,
        metadata={
            "document_number": document.document_number,
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
    Issue the official documents associated with a membership.

    Every membership gets an ID card.

    Contributor memberships additionally receive
    a Contributor Membership Certificate.
    """

    documents = {}

    id_card = create_document(
        membership=membership,
        document_type=Document.ID_CARD,
        issued_by=issued_by,
    )

    documents["id_card"] = id_card

    if membership.membership_type == Membership.CONTRIBUTOR:

        certificate = create_document(
            membership=membership,
            document_type=Document.CERTIFICATE,
            issued_by=issued_by,
        )

        documents["certificate"] = certificate

    return documents