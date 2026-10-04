from __future__ import annotations

from io import BytesIO
from pathlib import Path
import html
import re

import qrcode
from PIL import Image, ImageOps

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction

from pypdf import PdfReader, PdfWriter
from reportlab.graphics import renderPDF
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from svglib.svglib import svg2rlg

from apps.documents.models import Document, DocumentEvent
from apps.documents.services.qr import build_verification_url


# =============================================================================
# MASTER TEMPLATES
# =============================================================================

# Required files:
#   apps/documents/templates/id-card.svg
#   apps/documents/templates/certificate.pdf
#
# The supplied ID-card.svg is a 180 x 60 mm artboard containing both CR80 sides.
# The certificate master is the supplied one-page PDF artwork.

ID_CARD_TEMPLATE_SVG = (
    Path(settings.BASE_DIR)
    / "apps"
    / "documents"
    / "templates"
    / "id_card"
    / "id-card.svg"
)

CERTIFICATE_TEMPLATE_PDF = (
    Path(settings.BASE_DIR)
    / "apps"
    / "documents"
    / "templates"
    / "certificate"
    / "publication-approval.pdf"
)


# =============================================================================
# ID CARD SVG GEOMETRY
# =============================================================================

CARD_WIDTH_MM = 85.6
CARD_HEIGHT_MM = 54.0
MASTER_WIDTH_MM = 180.0
MASTER_HEIGHT_MM = 60.0

FRONT_VIEWBOX = "2 3 85.6 54"
BACK_VIEWBOX = "92.4 3 85.6 54"

# Dynamic overlay positions are based on the original SVG artboard.
# Coordinates use the SVG top-origin coordinate system.
PHOTO_X_MM = 7.0
PHOTO_Y_MM = 18.0
PHOTO_W_MM = 19.0
PHOTO_H_MM = 25.0

QR_X_MM = 160.8
QR_Y_MM = 17.2
QR_W_MM = 12.3
QR_H_MM = 12.3

# These are retained as documented template coordinates. The supplied SVG already
# contains sample text, so the renderer replaces that text directly in the SVG.
ID_X_MM = 30.0
ID_Y_MM = 25.3
NAME_X_MM = 30.0
NAME_Y_MM = 34.0
MEMBERSHIP_X_MM = 30.0
MEMBERSHIP_Y_MM = 42.5
VALID_X_MM = 20.5
VALID_Y_MM = 51.5

EMAIL_X_MM = 109.0
EMAIL_Y_MM = 22.5
STATUS_X_MM = 109.0
STATUS_Y_MM = 27.2
SUPPORT_X_MM = 109.0
SUPPORT_Y_MM = 39.0
PHONE_X_MM = 109.0
PHONE_Y_MM = 43.8
BILLING_X_MM = 109.0
BILLING_Y_MM = 48.5

ID_FONT_SIZE_PT = 4.2 * mm
NAME_FONT_SIZE_PT = 2.75 * mm
MEMBERSHIP_FONT_SIZE_PT = 2.4 * mm
VALID_FONT_SIZE_PT = 1.65 * mm
BACK_TEXT_FONT_SIZE_PT = 2.0 * mm
STATUS_FONT_SIZE_PT = 2.0 * mm

# Sample text contained in the supplied SVG artwork.
PLACEHOLDER_MEMBER_ID = "WOJ-2026-00003"
PLACEHOLDER_NAME = "WARRIOR JUSTICE26"
PLACEHOLDER_MEMBERSHIP = "GOLD ELITE • MONTHLY"
PLACEHOLDER_VALID_THROUGH = "31 DEC 2026"
PLACEHOLDER_EMAIL = "user.warrior26@email.com"
PLACEHOLDER_STATUS = "Verified"
PLACEHOLDER_SUPPORT_EMAIL = "support@warofjustice.com"
PLACEHOLDER_PHONE = "+1 (800) 555-0199"
PLACEHOLDER_BILLING_EMAIL = "billing@warofjustice.com"


# =============================================================================
# CERTIFICATE MASTER GEOMETRY
# =============================================================================

