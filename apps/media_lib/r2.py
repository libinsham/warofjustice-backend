"""
Cloudflare R2 direct-upload helper (R2 is S3-compatible, so boto3 works
unmodified — just point at the R2 endpoint). The Django server NEVER
proxies the actual file bytes: it only issues a short-lived presigned PUT
URL, the browser uploads straight to R2, and the client then confirms
the upload by POSTing the resulting metadata to /api/v1/dashboard/media/.
"""
import uuid

import boto3
from botocore.client import Config
from django.conf import settings


def get_r2_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def build_object_key(file_name: str, folder: str = "uploads") -> str:
    ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else "bin"
    return f"{folder}/{uuid.uuid4().hex}.{ext}"


def generate_presigned_put(file_name: str, content_type: str, folder: str = "uploads"):
    """Returns {upload_url, key, public_url} — the frontend PUTs the file
    bytes directly to `upload_url` with header Content-Type: content_type."""
    key = build_object_key(file_name, folder)
    client = get_r2_client()

    upload_url = client.generate_presigned_url(
        "put_object",
        Params={"Bucket": settings.R2_BUCKET_NAME, "Key": key, "ContentType": content_type},
        ExpiresIn=300,  # 5 minutes — plenty for a client to start the PUT
    )

    public_url = f"{settings.R2_PUBLIC_BASE_URL.rstrip('/')}/{key}"
    return {"upload_url": upload_url, "key": key, "public_url": public_url}
