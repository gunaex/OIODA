"""
Conductor Again — Cloudflare R2 Storage Adapter
S3-compatible object storage via boto3.
"""

import os
from datetime import datetime, timezone

import boto3
from botocore.config import Config

# Configuration
R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID", "")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY", "")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "conductor-again-dev")
R2_ENDPOINT = os.getenv("R2_ENDPOINT", f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com") if R2_ACCOUNT_ID else ""
R2_PRESIGN_TTL = int(os.getenv("R2_PRESIGN_TTL_SECONDS", "300"))
R2_MAX_UPLOAD_BYTES = int(os.getenv("R2_MAX_UPLOAD_BYTES", "52428800"))  # 50MB


def _get_client():
    """Get boto3 S3 client for R2."""
    if not R2_ACCESS_KEY_ID or not R2_SECRET_ACCESS_KEY:
        return None
    return boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
    )


def is_available() -> bool:
    """Check if R2 is configured."""
    return bool(R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY and R2_ENDPOINT)


def generate_upload_url(object_key: str, content_type: str = "application/octet-stream") -> dict | None:
    """Generate a pre-signed upload URL."""
    client = _get_client()
    if not client:
        return None
    try:
        url = client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": R2_BUCKET_NAME,
                "Key": object_key,
                "ContentType": content_type,
            },
            ExpiresIn=R2_PRESIGN_TTL,
        )
        return {"url": url, "key": object_key, "expires_in": R2_PRESIGN_TTL}
    except Exception as e:
        return {"error": str(e)}


def generate_download_url(object_key: str) -> dict | None:
    """Generate a pre-signed download URL."""
    client = _get_client()
    if not client:
        return None
    try:
        url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": R2_BUCKET_NAME, "Key": object_key},
            ExpiresIn=R2_PRESIGN_TTL,
        )
        return {"url": url, "key": object_key, "expires_in": R2_PRESIGN_TTL}
    except Exception as e:
        return {"error": str(e)}


def upload_bytes(data: bytes, object_key: str, content_type: str = "application/octet-stream") -> dict:
    """Upload bytes directly to R2."""
    client = _get_client()
    if not client:
        return {"ok": False, "error": "R2 not configured"}
    if len(data) > R2_MAX_UPLOAD_BYTES:
        return {"ok": False, "error": f"File exceeds max size of {R2_MAX_UPLOAD_BYTES} bytes"}
    try:
        client.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=object_key,
            Body=data,
            ContentType=content_type,
        )
        return {"ok": True, "key": object_key, "size": len(data)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def delete_object(object_key: str) -> dict:
    """Delete an object from R2."""
    client = _get_client()
    if not client:
        return {"ok": False, "error": "R2 not configured"}
    try:
        client.delete_object(Bucket=R2_BUCKET_NAME, Key=object_key)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def build_object_key(project_slug: str, category: str, filename: str) -> str:
    """Build a namespaced object key: projects/{slug}/{category}/{timestamp}_{filename}"""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    safe_name = filename.replace(" ", "_")[:100]
    return f"projects/{project_slug}/{category}/{ts}_{safe_name}"