# Supplied certificate master page is 1524 x 1032 points.
CERTIFICATE_PAGE_WIDTH = 1524.0
CERTIFICATE_PAGE_HEIGHT = 1032.0

CERT_REFERENCE_X = 190.0
CERT_REFERENCE_Y = 790.0
CERT_DATE_X = 920.0
CERT_DATE_Y = 790.0
CERT_TO_X = 190.0
CERT_TO_Y = 720.0
CERT_SUBJECT_X = 190.0
CERT_SUBJECT_Y = 680.0
CERT_NAME_X = 190.0
CERT_NAME_Y = 540.0
CERT_NEWS_TITLE_X = 300.0
CERT_NEWS_TITLE_Y = 515.0
CERT_AUTHORIZED_X = 985.0
CERT_AUTHORIZED_Y = 555.0
CERT_QR_X = 1030.0
CERT_QR_Y = 355.0
CERT_QR_SIZE = 75.0


# =============================================================================
# COMMON DATA HELPERS
# =============================================================================


def generate_qr_image(document: Document) -> BytesIO:
    """Generate a QR image containing the public verification URL."""
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
    """Resolve member/contributor name defensively."""
    membership = document.membership
    user = membership.user

    if hasattr(user, "get_full_name"):
        full_name = user.get_full_name().strip()
        if full_name:
            return full_name

    profile = getattr(user, "profile", None)
    if profile:
        for field_name in ("full_name", "name", "display_name"):
            value = getattr(profile, field_name, "")
            if value:
                return str(value).strip()

    try:
        application = membership.member_contributor_application
    except Exception:
        application = None

    if application:
        for field_name in ("full_name", "name", "applicant_name"):
            value = getattr(application, field_name, "")
            if value:
                return str(value).strip()

    return "War of Justice Member"


def get_designation(document: Document) -> str:
    """Return the membership designation/category."""
    designation = (document.membership.designation or "").strip()
    if designation:
        return designation

    membership_type = document.membership.membership_type
    if membership_type == document.membership.CONTRIBUTOR:
        return "Contributor"
    if membership_type == document.membership.SUBSCRIBER:
        return "Subscriber"
    return "Member"


def get_membership_id(document: Document) -> str:
    """Return the official membership ID shown on the card."""
    membership_id = (document.membership.membership_id or "").strip()
    if membership_id:
        return membership_id

    return document.document_number.replace("WOJ-ID-", "WOJ-")


def get_membership_label(document: Document) -> str:
    """Return a compact membership type label."""
    try:
        label = document.membership.get_membership_type_display()
    except Exception:
        label = get_designation(document)

    return str(label).upper()


def format_card_date(value) -> str:
    if not value:
        return "NO EXPIRY"
    return value.strftime("%d %b %Y").upper()


def get_member_phone(document: Document) -> str:
    """Resolve a phone/mobile field from profile/user/application."""
    user = document.membership.user
    profile = getattr(user, "profile", None)

    for source in (profile, user):
        if not source:
            continue
        for field_name in (
            "phone",
            "mobile",
            "phone_number",
            "mobile_number",
        ):
            value = getattr(source, field_name, "")
            if value:
                return str(value).strip()

    try:
        application = document.membership.member_contributor_application
    except Exception:
        application = None

    if application:
        for field_name in (
            "phone",
            "mobile",
            "phone_number",
            "mobile_number",
        ):
            value = getattr(application, field_name, "")
            if value:
                return str(value).strip()

    return "—"


def get_support_email() -> str:
    return getattr(
        settings,
        "DOCUMENT_SUPPORT_EMAIL",
        "support@warofjustice.news",
    )


def get_billing_email() -> str:
    return getattr(
        settings,
        "DOCUMENT_BILLING_EMAIL",
        get_support_email(),
    )


def get_member_photo_bytes(document: Document) -> bytes | None:
    """Read the member selfie/photo from configured Django storage."""
    try:
        application = document.membership.member_contributor_application
    except Exception:
        application = None

    if not application:
        return None

    selfie = getattr(application, "selfie_photo", None)
    if not selfie:
        return None

    try:
        with selfie.open("rb") as fh:
            data = fh.read()
    except Exception:
        return None

    return data or None


