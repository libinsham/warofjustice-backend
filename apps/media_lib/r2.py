"""
Cloudflare R2 direct-upload helper.

Article/public media:
    R2_PUBLIC_BUCKET_NAME

Private/member documents:
    R2_PRIVATE_BUCKET_NAME

The Django server never proxies article file bytes.
It only creates a short-lived presigned PUT URL.
The browser uploads directly to Cloudflare R2.
"""

import uuid

import boto3
from botocore.client import Config
from django.conf import settings


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


def build_object_key(
    file_name: str,
    folder: str = "uploads",
) -> str:
    """
    Generate a unique R2 object key.
    """
    ext = (
        file_name.rsplit(".", 1)[-1].lower()
        if "." in file_name
        else "bin"
    )

    return f"{folder}/{uuid.uuid4().hex}.{ext}"


def generate_presigned_put(
    file_name: str,
    content_type: str,
    folder: str = "uploads",
):
    """
    Generate a presigned PUT URL for PUBLIC ARTICLE MEDIA.

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