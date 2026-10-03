from __future__ import annotations

from io import BytesIO

import qrcode

from django.core.files.base import ContentFile
from django.db import transaction

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from apps.documents.models import Document, DocumentEvent
from apps.documents.services.qr import build_verification_url


def generate_qr_image(
    document: Document,
) -> BytesIO:
    """
    Generate a QR code containing the public verification URL.
    """

    verification_url = build_verification_url(document)

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )

    qr.add_data(verification_url)
    qr.make(fit=True)

    image = qr.make_image(
        fill_color="black",
        back_color="white",
    )

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)

    return buffer


def get_member_display_name(document: Document) -> str:
    """
    Get the member/contributor name.

    This intentionally keeps the lookup defensive because
    the exact Profile/User fields may evolve.
    """

    membership = document.membership
    user = membership.user

    # Try User first.
    full_name = ""

    if hasattr(user, "get_full_name"):
        full_name = user.get_full_name().strip()

    if full_name:
        return full_name

    # Try common profile/application sources.
    profile = getattr(user, "profile", None)

    if profile:
        for field_name in [
            "full_name",
            "name",
            "display_name",
        ]:
            value = getattr(profile, field_name, "")
            if value:
                return str(value).strip()

    application = (
        membership.member_contributor_application
    )

    if application:
        for field_name in [
            "full_name",
            "name",
            "applicant_name",
        ]:
            value = getattr(application, field_name, "")
            if value:
                return str(value).strip()

    return "War of Justice Member"


def get_designation(document: Document) -> str:
    """
    Get designation stored against the membership.
    """

    designation = (
        document.membership.designation
        or ""
    ).strip()

    if designation:
        return designation

    if document.membership.membership_type == (
        document.membership.CONTRIBUTOR
    ):
        return "Contributor"

    if document.membership.membership_type == (
        document.membership.SUBSCRIBER
    ):
        return "Subscriber"

    return "Member"


def draw_basic_header(
    pdf: canvas.Canvas,
    document: Document,
):
    """
    Temporary document header.

    This will later be replaced by the supplied
    production certificate / ID card artwork.
    """

    width, height = A4

    pdf.setFont(
        "Helvetica-Bold",
        22,
    )

    pdf.drawCentredString(
        width / 2,
        height - 80,
        "WAR OF JUSTICE",
    )

    pdf.setFont(
        "Helvetica",
        11,
    )

    pdf.drawCentredString(
        width / 2,
        height - 105,
        "Official Membership Document",
    )


def draw_document_information(
    pdf: canvas.Canvas,
    document: Document,
):
    width, height = A4

    member_name = get_member_display_name(
        document
    )

    designation = get_designation(
        document
    )

    pdf.setFont(
        "Helvetica-Bold",
        18,
    )

    pdf.drawCentredString(
        width / 2,
        height - 180,
        member_name,
    )

    pdf.setFont(
        "Helvetica",
        12,
    )

    pdf.drawCentredString(
        width / 2,
        height - 205,
        designation,
    )

    pdf.setFont(
        "Helvetica",
        10,
    )

    pdf.drawString(
        70,
        height - 260,
        f"Document No: {document.document_number}",
    )

    if document.issue_date:
        pdf.drawString(
            70,
            height - 280,
            f"Issue Date: {document.issue_date}",
        )

    if document.expiry_date:
        pdf.drawString(
            70,
            height - 300,
            f"Expiry Date: {document.expiry_date}",
        )

    pdf.drawString(
        70,
        height - 320,
        f"Document Type: "
        f"{document.get_document_type_display()}",
    )


def draw_qr_code(
    pdf: canvas.Canvas,
    document: Document,
):
    """
    Draw the verification QR code.
    """

    qr_buffer = generate_qr_image(
        document
    )

    width, height = A4

    qr_size = 100

    pdf.drawImage(
        qr_buffer,
        width - 160,
        70,
        width=qr_size,
        height=qr_size,
        preserveAspectRatio=True,
        mask="auto",
    )

    pdf.setFont(
        "Helvetica",
        8,
    )

    pdf.drawString(
        width - 190,
        55,
        "Scan to verify",
    )


def render_document_pdf(
    document: Document,
) -> bytes:
    """
    Render a document into PDF bytes.

    This is currently a clean placeholder renderer.
    The supplied official ID card/certificate artwork
    will be integrated into this renderer next.
    """

    buffer = BytesIO()

    pdf = canvas.Canvas(
        buffer,
        pagesize=A4,
    )

    draw_basic_header(
        pdf,
        document,
    )

    draw_document_information(
        pdf,
        document,
    )

    draw_qr_code(
        pdf,
        document,
    )

    pdf.showPage()
    pdf.save()

    buffer.seek(0)

    return buffer.getvalue()


@transaction.atomic
def generate_and_store_document_pdf(
    *,
    document: Document,
    actor=None,
) -> Document:
    """
    Generate a PDF and store it through Django's
    configured private storage backend.

    Since settings.py uses the private Cloudflare R2
    bucket as the default storage, this file will not
    become publicly accessible automatically.
    """

    if not document.document_number:
        raise ValueError(
            "Document must have a document number "
            "before generating its PDF."
        )

    pdf_bytes = render_document_pdf(
        document
    )

    filename = (
        f"{document.document_number}.pdf"
    )

    document.pdf_file.save(
        filename,
        ContentFile(pdf_bytes),
        save=False,
    )

    document.save(
        update_fields=[
            "pdf_file",
            "updated_at",
        ]
    )

    DocumentEvent.objects.create(
        document=document,
        actor=actor,
        event_type=DocumentEvent.REGENERATED,
        metadata={
            "document_number": (
                document.document_number
            ),
            "filename": filename,
            "template_version": (
                document.template_version
            ),
        },
    )

    return document