def prepare_member_photo(document: Document) -> BytesIO | None:
    """Crop the selfie to the ID-card photo aspect ratio."""
    raw = get_member_photo_bytes(document)
    if not raw:
        return None

    try:
        image = Image.open(BytesIO(raw)).convert("RGB")
        fitted = ImageOps.fit(
            image,
            (760, 1000),
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )
        output = BytesIO()
        fitted.save(output, format="JPEG", quality=92)
        output.seek(0)
        return output
    except Exception:
        return None


# =============================================================================
# MASTER PDF HELPERS
# =============================================================================


def _ensure_template(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Document template not found: {path}")


def _read_master(path: Path) -> PdfReader:
    _ensure_template(path)
    return PdfReader(str(path))


def _make_overlay(
    width: float,
    height: float,
    draw_callback,
) -> bytes:
    """Create a transparent ReportLab overlay PDF."""
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=(width, height))
    draw_callback(pdf)
    pdf.showPage()
    pdf.save()
    output.seek(0)
    return output.getvalue()


def _merge_overlay(master_page, overlay_bytes: bytes):
    overlay_page = PdfReader(BytesIO(overlay_bytes)).pages[0]
    master_page.merge_page(overlay_page)
    return master_page


# =============================================================================
# ID CARD SVG RENDERER
# =============================================================================


def _escape_svg_text(value: str) -> str:
    return html.escape(str(value), quote=False)


def _replace_svg_text(svg: str, placeholder: str, value: str) -> str:
    return svg.replace(placeholder, _escape_svg_text(value))


def _prepare_id_card_svg(document: Document) -> str:
    """Load the original full 180 x 60 mm SVG and replace sample text.

    IMPORTANT: the SVG contains BOTH CR80 sides on one artboard.
    We intentionally preserve its original root/viewBox. Cropping is
    performed by translating the full master artwork onto an 85.6 x 54 mm
    PDF page. This avoids the alignment/scaling problem caused by changing
    the SVG viewBox before passing it to svglib.
    """
    if not ID_CARD_TEMPLATE_SVG.exists():
        raise FileNotFoundError(
            f"ID card SVG template not found: {ID_CARD_TEMPLATE_SVG}"
        )

    svg = ID_CARD_TEMPLATE_SVG.read_text(encoding="utf-8")
    membership = document.membership
    user = membership.user

    member_id = get_membership_id(document)
    member_name = get_member_display_name(document)
    membership_label = get_membership_label(document)
    valid_through = format_card_date(membership.expiry_date)
    email = getattr(user, "email", "") or "—"
    phone = get_member_phone(document)
    support_email = get_support_email()
    billing_email = get_billing_email()
    status_label = getattr(
        membership,
        "get_status_display",
        lambda: "Active",
    )()

    replacements = {
        PLACEHOLDER_MEMBER_ID: member_id,
        PLACEHOLDER_NAME: member_name,
        PLACEHOLDER_MEMBERSHIP: membership_label,
        PLACEHOLDER_VALID_THROUGH: valid_through,
        PLACEHOLDER_EMAIL: email,
        PLACEHOLDER_STATUS: str(status_label),
        PLACEHOLDER_SUPPORT_EMAIL: support_email,
        PLACEHOLDER_PHONE: phone,
        PLACEHOLDER_BILLING_EMAIL: billing_email,
    }

    for placeholder, value in replacements.items():
        svg = _replace_svg_text(svg, placeholder, value)

    return svg


