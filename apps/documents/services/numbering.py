"""
War of Justice document numbering service.

This module generates official identifiers for:
    - Memberships
    - Membership ID Cards
    - Contributor Membership Certificates

Important:
    The database primary key is used as the collision-safe sequence
    component. We do NOT use Model.objects.count() because concurrent
    requests could generate duplicate numbers.

Examples:
    Membership:
        WOJ-2026-00001

    ID Card:
        WOJ-ID-2026-00001

    Certificate:
        WOJ-CERT-2026-00001
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.documents.models import Document, Membership


# ============================================================
# CONFIGURATION
# ============================================================

ORGANISATION_PREFIX = "WOJ"

MEMBERSHIP_PREFIX = "WOJ"
ID_CARD_PREFIX = "WOJ-ID"
CERTIFICATE_PREFIX = "WOJ-CERT"

NUMBER_WIDTH = 5


# ============================================================
# INTERNAL HELPERS
# ============================================================


def _year(value: date | None = None) -> int:
    """
    Return the year used in an official document number.

    If no date is supplied, the current local date is used.
    """

    if value is None:
        return date.today().year

    return value.year


def _sequence(value: int) -> str:
    """
    Convert a database integer into a fixed-width sequence.

    Example:
        1      -> 00001
        25     -> 00025
        123    -> 00123
        12345  -> 12345
    """

    if value < 1:
        raise ValueError("Sequence value must be greater than zero.")

    return str(value).zfill(NUMBER_WIDTH)


# ============================================================
# MEMBERSHIP NUMBER
# ============================================================


def generate_membership_number(
    membership: "Membership",
) -> str:
    """
    Generate the official membership ID.

    Example:
        WOJ-2026-00001

    IMPORTANT:
        The Membership must already have been saved so that
        membership.pk exists.
    """

    if not membership.pk:
        raise ValueError(
            "Membership must be saved before generating "
            "its membership number."
        )

    year = _year(membership.issue_date)

    return (
        f"{MEMBERSHIP_PREFIX}-"
        f"{year}-"
        f"{_sequence(membership.pk)}"
    )


# ============================================================
# ID CARD NUMBER
# ============================================================


def generate_id_card_number(
    document: "Document",
) -> str:
    """
    Generate the official ID card number.

    Example:
        WOJ-ID-2026-00001

    IMPORTANT:
        The Document must already have been saved so that
        document.pk exists.
    """

    if not document.pk:
        raise ValueError(
            "Document must be saved before generating "
            "its ID card number."
        )

    year = _year(document.issue_date)

    return (
        f"{ID_CARD_PREFIX}-"
        f"{year}-"
        f"{_sequence(document.pk)}"
    )


# ============================================================
# CERTIFICATE NUMBER
# ============================================================


def generate_certificate_number(
    document: "Document",
) -> str:
    """
    Generate the official contributor certificate number.

    Example:
        WOJ-CERT-2026-00001

    IMPORTANT:
        The Document must already have been saved so that
        document.pk exists.
    """

    if not document.pk:
        raise ValueError(
            "Document must be saved before generating "
            "its certificate number."
        )

    year = _year(document.issue_date)

    return (
        f"{CERTIFICATE_PREFIX}-"
        f"{year}-"
        f"{_sequence(document.pk)}"
    )


# ============================================================
# GENERIC DOCUMENT NUMBER
# ============================================================


def generate_document_number(
    document: "Document",
) -> str:
    """
    Generate the correct official number based on document type.
    """

    from apps.documents.models import Document

    if document.document_type == Document.ID_CARD:
        return generate_id_card_number(document)

    if document.document_type == Document.CERTIFICATE:
        return generate_certificate_number(document)

    raise ValueError(
        f"Unsupported document type: {document.document_type}"
    )


# ============================================================
# ASSIGN MEMBERSHIP NUMBER
# ============================================================


def assign_membership_number(
    membership: "Membership",
) -> str:
    """
    Generate and save the membership number.

    The membership must already exist in the database.
    """

    if membership.membership_id:
        return membership.membership_id

    membership_number = generate_membership_number(membership)

    membership.membership_id = membership_number

    membership.save(
        update_fields=[
            "membership_id",
            "updated_at",
        ]
    )

    return membership_number


# ============================================================
# ASSIGN DOCUMENT NUMBER
# ============================================================


def assign_document_number(
    document: "Document",
) -> str:
    """
    Generate and save the document number.

    Existing document numbers are preserved.

    This is important for preventing accidental changes to
    already-issued official documents.
    """

    if document.document_number:
        return document.document_number

    document_number = generate_document_number(document)

    document.document_number = document_number

    document.save(
        update_fields=[
            "document_number",
            "updated_at",
        ]
    )

    return document_number