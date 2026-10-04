from __future__ import annotations

from io import BytesIO
from pathlib import Path
import copy

import qrcode
from PIL import Image, ImageOps

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction

from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm

from apps.documents.models import Document, DocumentEvent
from apps.documents.services.qr import build_verification_url


# =============================================================================
# MASTER TEMPLATES
# =============================================================================
#
# The production-safe renderer uses PDF master artwork rather than CairoSVG,
# WeasyPrint, or svglib. This keeps gradients, shadows, clipping paths and
# other artwork exactly as exported from Illustrator.
#
# Required files:
#   apps/documents/templates/id-card-template.pdf
#   apps/documents/templates/certificate.pdf
#
# The ID-card master should be one 180 x 60 mm page containing both CR80 sides.
# The certificate master should be your supplied one-page publication approval
# / certificate artwork.
#

ID_CARD_TEMPLATE_PDF = (
    Path(settings.BASE_DIR)
    / "apps"
    / "documents"
    / "templates"
    / "id-card-template.pdf"
)

CERTIFICATE_TEMPLATE_PDF = (
    Path(settings.BASE_DIR)
    / "apps"
    / "documents"
    / "templates"
    / "certificate.pdf"
)


# =============================================================================
# ID CARD MASTER GEOMETRY
# =============================================================================

CARD_WIDTH_MM = 85.6
CARD_HEIGHT_MM = 54.0
MASTER_WIDTH_MM = 180.0
MASTER_HEIGHT_MM = 60.0

FRONT_X_MM = 2.0
FRONT_Y_MM = 3.0
BACK_X_MM = 92.4
BACK_Y_MM = 3.0

PHOTO_X_MM = 7.0
PHOTO_Y_MM = 18.0
PHOTO_W_MM = 19.0
PHOTO_H_MM = 25.0

QR_X_MM = 160.8
QR_Y_MM = 17.2
QR_W_MM = 12.3
QR_H_MM = 12.3

# Text baselines from the original SVG artwork.
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

# Keep these close to the original SVG typography.
ID_FONT_SIZE_PT = 4.2 * mm
NAME_FONT_SIZE_PT = 2.75 * mm
MEMBERSHIP_FONT_SIZE_PT = 2.4 * mm
VALID_FONT_SIZE_PT = 1.65 * mm
BACK_TEXT_FONT_SIZE_PT = 2.0 * mm
STATUS_FONT_SIZE_PT = 2.0 * mm

# Supplied certificate master page was 1524 x 1032 points.
CERTIFICATE_PAGE_WIDTH = 1524.0
CERTIFICATE_PAGE_HEIGHT = 1032.0

# Dynamic certificate field coordinates supplied during template work.
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
    """Read the member selfie/photo from the configured Django storage."""

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


def _merge_overlay(
    master_page,
    overlay_bytes: bytes,
):
    overlay_page = PdfReader(BytesIO(overlay_bytes)).pages[0]
    master_page.merge_page(overlay_page)
    return master_page


# =============================================================================
# ID CARD RENDERER
# =============================================================================


def _svg_y_to_pdf(y_from_top_mm: float) -> float:
    """Convert SVG top-origin Y to ReportLab bottom-origin Y."""

    return (MASTER_HEIGHT_MM - y_from_top_mm) * mm


