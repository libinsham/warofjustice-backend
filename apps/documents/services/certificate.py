from io import BytesIO

import qrcode

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from apps.documents.models import Document
from apps.documents.services.qr import build_verification_url


# ============================================================
# TEMPLATE
# ============================================================

CERTIFICATE_TEMPLATE = "documents/templates/certificate.pdf"


# ============================================================
# DYNAMIC FIELD POSITIONS
# ============================================================
#
# These coordinates will be adjusted after we inspect your
# actual certificate PDF.
#
# ReportLab coordinates:
# (0, 0) = bottom-left
#
# ============================================================

NAME_X = 421
NAME_Y = 360

DESIGNATION_X = 421
DESIGNATION_Y = 320

DOCUMENT_NUMBER_X = 421
DOCUMENT_NUMBER_Y = 90

ISSUE_DATE_X = 421
ISSUE_DATE_Y = 65

QR_X = 650
QR_Y = 55

QR_SIZE = 70


# ============================================================
# MEMBER NAME
# ============================================================

def get_member_name(document: Document) -> str:
    membership = document.membership
    user = membership.user

    # Prefer Django user's full name.
    if hasattr(user, "get_full_name"):
        name = user.get_full_name().strip()

        if name:
            return name

    # Profile fallback.
    profile = getattr(user, "profile", None)

    if profile:
        first_name = getattr(profile, "first_name", "") or ""
        last_name = getattr(profile, "last_name", "") or ""

        name = f"{first_name} {last_name}".strip()

        if name:
            return name

    # Application fallback.
    application = membership.member_contributor_application

    if application:
        for field_name in (
            "full_name",
            "name",
            "applicant_name",
        ):
            value = getattr(application, field_name, None)

            if value:
                value = str(value).strip()

                if value:
                    return value

    return user.username


# ============================================================
# DESIGNATION
# ============================================================

def get_designation(document: Document) -> str:
    membership = document.membership

    if membership.designation:
        return membership.designation

    if membership.membership_type == "contributor":
        return "Contributor"

    if membership.membership_type == "member":
        return "Member"

    if membership.membership_type == "subscriber":
        return "Subscriber"

    return "Member"


# ============================================================
# QR CODE
# ============================================================

def create_qr_code(document: Document) -> BytesIO:
    verification_url = build_verification_url(document)

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=2,
    )

    qr.add_data(verification_url)
    qr.make(fit=True)

    image = qr.make_image()

    output = BytesIO()
    image.save(output, format="PNG")
    output.seek(0)

    return output


# ============================================================
# OVERLAY
# ============================================================

def create_certificate_overlay(
    document: Document,
    width: float,
    height: float,
) -> BytesIO:

    output = BytesIO()

    pdf = canvas.Canvas(
        output,
        pagesize=(width, height),
    )

    name = get_member_name(document)
    designation = get_designation(document)

    # --------------------------------------------------------
    # MEMBER NAME
    # --------------------------------------------------------

    pdf.setFont(
        "Helvetica-Bold",
        24,
    )

    pdf.drawCentredString(
        NAME_X,
        NAME_Y,
        name,
    )

    # --------------------------------------------------------
    # DESIGNATION
    # --------------------------------------------------------

    pdf.setFont(
        "Helvetica",
        13,
    )

    pdf.drawCentredString(
        DESIGNATION_X,
        DESIGNATION_Y,
        designation,
    )

    # --------------------------------------------------------
    # DOCUMENT NUMBER
    # --------------------------------------------------------

    pdf.setFont(
        "Helvetica",
        8,
    )

    pdf.drawString(
        DOCUMENT_NUMBER_X,
        DOCUMENT_NUMBER_Y,
        document.document_number,
    )

    # --------------------------------------------------------
    # ISSUE DATE
    # --------------------------------------------------------

    issue_date = (
        document.issue_date.strftime("%d %B %Y")
        if document.issue_date
        else ""
    )

    pdf.drawString(
        ISSUE_DATE_X,
        ISSUE_DATE_Y,
        issue_date,
    )

    # --------------------------------------------------------
    # QR
    # --------------------------------------------------------

    qr_file = create_qr_code(document)

    pdf.drawImage(
        qr_file,
        QR_X,
        QR_Y,
        width=QR_SIZE,
        height=QR_SIZE,
        preserveAspectRatio=True,
        mask="auto",
    )

    pdf.save()

    output.seek(0)

    return output


# ============================================================
# GENERATE CERTIFICATE
# ============================================================

def generate_certificate_pdf(document: Document) -> bytes:
    """
    Load the original certificate template and overlay
    member-specific information and QR code.
    """

    if document.document_type != Document.CERTIFICATE:
        raise ValueError(
            "generate_certificate_pdf() requires a certificate document."
        )

    if not default_storage.exists(CERTIFICATE_TEMPLATE):
        raise FileNotFoundError(
            f"Certificate template not found: {CERTIFICATE_TEMPLATE}"
        )

    # --------------------------------------------------------
    # Load master certificate
    # --------------------------------------------------------

    with default_storage.open(
        CERTIFICATE_TEMPLATE,
        "rb",
    ) as template_file:

        template_reader = PdfReader(template_file)

        if not template_reader.pages:
            raise ValueError(
                "Certificate template PDF has no pages."
            )

        template_page = template_reader.pages[0]

        width = float(template_page.mediabox.width)
        height = float(template_page.mediabox.height)

        # ----------------------------------------------------
        # Create dynamic overlay
        # ----------------------------------------------------

        overlay_file = create_certificate_overlay(
            document=document,
            width=width,
            height=height,
        )

        overlay_reader = PdfReader(
            overlay_file
        )

        overlay_page = overlay_reader.pages[0]

        # ----------------------------------------------------
        # Merge dynamic data onto original design
        # ----------------------------------------------------

        template_page.merge_page(
            overlay_page
        )

        # ----------------------------------------------------
        # Create final PDF
        # ----------------------------------------------------

        writer = PdfWriter()

        writer.add_page(
            template_page
        )

        output = BytesIO()

        writer.write(output)

        return output.getvalue()


# ============================================================
# STORE CERTIFICATE
# ============================================================

def generate_and_store_certificate(
    document: Document,
    actor=None,
) -> Document:

    pdf_bytes = generate_certificate_pdf(
        document
    )

    filename = (
        f"documents/generated/"
        f"{document.document_number}.pdf"
    )

    # --------------------------------------------------------
    # Store in private R2
    # --------------------------------------------------------

    saved_path = default_storage.save(
        filename,
        ContentFile(pdf_bytes),
    )

    document.pdf_file.name = saved_path

    document.save(
        update_fields=[
            "pdf_file",
            "updated_at",
        ]
    )

    return document