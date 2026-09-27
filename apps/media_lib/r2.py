
"""
Cloudflare R2 direct-upload helper.

Public article media:
    R2_PUBLIC_BUCKET_NAME

Private/member documents:
    R2_PRIVATE_BUCKET_NAME

Article images and review videos use the public R2 bucket.
The Django server generates short-lived presigned URLs.
The browser uploads original files directly to Cloudflare R2.
"""

import uuid
from pathlib import PurePath
from urllib.parse import quote

import boto3
from botocore.client import Config
from django.conf import settings


# =========================================================
# R2 CLIENT
# =========================================================

def get_r2_client():
    """
    Create the S3-compatible Cloudflare R2 client.
    """
    return boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


# =========================================================
# OBJECT KEY
# =========================================================

def build_object_key(
    file_name: str,
    folder: str = "uploads",
) -> str:
    """
    Generate a unique R2 object key.

    Only the file extension is retained from the
    original filename. The uploaded filename itself
    is not used as the object key.
    """
    safe_name = PurePath(
        str(file_name).replace("\\", "/")
    ).name

    extension = (
        safe_name.rsplit(".", 1)[-1].lower()
        if "." in safe_name
        else "bin"
    )

    # Keep extensions simple and safe.
    if (
        not extension
        or len(extension) > 16
        or not extension.isascii()
        or not extension.isalnum()
    ):
        extension = "bin"

    safe_folder = str(folder).strip("/")

    if (
        not safe_folder
        or "\\" in safe_folder
        or ".." in safe_folder.split("/")
    ):
        raise ValueError("Invalid R2 folder.")

    return (
        f"{safe_folder}/"
        f"{uuid.uuid4().hex}.{extension}"
    )


# =========================================================
# PRESIGNED PUT URL
# =========================================================

def generate_presigned_put(
    file_name: str,
    content_type: str,
    folder: str = "uploads",
):
    """
    Generate a short-lived presigned PUT URL.

    Used for:
    - Article images
    - Article videos

    Uploads are sent directly from the browser to
    the public Cloudflare R2 bucket.

    Returns:
        {
            "upload_url": "...",
            "key": "...",
            "public_url": "..."
        }
    """
    key = build_object_key(
        file_name=file_name,
        folder=folder,
    )

    client = get_r2_client()

    upload_url = client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.R2_PUBLIC_BUCKET_NAME,
            "Key": key,
            "ContentType": content_type,
        },
        ExpiresIn=300,
    )

    public_base_url = (
        settings.R2_PUBLIC_BASE_URL.rstrip("/")
    )

    public_url = f"{public_base_url}/{key}"

    return {
        "upload_url": upload_url,
        "key": key,
        "public_url": public_url,
    }


# =========================================================
# VERIFY R2 OBJECT
# =========================================================

def head_r2_object(key: str):
    """
    Retrieve metadata for an existing object
    in the public R2 bucket.

    Used to verify uploaded video size and
    content type before creating a database record.
    """
    return get_r2_client().head_object(
        Bucket=settings.R2_PUBLIC_BUCKET_NAME,
        Key=key,
    )


# =========================================================
# PRESIGNED GET URL
# =========================================================

def generate_presigned_get(
    key: str,
    file_name: str = "video",
    expires_in: int = 600,
):
    """
    Generate a temporary R2 download URL.

    Content-Disposition requests a file download
    instead of inline playback.

    Note:
    This presigned URL does not make an object private
    if the same object is also accessible through a
    public R2 custom domain.
    """
    safe_name = PurePath(
        str(file_name).replace("\\", "/")
    ).name or "video"

    encoded_name = quote(safe_name, safe="")

    return get_r2_client().generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.R2_PUBLIC_BUCKET_NAME,
            "Key": key,
            "ResponseContentDisposition": (
                f"attachment; filename*=UTF-8''{encoded_name}"
            ),
        },
        ExpiresIn=expires_in,
    )


# =========================================================
# DELETE R2 OBJECT
# =========================================================

def delete_r2_object(key: str):
    """
    Delete an object from the public R2 bucket.

    Call this only after verifying that the
    requesting user is authorized to delete it.
    """
    return get_r2_client().delete_object(
        Bucket=settings.R2_PUBLIC_BUCKET_NAME,
        Key=key,
    )