def _render_svg_side(
    svg_text: str,
    document: Document,
    *,
    is_back: bool,
) -> bytes:
    """Render one CR80 side from the original 180 x 60 mm SVG master.

    The source artwork is laid out as:
      front = x=2, y=3, 85.6 x 54 mm
      back  = x=92.4, y=3, 85.6 x 54 mm

    We keep the SVG untouched and crop it by translating the full artwork.
    """
    drawing = svg2rlg(BytesIO(svg_text.encode("utf-8")))
    if drawing is None:
        raise ValueError("Unable to parse the ID card SVG template.")

    page_width = CARD_WIDTH_MM * mm
    page_height = CARD_HEIGHT_MM * mm

    # Normalize the parsed drawing to the SVG master's exact physical size.
    # This prevents svglib's interpretation of SVG units from changing the
    # crop/scale and causing the card to be cut off.
    master_width = MASTER_WIDTH_MM * mm
    master_height = MASTER_HEIGHT_MM * mm

    drawing_width = float(getattr(drawing, "width", 0) or 0)
    drawing_height = float(getattr(drawing, "height", 0) or 0)

    if drawing_width <= 0 or drawing_height <= 0:
        raise ValueError(
            "SVG renderer returned an invalid drawing size: "
            f"{drawing_width} x {drawing_height}"
        )

    drawing.scale(
        master_width / drawing_width,
        master_height / drawing_height,
    )

    output = BytesIO()
    pdf = canvas.Canvas(
        output,
        pagesize=(page_width, page_height),
    )

    # Translate the full master so the requested CR80 card lands exactly on
    # the PDF page. The 3 mm vertical margin is symmetric in the 60 mm master.
    master_x_mm = -92.4 if is_back else -2.0
    master_y_mm = -3.0

    renderPDF.draw(
        drawing,
        pdf,
        master_x_mm * mm,
        master_y_mm * mm,
    )

    # Front photo overlay.
    if not is_back and document.document_type == Document.ID_CARD:
        photo = prepare_member_photo(document)
        if photo:
            photo_x = PHOTO_X_MM * mm
            photo_y = (
                CARD_HEIGHT_MM
                - PHOTO_Y_MM
                - PHOTO_H_MM
            ) * mm

            pdf.drawImage(
                ImageReader(photo),
                photo_x,
                photo_y,
                width=PHOTO_W_MM * mm,
                height=PHOTO_H_MM * mm,
                preserveAspectRatio=False,
                mask="auto",
            )

    # Back QR overlay.
    if is_back:
        qr = generate_qr_image(document)
        qr_x = (QR_X_MM - 92.4) * mm
        qr_y = (
            CARD_HEIGHT_MM
            - (QR_Y_MM - 3.0)
            - QR_H_MM
        ) * mm

        pdf.drawImage(
            ImageReader(qr),
            qr_x,
            qr_y,
            width=QR_W_MM * mm,
            height=QR_H_MM * mm,
            preserveAspectRatio=False,
            mask="auto",
        )

    pdf.showPage()
    pdf.save()
    output.seek(0)
    return output.getvalue()


def render_id_card_pdf(document: Document) -> bytes:
    """Render the original SVG ID-card artwork as two CR80 PDF pages."""
    svg = _prepare_id_card_svg(document)

    writer = PdfWriter()

    for is_back in (False, True):
        rendered = _render_svg_side(
            svg,
            document,
            is_back=is_back,
        )

        reader = PdfReader(BytesIO(rendered))
        for page in reader.pages:
            writer.add_page(page)

    output = BytesIO()
    writer.write(output)
    output.seek(0)
    return output.getvalue()


# =============================================================================
# CERTIFICATE RENDERER
# =============================================================================


def _get_certificate_fields(document: Document) -> dict[str, str]:
    """Build dynamic fields for the supplied certificate master artwork."""
    name = get_member_display_name(document)
    designation = get_designation(document)
    reference = document.document_number
    date_text = (
        document.issue_date.strftime("%d %b %Y")
        if document.issue_date
        else ""
    )

    subject = "Membership Approval & Certification"
    news_title = ""

    try:
        application = document.membership.member_contributor_application
    except Exception:
        application = None

    if application:
        for field_name in (
            "subject",
            "application_subject",
            "membership_subject",
        ):
            value = getattr(application, field_name, "")
            if value:
                subject = str(value).strip()
                break

        for field_name in (
            "news_title",
            "title",
            "publication_title",
        ):
            value = getattr(application, field_name, "")
            if value:
                news_title = str(value).strip()
                break

    authorized_by = "War of Justice"
    if document.issued_by:
        authorized_by = get_member_display_name_from_user(
            document.issued_by
        )

    return {
        "reference": reference,
        "date": date_text,
        "to": name,
        "subject": subject,
        "name": name,
        "news_title": news_title,
        "authorized_by": authorized_by,
        "designation": designation,
    }