def _overlay_id_card_master(document: Document) -> bytes:
    """Overlay dynamic ID card fields on the 180 x 60 mm master PDF."""

    master = _read_master(ID_CARD_TEMPLATE_PDF)
    if not master.pages:
        raise ValueError("ID-card PDF template has no pages.")

    master_page = master.pages[0]
    page_width = MASTER_WIDTH_MM * mm
    page_height = MASTER_HEIGHT_MM * mm

    member_id = get_membership_id(document)
    member_name = get_member_display_name(document)
    membership_label = get_membership_label(document)
    valid_through = format_card_date(document.membership.expiry_date)

    user = document.membership.user
    email = getattr(user, "email", "") or "—"
    phone = get_member_phone(document)
    support_email = get_support_email()
    billing_email = get_billing_email()

    status_label = getattr(
        document.membership,
        "get_status_display",
        lambda: "Active",
    )()

    # ReportLab PDF page has the exact same 180 x 60 mm coordinate system.
    def draw_overlay(pdf: canvas.Canvas) -> None:
        # Front side ---------------------------------------------------------
        pdf.setFillColor(colors.white)

        pdf.setFont("Helvetica-Bold", ID_FONT_SIZE_PT)
        pdf.drawString(
            ID_X_MM * mm,
            _svg_y_to_pdf(ID_Y_MM),
            member_id,
        )

        pdf.setFont("Helvetica-Bold", NAME_FONT_SIZE_PT)
        pdf.drawString(
            NAME_X_MM * mm,
            _svg_y_to_pdf(NAME_Y_MM),
            member_name,
        )

        pdf.setFont("Helvetica-Bold", MEMBERSHIP_FONT_SIZE_PT)
        pdf.drawString(
            MEMBERSHIP_X_MM * mm,
            _svg_y_to_pdf(MEMBERSHIP_Y_MM),
            membership_label,
        )

        pdf.setFont("Helvetica-Bold", VALID_FONT_SIZE_PT)
        pdf.drawString(
            VALID_X_MM * mm,
            _svg_y_to_pdf(VALID_Y_MM),
            valid_through,
        )

        # Back side ----------------------------------------------------------
        pdf.setFillColor(colors.HexColor("#152A3C"))
        pdf.setFont("Helvetica", BACK_TEXT_FONT_SIZE_PT)
        pdf.drawString(
            EMAIL_X_MM * mm,
            _svg_y_to_pdf(EMAIL_Y_MM),
            email,
        )

        pdf.setFont("Helvetica-Bold", STATUS_FONT_SIZE_PT)
        pdf.drawString(
            STATUS_X_MM * mm,
            _svg_y_to_pdf(STATUS_Y_MM),
            str(status_label),
        )

        pdf.setFillColor(colors.HexColor("#0C567B"))
        pdf.setFont("Helvetica", BACK_TEXT_FONT_SIZE_PT)
        pdf.drawString(
            SUPPORT_X_MM * mm,
            _svg_y_to_pdf(SUPPORT_Y_MM),
            support_email,
        )

        pdf.setFillColor(colors.HexColor("#152A3C"))
        pdf.drawString(
            PHONE_X_MM * mm,
            _svg_y_to_pdf(PHONE_Y_MM),
            phone,
        )

        pdf.drawString(
            BILLING_X_MM * mm,
            _svg_y_to_pdf(BILLING_Y_MM),
            billing_email,
        )

        # Photo overlay ------------------------------------------------------
        photo = prepare_member_photo(document)
        if photo:
            photo_x = PHOTO_X_MM * mm
            photo_y = (MASTER_HEIGHT_MM - PHOTO_Y_MM - PHOTO_H_MM) * mm
            photo_w = PHOTO_W_MM * mm
            photo_h = PHOTO_H_MM * mm

            pdf.drawImage(
                ImageReader(photo),
                photo_x,
                photo_y,
                width=photo_w,
                height=photo_h,
                preserveAspectRatio=False,
                mask="auto",
            )

            pdf.setStrokeColor(colors.white)
            pdf.setLineWidth(0.5 * mm)
            pdf.roundRect(
                photo_x,
                photo_y,
                photo_w,
                photo_h,
                2.2 * mm,
                stroke=1,
                fill=0,
            )

        # QR overlay ---------------------------------------------------------
        qr = generate_qr_image(document)
        qr_x = QR_X_MM * mm
        qr_y = (MASTER_HEIGHT_MM - QR_Y_MM - QR_H_MM) * mm
        qr_w = QR_W_MM * mm
        qr_h = QR_H_MM * mm

        pdf.drawImage(
            ImageReader(qr),
            qr_x,
            qr_y,
            width=qr_w,
            height=qr_h,
            preserveAspectRatio=False,
            mask="auto",
        )

        pdf.setStrokeColor(colors.HexColor("#C8D6DF"))
        pdf.setLineWidth(0.35 * mm)
        pdf.roundRect(
            qr_x,
            qr_y,
            qr_w,
            qr_h,
            1 * mm,
            stroke=1,
            fill=0,
        )

    overlay = _make_overlay(
        page_width,
        page_height,
        draw_overlay,
    )

    _merge_overlay(master_page, overlay)

    # Crop the single master page into two printable CR80 pages.
    pages = []
    front = copy.deepcopy(master_page)
    back = copy.deepcopy(master_page)

    front.mediabox.lower_left = (FRONT_X_MM * mm, FRONT_Y_MM * mm)
    front.mediabox.upper_right = (
        (FRONT_X_MM + CARD_WIDTH_MM) * mm,
        (FRONT_Y_MM + CARD_HEIGHT_MM) * mm,
    )
    front.cropbox = front.mediabox

    back.mediabox.lower_left = (BACK_X_MM * mm, BACK_Y_MM * mm)
    back.mediabox.upper_right = (
        (BACK_X_MM + CARD_WIDTH_MM) * mm,
        (BACK_Y_MM + CARD_HEIGHT_MM) * mm,
    )
    back.cropbox = back.mediabox

    pages.extend((front, back))

    writer = PdfWriter()
    for page in pages:
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

    # Prefer application title/subject fields when available.
    subject = "Membership Approval & Certification"
    news_title = ""

    try:
        application = document.membership.member_contributor_application
    except Exception:
        application = None

    if application:
        for field_name in ("subject", "application_subject", "membership_subject"):
            value = getattr(application, field_name, "")
            if value:
                subject = str(value).strip()
                break

        for field_name in ("news_title", "title", "publication_title"):
            value = getattr(application, field_name, "")
            if value:
                news_title = str(value).strip()
                break

    authorized_by = "War of Justice"
    if document.issued_by:
        authorized_by = get_member_display_name_from_user(document.issued_by)

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
    """
    Preserve the supplied certificate PDF artwork and overlay dynamic data + QR.
    """

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
        return _overlay_id_card_master(document)

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