def get_member_display_name_from_user(user) -> str:
    if hasattr(user, "get_full_name"):
        full_name = user.get_full_name().strip()
        if full_name:
            return full_name

    username = getattr(user, "username", "")
    return str(username or "War of Justice").strip()


def render_certificate_pdf(document: Document) -> bytes:
    """Preserve the supplied certificate artwork and overlay dynamic data + QR."""
    master = _read_master(CERTIFICATE_TEMPLATE_PDF)
    if not master.pages:
        raise ValueError("Certificate PDF template has no pages.")

    page = master.pages[0]
    fields = _get_certificate_fields(document)

    def draw_overlay(pdf: canvas.Canvas) -> None:
        pdf.setFillColor(colors.HexColor("#111827"))

        pdf.setFont("Helvetica", 14)
        pdf.drawString(
            CERT_REFERENCE_X,
            CERT_REFERENCE_Y,
            fields["reference"],
        )

        pdf.drawString(
            CERT_DATE_X,
            CERT_DATE_Y,
            fields["date"],
        )

        pdf.setFont("Helvetica", 12)
        pdf.drawString(
            CERT_TO_X,
            CERT_TO_Y,
            fields["to"],
        )

        pdf.drawString(
            CERT_SUBJECT_X,
            CERT_SUBJECT_Y,
            fields["subject"],
        )

        pdf.setFont("Helvetica-Bold", 18)
        pdf.drawString(
            CERT_NAME_X,
            CERT_NAME_Y,
            fields["name"],
        )

        if fields["news_title"]:
            pdf.setFont("Helvetica", 12)
            pdf.drawString(
                CERT_NEWS_TITLE_X,
                CERT_NEWS_TITLE_Y,
                fields["news_title"],
            )

        pdf.setFont("Helvetica", 12)
        pdf.drawString(
            CERT_AUTHORIZED_X,
            CERT_AUTHORIZED_Y,
            fields["authorized_by"],
        )

        qr = generate_qr_image(document)
        pdf.drawImage(
            ImageReader(qr),
            CERT_QR_X,
            CERT_QR_Y,
            width=CERT_QR_SIZE,
            height=CERT_QR_SIZE,
            preserveAspectRatio=False,
            mask="auto",
        )

    page_width = float(page.mediabox.width)
    page_height = float(page.mediabox.height)

    overlay = _make_overlay(
        page_width,
        page_height,
        draw_overlay,
    )
    _merge_overlay(page, overlay)

    writer = PdfWriter()
    writer.add_page(page)

    output = BytesIO()
    writer.write(output)
    output.seek(0)
    return output.getvalue()


# =============================================================================
# DOCUMENT DISPATCH + STORAGE
# =============================================================================


def render_document_pdf(document: Document) -> bytes:
    """Render according to document type."""
    if document.document_type == Document.ID_CARD:
        return render_id_card_pdf(document)

    if document.document_type == Document.CERTIFICATE:
        return render_certificate_pdf(document)

    raise ValueError(
        f"Unsupported document type: {document.document_type}"
    )


@transaction.atomic
def generate_and_store_document_pdf(
    *,
    document: Document,
    actor=None,
) -> Document:
    """Generate a document PDF and store it using the private default storage."""
    if not document.document_number:
        raise ValueError(
            "Document must have a document number before generating its PDF."
        )

    pdf_bytes = render_document_pdf(document)
    filename = f"{document.document_number}.pdf"

    document.pdf_file.save(
        filename,
        ContentFile(pdf_bytes),
        save=False,
    )

    document.save(
        update_fields=[
            "pdf_file",
            "updated_at",
        ],
    )

    DocumentEvent.objects.create(
        document=document,
        actor=actor,
        event_type=DocumentEvent.REGENERATED,
        metadata={
            "document_number": document.document_number,
            "filename": filename,
            "template_version": document.template_version,
        },
    )

    return document
